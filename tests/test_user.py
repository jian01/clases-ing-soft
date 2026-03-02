"""Tests para los endpoints de usuario."""

import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.user import routes as user_routes


class TestUser(unittest.TestCase):
    """Tests para los endpoints CRUD de ``/user``."""

    def setUp(self) -> None:
        """Inicializa el cliente de test y limpia la base de datos."""
        self.client = TestClient(app)
        user_routes.users_db.clear()

    def test_create_user(self) -> None:
        """Verifica que ``POST /user`` crea un usuario."""
        response = self.client.post(
            "/user",
            json={
                "username": "juan01",
                "name": "Juan",
                "email": "juan@example.com",
                "dni": 12345678,
            },
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["username"], "juan01")
        self.assertEqual(data["name"], "Juan")
        self.assertEqual(data["email"], "juan@example.com")
        self.assertEqual(data["dni"], 12345678)

    def test_create_user_duplicate_username(self) -> None:
        """Verifica que ``POST /user`` devuelve 409 si el username ya existe."""
        self.client.post(
            "/user",
            json={
                "username": "juan01",
                "name": "Juan",
                "email": "juan@example.com",
                "dni": 12345678,
            },
        )
        response = self.client.post(
            "/user",
            json={
                "username": "juan01",
                "name": "Otro",
                "email": "otro@example.com",
                "dni": 99999999,
            },
        )
        self.assertEqual(response.status_code, 409)

    def test_get_user(self) -> None:
        """Verifica que ``GET /user/{username}`` devuelve el usuario correcto."""
        self.client.post(
            "/user",
            json={
                "username": "maria01",
                "name": "Maria",
                "email": "maria@example.com",
                "dni": 22334455,
            },
        )

        response = self.client.get("/user/maria01")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "maria01")
        self.assertEqual(response.json()["name"], "Maria")
        self.assertEqual(response.json()["email"], "maria@example.com")
        self.assertEqual(response.json()["dni"], 22334455)

    def test_get_user_not_found(self) -> None:
        """Verifica que ``GET /user/{username}`` devuelve 404 si no existe."""
        response = self.client.get("/user/noexiste")
        self.assertEqual(response.status_code, 404)

    def test_list_users(self) -> None:
        """Verifica que ``GET /user`` lista todos los usuarios."""
        response = self.client.get("/user")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

        self.client.post(
            "/user",
            json={
                "username": "user_a",
                "name": "A",
                "email": "a@example.com",
                "dni": 11111111,
            },
        )
        self.client.post(
            "/user",
            json={
                "username": "user_b",
                "name": "B",
                "email": "b@example.com",
                "dni": 22222222,
            },
        )

        response = self.client.get("/user")
        self.assertEqual(len(response.json()), 2)

    def test_put_user(self) -> None:
        """Verifica que ``PUT /user/{username}`` reemplaza el usuario."""
        self.client.post(
            "/user",
            json={
                "username": "pedro01",
                "name": "Pedro",
                "email": "pedro@example.com",
                "dni": 33333333,
            },
        )

        response = self.client.put(
            "/user/pedro01",
            json={
                "username": "pedro01",
                "name": "Pedro Updated",
                "email": "pedro2@example.com",
                "dni": 44444444,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Pedro Updated")
        self.assertEqual(response.json()["email"], "pedro2@example.com")
        self.assertEqual(response.json()["dni"], 44444444)

    def test_put_user_not_found(self) -> None:
        """Verifica que ``PUT /user/{username}`` devuelve 404 si no existe."""
        response = self.client.put(
            "/user/noexiste",
            json={
                "username": "noexiste",
                "name": "Ghost",
                "email": "ghost@example.com",
                "dni": 99999999,
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_patch_user(self) -> None:
        """Verifica que ``PATCH /user/{username}`` actualiza parcialmente."""
        self.client.post(
            "/user",
            json={
                "username": "ana01",
                "name": "Ana",
                "email": "ana@example.com",
                "dni": 55555555,
            },
        )

        response = self.client.patch("/user/ana01", json={"name": "Ana Updated"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Ana Updated")
        self.assertEqual(response.json()["email"], "ana@example.com")
        self.assertEqual(response.json()["dni"], 55555555)

    def test_patch_user_dni(self) -> None:
        """Verifica que ``PATCH /user/{username}`` actualiza el DNI."""
        self.client.post(
            "/user",
            json={
                "username": "luis01",
                "name": "Luis",
                "email": "luis@example.com",
                "dni": 66666666,
            },
        )

        response = self.client.patch("/user/luis01", json={"dni": 77777777})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["dni"], 77777777)
        self.assertEqual(response.json()["name"], "Luis")

    def test_patch_user_not_found(self) -> None:
        """Verifica que ``PATCH /user/{username}`` devuelve 404 si no existe."""
        response = self.client.patch("/user/noexiste", json={"name": "Ghost"})
        self.assertEqual(response.status_code, 404)

    def test_delete_user(self) -> None:
        """Verifica que ``DELETE /user/{username}`` elimina el usuario."""
        self.client.post(
            "/user",
            json={
                "username": "todelete",
                "name": "Delete Me",
                "email": "delete@example.com",
                "dni": 88888888,
            },
        )

        response = self.client.delete("/user/todelete")
        self.assertEqual(response.status_code, 204)

        response = self.client.get("/user/todelete")
        self.assertEqual(response.status_code, 404)

    def test_delete_user_not_found(self) -> None:
        """Verifica que ``DELETE /user/{username}`` devuelve 404 si no existe."""
        response = self.client.delete("/user/noexiste")
        self.assertEqual(response.status_code, 404)
