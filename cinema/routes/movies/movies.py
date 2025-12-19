from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from cinema.database import get_db
from cinema.database.models.movies import (
    CountryModel,
    GenreModel,
    ActorModel,
    LanguageModel
)
from cinema.schemas.movies import (
    MovieListResponseSchema,
    MovieListItemSchema,
    MovieDetailSchema,
    MovieCreateSchema,
    MovieUpdateSchema
)

from cinema.config.dependencies import user_is_staff
from cinema.database.models.accounts import UserModel
from cinema.database.models.movies import DirectorModel, MovieModel
from cinema.schemas.movies import MovieQueryParamsSchema

router = APIRouter()


@router.get(
    "/movies/",
    response_model=MovieListResponseSchema,
    summary="Get a paginated list of movies",
    description=(
            "<h3>This endpoint retrieves a paginated list of movies from the database.</h3>"
            "<p>Supports:</p>"
            "<ul>"
            "<li><b>Pagination</b> via <code>page</code> and <code>per_page</code></li>"
            "<li><b>Search</b> via <code>search</code> (matches movie name/description, "
            "actor name, director name)</li>"
            "<li><b>Filtering</b> via <code>year</code> and <code>imdb</code> (minimum IMDB rating)</li>"
            "<li><b>Sorting</b> via <code>sort_by</code> (price/budget/duration) and "
            "<code>sort_order</code> (asc/desc)</li>"
            "</ul>"
            "<p>The response includes items, total counts, and previous/next page links when applicable.</p>"
    ),
    responses={
        404: {
            "description": "No movies found or page out of range.",
            "content": {
                "application/json": {
                    "examples": {
                        "no_movies": {"value": {"detail": "No movies found."}},
                        "page_out_of_range": {"value": {"detail": "Page out of range."}},
                    }
                }
            },
        }
    }
)
async def get_movie_list(
        page: int = Query(1, ge=1, description="Page number (1-based index)"),
        per_page: int = Query(10, ge=1, le=20, description="Number of items per page"),
        params: MovieQueryParamsSchema = Depends(),
        db: AsyncSession = Depends(get_db),
) -> MovieListResponseSchema:
    """
    Retrieve a paginated list of movies with optional search, filtering, and sorting.

    Behavior:
    - Pagination uses `page` and `per_page` (1-based index).
    - Search (`params.search`) matches:
      - Movie name
      - Movie description
      - Actor name
      - Director name
    - Filters:
      - `params.year` filters by exact release year
      - `params.imdb` filters by minimum IMDB rating (`MovieModel.imdb >= params.imdb`)
    - Sorting:
      - `params.sort_by` supports: price, budget, duration
      - `params.sort_order` supports: asc/desc
      - A model-defined default ordering is appended after custom sorting (if present).
    - Total count is computed over distinct movie IDs (to avoid duplicates from joins).

    Returns:
    - 200 with `MovieListResponseSchema` (movies + pagination metadata).

    Errors:
    - 404 if no movies match the query (`"No movies found."`)
    - 404 if `page` exceeds total pages (`"Page out of range."`)
    """
    offset = (page - 1) * per_page

    base_from = (
        select(MovieModel.id)
        .select_from(MovieModel)
        .outerjoin(MovieModel.actors)
        .outerjoin(MovieModel.directors)
    )

    if params.search:
        pattern = f"%{params.search}%"
        base_from = base_from.where(
            or_(
                MovieModel.name.ilike(pattern),
                MovieModel.description.ilike(pattern),
                ActorModel.name.ilike(pattern),
                DirectorModel.name.ilike(pattern),
            )
        )

    if params.year is not None:
        base_from = base_from.where(MovieModel.year == params.year)

    if params.imdb is not None:
        base_from = base_from.where(MovieModel.imdb >= params.imdb)

    # ---- count distinct movies ----
    count_stmt = select(func.count()).select_from(base_from.distinct().subquery())
    total_items = (await db.execute(count_stmt)).scalar_one()

    if total_items == 0:
        raise HTTPException(status_code=404, detail="No movies found.")

    total_pages = (total_items + per_page - 1) // per_page
    if page > total_pages:
        raise HTTPException(status_code=404, detail="Page out of range.")

    # ---- sorting (apply to the ID query) ----
    sort_columns = {
        "price": MovieModel.price,
        "budget": MovieModel.budget,
        "duration": MovieModel.duration,
    }

    order_clauses = []
    sort_column = sort_columns.get(params.sort_by)
    if sort_column is not None:
        order_clauses.append(sort_column.asc() if params.sort_order == "asc" else sort_column.desc())

    default_order = MovieModel.default_order_by()
    if default_order:
        order_clauses.extend(default_order)

    # ---- page IDs (distinct!) ----
    ids_stmt = base_from.distinct()
    if order_clauses:
        ids_stmt = ids_stmt.order_by(*order_clauses)

    ids_stmt = ids_stmt.offset(offset).limit(per_page)
    movie_ids = (await db.execute(ids_stmt)).scalars().all()

    # Safety (shouldn’t happen, but keeps behavior stable)
    if not movie_ids:
        raise HTTPException(status_code=404, detail="No movies found.")

    # ---- fetch full movies by IDs ----
    # Keep the same order as movie_ids (important for stable pagination)
    order_by_ids = case({mid: idx for idx, mid in enumerate(movie_ids)}, value=MovieModel.id)

    movies_stmt = select(MovieModel).where(MovieModel.id.in_(movie_ids)).order_by(order_by_ids)
    movies = (await db.execute(movies_stmt)).scalars().all()

    movie_list = [MovieListItemSchema.model_validate(m) for m in movies]

    return MovieListResponseSchema(
        movies=movie_list,
        prev_page=f"/cinema/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None,
        next_page=f"/cinema/movies/?page={page + 1}&per_page={per_page}" if page < total_pages else None,
        total_pages=total_pages,
        total_items=total_items,
    )


