from sqlalchemy.exc import IntegrityError

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cinema.config.dependencies import get_user, get_movie
from cinema.database.models.accounts import UserModel
from cinema.database.models.movies import MovieModel, CommentModel
from cinema.schemas.movies import (
    CommentCreateSchema,
    CommentUpdateSchema,
    CommentCreateResponseSchema,
    CommentUpdateResponseSchema,
    CommentReadSchema
)
from cinema.database import get_db


router = APIRouter()


@router.post("/movies/{movie_id}/comments/",
             summary="Post a comment for a specific movie",
             description=(
                     "<h3>This endpoint allows clients to add a new comment for a specific movie "
                     "to the database.</h3>"
             ),
             response_model=CommentCreateResponseSchema,
             responses={
                 400: {
                     "description": "Invalid input.",
                     "content": {
                         "application/json": {
                             "example": {"detail": "Invalid input data."}
                         }
                     },
                 }
             },
             status_code=201
             )
async def post_comment(
        data: CommentCreateSchema,
        db: AsyncSession = Depends(get_db),
        movie: MovieModel = Depends(get_movie),
        user: UserModel = Depends(get_user)
) -> CommentCreateResponseSchema:
    """
    Add a comment for a specific movie to the database.

    This endpoint allows the creation of a new comment for a specific movie.

    :param data: The data required to create a new comment.
    :type data: CommentCreateSchema
    :param db: The async SQLAlchemy database session (provided via dependency injection).
    :type db: AsyncSession
    :param movie: Movie fetched from database or 404 if movie not found  (provided via dependency injection).
    :type db: AsyncSession
    :param user: User session via decoded token, 404 if user not found or 403 if user is not active
    (provided via dependency injection).
    :type db: AsyncSession

    :return: The created comment.
    :rtype: CommentCreateResponseSchema

    :raises HTTPException:
        - 400 if input data is invalid (e.g., violating a constraint).
    """

    try:
        comment = CommentModel(
            user=user,
            movie=movie,
            comment=data.comment,
        )
        db.add(comment)
        await db.commit()
        await db.refresh(comment)

        return CommentCreateResponseSchema.model_validate(comment)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")


@router.get("/movies/{movie_id}/comments/",
            summary="Get a list of comments for a movie",
            response_model=list[CommentReadSchema],
            description=(
                    "This endpoint retrieves a  list of comments for a movie from the database. "
            ),
            )
async def read_comments(
        db: AsyncSession = Depends(get_db),
        movie: MovieModel = Depends(get_movie),
        _user: UserModel = Depends(get_user),
) -> list[CommentReadSchema]:
    """
    Fetch a list of comments for a movie from the database (asynchronously).

    This function retrieves a list of comments for a specific movie.

    :param db: The async SQLAlchemy database session (provided via dependency injection).
    :type db: AsyncSession
    :param movie: Movie fetched from database or 404 if movie not found  (provided via dependency injection).
    :type db: AsyncSession
    :param _user: User session via decoded token, 404 if user not found or 403 if user is not active
    (provided via dependency injection).
    :type db: AsyncSession

    :return: A response containing the list of comments for a specific movie and metadata.
    Returns an empty list if no comments are found.
    :rtype: list[CommentReadSchema]
.
    """

    stmt = select(CommentModel).where(CommentModel.movie_id == movie.id)
    result = await db.execute(stmt)
    comments = result.scalars().all()

    return [CommentReadSchema.model_validate(comment) for comment in comments]


