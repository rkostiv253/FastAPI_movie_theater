import pytest

from sqlalchemy import select

from cinema.database.models.movies import MovieReactionModel, ReactionTypeEnum, MovieModel


@pytest.mark.asyncio
async def test_add_movie_reaction(client, user_token, db_session, seed_database):
    """
    Test POST `/api/v1/cinema/movies/{movie_id}/reactions/` adds a valid reaction to a movie.

    Steps:
    - Authenticate as a regular user.
    - Pick any existing movie from the seeded database.
    - Submit a valid reaction value (e.g., "like") to the reaction endpoint.
    - Verify response payload contains the same reaction.
    - Verify the reaction row exists in the DB with correct (movie_id, user_id, reaction).

    Expected result:
    - 201 Created
    - Response body includes `reaction` equal to the submitted value
    - Reaction is persisted in the database
    """

    user_id = user_token["user_id"]
    token = user_token["token"]

    user_headers = {"Authorization": f"Bearer {token}"}
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalar_one_or_none()

    reaction_payload = {
        "reaction": ReactionTypeEnum.LIKE.value,
    }

    response = await client.post(
        f"/api/v1/cinema/movies/{movie.id}/reactions/",
        json=reaction_payload,
        headers=user_headers
    )
    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}"
    response_data = response.json()
    assert response_data["reaction"] == ReactionTypeEnum.LIKE.value

    stmt = select(MovieReactionModel).where(
        MovieReactionModel.movie_id == movie.id,
        MovieReactionModel.user_id == user_id,
        MovieReactionModel.reaction == ReactionTypeEnum.LIKE.value
    )
    result = await db_session.execute(stmt)
    reaction = result.scalar_one_or_none()

    assert reaction is not None, "Reaction was not added to the movie."


@pytest.mark.asyncio
async def test_add_wrong_movie_reaction(client, user_token, db_session, seed_database):
    """
    Test POST `/api/v1/cinema/movies/{movie_id}/reactions/` rejects an invalid reaction value.

    Steps:
    - Authenticate as a regular user.
    - Pick any existing movie from the seeded database.
    - Submit an invalid reaction string (e.g., "nice") that is not allowed by the schema/enum.

    Expected result:
    - 422 Unprocessable Entity (validation error)
    - The request is not accepted due to schema/enum validation
    """

    token = user_token["token"]

    user_headers = {"Authorization": f"Bearer {token}"}
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalar_one_or_none()

    reaction_payload = {
        "reaction": "nice",
    }

    response = await client.post(
        f"/api/v1/cinema/movies/{movie.id}/reactions/",
        json=reaction_payload,
        headers=user_headers
    )
    assert response.status_code == 422, f"Expected status code 400, but got {response.status_code}"
