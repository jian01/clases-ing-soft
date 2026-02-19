"""Microservicio de usuarios."""

from fastapi import FastAPI

from app.user.routes import router as user_router

app = FastAPI(title="API de usuarios")

app.include_router(user_router)
