import aioboto3
import pytest_asyncio
from botocore.exceptions import ClientError
from httpx import AsyncClient, ASGITransport
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from cinema.config.dependencies import get_accounts_email_notificator, get_s3_storage_client
from cinema.config.settings import get_settings
from cinema.database.models.accounts import UserGroupModel, UserGroupEnum, UserModel

from cinema.database import reset_database, get_db_contextmanager
from cinema.database.populate import CSVDatabaseSeeder
from cinema.main import app
from cinema.security.interfaces import JWTAuthManagerInterface
from cinema.security.token_manager import JWTAuthManager
from cinema.storages.s3 import S3StorageClient
from cinema.tests.doubles.fakes.storage import FakeS3Storage
from cinema.tests.doubles.stubs.emails import StubEmailSender


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests"
    )
    config.addinivalue_line(
        "markers", "order: Specify the order of test execution"
    )
    config.addinivalue_line(
        "markers", "unit: Unit tests"
    )


@pytest_asyncio.fixture(scope="function", autouse=True)
async def reset_db(request):
    """
    Reset the SQLite database before each test function, except for tests marked with 'e2e'.

    By default, this fixture ensures that the database is cleared and recreated before every
    test function to maintain test isolation. However, if the test is marked with 'e2e',
    the database reset is skipped to allow preserving state between end-to-end tests.
    """
    if "e2e" in request.keywords:
        yield
    else:
        await reset_database()
        yield


@pytest_asyncio.fixture(scope="session")
async def reset_db_once_for_e2e(request):
    """
    Reset the database once for end-to-end tests.

    This fixture is intended to be used for end-to-end tests at the session scope,
    ensuring the database is reset before running E2E tests.
    """
    await reset_database()


@pytest_asyncio.fixture(scope="session")
async def settings():
    """
    Provide application settings.

    This fixture returns the application settings by calling get_settings().
    """
    return get_settings()


@pytest_asyncio.fixture(scope="function")
async def email_sender_stub():
    """
    Provide a stub implementation of the email sender.

    This fixture returns an instance of StubEmailSender for testing purposes.
    """
    return StubEmailSender()


@pytest_asyncio.fixture(scope="function")
async def s3_storage_fake():
    """
    Provide a fake S3 storage client.

    This fixture returns an instance of FakeS3Storage for testing purposes.
    """
    return FakeS3Storage()


@pytest_asyncio.fixture(scope="session")
async def s3_client(settings):
    """
    Provide an S3 storage client.

    This fixture returns an instance of S3StorageClient configured with the application settings.
    """
    return S3StorageClient(
        endpoint_url=settings.S3_STORAGE_ENDPOINT,
        access_key=settings.S3_STORAGE_ACCESS_KEY,
        secret_key=settings.S3_STORAGE_SECRET_KEY,
        bucket_name=settings.S3_BUCKET_NAME
    )


@pytest_asyncio.fixture(scope="function")
async def client(email_sender_stub, s3_storage_fake):
    """
    Provide an asynchronous HTTP client for testing.

    Overrides the dependencies for email sender and S3 storage with test doubles.
    """
    app.dependency_overrides[get_accounts_email_notificator] = lambda: email_sender_stub
    app.dependency_overrides[get_s3_storage_client] = lambda: s3_storage_fake

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="session")
async def e2e_client():
    """
    Provide an asynchronous HTTP client for end-to-end tests.

    This client is available at the session scope.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as async_client:
        yield async_client


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Provide an async database session for database interactions.

    This fixture yields an async session using `get_db_contextmanager`, ensuring that the session
    is properly closed after each test.
    """
    async with get_db_contextmanager() as session:
        yield session


@pytest_asyncio.fixture(scope="session")
async def e2e_db_session():
    """
    Provide an async database session for end-to-end tests.

    This fixture yields an async session using `get_db_contextmanager` at the session scope,
    ensuring that the same session is used throughout the E2E test suite.
    Note: Using a session-scoped DB session in async tests may lead to shared state between tests,
    so use this fixture with caution if tests run concurrently.
    """
    async with get_db_contextmanager() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def jwt_manager() -> JWTAuthManagerInterface:
    """
    Asynchronous fixture to create a JWT authentication manager instance.

    This fixture retrieves the application settings via `get_settings()` and uses them to
    instantiate a `JWTAuthManager`. The manager is configured with the secret keys for
    access and refresh tokens, as well as the JWT signing algorithm specified in the settings.

    Returns:
        JWTAuthManagerInterface: An instance of JWTAuthManager configured with the appropriate
        secret keys and algorithm.
    """
    settings = get_settings()
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM
    )


