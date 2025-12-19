from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy import select, exists, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cinema.config.dependencies import get_user, get_movie
from cinema.database.models.accounts import UserModel
from cinema.database.models.movies import MovieModel, FavouriteModel, FavouritesMoviesModel
from cinema.schemas import MovieListItemSchema
from cinema.schemas.accounts import MessageResponseSchema
from cinema.database import get_db

router = APIRouter()


@router.post(
    "/user/favourites/{movie_id}/",
    summary="Add a movie to the user's favourites",
    description=(
        "<h3>Add a movie to favourites</h3>"
        "<p>This endpoint adds the specified movie to the authenticated user's favourites list.</p>"
        "<ul>"
        "<li>If the user has no favourites list yet, it will be created automatically.</li>"
        "<li>If the movie is already in favourites, the endpoint returns <b>409 Conflict</b>.</li>"
        "</ul>"
    ),
    status_code=201,
    response_model=MessageResponseSchema,
    responses={
        201: {"description": "Movie added to favourites successfully."},
        404: {"description": "Movie not found or user not found."},
        409: {
            "description": "Movie already in favourites.",
            "content": {"application/json": {"example": {"detail": "Movie already in favourites."}}},
        },
    },
)
async def add_to_favourites(
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_user),
    movie: MovieModel = Depends(get_movie),
) -> MessageResponseSchema:
    """
    Add a movie to the authenticated user's favourites.

    Creates a favourites container for the user if it doesn't exist yet, then inserts a row
    into the association table between favourites and movies.

    Args:
        db (AsyncSession): Async SQLAlchemy DB session.
        user (UserModel): Authenticated user from token (dependency).
        movie (MovieModel): Movie instance from DB or 404 (dependency).

    Returns:
        MessageResponseSchema: Success message.

    Raises:
        HTTPException:
            - 409 if the movie already exists in favourites.
    """
    stmt = (
        select(FavouriteModel)
        .options(selectinload(FavouriteModel.movies))
        .where(FavouriteModel.user_id == user.id)
    )
    result = await db.execute(stmt)
    favourites = result.scalar_one_or_none()

    if favourites is None:
        favourites = FavouriteModel(user_id=user.id)
        db.add(favourites)
        await db.flush()  # ensure favourites.id is available without committing

    exists_stmt = select(
        exists().where(
            FavouritesMoviesModel.c.favourite_id == favourites.id,
            FavouritesMoviesModel.c.movie_id == movie.id,
        )
    )
    already_exists = await db.scalar(exists_stmt)

    if already_exists:
        raise HTTPException(status_code=409, detail="Movie already in favourites.")

    await db.execute(
        insert(FavouritesMoviesModel).values(
            favourite_id=favourites.id,
            movie_id=movie.id,
        )
    )
    await db.commit()

    return MessageResponseSchema(message="Movie added to favourites successfully.")


@router.get(
    "/user/favourites/",
    summary="Get the user's favourite movies",
    description=(
        "<h3>Get favourites</h3>"
        "<p>This endpoint returns the authenticated user's list of favourite movies.</p>"
        "<p>If the user has no favourites yet, it returns an empty list.</p>"
    ),
    responses={
        200: {"description": "List of favourite movies (possibly empty)."},
        404: {"description": "User not found or inactive."},
    },
)
async def get_favourites(
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_user),
) -> list[MovieListItemSchema]:
    """
    Retrieve the authenticated user's favourite movies.

    Args:
        db (AsyncSession): Async SQLAlchemy DB session.
        user (UserModel): Authenticated user from token (dependency).

    Returns:
        list[MovieModel]: A list of favourite movies (empty if none exist).
    """
    stmt = (
        select(FavouriteModel)
        .options(selectinload(FavouriteModel.movies))
        .where(FavouriteModel.user_id == user.id)
    )
    result = await db.execute(stmt)
    favourites = result.scalar_one_or_none()

    if not favourites:
        return []

    return [MovieListItemSchema.model_validate(movie) for movie in favourites.movies]


@router.delete(
    "/user/favourites/{movie_id}/",
    summary="Remove a movie from the user's favourites",
    description=(
        "<h3>Remove a movie from favourites</h3>"
        "<p>This endpoint removes the specified movie from the authenticated user's favourites list.</p>"
        "<ul>"
        "<li>If the user has no favourites list, returns <b>404</b>.</li>"
        "<li>If the movie is not in favourites, returns <b>404</b>.</li>"
        "</ul>"
    ),
    status_code=204,
    responses={
        204: {"description": "Movie removed successfully."},
        404: {
            "description": "No favourites found or movie not in favourites.",
            "content": {"application/json": {"example": {"detail": "Movie not in favourites."}}},
        },
    },
)
async def remove_from_favourites(
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_user),
    movie: MovieModel = Depends(get_movie),
):
    """
    Remove a movie from the authenticated user's favourites.

    Args:
        db (AsyncSession): Async SQLAlchemy DB session.
        user (UserModel): Authenticated user from token (dependency).
        movie (MovieModel): Movie instance from DB or 404 (dependency).

    Returns:
        dict: A small confirmation payload (even though status code is 204).

    Raises:
        HTTPException:
            - 404 if the favourites list doesn't exist or the movie isn't in favourites.
    """
    stmt = (
        select(FavouriteModel)
        .options(selectinload(FavouriteModel.movies))
        .where(FavouriteModel.user_id == user.id)
    )
    result = await db.execute(stmt)
    favourites = result.scalar_one_or_none()

    if not favourites:
        raise HTTPException(status_code=404, detail="No favourites found.")

    exists_stmt = select(
        exists().where(
            FavouritesMoviesModel.c.favourite_id == favourites.id,
            FavouritesMoviesModel.c.movie_id == movie.id,
        )
    )
    exists_movie = await db.scalar(exists_stmt)

    if not exists_movie:
        raise HTTPException(status_code=404, detail="Movie not in favourites.")

    await db.execute(
        FavouritesMoviesModel.delete().where(
            FavouritesMoviesModel.c.favourite_id == favourites.id,
            FavouritesMoviesModel.c.movie_id == movie.id,
        )
    )
    await db.commit()

    return {"detail": "Movie removed successfully."}
