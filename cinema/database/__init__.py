import os

from cinema.database.models.base import Base
from cinema.database.models.accounts import (
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
    UserProfileModel
)
from cinema.database.models.movies import (
    MovieModel,
    LanguageModel,
    ActorModel,
    GenreModel,
    CountryModel,
    MoviesGenresModel,
    ActorsMoviesModel,
    MoviesLanguagesModel
)
from cinema.database.session_sqlite import reset_sqlite_database as reset_database
from cinema.database.validators import accounts as accounts_validators

environment = os.getenv("ENVIRONMENT", "developing")

if environment == "testing":
    from cinema.database.session_sqlite import (
        get_sqlite_db_contextmanager as get_db_contextmanager,
        get_sqlite_db as get_db
    )
else:
    from cinema.database.session_postgresql import (
        get_postgresql_db_contextmanager as get_db_contextmanager,
        get_postgresql_db as get_db
    )