@router.delete(
    "/movies/{movie_id}/comments/{comment_id}/",
    description=(
        "<h3>Delete a specific comment from the database by its unique ID.</h3>"
        "<p>If the comment exists, it will be deleted. If it does not exist, "
        "a 404 error will be returned. Admins and moderators can delete any comment.</p>"
    ),
    responses={
        204: {
            "description": "Comment deleted successfully."
        },
        404: {
            "description": "Comment not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Comment not found"}
                }
            },
        },
        403: {
            "description": "User does not have permission to delete other users comments.",
            "content": {
                "application/json": {
                    "example": {"detail": "You can't delete this comment."}
                }
            },
        },
    },
    status_code=204,
)
async def delete_comment(
        comment_id: int,
        db: AsyncSession = Depends(get_db),
        movie: MovieModel = Depends(get_movie),
        user: UserModel = Depends(get_user)
):
    """
    Delete a specific comment by its ID.

    This function deletes a comment identified by its unique ID.
    If comment does not exist, 404 error is raised.
    Users can only delete their own comments.

    :param comment_id: The unique identifier of the comment to delete.
    :type comment_id: int
    :param db: The async SQLAlchemy database session (provided via dependency injection).
    :type db: AsyncSession
    :param movie: Movie fetched from database or 404 if movie not found  (provided via dependency injection).
    :type db: AsyncSession
    :param user: User session via decoded token, 404 if user not found or 403 if user is not active
    (provided via dependency injection).
    :type db: AsyncSession

    :raises HTTPException: Raises a 404 error if comment with the given ID is not found.
    :raises HTTPException: Raises a 403 error if user tries to delete other users comments.

    :return: A response indicating the successful deletion of the movie.
    :rtype: None
    """
    stmt = select(CommentModel).where(
        CommentModel.id == comment_id,
        CommentModel.movie_id == movie.id,
    )
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found.")

    is_owner = comment.user_id == user.id
    is_moderator_or_admin = user.group.name in ("moderator", "admin")

    if not (is_owner or is_moderator_or_admin):
        raise HTTPException(status_code=403, detail="You can't delete this comment.")

    await db.delete(comment)
    await db.commit()

    return {"detail": "Comment deleted successfully."}


@router.put(
    "/movies/{movie_id}/comments/{comment_id}/",
    description=(
        "<h3>Update a specific comment from the database by its unique ID.</h3>"
        "<p>If the comment exists, it will be updated. If it does not exist, "
        "a 404 error will be returned.</p>"
    ),
    response_model=CommentUpdateResponseSchema,
    responses={
        404: {
            "description": "Comment not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Comment not found"}
                }
            },
        },
        403: {
            "description": "User does not have permission to update other users comments.",
            "content": {
                "application/json": {
                    "example": {"detail": "You can't delete this comment."}
                }
            },
        },
    },
)
async def update_comment(
        comment_id: int,
        data: CommentUpdateSchema,
        db: AsyncSession = Depends(get_db),
        movie: MovieModel = Depends(get_movie),
        user: UserModel = Depends(get_user)
) -> CommentUpdateResponseSchema:
    """
    Update a specific comment by its ID.

    This function updates a comment identified by its unique ID.
    If comment does not exist, 404 error is raised.
    Users can only update their own comments.

    :param comment_id: The unique identifier of the comment to update.
    :type comment_id: int
    :param data: The updated data for the comment.
    :type data: CommentUpdateSchema
    :param db: The async SQLAlchemy database session (provided via dependency injection).
    :type db: AsyncSession
    :param movie: Movie fetched from database or 404 if movie not found  (provided via dependency injection).
    :type db: AsyncSession
    :param user: User session via decoded token, 404 if user not found or 403 if user is not active
    (provided via dependency injection).
    :type db: AsyncSession

    :raises HTTPException: Raises 404 error if comment with the given ID is not found.
    :raises HTTPException: Raises 403 error if user tries to update other users comments.
    :raises HTTPException: Raises 400 error if input data is invalid (e.g., violating a constraint).

    :return: A response indicating the successful update of the comment.
    :rtype: CommentUpdateResponseSchema
    """
    stmt = select(CommentModel).where(
        CommentModel.id == comment_id,
        CommentModel.movie_id == movie.id,
    )
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()

    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found.")

    is_owner = comment.user_id == user.id
    is_moderator_or_admin = user.group.name in ("moderator", "admin")

    if not (is_owner or is_moderator_or_admin):
        raise HTTPException(status_code=403, detail="You can't update this comment.")

    comment.comment = data.comment

    try:
        await db.commit()
        await db.refresh(comment)
        return CommentUpdateResponseSchema.model_validate(comment)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")
