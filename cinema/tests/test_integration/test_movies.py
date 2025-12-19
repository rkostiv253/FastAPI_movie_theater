import random
from decimal import Decimal

import pytest
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from cinema.database.models.movies import (
    MovieModel,
    GenreModel,
    ActorModel,
    LanguageModel,
    CountryModel
)

from cinema.database.models.movies import DirectorModel

movie_data = {
    "uuid": "8f4b2c9e-3a4f-4c1a-9c72-1d9b5e8c1f21",
    "name": "The Silent Horizon",
    "year": 2023,
    "duration": 128,
    "imdb": Decimal("8.4"),
    "imdb_votes": 154321,
    "description": "A gripping sci-fi drama about humanity's last mission beyond the known universe.",
    "budget": Decimal("120000000.00"),
    "revenue": Decimal("356450000.00"),
    "certification": "PG13",
    "price": Decimal("9.99"),
    "country": "US",
    "genres": ["Science Fiction", "Drama", "Adventure"],
    "actors": ["John Doe", "Jane Smith", "Michael Johnson"],
    "directors": ["Christopher Nolan"],
    "languages": ["English", "Spanish"]
}


@pytest.mark.asyncio
async def test_get_movies_empty_database(client):
    """
    Test GET `/api/v1/cinema/movies/` returns an error when the database is empty.

    Steps:
    - Make a GET request to the movies list endpoint without seeding the database.

    Expected result:
    - 404 Not Found
    - Response body is exactly: {"detail": "No movies found."}
    """
    response = await client.get("/api/v1/cinema/movies/")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    expected_detail = {"detail": "No movies found."}
    assert response.json() == expected_detail, f"Expected {expected_detail}, got {response.json()}"


@pytest.mark.asyncio
async def test_get_movies_default_parameters(client, seed_database):
    """
    Test GET `/api/v1/cinema/movies/` returns movies with default pagination parameters.

    Steps:
    - Seed the database with movies.
    - Make a GET request to the movies list endpoint without specifying `page` and `per_page`.

    Expected result:
    - 200 OK
    - Response contains `movies` with length 10 (default per_page)
    - `total_pages` > 0 and `total_items` > 0
    - `prev_page` is None on the first page
    - `next_page` is present when `total_pages` > 1
    """
    response = await client.get("/api/v1/cinema/movies/")
    assert response.status_code == 200, "Expected status code 200, but got a different value"

    response_data = response.json()

    assert len(response_data["movies"]) == 10, "Expected 10 movies in the response, but got a different count"

    assert response_data["total_pages"] > 0, "Expected total_pages > 0, but got a non-positive value"
    assert response_data["total_items"] > 0, "Expected total_items > 0, but got a non-positive value"

    assert response_data["prev_page"] is None, "Expected prev_page to be None on the first page, but got a value"

    if response_data["total_pages"] > 1:
        assert response_data["next_page"] is not None, (
            "Expected next_page to be present when total_pages > 1, but got None"
        )


@pytest.mark.asyncio
async def test_get_movies_with_custom_parameters(client, seed_database):
    """
    Test GET `/api/v1/cinema/movies/` returns movies with custom pagination parameters.

    Steps:
    - Seed the database with movies.
    - Request page=2 and per_page=5.

    Expected result:
    - 200 OK
    - Response contains exactly `per_page` movies
    - `total_pages` > 0 and `total_items` > 0
    - `prev_page` link matches the expected URL for page-1
    - `next_page` link matches the expected URL for page+1 (or None if last page)
    """
    page = 2
    per_page = 5

    response = await client.get(f"/api/v1/cinema/movies/?page={page}&per_page={per_page}")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert len(response_data["movies"]) == per_page, (
        f"Expected {per_page} movies in the response, but got {len(response_data['movies'])}"
    )

    assert response_data["total_pages"] > 0, "Expected total_pages > 0, but got a non-positive value"
    assert response_data["total_items"] > 0, "Expected total_items > 0, but got a non-positive value"

    if page > 1:
        assert response_data["prev_page"] == f"/cinema/movies/?page={page - 1}&per_page={per_page}", (
            f"Expected prev_page to be '/cinema/movies/?page={page - 1}&per_page={per_page}', "
            f"but got {response_data['prev_page']}"
        )

    if page < response_data["total_pages"]:
        assert response_data["next_page"] == f"/cinema/movies/?page={page + 1}&per_page={per_page}", (
            f"Expected next_page to be '/cinema/movies/?page={page + 1}&per_page={per_page}', "
            f"but got {response_data['next_page']}"
        )
    else:
        assert response_data["next_page"] is None, "Expected next_page to be None on the last page, but got a value"


