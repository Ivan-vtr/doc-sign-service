import pytest
from django.contrib.auth.models import User

from app.infrastructure.persistence.models import UserProfile


@pytest.fixture
def user(db):
    u = User.objects.create_user(username="testuser", password="testpass123")
    UserProfile.objects.create(
        user=u,
        iin="123456789012",
        full_name="Test User",
        signer_type="individual",
    )
    return u


@pytest.fixture
def legal_user(db):
    u = User.objects.create_user(username="legaluser", password="testpass123")
    UserProfile.objects.create(
        user=u,
        iin="987654321098",
        full_name="Legal User",
        signer_type="legal_entity",
        bin="111222333444",
        company_name="Test Company LLP",
    )
    return u


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def legal_auth_client(api_client, legal_user):
    api_client.force_authenticate(user=legal_user)
    return api_client


@pytest.fixture
def sample_pdf():
    # Minimal valid PDF
    return (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF"
    )


@pytest.fixture
def sample_png():
    # Minimal 1x1 white PNG
    import base64
    data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
        "nGP4z8BQDwAEgAF/pooBPQAAAABJRU5ErkJggg=="
    )
    return data
