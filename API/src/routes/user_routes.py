from fastapi import APIRouter
from src.models.user_model import UserPatch
from src.models.user_model import UserPost
from src.repository.user_repository import users

from src.conf.db import cursor

user_router = APIRouter()


@user_router.get("/users")
def get_all_users(limit: int = 100, offset: int = 0):
    return users[offset : offset + limit]


@user_router.post("/users")
def create_user(body: UserPost):
    new_user = body.model_dump()
    new_user["id"] = len(users) + 1
    users.append(new_user)
    return new_user


@user_router.patch("/users/{id}")
def patch_user_by_id(id: int, body: UserPatch):
    for user in users:
        if user["id"] == id:
            data = body.model_dump(exclude_unset=True)
            user.update(data)
            return user
    return "User not found"


@user_router.get("/users/{id}")
def get_user_by_id(id: int):
    for user in users:
        if user["id"] == id:
            return user
    return "User not found"


@user_router.delete("/users/{id}")
def delete_user_by_id(id: int):
    for user in users:
        if user["id"] == id:
            users.remove(user)
            return user
    return "User not found"