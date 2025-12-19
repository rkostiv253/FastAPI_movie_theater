import pytest

from sqlalchemy import select

from cinema.database import MovieModel
from cinema.database.models.movies import RatingTypeEnum, RatingModel


@pytest.mark.asyncio
async def test_add_movie_rating(client, user_token, db_session, seed_database):
    """
    Test POST `/api/v1/cinema/movies/{movie_id}/ratings/` adds a valid rating to a movie.

    Steps:
    - Authenticate as a regular user.
    - Pick any existing movie from the seeded database.
    - Submit a valid rating value (e.g., "8") to the rating endpoint.
    - Verify response payload contains the same rating.
    - Verify the rating row exists in the DB with correct (movie_id, user_id, rating).

    Expected result:
    - 201 Created
    - Response body includes `rating` equal to the submitted value
    - Rating is persisted in the database
    """

    user_id = user_token["user_id"]
    token = user_token["token"]

    user_headers = {"Authorization": f"Bearer {token}"}
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalar_one_or_none()

    rating_payload = {
        "rating": RatingTypeEnum.EIGHT.value,
    }

    response = await client.post(
        f"/api/v1/cinema/movies/{movie.id}/ratings/",
        json=rating_payload,
        headers=user_headers
    )
    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}"
    response_data = response.json()
    assert response_data["rating"] == RatingTypeEnum.EIGHT.value

    stmt = select(RatingModel).where(
        RatingModel.movie_id == movie.id,
        RatingModel.user_id == user_id,
        RatingModel.rating == RatingTypeEnum.EIGHT.value
    )
    result = await db_session.execute(stmt)
    rating = result.scalar_one_or_none()

    assert rating is not None, "Rating was not added to the movie."


@pytest.mark.asyncio
async def test_add_wrong_movie_rating(client, user_token, db_session, seed_database):
    """
    Test POST `/api/v1/cinema/movies/{movie_id}/ratings/` rejects an invalid rating value.

    Steps:
    - Authenticate as a regular user.
    - Pick any existing movie from the seeded database.
    - Submit an invalid rating value (e.g., 12) that is not allowed by the schema/enum.

    Expected result:
    - 422 Unprocessable Entity (validation error)
    - The request is not accepted due to schema/enum validation
    """

    token = user_token["token"]

    user_headers = {"Authorization": f"Bearer {token}"}
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalar_one_or_none()

    rating_payload = {
        "rating": 12,
    }

    response = await client.post(
        f"/api/v1/cinema/movies/{movie.id}/ratings/",
        json=rating_payload,
        headers=user_headers
    )
    assert response.status_code == 422, f"Expected status code 400, but got {response.status_code}"
