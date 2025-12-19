from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Literal

from pydantic import BaseModel, Field, field_validator
from cinema.database.models.movies import CertificationEnum, ReactionTypeEnum, RatingTypeEnum


# -------------------------
# Base schemas
# -------------------------

class LanguageSchema(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class CountrySchema(BaseModel):
    id: int
    code: str
    name: Optional[str] = None
    model_config = {"from_attributes": True}


class GenreSchema(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class ActorSchema(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class DirectorSchema(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


# -------------------------
# Comments
# -------------------------

class CommentBaseSchema(BaseModel):
    movie_id: int
    user_id: int
    comment: Optional[str] = Field(None, min_length=1, max_length=1000)

    model_config = {"from_attributes": True}


class CommentCreateSchema(BaseModel):
    comment: Optional[str] = Field(None, min_length=1, max_length=1000)

    model_config = {"extra": "forbid"}


class CommentReadSchema(BaseModel):
    id: int
    movie_id: int
    user_id: int
    comment: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentCreateResponseSchema(CommentReadSchema):
    pass


class CommentUpdateSchema(BaseModel):
    comment: str = Field(..., min_length=1, max_length=1000)
    model_config = {"extra": "forbid"}


class CommentUpdateResponseSchema(CommentReadSchema):
    updated_at: datetime


# -------------------------
# Reactions
# -------------------------

class MovieReactionBaseSchema(BaseModel):
    movie_id: int
    user_id: int
    reaction: ReactionTypeEnum

    model_config = {"from_attributes": True}


class MovieReactionRequestSchema(BaseModel):
    reaction: ReactionTypeEnum
    model_config = {"extra": "forbid"}


class MovieReactionResponseSchema(BaseModel):
    movie_id: int
    user_id: int
    reaction: Optional[ReactionTypeEnum] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}
    detail: str


# -------------------------
# Ratings
# -------------------------

class RatingBaseSchema(BaseModel):
    movie_id: int
    user_id: int
    rating: RatingTypeEnum

    model_config = {"from_attributes": True}


class RatingRequestSchema(BaseModel):
    rating: RatingTypeEnum
    model_config = {"extra": "forbid"}


class RatingResponseSchema(BaseModel):
    movie_id: int
    user_id: int
    rating: Optional[RatingTypeEnum] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}
    detail: str


# -------------------------
# Movies
# -------------------------

class MovieBaseSchema(BaseModel):
    uuid: str
    name: str = Field(..., max_length=255)
    year: int
    duration: int
    imdb: Decimal = Field(..., ge=0, le=10)
    imdb_votes: int
    description: str
    budget: Decimal = Field(..., ge=0)
    revenue: Decimal = Field(..., ge=0)
    certification: CertificationEnum
    price: Decimal = Field(..., ge=0)

    model_config = {"from_attributes": True}

    @field_validator("year")
    @classmethod
    def validate_year(cls, value: int) -> int:
        current_year = datetime.now().year
        if value > current_year + 1:
            raise ValueError(f"year cannot be greater than {current_year + 1}.")
        return value


class MovieDetailSchema(MovieBaseSchema):
    id: int
    country: CountrySchema
    genres: List[GenreSchema]
    actors: List[ActorSchema]
    directors: List[DirectorSchema]
    languages: List[LanguageSchema]
    comments: List[CommentCreateResponseSchema] = Field(default_factory=list)
    reactions: List[MovieReactionResponseSchema] = Field(default_factory=list)
    ratings: List[RatingResponseSchema] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class MovieListItemSchema(BaseModel):
    id: int
    name: str
    year: int
    imdb: Decimal
    description: str

    model_config = {"from_attributes": True}


class MovieListResponseSchema(BaseModel):
    movies: List[MovieListItemSchema]
    prev_page: Optional[str] = None
    next_page: Optional[str] = None
    total_pages: int
    total_items: int

    model_config = {"from_attributes": True}


class MovieCreateSchema(MovieBaseSchema):
    country: str
    genres: List[str]
    actors: List[str]
    directors: List[str]
    languages: List[str]

    model_config = {"extra": "forbid"}

    @field_validator("country", mode="before")
    @classmethod
    def normalize_country(cls, value):
        if value is None:
            return value
        return str(value).strip().upper()

    @field_validator("genres", "actors", "directors", "languages", mode="before")
    @classmethod
    def normalize_list_fields(cls, value):
        if value is None:
            return []
        return [str(item).strip().title() for item in value]


class MovieUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    year: Optional[int] = None
    description: Optional[str] = None
    budget: Optional[Decimal] = Field(None, ge=0)
    revenue: Optional[Decimal] = Field(None, ge=0)

    model_config = {"extra": "forbid"}


# -------------------------
# Genres
# -------------------------

class GenreListItemSchema(BaseModel):
    id: int
    name: str
    movies_count: int

    model_config = {"from_attributes": True}


class GenreDetailSchema(BaseModel):
    id: int
    name: str
    movies: List[MovieBaseSchema]

    model_config = {"from_attributes": True}


class GenreListResponseSchema(BaseModel):
    genres: List[GenreListItemSchema]
    prev_page: Optional[str] = None
    next_page: Optional[str] = None
    total_pages: int
    total_items: int

    model_config = {"from_attributes": True}


# -------------------------
# Favourites
# -------------------------

class FavouriteListResponseSchema(BaseModel):
    movies: List[MovieBaseSchema]

    model_config = {"from_attributes": True}


# -------------------------
# Query params
# -------------------------

class MovieQueryParamsSchema(BaseModel):
    search: Optional[str] = None
    year: Optional[int] = None
    imdb: Optional[Decimal] = None
    sort_by: Literal["name", "price", "budget", "duration"] = "name"
    sort_order: Literal["asc", "desc"] = "asc"

    model_config = {"extra": "forbid"}
