from fastapi import FastAPI

from cinema.routes import (
    movie_router,
    accounts_router,
    profiles_router,
    movies_comments_router,
    movies_favourites_router,
    movies_ratings_router,
    movies_reactions_router
)

app = FastAPI()

api_version_prefix = "/api/v1"

app.include_router(accounts_router, prefix=f"{api_version_prefix}/accounts", tags=["accounts"])
app.include_router(profiles_router, prefix=f"{api_version_prefix}/profiles", tags=["profiles"])
app.include_router(movie_router, prefix=f"{api_version_prefix}/cinema", tags=["cinema"])
app.include_router(movies_comments_router, prefix=f"{api_version_prefix}/cinema", tags=["comments"])
app.include_router(movies_favourites_router, prefix=f"{api_version_prefix}/accounts", tags=["favourites"])
app.include_router(movies_ratings_router, prefix=f"{api_version_prefix}/cinema", tags=["cinema"])
app.include_router(movies_reactions_router, prefix=f"{api_version_prefix}/cinema", tags=["cinema"])