@pytest_asyncio.fixture(scope="function")
async def seed_user_groups(db_session: AsyncSession):
    """
    Asynchronously seed the UserGroupModel table with default user groups.

    This fixture inserts all user groups defined in UserGroupEnum into the database and commits the transaction.
    It then yields the asynchronous database session for further testing.
    """
    groups = [{"name": group.value} for group in UserGroupEnum]
    await db_session.execute(insert(UserGroupModel).values(groups))
    await db_session.commit()
    yield db_session


@pytest_asyncio.fixture(scope="function")
async def seed_database(db_session):
    """
    Seed the database with test data if it is empty.

    This fixture initializes a `CSVDatabaseSeeder` and ensures the test database is populated before
    running tests that require existing data.

    :param db_session: The async database session fixture.
    :type db_session: AsyncSession
    """
    settings = get_settings()
    seeder = CSVDatabaseSeeder(csv_file_path=settings.PATH_TO_MOVIES_CSV, db_session=db_session)

    if not await seeder.is_db_populated():
        await seeder.seed()

    yield db_session


@pytest_asyncio.fixture(scope="session", autouse=True)
async def ensure_minio_bucket(settings):
    """
    Ensure MinIO bucket exists before any tests run.

    This prevents NoSuchBucket errors when uploading files
    during E2E and integration tests.
    """
    session = aioboto3.Session()

    async with session.client(
        "s3",
        endpoint_url=settings.S3_STORAGE_ENDPOINT,
        aws_access_key_id=settings.S3_STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.S3_STORAGE_SECRET_KEY,
    ) as s3:
        bucket_name = settings.S3_BUCKET_NAME

        try:
            await s3.head_bucket(Bucket=bucket_name)
        except ClientError:
            await s3.create_bucket(Bucket=bucket_name)


@pytest_asyncio.fixture
async def admin_token(db_session, client, seed_user_groups):
    """
    Create and authenticate an active admin user for tests.

    Steps:
    - Ensure the ADMIN user group exists in the database.
    - Create a new admin user with a predefined email and password.
    - Mark the admin user as active and persist it to the database.
    - Authenticate the admin user via the login endpoint.
    - Extract and return the access token along with the admin user instance.

    Returns:
        dict: A dictionary containing:
            - "admin": the created admin UserModel instance
            - "token": JWT access token for authenticated admin requests
    """
    admin_payload = {
        "email": "admin@email.com",
        "password": "AdminPassword123@@",
    }

    stmt = select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.ADMIN)
    result = await db_session.execute(stmt)
    admin_group = result.scalars().first()
    assert admin_group is not None, "Default admin group should exist."

    admin = UserModel.create(
        email=admin_payload["email"],
        raw_password=admin_payload["password"],
        group_id=admin_group.id
    )
    admin.is_active = True
    db_session.add(admin)
    await db_session.commit()

    login_payload = {
        "email": admin_payload["email"],
        "password": admin_payload["password"],
    }

    login_response = await client.post("/api/v1/accounts/login/", json=login_payload)
    assert login_response.status_code == 201, "Expected status code 201 for successful login."
    login_data = login_response.json()
    token = login_data["access_token"]
    assert token, "Access token must be present in login response"

    return {"admin": admin, "token": token}


@pytest_asyncio.fixture
async def user_token(db_session, client, seed_user_groups):
    """
    Create and authenticate an active regular user for tests.

    Steps:
    - Ensure the user group exists in the database.
    - Create a new user with a predefined email and password.
    - Mark the user as active and persist it to the database.
    - Authenticate the user via the login endpoint.
    - Extract and return access and refresh tokens along with user metadata.

    Returns:
        dict: A dictionary containing:
            - "user": the created UserModel instance
            - "user_id": ID of the created user
            - "email": user's email
            - "raw_password": user's plaintext password (for test reuse)
            - "token": JWT access token
            - "refresh_token": JWT refresh token
    """
    user_payload = {
        "email": "user@email.com",
        "password": "UserPassword123@@",
    }

    stmt = select(UserGroupModel).where(UserGroupModel.name == UserGroupEnum.USER)
    result = await db_session.execute(stmt)
    user_group = result.scalars().first()
    assert user_group is not None, "Default user group should exist."

    user = UserModel.create(
        email=user_payload["email"],
        raw_password=user_payload["password"],
        group_id=user_group.id
    )
    user.is_active = True
    db_session.add(user)
    await db_session.commit()

    login_payload = {
        "email": user_payload["email"],
        "password": user_payload["password"],
    }

    login_response = await client.post("/api/v1/accounts/login/", json=login_payload)
    assert login_response.status_code == 201, "Expected status code 201 for successful login."
    login_data = login_response.json()
    token = login_data["access_token"]
    refresh_token = login_data["refresh_token"]
    assert token, "Access token must be present in login response"

    return {
        "user": user,
        "user_id": user.id,
        "email": user_payload["email"],
        "raw_password": user_payload["password"],
        "token": token,
        "refresh_token": refresh_token,
    }
