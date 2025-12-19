from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cinema.config.dependencies import get_user, get_movie
from cinema.database.models.accounts import UserModel
from cinema.database.models.movies import MovieModel, MovieReactionModel, ReactionTypeEnum
from cinema.schemas.movies import MovieReactionRequestSchema, MovieReactionResponseSchema
from cinema.database import get_db


router = APIRouter()


@router.post(
    "/movies/{movie_id}/reactions/",
    summary="React to a movie (toggle/update/remove)",
    description=(
        "<h3>React to a movie</h3>"
        "<p>This endpoint lets the authenticated user add a reaction to a movie.</p>"
        "<ul>"
        "<li>If no reaction exists yet, a new reaction is created.</li>"
        "<li>If the same reaction is sent again, the reaction is removed (toggle off).</li>"
        "<li>If a different reaction is sent, the reaction is updated.</li>"
        "</ul>"
    ),
    status_code=201,
    response_model=MovieReactionResponseSchema,
    responses={
        201: {"description": "Reaction created/updated/removed successfully."},
        400: {
            "description": "Invalid input data.",
            "content": {"application/json": {"example": {"detail": "Invalid input data."}}},
        },
        404: {"description": "Movie not found or user not found."},
    },
)
async def toggle_reaction(
    data: MovieReactionRequestSchema,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_user),
    movie: MovieModel = Depends(get_movie),
) -> MovieReactionResponseSchema:
    """
    Create/update/remove a reaction for a movie (toggle behavior).

    Rules:
    - If the user has no reaction for this movie -> create one.
    - If the user sends the same reaction again -> delete it.
    - If the user sends a different reaction -> update existing reaction.

    Args:
        data (MovieReactionRequestSchema): Reaction payload.
        db (AsyncSession): Async SQLAlchemy DB session.
        user (UserModel): Authenticated user from token (dependency).
        movie (MovieModel): Movie instance from DB or 404 (dependency).

    Returns:
        MovieReactionResponseSchema: Current reaction (or null if removed) + message.

    Raises:
        HTTPException:
            - 400 if reaction is missing or not allowed.
    """
    if data.reaction is None:
        raise HTTPException(status_code=400, detail="Invalid input data.")

    if data.reaction not in ReactionTypeEnum:
        raise HTTPException(status_code=400, detail="Invalid input data.")

    stmt = select(MovieReactionModel).filter_by(movie_id=movie.id, user_id=user.id)
    result = await db.execute(stmt)
    reaction = result.scalar_one_or_none()

    if reaction is None:
        reaction = MovieReactionModel(
            movie_id=movie.id,
            user_id=user.id,
            reaction=data.reaction,
        )
        db.add(reaction)
        message = f"You {data.reaction}d this movie"

    elif reaction.reaction == data.reaction:
        await db.delete(reaction)
        reaction = None
        message = "Your reaction was removed"

    else:
        reaction.reaction = data.reaction
        message = f"You {data.reaction}d this movie"

    await db.commit()

    return MovieReactionResponseSchema(
        movie_id=movie.id,
        user_id=user.id,
        reaction=reaction.reaction if reaction else None,
        created_at=reaction.created_at if reaction else None,
        detail=message,
    )