@router.post(
    "/movies/",
    response_model=MovieDetailSchema,
    summary="Add a new movie",
    description=(
            "<h3>This endpoint creates a new movie in the database (staff-only).</h3>"
            "<p>It will link existing related entities or create them if missing:</p>"
            "<ul>"
            "<li>Country (by code)</li>"
            "<li>Genres (by name)</li>"
            "<li>Actors (by name)</li>"
            "<li>Directors (by name)</li>"
            "<li>Languages (by name)</li>"
            "</ul>"
            "<p>Uniqueness check: a movie with the same <code>name</code> and "
            "<code>year</code> cannot be created twice.</p>"
    ),
    responses={
        201: {
            "description": "Movie created successfully.",
        },
        400: {
            "description": "Invalid input data (constraint/validation error at DB level).",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid input data."}
                }
            },
        },
        409: {
            "description": "Movie with the same name and year already exists.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "A movie with the name 'Movie X' and release year '2020' already exists."
                    }
                }
            },
        },
    },
    status_code=201
)
async def create_movie(
        movie_data: MovieCreateSchema,
        db: AsyncSession = Depends(get_db),
        _user: UserModel = Depends(user_is_staff),
) -> MovieDetailSchema:
    """
    Create a new movie and attach related entities (staff-only).

    Workflow:
    - Rejects duplicates by checking `(name, year)` before insert.
    - Resolves relations by lookup-and-create:
      - Country by `code`
      - Genres/Actors/Directors/Languages by `name`
    - Commits the transaction and refreshes the movie with relationships.

    Returns:
    - 201 with the created movie (`MovieDetailSchema`).

    Errors:
    - 409 if a movie with the same `name` and `year` already exists.
    - 400 if a database constraint fails (captured as `IntegrityError`).
    """
    existing_stmt = select(MovieModel).where(
        (MovieModel.name == movie_data.name),
        (MovieModel.year == movie_data.year)
    )
    existing_result = await db.execute(existing_stmt)
    existing_movie = existing_result.scalars().first()

    if existing_movie:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A movie with the name '{movie_data.name}' and release year "
                f"'{movie_data.year}' already exists."
            )
        )

    try:
        country_stmt = select(CountryModel).where(CountryModel.code == movie_data.country)
        country_result = await db.execute(country_stmt)
        country = country_result.scalars().first()
        if not country:
            country = CountryModel(code=movie_data.country)
            db.add(country)
            await db.flush()

        genres = []
        for genre_name in movie_data.genres:
            genre_stmt = select(GenreModel).where(GenreModel.name == genre_name)
            genre_result = await db.execute(genre_stmt)
            genre = genre_result.scalars().first()

            if not genre:
                genre = GenreModel(name=genre_name)
                db.add(genre)
                await db.flush()
            genres.append(genre)

        actors = []
        for actor_name in movie_data.actors:
            actor_stmt = select(ActorModel).where(ActorModel.name == actor_name)
            actor_result = await db.execute(actor_stmt)
            actor = actor_result.scalars().first()

            if not actor:
                actor = ActorModel(name=actor_name)
                db.add(actor)
                await db.flush()
            actors.append(actor)

        directors = []
        for director_name in movie_data.directors:
            director_stmt = select(DirectorModel).where(DirectorModel.name == director_name)
            director_result = await db.execute(director_stmt)
            director = director_result.scalars().first()

            if not director:
                director = DirectorModel(name=director_name)
                db.add(director)
                await db.flush()
            directors.append(director)

        languages = []
        for language_name in movie_data.languages:
            lang_stmt = select(LanguageModel).where(LanguageModel.name == language_name)
            lang_result = await db.execute(lang_stmt)
            language = lang_result.scalars().first()

            if not language:
                language = LanguageModel(name=language_name)
                db.add(language)
                await db.flush()
            languages.append(language)

        movie = MovieModel(
            name=movie_data.name,
            uuid=movie_data.uuid,
            year=movie_data.year,
            duration=movie_data.duration,
            imdb=movie_data.imdb,
            imdb_votes=movie_data.imdb_votes,
            description=movie_data.description,
            budget=movie_data.budget,
            revenue=movie_data.revenue,
            certification=movie_data.certification,
            price=movie_data.price,
            country=country,
            genres=genres,
            actors=actors,
            directors=directors,
            languages=languages,
        )
        db.add(movie)
        await db.commit()
        await db.refresh(movie, [
            "country",
            "genres",
            "actors",
            "directors",
            "languages",
            "comments",
            "reactions",
            "ratings",
        ])
        return MovieDetailSchema.model_validate(movie)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


