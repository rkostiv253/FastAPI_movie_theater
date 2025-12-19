from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cinema.config.dependencies import get_user, get_movie
from cinema.database.models.accounts import UserModel
from cinema.database.models.movies import MovieModel, RatingModel, RatingTypeEnum
from cinema.schemas.movies import RatingRequestSchema, RatingResponseSchema
from cinema.database import get_db


router = APIRouter()


@router.post(
    "/movies/{movie_id}/ratings/",
    summary="Rate a movie (toggle/update/remove)",
    description=(
        "<h3>Rate a movie</h3>"
        "<p>This endpoint lets the authenticated user rate a movie.</p>"
        "<ul>"
        "<li>If no rating exists yet, a new rating is created.</li>"
        "<li>If the same rating is sent again, the rating is removed (toggle off).</li>"
        "<li>If a different rating is sent, the rating is updated.</li>"
        "</ul>"
    ),
    status_code=201,
    response_model=RatingResponseSchema,
    responses={
        201: {"description": "Rating created/updated/removed successfully."},
        400: {
            "description": "Invalid input data.",
            "content": {"application/json": {"example": {"detail": "Invalid input data."}}},
        },
        404: {"description": "Movie not found or user not found."},
    },
)
async def toggle_rating(
    data: RatingRequestSchema,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_user),
    movie: MovieModel = Depends(get_movie),
) -> RatingResponseSchema:
    """
    Create/update/remove a rating for a movie (toggle behavior).

    Rules:
    - If the user has no rating for this movie -> create one.
    - If the user sends the same rating again -> delete it.
    - If the user sends a different rating -> update existing rating.

    Args:
        data (RatingRequestSchema): Rating payload.
        db (AsyncSession): Async SQLAlchemy DB session.
        user (UserModel): Authenticated user from token (dependency).
        movie (MovieModel): Movie instance from DB or 404 (dependency).

    Returns:
        RatingResponseSchema: Current rating (or null if removed) + message.

    Raises:
        HTTPException:
            - 400 if rating is missing or not allowed.
    """
    if data.rating is None:
        raise HTTPException(status_code=400, detail="Invalid input data.")

    if data.rating not in RatingTypeEnum:
        raise HTTPException(status_code=400, detail="Invalid input data.")

    stmt = select(RatingModel).filter_by(movie_id=movie.id, user_id=user.id)
    result = await db.execute(stmt)
    rating = result.scalar_one_or_none()

    if rating is None:
        rating = RatingModel(
            movie_id=movie.id,
            user_id=user.id,
            rating=data.rating,
        )
        db.add(rating)
        message = f"You gave this movie {data.rating}"

    elif rating.rating == data.rating:
        await db.delete(rating)
        rating = None
        message = "Your rating was removed"

    else:
        rating.rating = data.rating
        message = f"You gave this movie {data.rating}"

    await db.commit()

    return RatingResponseSchema(
        movie_id=movie.id,
        user_id=user.id,
        rating=rating.rating if rating else None,
        created_at=rating.created_at if rating else None,
        detail=message,
    )
