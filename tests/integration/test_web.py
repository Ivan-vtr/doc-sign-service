"""Integration tests for web UI views."""

import uuid

import pytest
from django.contrib.auth.models import User
from django.test import Client

from app.infrastructure.persistence.models import UserProfile


@pytest.fixture
def web_client():
    return Client()


@pytest.fixture
def auth_web_client(web_client, user):
    web_client.login(username="testuser", password="testpass123")
    return web_client


# ── Auth Tests ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestWebLogin:
    def test_login_page_renders(self, web_client):
        response = web_client.get("/login/")
        assert response.status_code == 200
        assert "Вход".encode() in response.content

    def test_login_success_redirects(self, web_client, user):
        response = web_client.post("/login/", {
            "username": "testuser",
            "password": "testpass123",
        })
        assert response.status_code == 302
        assert response.url == "/"

    def test_login_invalid_credentials(self, web_client, user):
        response = web_client.post("/login/", {
            "username": "testuser",
            "password": "wrongpass",
        })
        assert response.status_code == 200
        assert "Неверное".encode() in response.content

    def test_login_redirects_authenticated_user(self, auth_web_client):
        response = auth_web_client.get("/login/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_login_respects_next_param(self, web_client, user):
        response = web_client.post("/login/?next=/upload/", {
            "username": "testuser",
            "password": "testpass123",
        })
        assert response.status_code == 302
        assert response.url == "/upload/"


@pytest.mark.django_db
class TestWebRegister:
    def test_register_page_renders(self, web_client):
        response = web_client.get("/register/")
        assert response.status_code == 200
        assert "Регистрация".encode() in response.content

    def test_register_individual_success(self, web_client):
        response = web_client.post("/register/", {
            "username": "newuser",
            "password": "securepass123",
            "email": "new@example.com",
            "iin": "123456789012",
            "full_name": "New User",
            "signer_type": "individual",
        })
        assert response.status_code == 302
        assert response.url == "/"
        assert User.objects.filter(username="newuser").exists()
        profile = User.objects.get(username="newuser").profile
        assert profile.iin == "123456789012"
        assert profile.signer_type == "individual"

    def test_register_legal_entity_success(self, web_client):
        response = web_client.post("/register/", {
            "username": "company",
            "password": "securepass123",
            "iin": "123456789012",
            "full_name": "Company Rep",
            "signer_type": "legal_entity",
            "bin": "111222333444",
            "company_name": "Test LLP",
        })
        assert response.status_code == 302
        profile = User.objects.get(username="company").profile
        assert profile.signer_type == "legal_entity"
        assert profile.bin == "111222333444"

    def test_register_legal_entity_missing_bin(self, web_client):
        response = web_client.post("/register/", {
            "username": "company2",
            "password": "securepass123",
            "iin": "123456789012",
            "full_name": "Company Rep",
            "signer_type": "legal_entity",
        })
        assert response.status_code == 200
        assert not User.objects.filter(username="company2").exists()

    def test_register_duplicate_username(self, web_client, user):
        response = web_client.post("/register/", {
            "username": "testuser",
            "password": "securepass123",
            "iin": "123456789012",
            "full_name": "Duplicate",
            "signer_type": "individual",
        })
        assert response.status_code == 200
        assert "уже занято".encode() in response.content

    def test_register_invalid_iin(self, web_client):
        response = web_client.post("/register/", {
            "username": "badiin",
            "password": "securepass123",
            "iin": "12345",
            "full_name": "Bad IIN",
            "signer_type": "individual",
        })
        assert response.status_code == 200
        assert not User.objects.filter(username="badiin").exists()

    def test_register_short_password(self, web_client):
        response = web_client.post("/register/", {
            "username": "shortpass",
            "password": "abc",
            "iin": "123456789012",
            "full_name": "Short Pass",
            "signer_type": "individual",
        })
        assert response.status_code == 200
        assert not User.objects.filter(username="shortpass").exists()

    def test_register_redirects_authenticated_user(self, auth_web_client):
        response = auth_web_client.get("/register/")
        assert response.status_code == 302


@pytest.mark.django_db
class TestWebLogout:
    def test_logout_redirects(self, auth_web_client):
        response = auth_web_client.post("/logout/")
        assert response.status_code == 302
        assert response.url == "/login/"

    def test_logout_clears_session(self, auth_web_client):
        auth_web_client.post("/logout/")
        response = auth_web_client.get("/")
        assert response.status_code == 302
        assert "/login/" in response.url


# ── Dashboard Tests ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestWebDashboard:
    def test_dashboard_requires_auth(self, web_client):
        response = web_client.get("/")
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_dashboard_renders(self, auth_web_client):
        response = auth_web_client.get("/")
        assert response.status_code == 200
        assert "Мои документы".encode() in response.content

    def test_dashboard_shows_empty_state(self, auth_web_client):
        response = auth_web_client.get("/")
        assert "Документов пока нет".encode() in response.content


# ── Upload Tests ─────────────────────────────────────────────────────


@pytest.mark.django_db
class TestWebUpload:
    def test_upload_requires_auth(self, web_client):
        response = web_client.get("/upload/")
        assert response.status_code == 302

    def test_upload_page_renders(self, auth_web_client):
        response = auth_web_client.get("/upload/")
        assert response.status_code == 200
        assert "Загрузка документов".encode() in response.content
        assert b"drop-zone" in response.content


# ── Document Detail Tests ────────────────────────────────────────────


@pytest.mark.django_db
class TestWebDocumentDetail:
    def test_document_detail_requires_auth(self, web_client):
        doc_id = uuid.uuid4()
        response = web_client.get(f"/documents/{doc_id}/")
        assert response.status_code == 302

    def test_document_detail_not_found_redirects(self, auth_web_client):
        doc_id = uuid.uuid4()
        response = auth_web_client.get(f"/documents/{doc_id}/")
        assert response.status_code == 302


# ── Signing Tests ────────────────────────────────────────────────────


@pytest.mark.django_db
class TestWebSigning:
    def test_signing_requires_auth(self, web_client):
        doc_id = uuid.uuid4()
        response = web_client.get(f"/documents/{doc_id}/sign/")
        assert response.status_code == 302

    def test_signing_not_found_redirects(self, auth_web_client):
        doc_id = uuid.uuid4()
        response = auth_web_client.get(f"/documents/{doc_id}/sign/")
        assert response.status_code == 302


# ── Package Tests ────────────────────────────────────────────────────


@pytest.mark.django_db
class TestWebPackages:
    def test_packages_requires_auth(self, web_client):
        response = web_client.get("/packages/")
        assert response.status_code == 302

    def test_packages_page_renders(self, auth_web_client):
        response = auth_web_client.get("/packages/")
        assert response.status_code == 200
        assert "Пакеты".encode() in response.content

    def test_create_package(self, auth_web_client):
        response = auth_web_client.post("/packages/", {
            "title": "Test Package",
            "description": "Test description",
        })
        assert response.status_code == 302
        assert response.url == "/packages/"

    def test_create_package_missing_title(self, auth_web_client):
        response = auth_web_client.post("/packages/", {
            "title": "",
            "description": "No title",
        })
        assert response.status_code == 200

    def test_package_detail_not_found_redirects(self, auth_web_client):
        pkg_id = uuid.uuid4()
        response = auth_web_client.get(f"/packages/{pkg_id}/")
        assert response.status_code == 302

    def test_package_signing_not_found_redirects(self, auth_web_client):
        pkg_id = uuid.uuid4()
        response = auth_web_client.get(f"/packages/{pkg_id}/sign/")
        assert response.status_code == 302