@router.get(
    "/movies/{movie_id}/",
    response_model=MovieDetailSchema,
    summary="Get movie details by ID",
    description=(
            "<h3>Fetch detailed information about a specific movie by its unique ID.</h3>"
            "<p>The response includes the movie and its related entities:</p>"
            "<ul>"
            "<li>Country</li>"
            "<li>Genres</li>"
            "<li>Actors</li>"
            "<li>Languages</li>"
            "<li>Directors</li>"
            "<li>Comments</li>"
            "<li>Reactions</li>"
            "<li>Ratings</li>"
            "</ul>"
            "<p>If the movie with the given ID is not found, a 404 error is returned.</p>"
    ),
    responses={
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        }
    }
)
async def get_movie_by_id(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
) -> MovieDetailSchema:
    """
    Retrieve a single movie by ID, including related entities.

    The query eagerly loads the following relationships:
    - country, genres, actors, languages, directors
    - comments, reactions, ratings

    Returns:
    - 200 with `MovieDetailSchema`.

    Errors:
    - 404 if the movie does not exist (`"Movie with the given ID was not found."`).
    """
    stmt = (
        select(MovieModel)
        .options(
            joinedload(MovieModel.country),
            joinedload(MovieModel.genres),
            joinedload(MovieModel.actors),
            joinedload(MovieModel.languages),
            joinedload(MovieModel.directors),
            joinedload(MovieModel.comments),
            joinedload(MovieModel.reactions),
            joinedload(MovieModel.ratings),
        )
        .where(MovieModel.id == movie_id)
    )

    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    return MovieDetailSchema.model_validate(movie)


@router.delete(
    "/movies/{movie_id}/",
    summary="Delete a movie by ID",
    description=(
            "<h3>Delete a specific movie from the database by its unique ID (staff-only).</h3>"
            "<p>If the movie does not exist, a 404 error will be returned.</p>"
            "<p><b>Note:</b> This endpoint is declared with status code <code>204 No Content</code>.</p>"
    ),
    responses={
        204: {
            "description": "Movie deleted successfully."
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        },
    },
    status_code=204
)
async def delete_movie(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
        _requestor: UserModel = Depends(user_is_staff),
):
    """
    Delete a movie by ID (staff-only).

    Workflow:
    - Fetches the movie by `movie_id`.
    - If found, deletes it and commits.

    Returns:
    - 204 (as declared in the router decorator).

    Errors:
    - 404 if the movie does not exist (`"Movie with the given ID was not found."`).

    Note:
    - The function currently returns a JSON body, even though the route is configured as 204.
    """
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    await db.delete(movie)
    await db.commit()

    return {"detail": "Movie deleted successfully."}


@router.patch(
    "/movies/{movie_id}/",
    summary="Update a movie by ID",
    description=(
            "<h3>Update fields of an existing movie by its unique ID (staff-only).</h3>"
            "<p>Only fields provided in the request body are updated (partial update).</p>"
            "<p>If the movie does not exist, a 404 error is returned.</p>"
    ),
    responses={
        200: {
            "description": "Movie updated successfully.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie updated successfully."}
                }
            },
        },
        400: {
            "description": "Invalid input data (constraint/validation error at DB level).",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid input data."}
                }
            },
        },
        404: {
            "description": "Movie not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with the given ID was not found."}
                }
            },
        },
    }
)
async def update_movie(
        movie_id: int,
        movie_data: MovieUpdateSchema,
        db: AsyncSession = Depends(get_db),
        _user: UserModel = Depends(user_is_staff),
) -> dict[str, str]:
    """
    Partially update a movie by ID (staff-only).

    Behavior:
    - Fetches the movie by `movie_id`.
    - Applies only provided fields from `movie_data` (`exclude_unset=True`).
    - Commits changes and refreshes the instance.

    Returns:
    - 200 with a confirmation message.

    Errors:
    - 404 if the movie does not exist (`"Movie with the given ID was not found."`).
    - 400 if a database constraint fails during commit (captured as `IntegrityError`).
    """
    stmt = select(MovieModel).where(MovieModel.id == movie_id)
    result = await db.execute(stmt)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    for field, value in movie_data.model_dump(exclude_unset=True).items():
        setattr(movie, field, value)

    try:
        await db.commit()
        await db.refresh(movie)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return {"detail": "Movie updated successfully."}
