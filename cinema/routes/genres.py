from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cinema.config.dependencies import get_user
from cinema.database.models.movies import GenreModel, MovieModel
from cinema.schemas.movies import GenreListResponseSchema, GenreListItemSchema, GenreDetailSchema
from cinema.database import get_db, UserModel

router = APIRouter()


@router.get(
    "/genres/",
    response_model=GenreListResponseSchema,
    summary="Get a list of genres.",
    description=(
            "This endpoint retrieves the list of genres with movie count for each genre."
    ),
    responses={
        404: {
            "description": "No genres found.",
            "content": {
                "application/json": {
                    "example": {"detail": "No genres found."}
                }
            },
        }
    }
)
async def get_genre_list(
        page: int = Query(1, ge=1, description="Page number (1-based index)"),
        per_page: int = Query(10, ge=1, le=20, description="Number of items per page"),
        db: AsyncSession = Depends(get_db),
        _user: UserModel = Depends(get_user)
) -> GenreListResponseSchema:
    """
    Fetch a paginated list of genres from the database (asynchronously).

    This function retrieves a paginated list of genres with movie count, allowing
    the client to specify the page number and the number of items per page. It calculates
    the total pages and provides links to the previous and next pages when applicable.

    :param page: The page number to retrieve (1-based index, must be >= 1).
    :type page: int
    :param per_page: The number of items to display per page (must be between 1 and 20).
    :type per_page: int
    :param db: The async SQLAlchemy database session (provided via dependency injection).
    :type db: AsyncSession

    :return: A response containing the paginated list of genres and metadata.
    :rtype: GenreListResponseSchema

    :raises HTTPException: Raises a 404 error if no genres are found for the requested page.
    """
    offset = (page - 1) * per_page

    count_stmt = select(func.count(GenreModel.id))
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    if total_items == 0:
        raise HTTPException(status_code=404, detail="No genres found.")

    stmt = (
        select(
            GenreModel,
            func.count(MovieModel.id).label("movies_count")
        )
        .outerjoin(MovieModel, MovieModel.genre.id == GenreModel.id)
        .group_by(GenreModel.id)
        .order_by(GenreModel.id)
        .offset(offset)
        .limit(per_page)
    )

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        raise HTTPException(status_code=404, detail="No genres found.")

    genre_list = [
        GenreListItemSchema(
            id=genre.id,
            name=genre.name,
            movies_count=movies_count,
        )
        for genre, movies_count in rows
    ]

    total_pages = (total_items + per_page - 1) // per_page

    response = GenreListResponseSchema(
        genres=genre_list,
        prev_page=f"/cinema/genres/?page={page - 1}&per_page={per_page}" if page > 1 else None,
        next_page=f"/cinema/genres/?page={page + 1}&per_page={per_page}" if page < total_pages else None,
        total_pages=total_pages,
        total_items=total_items,
    )
    return response


@router.get(
    "/genres/{genre_id}/",
    response_model=GenreDetailSchema,
    summary="Get genre details by ID",
    description=(
            "This endpoint retrieves all movies which relate to specific genre."
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
async def get_movies_by_genre_id(
        genre_id: int,
        db: AsyncSession = Depends(get_db),
        _user: UserModel = Depends(get_user)
) -> GenreDetailSchema:
    """
    Retrieve movies for a specific genre.

    This function fetches movies which relate to specific genre by unique ID of genre.
    If genre does not exist, a 404 error is returned.

    :param genre_id: The unique identifier of genre to retrieve.
    :type genre_id: int
    :param db: The SQLAlchemy database session (provided via dependency injection).
    :type db: AsyncSession

    :return: The details of the requested genre.
    :rtype: GenreDetailResponseSchema

    :raises HTTPException: Raises a 404 error if genre with the given ID is not found.
    """
    stmt = (
        select(GenreModel)
        .options(
            selectinload(GenreModel.movies),
        )
        .where(GenreModel.id == genre_id)
    )

    result = await db.execute(stmt)
    genre = result.scalars().first()

    if not genre:
        raise HTTPException(
            status_code=404,
            detail="Genre with the given ID was not found."
        )

    return GenreDetailSchema.model_validate(genre)
