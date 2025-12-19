import pytest

from sqlalchemy import select

from cinema.database.models.movies import CommentModel, MovieModel


@pytest.mark.asyncio
async def test_get_movie_without_comments(client, user_token, db_session, seed_database):
    """
    Test GET `/api/v1/cinema/movies/{movie_id}/comments/` when a movie has no comments.

    Steps:
    - Authenticate as a regular user.
    - Pick any existing movie from the seeded database.
    - Request the movie comments list.

    Expected result:
    - 200 OK
    - Response body is an empty list: []
    """

    token = user_token["token"]

    user_headers = {"Authorization": f"Bearer {token}"}
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalar_one_or_none()

    comments_response = await client.get(f"/api/v1/cinema/movies/{movie.id}/comments/", headers=user_headers)
    assert comments_response.status_code == 200, (
        f"Expected status code 200, but got {comments_response.status_code}"
    )

    response_data = comments_response.json()
    assert response_data == [], (
        f"Expected empty list. Got: {response_data}"
    )


@pytest.mark.asyncio
async def test_post_comment(client, user_token, db_session, seed_database):
    """
    Test POST `/api/v1/cinema/movies/{movie_id}/comments/` creates a new comment.

    Steps:
    - Authenticate as a regular user.
    - Pick any existing movie from the seeded database.
    - Send a valid comment payload to create a comment.
    - Verify the comment appears in the DB.

    Expected result:
    - 201 Created
    - Response contains the same `comment` text that was submitted
    - Comment row exists in the database for (movie_id, comment text)
    """

    token = user_token["token"]

    user_headers = {"Authorization": f"Bearer {token}"}
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalar_one_or_none()
    comment_payload = {
        "comment": "Nice movie!"
    }

    response = await client.post(
        f"/api/v1/cinema/movies/{movie.id}/comments/",
        json=comment_payload,
        headers=user_headers
    )
    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}"
    response_data = response.json()
    assert response_data["comment"] == comment_payload["comment"]

    stmt = select(CommentModel).where(
        CommentModel.movie_id == movie.id,
        CommentModel.comment == comment_payload["comment"]
    )
    result = await db_session.execute(stmt)
    comment = result.scalar_one_or_none()

    assert comment is not None, "Comment was not created in database."


@pytest.mark.asyncio
async def test_read_comments(client, user_token, db_session, seed_database):
    """
    Test GET `/api/v1/cinema/movies/{movie_id}/comments/` returns created comments.

    Steps:
    - Authenticate as a regular user.
    - Pick any existing movie from the seeded database.
    - Create a comment via POST.
    - Fetch comments via GET for the same movie.

    Expected result:
    - POST returns 201 Created
    - GET returns 200 OK
    - GET response is a list with exactly 1 item
    - The returned comment text matches the payload used in POST
    """

    token = user_token["token"]

    user_headers = {"Authorization": f"Bearer {token}"}
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalar_one_or_none()
    comment_payload = {
        "comment": "Nice movie!"
    }

    response = await client.post(
        f"/api/v1/cinema/movies/{movie.id}/comments/",
        json=comment_payload,
        headers=user_headers
    )
    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}"

    response_comments = await client.get(
        f"/api/v1/cinema/movies/{movie.id}/comments/",
        headers=user_headers
    )
    assert response_comments.status_code == 200, (
        f"Expected status code 200, but got {response_comments.status_code}"
    )
    comments = response_comments.json()

    assert isinstance(comments, list), f"Expected list, got {type(comments)}"
    assert len(comments) == 1, f"Expected 1 comment, got {len(comments)}"

    first_comment = comments[0]
    assert first_comment["comment"] == comment_payload["comment"]


@pytest.mark.asyncio
async def test_delete_comment(client, user_token, db_session, seed_database):
    """
    Test DELETE `/api/v1/cinema/movies/{movie_id}/comments/{comment_id}/` removes a comment.

    Steps:
    - Authenticate as a regular user.
    - Pick any existing movie from the seeded database.
    - Create a comment via POST and capture its ID from the response.
    - Ensure the comment exists in the database.
    - Delete it via DELETE.
    - Ensure the comment no longer exists in the database.

    Expected result:
    - POST returns 201 Created and includes comment `id`
    - DELETE returns 204 No Content
    - Database query for that comment ID returns None
    """

    token = user_token["token"]

    user_headers = {"Authorization": f"Bearer {token}"}
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalar_one_or_none()
    comment_payload = {
        "comment": "Nice movie!"
    }

    response = await client.post(
        f"/api/v1/cinema/movies/{movie.id}/comments/",
        json=comment_payload,
        headers=user_headers
    )
    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}"

    created_comment_id = response.json().get("id")

    stmt = select(CommentModel).where(
        CommentModel.movie_id == movie.id,
        CommentModel.id == created_comment_id
    )
    result = await db_session.execute(stmt)
    comment = result.scalar_one_or_none()

    assert comment is not None, "Comment was not created in database."
    response_delete = await client.delete(
        f"/api/v1/cinema/movies/{movie.id}/comments/{comment.id}/", headers=user_headers)
    assert response_delete.status_code == 204, (
        f"Expected status code 204, but got {response_delete.status_code}"
    )

    deleted_stmt = select(CommentModel).where(
        CommentModel.movie_id == movie.id,
        CommentModel.id == created_comment_id
    )
    result = await db_session.execute(deleted_stmt)
    deleted_comment = result.scalar_one_or_none()

    assert deleted_comment is None, "Comment was not deleted from database."


@pytest.mark.asyncio
async def test_update_comment(client, user_token, db_session, seed_database):
    """
    Test PUT `/api/v1/cinema/movies/{movie_id}/comments/{comment_id}/` updates a comment.

    Steps:
    - Authenticate as a regular user.
    - Pick any existing movie from the seeded database.
    - Create a comment via POST and capture its ID.
    - Ensure the comment exists in the database.
    - Update the comment text via PUT.
    - Verify the response contains the updated comment text.

    Expected result:
    - POST returns 201 Created and includes comment `id`
    - PUT returns 200 OK
    - Response body contains the updated `comment` text
    """

    token = user_token["token"]

    user_headers = {"Authorization": f"Bearer {token}"}
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalar_one_or_none()
    comment_payload = {
        "comment": "Nice movie!"
    }

    response = await client.post(
        f"/api/v1/cinema/movies/{movie.id}/comments/",
        json=comment_payload,
        headers=user_headers
    )
    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}"

    created_comment_id = response.json().get("id")

    stmt = select(CommentModel).where(
        CommentModel.movie_id == movie.id,
        CommentModel.id == created_comment_id
    )
    result = await db_session.execute(stmt)
    comment = result.scalar_one_or_none()

    assert comment is not None, "Comment was not created in database."

    comment_update_payload = {
        "comment": "Nice movie and actors are also very good!"
    }

    response = await client.put(
        f"/api/v1/cinema/movies/{movie.id}/comments/{comment.id}/",
        json=comment_update_payload,
        headers=user_headers
    )
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()
    assert response_data["comment"] == comment_update_payload["comment"]
