import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from cinema.database.models.movies import MovieModel, FavouriteModel


@pytest.mark.asyncio
async def test_add_movie_to_favourites(client, user_token, db_session, seed_database):
    """
    Test POST `/api/v1/accounts/user/favourites/{movie_id}/` adds a movie to the user's favourites.

    Steps:
    - Authenticate as a regular user.
    - Pick any existing movie from the seeded database.
    - Call the endpoint to add that movie to favourites.
    - Verify 201 response + success message.
    - Query the DB for user's favourites and ensure the movie is present in the relationship list.

    Expected result:
    - 201 Created
    - Response JSON contains: {"message": "Movie added to favourites successfully."}
    - DB contains a FavouriteModel row for user, with the movie included in `favourites.movies`
    """
    user_id = user_token["user_id"]
    token = user_token["token"]
    headers = {"Authorization": f"Bearer {token}"}

    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalar_one_or_none()
    assert movie is not None, "No movies in seeded database."

    resp = await client.post(f"/api/v1/accounts/user/favourites/{movie.id}/", headers=headers)
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}"
    assert resp.json()["message"] == "Movie added to favourites successfully."

    stmt = (
        select(FavouriteModel)
        .options(selectinload(FavouriteModel.movies))
        .where(FavouriteModel.user_id == user_id)
    )
    result = await db_session.execute(stmt)
    favourites = result.scalar_one_or_none()
    assert favourites is not None, "No favourites in seeded database."

    movie_ids = [m.id for m in favourites.movies]
    assert movie.id in movie_ids, "Movie id not in favourites."


@pytest.mark.asyncio
async def test_get_favourites(client, user_token, db_session, seed_database):
    """
    Test GET `/api/v1/accounts/user/favourites/` returns the user's favourites list.

    Steps:
    - Authenticate as a regular user.
    - Pick any existing movie from the seeded database.
    - Add the movie to favourites via POST (setup).
    - Fetch the favourites list via GET.
    - Verify 200 response and that the returned list contains the added movie.

    Expected result:
    - POST returns 201 Created
    - GET returns 200 OK
    - Response body is a list of movies
    - The list includes the movie that was added
    """
    token = user_token["token"]
    headers = {"Authorization": f"Bearer {token}"}

    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalar_one_or_none()
    assert movie is not None, "No movies in seeded database."

    resp_add = await client.post(f"/api/v1/accounts/user/favourites/{movie.id}/", headers=headers)
    assert resp_add.status_code == 201, f"Expected 201, got {resp_add.status_code}"

    resp = await client.get("/api/v1/accounts/user/favourites/", headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

    movies = resp.json()
    assert isinstance(movies, list), f"Expected list, got {type(movies)}"

    movie_ids = [m["id"] for m in movies]
    assert movie.id in movie_ids, "Movie id not in favourites."


@pytest.mark.asyncio
async def test_delete_movie_from_favourites(client, user_token, db_session, seed_database):
    """
    Test DELETE `/api/v1/accounts/user/favourites/{movie_id}/` removes a movie from favourites.

    Steps:
    - Authenticate as a regular user.
    - Pick at least 2 existing movies from the seeded database.
    - Add both movies to favourites via POST.
    - Delete one of them via DELETE.
    - Verify 204 response (no content).
    - Query DB favourites for user and confirm:
        - deleted movie is NOT present
        - the other movie IS still present

    Expected result:
    - DELETE returns 204 No Content
    - FavouriteModel.movies relationship contains remaining movie but not the removed one
    """
    user_id = user_token["user_id"]
    token = user_token["token"]
    headers = {"Authorization": f"Bearer {token}"}

    stmt = select(MovieModel).limit(2)
    result = await db_session.execute(stmt)
    movies = result.scalars().all()
    assert len(movies) >= 2, "Need at least 2 movies in seeded database."

    movie_id_1 = movies[0].id
    movie_id_2 = movies[1].id

    resp_add_1 = await client.post(f"/api/v1/accounts/user/favourites/{movie_id_1}/", headers=headers)
    resp_add_2 = await client.post(f"/api/v1/accounts/user/favourites/{movie_id_2}/", headers=headers)
    assert resp_add_1.status_code == 201, f"Expected 201, got {resp_add_1.status_code}"
    assert resp_add_2.status_code == 201, f"Expected 201, got {resp_add_2.status_code}"

    resp_delete = await client.delete(f"/api/v1/accounts/user/favourites/{movie_id_1}/", headers=headers)
    assert resp_delete.status_code == 204, f"Expected 204, got {resp_delete.status_code}"

    stmt = (
        select(FavouriteModel)
        .options(selectinload(FavouriteModel.movies))
        .where(FavouriteModel.user_id == user_id)
    )
    result = await db_session.execute(stmt)
    favourites = result.scalar_one_or_none()
    assert favourites is not None, "No favourites in seeded database."

    movie_ids = [m.id for m in favourites.movies]
    assert movie_id_1 not in movie_ids, "Movie id in favourites."
    assert movie_id_2 in movie_ids, "Movie id not in favourites."
