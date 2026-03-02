"""Rutas CRUD para el recurso usuario."""

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

users_db: Dict[str, Dict] = {}


class UserCreate(BaseModel):
    """Esquema para la creacion de un usuario.

    :param username: Nombre de usuario (identificador unico).
    :param name: Nombre del usuario.
    :param email: Email del usuario.
    :param dni: DNI del usuario.
    """

    username: str
    name: str
    email: str
    dni: int


class UserUpdate(BaseModel):
    """Esquema para la actualizacion parcial de un usuario.

    :param name: Nombre del usuario (opcional).
    :param email: Email del usuario (opcional).
    :param dni: DNI del usuario (opcional).
    """

    name: Optional[str] = None
    email: Optional[str] = None
    dni: Optional[int] = None


@router.get("/user")
def list_users() -> List[Dict]:
    """Lista todos los usuarios.

    :return: Lista de usuarios.
    """
    return list(users_db.values())


@router.post("/user", status_code=201)
def create_user(user: UserCreate) -> Dict:
    """Crea un nuevo usuario.

    :param user: Datos del usuario a crear.
    :return: Usuario creado.
    :raises HTTPException: Si el username ya existe (409).
    """
    if user.username in users_db:
        raise HTTPException(status_code=409, detail="Username already exists")
    user_data = {
        "username": user.username,
        "name": user.name,
        "email": user.email,
        "dni": user.dni,
    }
    users_db[user.username] = user_data
    return user_data


@router.get("/user/{username}")
def get_user(username: str) -> Dict:
    """Obtiene un usuario por su username.

    :param username: Nombre de usuario.
    :return: Datos del usuario.
    :raises HTTPException: Si el usuario no existe (404).
    """
    if username not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return users_db[username]


@router.put("/user/{username}")
def replace_user(username: str, user: UserCreate) -> Dict:
    """Reemplaza completamente un usuario.

    :param username: Nombre de usuario a reemplazar.
    :param user: Nuevos datos del usuario.
    :return: Usuario actualizado.
    :raises HTTPException: Si el usuario no existe (404).
    """
    if username not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    user_data = {
        "username": username,
        "name": user.name,
        "email": user.email,
        "dni": user.dni,
    }
    users_db[username] = user_data
    return user_data


@router.patch("/user/{username}")
def update_user(username: str, user: UserUpdate) -> Dict:
    """Actualiza parcialmente un usuario.

    :param username: Nombre de usuario a actualizar.
    :param user: Campos a actualizar.
    :return: Usuario actualizado.
    :raises HTTPException: Si el usuario no existe (404).
    """
    if username not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    if user.name is not None:
        users_db[username]["name"] = user.name
    if user.email is not None:
        users_db[username]["email"] = user.email
    if user.dni is not None:
        users_db[username]["dni"] = user.dni
    return users_db[username]


@router.delete("/user/{username}", status_code=204)
def delete_user(username: str) -> None:
    """Elimina un usuario.

    :param username: Nombre de usuario a eliminar.
    :raises HTTPException: Si el usuario no existe (404).
    """
    if username not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    del users_db[username]
