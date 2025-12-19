import enum
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    String,
    Text,
    UniqueConstraint,
    ForeignKey,
    Table,
    Column,
    Integer,
    Enum,
    DateTime,
    func,
    Numeric,
)
from sqlalchemy.orm import mapped_column, Mapped, relationship

from cinema.database.models.base import Base


MoviesGenresModel = Table(
    "movies_genres",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    Column(
        "genre_id",
        ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True, nullable=False),
)

ActorsMoviesModel = Table(
    "actors_movies",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    Column(
        "actor_id",
        ForeignKey("actors.id", ondelete="CASCADE"), primary_key=True, nullable=False),
)

DirectorsMoviesModel = Table(
    "directors_movies",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    Column(
        "director_id",
        ForeignKey("directors.id", ondelete="CASCADE"), primary_key=True, nullable=False),
)

FavouritesMoviesModel = Table(
    "favourites_movies",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    Column(
        "favourite_id",
        ForeignKey("favourites.id", ondelete="CASCADE"), primary_key=True, nullable=False),
)


MoviesLanguagesModel = Table(
    "movies_languages",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("language_id", ForeignKey("languages.id", ondelete="CASCADE"), primary_key=True),
)


class CertificationEnum(str, enum.Enum):
    G = "G"
    PG = "PG"
    PG13 = "PG13"
    R = "R"
    NC17 = "NC17"


class RatingTypeEnum(str, enum.Enum):
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10


class ReactionTypeEnum(str, enum.Enum):
    LIKE = "like"
    DISLIKE = "dislike"


class GenreModel(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel",
        secondary=MoviesGenresModel,
        back_populates="genres"
    )

    def __repr__(self):
        return f"<Genre(name='{self.name}')>"


class ActorModel(Base):
    __tablename__ = "actors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel",
        secondary=ActorsMoviesModel,
        back_populates="actors"
    )

    def __repr__(self):
        return f"<Actor(name='{self.name}')>"


class DirectorModel(Base):
    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel",
        secondary=DirectorsMoviesModel,
        back_populates="directors"
    )

    def __repr__(self):
        return f"<Director(name='{self.name}')>"


class CountryModel(Base):
    __tablename__ = "countries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    movies: Mapped[list["MovieModel"]] = relationship("MovieModel", back_populates="country")

    def __repr__(self):
        return f"<Country(code='{self.code}', name='{self.name}')>"


class LanguageModel(Base):
    __tablename__ = "languages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel",
        secondary=MoviesLanguagesModel,
        back_populates="languages"
    )

    def __repr__(self):
        return f"<Language(name='{self.name}')>"


class CommentModel(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="comments")
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    movie: Mapped["MovieModel"] = relationship("MovieModel", back_populates="comments")
    created_at = mapped_column(DateTime, default=func.now())
    updated_at = mapped_column(DateTime, default=func.now())

    def __repr__(self):
        return f"<Comment(comment='{self.comment}')>"


class FavouriteModel(Base):
    __tablename__ = "favourites"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="favourites")
    movies: Mapped[list["MovieModel"]] = relationship(
        "MovieModel",
        secondary=FavouritesMoviesModel,
        back_populates="favourites"
    )

    @classmethod
    def default_order_by(cls):
        return [cls.id.desc()]

    def __repr__(self):
        return f"<Favourite id={self.id}, user={self.user_id})>"


class RatingModel(Base):
    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="ratings")
    rating: Mapped["RatingTypeEnum"] = mapped_column(
        Enum(RatingTypeEnum),
        nullable=False
    )
    created_at = mapped_column(DateTime, default=func.now())
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    movie: Mapped["MovieModel"] = relationship("MovieModel", back_populates="ratings")

    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="unique_user_movie_rating"),
    )

    def __repr__(self):
        return f"<User id={self.user_id} gave movie={self.movie_id} {self.rating}/10>"


class MovieReactionModel(Base):
    __tablename__ = "movie_reactions"

    id = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(ForeignKey("users.id"), nullable=False)
    movie_id = mapped_column(ForeignKey("movies.id"), nullable=False)

    reaction: Mapped["ReactionTypeEnum"] = mapped_column(
        Enum(ReactionTypeEnum),
        nullable=False
    )

    created_at = mapped_column(DateTime, default=func.now())

    user: Mapped["UserModel"] = relationship(back_populates="reactions")
    movie: Mapped["MovieModel"] = relationship(back_populates="reactions")

    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="unique_user_movie_reaction"),
    )


class MovieModel(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    imdb: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    imdb_votes: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    budget: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    country_id: Mapped[int] = mapped_column(ForeignKey("countries.id"), nullable=False)
    country: Mapped["CountryModel"] = relationship("CountryModel", back_populates="movies")
    certification: Mapped[CertificationEnum] = mapped_column(Enum(CertificationEnum), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    genres: Mapped[list["GenreModel"]] = relationship(
        "GenreModel",
        secondary=MoviesGenresModel,
        back_populates="movies"
    )

    actors: Mapped[list["ActorModel"]] = relationship(
        "ActorModel",
        secondary=ActorsMoviesModel,
        back_populates="movies"
    )

    directors: Mapped[list["DirectorModel"]] = relationship(
        "DirectorModel",
        secondary=DirectorsMoviesModel,
        back_populates="movies"
    )

    languages: Mapped[list["LanguageModel"]] = relationship(
        "LanguageModel",
        secondary=MoviesLanguagesModel,
        back_populates="movies"
    )
    comments: Mapped[list["CommentModel"]] = relationship("CommentModel", back_populates="movie")
    reactions: Mapped[list["MovieReactionModel"]] = relationship("MovieReactionModel", back_populates="movie")
    favourites: Mapped[list["FavouriteModel"]] = relationship(
        "FavouriteModel",
        secondary=FavouritesMoviesModel,
        back_populates="movies"
    )
    ratings: Mapped[list["RatingModel"]] = relationship(
        "RatingModel",
        back_populates="movie"
    )

    __table_args__ = (
        UniqueConstraint("name", "year", "duration", name="unique_movie_constraint"),
    )

    @classmethod
    def default_order_by(cls):
        return [cls.id.desc()]

    def __repr__(self):
        return f"<Movie(name='{self.name}', year='{self.year}', imdb={self.imdb})>"
