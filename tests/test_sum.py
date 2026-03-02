"""Tests para los endpoints de suma."""

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


class TestSum(unittest.TestCase):
    """Tests para los endpoints ``/sum`` y ``/sum-square``."""

    def setUp(self) -> None:
        """Inicializa el cliente de test."""
        self.client = TestClient(app)

    def test_hello(self) -> None:
        """Verifica que ``GET /hello`` devuelve un saludo."""
        response = self.client.get("/hello")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Hola mundo!"})

    def test_sum(self) -> None:
        """Verifica que ``GET /sum`` suma correctamente."""
        response = self.client.get("/sum", params={"a": 3, "b": 4})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"result": 7})

    def test_sum_negative_numbers(self) -> None:
        """Verifica que ``GET /sum`` maneja numeros negativos."""
        response = self.client.get("/sum", params={"a": -5, "b": 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"result": -2})

    @patch("app.sum.routes.httpx.Client")
    def test_sum_square(self, mock_client_class: MagicMock) -> None:
        """Verifica que ``GET /sum-square`` devuelve el cuadrado de la suma.

        :param mock_client_class: Mock de ``httpx.Client``.
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": 5}
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        response = self.client.get("/sum-square", params={"a": 2, "b": 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"result": 25})
