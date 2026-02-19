"""Tests para los endpoints de usuario."""

import unittest

from fastapi.testclient import TestClient

from app.user.main import app
from app.user import routes as user_routes


class TestUser(unittest.TestCase):
    """Tests para los endpoints CRUD de ``/user``."""

    def setUp(self) -> None:
        """Inicializa el cliente de test y limpia la base de datos."""
        self.client = TestClient(app)
        user_routes.users_db.clear()
        user_routes.next_id = 1

    def test_create_user(self) -> None:
        """Verifica que ``POST /user`` crea un usuario."""
        response = self.client.post(
            "/user", json={"name": "Juan", "email": "juan@example.com"}
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["name"], "Juan")
        self.assertEqual(data["email"], "juan@example.com")
        self.assertIn("id", data)

    def test_get_user(self) -> None:
        """Verifica que ``GET /user/{id}`` devuelve el usuario correcto."""
        post_response = self.client.post(
            "/user", json={"name": "Maria", "email": "maria@example.com"}
        )
        user_id = post_response.json()["id"]

        response = self.client.get(f"/user/{user_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Maria")
        self.assertEqual(response.json()["email"], "maria@example.com")

    def test_get_user_not_found(self) -> None:
        """Verifica que ``GET /user/{id}`` devuelve 404 si no existe."""
        response = self.client.get("/user/99999")
        self.assertEqual(response.status_code, 404)

    def test_list_users(self) -> None:
        """Verifica que ``GET /user`` lista todos los usuarios."""
        response = self.client.get("/user")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

        self.client.post("/user", json={"name": "A", "email": "a@example.com"})
        self.client.post("/user", json={"name": "B", "email": "b@example.com"})

        response = self.client.get("/user")
        self.assertEqual(len(response.json()), 2)

    def test_put_user(self) -> None:
        """Verifica que ``PUT /user/{id}`` reemplaza el usuario."""
        post_response = self.client.post(
            "/user", json={"name": "Pedro", "email": "pedro@example.com"}
        )
        user_id = post_response.json()["id"]

        response = self.client.put(
            f"/user/{user_id}",
            json={"name": "Pedro Updated", "email": "pedro2@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Pedro Updated")
        self.assertEqual(response.json()["email"], "pedro2@example.com")

    def test_put_user_not_found(self) -> None:
        """Verifica que ``PUT /user/{id}`` devuelve 404 si no existe."""
        response = self.client.put(
            "/user/99999",
            json={"name": "Ghost", "email": "ghost@example.com"},
        )
        self.assertEqual(response.status_code, 404)

    def test_patch_user(self) -> None:
        """Verifica que ``PATCH /user/{id}`` actualiza parcialmente."""
        post_response = self.client.post(
            "/user", json={"name": "Ana", "email": "ana@example.com"}
        )
        user_id = post_response.json()["id"]

        response = self.client.patch(f"/user/{user_id}", json={"name": "Ana Updated"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Ana Updated")
        self.assertEqual(response.json()["email"], "ana@example.com")

    def test_patch_user_not_found(self) -> None:
        """Verifica que ``PATCH /user/{id}`` devuelve 404 si no existe."""
        response = self.client.patch("/user/99999", json={"name": "Ghost"})
        self.assertEqual(response.status_code, 404)

    def test_delete_user(self) -> None:
        """Verifica que ``DELETE /user/{id}`` elimina el usuario."""
        post_response = self.client.post(
            "/user",
            json={"name": "Delete Me", "email": "delete@example.com"},
        )
        user_id = post_response.json()["id"]

        response = self.client.delete(f"/user/{user_id}")
        self.assertEqual(response.status_code, 204)

        response = self.client.get(f"/user/{user_id}")
        self.assertEqual(response.status_code, 404)

    def test_delete_user_not_found(self) -> None:
        """Verifica que ``DELETE /user/{id}`` devuelve 404 si no existe."""
        response = self.client.delete("/user/99999")
        self.assertEqual(response.status_code, 404)
