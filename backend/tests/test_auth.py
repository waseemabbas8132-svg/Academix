from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_login_accepts_demo_credentials() -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@academix.app", "password": "password123"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "teacher"
    assert response.json()["user"]["email"] == "teacher@academix.app"


def test_login_rejects_invalid_credentials() -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@academix.app", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_student_login_and_me_endpoint() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "student@academix.app", "password": "password123"},
    )

    assert login_response.status_code == 200
    token = login_response.json()["token"]
    assert token

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["role"] == "student"


def test_student_cannot_access_teacher_dashboard() -> None:
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "student@academix.app", "password": "password123"},
    )
    token = login_response.json()["token"]

    response = client.get(
        "/api/v1/teacher/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_local_flutter_web_origin_passes_cors_preflight() -> None:
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_untrusted_web_origin_fails_cors_preflight() -> None:
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