@pytest.mark.asyncio
@pytest.mark.parametrize("page, per_page, expected_detail", [
    (0, 10, "Input should be greater than or equal to 1"),
    (1, 0, "Input should be greater than or equal to 1"),
    (0, 0, "Input should be greater than or equal to 1"),
])
async def test_invalid_page_and_per_page(client, page, per_page, expected_detail):
    """
    Test GET `/api/v1/cinema/movies/` returns validation errors for invalid `page` / `per_page`.

    Steps:
    - Call the movies list endpoint using invalid pagination values (0 or less).

    Expected result:
    - 422 Unprocessable Entity
    - Response contains `detail` with validation errors
    - At least one error message includes: "Input should be greater than or equal to 1"
    """
    response = await client.get(f"/api/v1/cinema/movies/?page={page}&per_page={per_page}")

    assert response.status_code == 422, (
        f"Expected status code 422 for invalid parameters, but got {response.status_code}"
    )

    response_data = response.json()

    assert "detail" in response_data, "Expected 'detail' in the response, but it was missing"

    assert any(expected_detail in error["msg"] for error in response_data["detail"]), (
        f"Expected error message '{expected_detail}' in the response details, but got {response_data['detail']}"
    )


@pytest.mark.asyncio
async def test_per_page_maximum_allowed_value(client, seed_database):
    """
    Test GET `/api/v1/cinema/movies/` accepts the maximum allowed `per_page` value.

    Steps:
    - Seed the database with movies.
    - Request page=1 and per_page=20.

    Expected result:
    - 200 OK
    - Response contains `movies`
    - Number of returned movies is <= 20
    """
    response = await client.get("/api/v1/cinema/movies/?page=1&per_page=20")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert "movies" in response_data, "Response missing 'movies' field."
    assert len(response_data["movies"]) <= 20, (
        f"Expected at most 20 movies, but got {len(response_data['movies'])}"
    )


@pytest.mark.asyncio
async def test_page_exceeds_maximum(client, db_session, seed_database):
    """
    Test GET `/api/v1/cinema/movies/` returns 404 when requested page exceeds the last page.

    Steps:
    - Seed the database with movies.
    - Compute total movies in the DB.
    - Compute max_page for a given per_page.
    - Request page = max_page + 1.

    Expected result:
    - 404 Not Found
    - Response contains `detail`
    """
    per_page = 10

    count_stmt = select(func.count(MovieModel.id))
    result = await db_session.execute(count_stmt)
    total_movies = result.scalar_one()

    max_page = (total_movies + per_page - 1) // per_page

    response = await client.get(f"/api/v1/cinema/movies/?page={max_page + 1}&per_page={per_page}")

    assert response.status_code == 404, f"Expected status code 404, but got {response.status_code}"
    response_data = response.json()

    assert "detail" in response_data, "Response missing 'detail' field."


@pytest.mark.asyncio
async def test_movies_sorted_by_id_desc(client, db_session, seed_database):
    """
    Test GET `/api/v1/cinema/movies/` returns movies sorted by `id` descending.

    Steps:
    - Seed the database with movies.
    - Request page=1 and per_page=10 from the endpoint.
    - Fetch the expected first 10 movies directly from the DB ordered by `id` DESC.
    - Compare IDs from response and DB.

    Expected result:
    - 200 OK
    - Returned movie IDs are in strictly DB-matching descending order
    """
    response = await client.get("/api/v1/cinema/movies/?page=1&per_page=10")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    stmt = select(MovieModel).order_by(MovieModel.id.desc()).limit(10)
    result = await db_session.execute(stmt)
    expected_movies = result.scalars().all()

    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["movies"]]

    assert returned_movie_ids == expected_movie_ids, (
        f"Movies are not sorted by `id` in descending order. "
        f"Expected: {expected_movie_ids}, but got: {returned_movie_ids}"
    )


@pytest.mark.asyncio
async def test_movie_list_with_pagination(client, db_session, seed_database):
    """
    Test GET `/api/v1/cinema/movies/` pagination metadata and page contents.

    Steps:
    - Seed the database with movies.
    - Request page=2 and per_page=5.
    - Compute `total_items` from DB and derive `total_pages`.
    - Fetch expected movies from DB using the same offset/limit and ordering as the endpoint.
    - Compare returned movie IDs to expected IDs.
    - Validate `prev_page` and `next_page` links.

    Expected result:
    - 200 OK
    - `total_items` and `total_pages` match DB-derived values
    - Returned movies match expected movies for requested page
    - `prev_page` and `next_page` links match expected URLs
    """
    page = 2
    per_page = 5
    offset = (page - 1) * per_page

    response = await client.get(f"/api/v1/cinema/movies/?page={page}&per_page={per_page}")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    count_stmt = select(func.count(MovieModel.id))
    count_result = await db_session.execute(count_stmt)
    total_items = count_result.scalar_one()

    total_pages = (total_items + per_page - 1) // per_page

    assert response_data["total_items"] == total_items, "Total items mismatch."
    assert response_data["total_pages"] == total_pages, "Total pages mismatch."

    stmt = (
        select(MovieModel)
        .order_by(MovieModel.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db_session.execute(stmt)
    expected_movies = result.scalars().all()

    expected_movie_ids = [movie.id for movie in expected_movies]
    returned_movie_ids = [movie["id"] for movie in response_data["movies"]]

    assert expected_movie_ids == returned_movie_ids, "Movies on the page mismatch."

    expected_prev_page = f"/cinema/movies/?page={page - 1}&per_page={per_page}" if page > 1 else None
    expected_next_page = f"/cinema/movies/?page={page + 1}&per_page={per_page}" if page < total_pages else None

    assert response_data["prev_page"] == expected_prev_page, "Previous page link mismatch."
    assert response_data["next_page"] == expected_next_page, "Next page link mismatch."


@pytest.mark.asyncio
async def test_movies_fields_match_schema(client, db_session, seed_database):
    """
    Test GET `/api/v1/cinema/movies/` list items include only the expected schema fields.

    Steps:
    - Seed the database with movies.
    - Request page=1 and per_page=10.
    - For each returned movie item, compare its keys to the expected schema keys.

    Expected result:
    - 200 OK
    - Every movie item contains exactly: {"id", "name", "year", "imdb", "description"}
    """
    response = await client.get("/api/v1/cinema/movies/?page=1&per_page=10")

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert "movies" in response_data, "Response missing 'movies' field."

    expected_fields = {"id", "name", "year", "imdb", "description"}

    for movie in response_data["movies"]:
        assert set(movie.keys()) == expected_fields, (
            f"Movie fields do not match schema. "
            f"Expected: {expected_fields}, but got: {set(movie.keys())}"
        )


@pytest.mark.asyncio
async def test_get_movie_by_id_not_found(client):
    """
    Test GET `/api/v1/cinema/movies/{movie_id}/` returns 404 for a missing movie.

    Steps:
    - Request a movie ID that does not exist.

    Expected result:
    - 404 Not Found
    - Response body is exactly: {"detail": "Movie with the given ID was not found."}
    """
    movie_id = 1

    response = await client.get(f"/api/v1/cinema/movies/{movie_id}/")
    assert response.status_code == 404, f"Expected status code 404, but got {response.status_code}"

    response_data = response.json()
    assert response_data == {"detail": "Movie with the given ID was not found."}, (
        f"Expected error message not found. Got: {response_data}"
    )


@pytest.mark.asyncio
async def test_get_movie_by_id_valid(client, db_session, seed_database):
    """
    Test GET `/api/v1/cinema/movies/{movie_id}/` returns correct details for a valid movie.

    Steps:
    - Seed the database with movies.
    - Fetch min and max movie IDs from DB.
    - Pick a random ID within that range.
    - Fetch expected movie from DB.
    - Request the movie by ID from the API.

    Expected result:
    - 200 OK
    - Response `id` matches requested ID
    - Response `name` matches the database value for that movie
    """
    stmt_min = select(MovieModel.id).order_by(MovieModel.id.asc()).limit(1)
    result_min = await db_session.execute(stmt_min)
    min_id = result_min.scalars().first()

    stmt_max = select(MovieModel.id).order_by(MovieModel.id.desc()).limit(1)
    result_max = await db_session.execute(stmt_max)
    max_id = result_max.scalars().first()

    random_id = random.randint(min_id, max_id)

    stmt_movie = select(MovieModel).where(MovieModel.id == random_id)
    result_movie = await db_session.execute(stmt_movie)
    expected_movie = result_movie.scalars().first()
    assert expected_movie is not None, "Movie not found in database."

    response = await client.get(f"/api/v1/cinema/movies/{random_id}/")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert response_data["id"] == expected_movie.id, "Returned ID does not match the requested ID."
    assert response_data["name"] == expected_movie.name, "Returned name does not match the expected name."


@pytest.mark.asyncio
async def test_get_movie_by_id_fields_match_database(client, db_session, seed_database):
    """
    Test GET `/api/v1/cinema/movies/{movie_id}/` fields match the database record.

    Steps:
    - Seed the database with movies.
    - Select one movie from DB with all relationships eagerly loaded.
    - Request the same movie by ID via the API.
    - Compare scalar fields to DB values.
    - Compare nested relations (country, genres, actors, directors, languages, comments, reactions, ratings).

    Expected result:
    - 200 OK
    - Response scalar fields exactly match the DB values
    - Response nested relations match the DB values (order-insensitive comparisons where needed)
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
        .limit(1)
    )
    result = await db_session.execute(stmt)
    random_movie = result.scalars().first()
    assert random_movie is not None, "No movies found in the database."

    response = await client.get(f"/api/v1/cinema/movies/{random_movie.id}/")
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()

    assert response_data["id"] == random_movie.id, "ID does not match."
    assert response_data["uuid"] == random_movie.uuid, "UUID does not match."
    assert response_data["name"] == random_movie.name, "Name does not match."
    assert response_data["year"] == random_movie.year, "Year does not match."
    assert response_data["duration"] == random_movie.duration, "Duration does not match."
    assert Decimal(
        str(response_data["imdb"])) == Decimal(str(random_movie.imdb)), "Imdb does not match."
    assert response_data["imdb_votes"] == random_movie.imdb_votes, "Imdb_votes does not match."
    assert response_data["description"] == random_movie.description, "Description does not match."
    assert Decimal(str(response_data["budget"])) == Decimal(str(random_movie.budget)), "Budget does not match."
    assert Decimal(str(response_data["revenue"])) == Decimal(str(random_movie.revenue)), "Revenue does not match."
    assert response_data["certification"] == random_movie.certification, "Certification does not match."
    assert Decimal(str(response_data["price"])) == Decimal(str(random_movie.price)), "Price does not match."

    assert response_data["country"]["code"] == random_movie.country.code, "Country code does not match."
    assert response_data["country"]["name"] == random_movie.country.name, "Country name does not match."

    actual_genres = sorted(response_data["genres"], key=lambda x: x["id"])
    expected_genres = sorted(
        [{"id": genre.id, "name": genre.name} for genre in random_movie.genres],
        key=lambda x: x["id"]
    )
    assert actual_genres == expected_genres, "Genres do not match."

    actual_actors = sorted(response_data["actors"], key=lambda x: x["id"])
    expected_actors = sorted(
        [{"id": actor.id, "name": actor.name} for actor in random_movie.actors],
        key=lambda x: x["id"]
    )
    assert actual_actors == expected_actors, "Actors do not match."

    actual_directors = sorted(response_data["directors"], key=lambda x: x["id"])
    expected_directors = sorted(
        [{"id": director.id, "name": director.name} for director in random_movie.directors],
        key=lambda x: x["id"]
    )
    assert actual_directors == expected_directors, "Directors do not match."

    actual_languages = sorted(response_data["languages"], key=lambda x: x["id"])
    expected_languages = sorted(
        [{"id": lang.id, "name": lang.name} for lang in random_movie.languages],
        key=lambda x: x["id"]
    )
    assert actual_languages == expected_languages, "Languages do not match."

    actual_comments = sorted(
        response_data["comments"],
        key=lambda x: x["id"]
    )

    expected_comments = sorted(
        [
            {
                "id": comment.id,
                "text": comment.text,
                "user_id": comment.user_id,
            }
            for comment in random_movie.comments
        ],
        key=lambda x: x["id"]
    )

    assert actual_comments == expected_comments, "Comments do not match."

    actual_reactions = sorted(
        response_data["reactions"],
        key=lambda x: x["id"]
    )

    expected_reactions = sorted(
        [
            {
                "id": reaction.id,
                "type": reaction.type,
                "user_id": reaction.user_id,
            }
            for reaction in random_movie.reactions
        ],
        key=lambda x: x["id"]
    )

    assert actual_reactions == expected_reactions, "Reactions do not match."

    actual_ratings = sorted(
        response_data["ratings"],
        key=lambda x: x["id"]
    )

    expected_ratings = sorted(
        [
            {
                "id": rating.id,
                "rating": rating.rating,
                "user_id": rating.user_id,
            }
            for rating in random_movie.ratings
        ],
        key=lambda x: x["id"]
    )

    assert actual_ratings == expected_ratings, "Ratings do not match."


@pytest.mark.asyncio
async def test_create_movie_and_related_models(client, admin_token, db_session):
    """
    Test POST `/api/v1/cinema/movies/` creates a new movie and related models if missing.

    Steps:
    - Authenticate as an admin user.
    - Submit a valid movie payload.
    - Verify response fields match the submitted payload.
    - Verify related models exist in DB (genres, actors, directors, languages, country).

    Expected result:
    - 201 Created
    - Response body matches submitted movie data
    - Missing related entities are created in the database
    - Newly created movie has empty `comments`, `reactions`, and `ratings`
    """
    token = admin_token["token"]

    headers = {"Authorization": f"Bearer {token}"}
    sample_movie = jsonable_encoder(movie_data)

    response = await client.post("/api/v1/cinema/movies/", json=sample_movie, headers=headers)
    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}"

    response_data = response.json()
    assert response_data["uuid"] == sample_movie["uuid"], "UUID does not match."
    assert response_data["name"] == sample_movie["name"], "Name does not match."
    assert response_data["year"] == sample_movie["year"], "Year does not match."
    assert response_data["duration"] == sample_movie["duration"], "Duration does not match."
    assert Decimal(
        str(response_data["imdb"])) == Decimal(str(sample_movie["imdb"])), "Imdb does not match."
    assert response_data["imdb_votes"] == sample_movie["imdb_votes"], "Imdb votes does not match."
    assert response_data["description"] == sample_movie["description"], "Description does not match."
    assert Decimal(str(response_data["budget"])) == Decimal(str(sample_movie["budget"])), "Budget does not match."
    assert Decimal(str(response_data["revenue"])) == Decimal(str(sample_movie["revenue"])), "Revenue does not match."
    assert response_data["certification"] == sample_movie["certification"], "Certification does not match."
    assert Decimal(str(response_data["price"])) == Decimal(str(sample_movie["price"])), "Price does not match."

    for genre_name in sample_movie["genres"]:
        stmt = select(GenreModel).where(GenreModel.name == genre_name)
        result = await db_session.execute(stmt)
        genre = result.scalars().first()
        assert genre is not None, f"Genre '{genre_name}' was not created."

    for actor_name in sample_movie["actors"]:
        stmt = select(ActorModel).where(ActorModel.name == actor_name)
        result = await db_session.execute(stmt)
        actor = result.scalars().first()
        assert actor is not None, f"Actor '{actor_name}' was not created."

    for director_name in sample_movie["directors"]:
        stmt = select(DirectorModel).where(DirectorModel.name == director_name)
        result = await db_session.execute(stmt)
        director = result.scalars().first()
        assert director is not None, f"Director '{director_name}' was not created."

    for language_name in sample_movie["languages"]:
        stmt = select(LanguageModel).where(LanguageModel.name == language_name)
        result = await db_session.execute(stmt)
        language = result.scalars().first()
        assert language is not None, f"Language '{language_name}' was not created."

    stmt = select(CountryModel).where(CountryModel.code == sample_movie["country"])
    result = await db_session.execute(stmt)
    country = result.scalars().first()
    assert country is not None, f"Country '{sample_movie['country']}' was not created."

    assert response_data["comments"] == [], "Expected no comments on newly created movie."
    assert response_data["reactions"] == [], "Expected no reactions on newly created movie."
    assert response_data["ratings"] == [], "Expected no ratings on newly created movie."


@pytest.mark.asyncio
async def test_create_movie_duplicate_error(client, admin_token, db_session):
    """
    Test POST `/api/v1/cinema/movies/` returns 409 when creating a duplicate movie.

    Steps:
    - Authenticate as an admin user.
    - Create a movie using a valid payload.
    - Submit the same payload again.

    Expected result:
    - First request: 201 Created
    - Second request: 409 Conflict
    - Response `detail` explains a movie with the same name and year already exists
    """
    token = admin_token["token"]

    headers = {"Authorization": f"Bearer {token}"}
    sample_movie = jsonable_encoder(movie_data)

    response = await client.post("/api/v1/cinema/movies/", json=sample_movie, headers=headers)
    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}"

    duplicate_response = await client.post("/api/v1/cinema/movies/", json=sample_movie, headers=headers)
    assert duplicate_response.status_code == 409, f"Expected status code 409, but got {duplicate_response.status_code}"

    response_data = duplicate_response.json()
    expected_detail = (
        f"A movie with the name '{sample_movie['name']}' and release year '{sample_movie['year']}' already exists."
    )
    assert response_data["detail"] == expected_detail, (
        f"Expected detail message: {expected_detail}, but got: {response_data['detail']}"
    )


@pytest.mark.asyncio
async def test_delete_movie_success(client, admin_token, db_session, seed_database):
    """
    Test DELETE `/api/v1/cinema/movies/{movie_id}/` deletes an existing movie.

    Steps:
    - Seed the database with movies.
    - Authenticate as an admin user.
    - Pick any existing movie from the DB.
    - Send a DELETE request for that movie ID.
    - Query DB to ensure the movie no longer exists.

    Expected result:
    - 204 No Content
    - The deleted movie is not present in the database anymore
    """
    token = admin_token["token"]

    headers = {"Authorization": f"Bearer {token}"}

    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalar_one_or_none()

    response = await client.delete(f"/api/v1/cinema/movies/{movie.id}/", headers=headers)
    assert response.status_code == 204, f"Expected status code 204, but got {response.status_code}"

    stmt_check = select(MovieModel).where(MovieModel.id == movie.id)
    result_check = await db_session.execute(stmt_check)
    deleted_movie = result_check.scalars().first()
    assert deleted_movie is None, f"Movie with ID {movie.id} was not deleted."


@pytest.mark.asyncio
async def test_delete_movie_not_found(client, admin_token):
    """
    Test DELETE `/api/v1/cinema/movies/{movie_id}/` returns 404 for a missing movie.

    Steps:
    - Authenticate as an admin user.
    - Send a DELETE request for a non-existent movie ID.

    Expected result:
    - 404 Not Found
    - Response `detail` is: "Movie with the given ID was not found."
    """
    token = admin_token["token"]

    headers = {"Authorization": f"Bearer {token}"}

    non_existent_id = 99999

    response = await client.delete(f"/api/v1/cinema/movies/{non_existent_id}/", headers=headers)
    assert response.status_code == 404, f"Expected status code 404, but got {response.status_code}"

    response_data = response.json()
    expected_detail = "Movie with the given ID was not found."
    assert response_data["detail"] == expected_detail, (
        f"Expected detail message: {expected_detail}, but got: {response_data['detail']}"
    )


@pytest.mark.asyncio
async def test_update_movie_success(client, admin_token, db_session, seed_database):
    """
    Test PATCH `/api/v1/cinema/movies/{movie_id}/` updates an existing movie.

    Steps:
    - Seed the database with movies.
    - Authenticate as an admin user.
    - Pick any existing movie from the DB.
    - Send a PATCH request with updated fields (name, description).
    - Query DB to confirm changes were persisted.

    Expected result:
    - 200 OK
    - Response `detail` is: "Movie updated successfully."
    - Database values match the updated fields
    """
    token = admin_token["token"]

    headers = {"Authorization": f"Bearer {token}"}
    stmt = select(MovieModel).limit(1)
    result = await db_session.execute(stmt)
    movie = result.scalar_one_or_none()

    update_data = {
        "name": "Updated Movie Name",
        "description": "Great movie!",
    }

    response = await client.patch(f"/api/v1/cinema/movies/{movie.id}/", json=update_data, headers=headers)
    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}"

    response_data = response.json()
    assert response_data["detail"] == "Movie updated successfully.", (
        f"Expected detail message: 'Movie updated successfully.', but got: {response_data['detail']}"
    )

    stmt_check = select(MovieModel).where(MovieModel.id == movie.id)
    result_check = await db_session.execute(stmt_check)
    updated_movie = result_check.scalars().first()

    await db_session.refresh(updated_movie)

    assert updated_movie.name == update_data["name"], "Movie name was not updated."
    assert updated_movie.description == update_data["description"], "Movie imdb rating was not updated."


@pytest.mark.asyncio
async def test_update_movie_not_found(client, admin_token, db_session):
    """
    Test PATCH `/api/v1/cinema/movies/{movie_id}/` returns 404 for a missing movie.

    Steps:
    - Authenticate as an admin user.
    - Send a PATCH request for a non-existent movie ID with a valid payload.

    Expected result:
    - 404 Not Found
    - Response `detail` is: "Movie with the given ID was not found."
    """
    token = admin_token["token"]

    headers = {"Authorization": f"Bearer {token}"}

    non_existent_id = 99999
    update_data = {
        "name": "Non-existent Movie",
        "description": "Nice movie!"
    }

    response = await client.patch(
        f"/api/v1/cinema/movies/{non_existent_id}/",
        json=update_data,
        headers=headers
    )
    assert response.status_code == 404, f"Expected status code 404, but got {response.status_code}"

    response_data = response.json()
    expected_detail = "Movie with the given ID was not found."
    assert response_data["detail"] == expected_detail, (
        f"Expected detail message: {expected_detail}, but got: {response_data['detail']}"
    )
