"""Integration tests for REST API endpoints."""

import io
import json
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from app.domain.entities import DocumentStatus, QRSigningSession


@pytest.mark.django_db
class TestAuthAPI:
    def test_register_individual(self, api_client):
        response = api_client.post(
            "/api/auth/register/",
            {
                "username": "newuser",
                "password": "securepass123",
                "iin": "123456789012",
                "full_name": "New User",
                "signer_type": "individual",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["username"] == "newuser"

    def test_register_legal_entity(self, api_client):
        response = api_client.post(
            "/api/auth/register/",
            {
                "username": "company",
                "password": "securepass123",
                "iin": "123456789012",
                "full_name": "Company Rep",
                "signer_type": "legal_entity",
                "bin": "111222333444",
                "company_name": "Test LLP",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_register_legal_entity_missing_bin(self, api_client):
        response = api_client.post(
            "/api/auth/register/",
            {
                "username": "company2",
                "password": "securepass123",
                "iin": "123456789012",
                "full_name": "Company Rep",
                "signer_type": "legal_entity",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_username(self, api_client, user):
        response = api_client.post(
            "/api/auth/register/",
            {
                "username": "testuser",
                "password": "securepass123",
                "iin": "123456789012",
                "full_name": "Test",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_login_success(self, api_client, user):
        response = api_client.post(
            "/api/auth/login/",
            {"username": "testuser", "password": "testpass123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == "testuser"

    def test_login_invalid(self, api_client, user):
        response = api_client.post(
            "/api/auth/login/",
            {"username": "testuser", "password": "wrong"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout(self, auth_client):
        response = auth_client.post("/api/auth/logout/")
        assert response.status_code == status.HTTP_200_OK

    def test_profile(self, auth_client):
        response = auth_client.get("/api/auth/profile/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["iin"] == "123456789012"
        assert response.data["full_name"] == "Test User"

    def test_unauthenticated_access(self, api_client):
        response = api_client.get("/api/documents/")
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


@pytest.mark.django_db
class TestDocumentAPI:
    def test_upload_pdf(self, auth_client, sample_pdf):
        pdf_file = io.BytesIO(sample_pdf)
        pdf_file.name = "test.pdf"

        response = auth_client.post(
            "/api/documents/upload/",
            {"file": pdf_file, "title": "Test PDF"},
            format="multipart",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["filename"] == "test.pdf"
        assert response.data["status"] == "uploaded"
        assert len(response.data["sha256"]) == 64

    def test_upload_png(self, auth_client, sample_png):
        png_file = io.BytesIO(sample_png)
        png_file.name = "scan.png"

        response = auth_client.post(
            "/api/documents/upload/",
            {"file": png_file, "title": "Scan"},
            format="multipart",
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_list_documents(self, auth_client, sample_pdf):
        # Upload first
        pdf_file = io.BytesIO(sample_pdf)
        pdf_file.name = "test.pdf"
        auth_client.post(
            "/api/documents/upload/",
            {"file": pdf_file, "title": "Test"},
            format="multipart",
        )

        response = auth_client.get("/api/documents/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_document_detail(self, auth_client, sample_pdf):
        pdf_file = io.BytesIO(sample_pdf)
        pdf_file.name = "test.pdf"
        upload = auth_client.post(
            "/api/documents/upload/",
            {"file": pdf_file, "title": "Test"},
            format="multipart",
        )
        doc_id = upload.data["document_id"]

        response = auth_client.get(f"/api/documents/{doc_id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["document_id"] == doc_id

    def test_document_download(self, auth_client, sample_pdf):
        pdf_file = io.BytesIO(sample_pdf)
        pdf_file.name = "test.pdf"
        upload = auth_client.post(
            "/api/documents/upload/",
            {"file": pdf_file, "title": "Test"},
            format="multipart",
        )
        doc_id = upload.data["document_id"]

        response = auth_client.get(f"/api/documents/{doc_id}/download/")
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/pdf"

    def test_document_verify(self, auth_client, sample_pdf):
        pdf_file = io.BytesIO(sample_pdf)
        pdf_file.name = "test.pdf"
        upload = auth_client.post(
            "/api/documents/upload/",
            {"file": pdf_file, "title": "Test"},
            format="multipart",
        )
        doc_id = upload.data["document_id"]

        response = auth_client.post(f"/api/documents/{doc_id}/verify/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["checksum_match"] is True

    def test_document_not_found(self, auth_client):
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = auth_client.get(f"/api/documents/{fake_id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_multi_upload(self, auth_client, sample_pdf, sample_png):
        pdf_file = io.BytesIO(sample_pdf)
        pdf_file.name = "test.pdf"
        png_file = io.BytesIO(sample_png)
        png_file.name = "scan.png"

        response = auth_client.post(
            "/api/documents/upload-multiple/",
            {"files": [pdf_file, png_file], "title": "Batch"},
            format="multipart",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data["documents"]) == 2


@pytest.mark.django_db
class TestSigningAPI:
    @patch("app.interfaces.api.views.get_signing_service")
    def test_initiate_signing(self, mock_get_svc, auth_client, sample_pdf):
        # Upload document first
        pdf_file = io.BytesIO(sample_pdf)
        pdf_file.name = "test.pdf"
        upload = auth_client.post(
            "/api/documents/upload/",
            {"file": pdf_file, "title": "Test"},
            format="multipart",
        )
        doc_id = upload.data["document_id"]

        # Mock signing service
        mock_svc = MagicMock()
        mock_svc.register_qr_signing.return_value = QRSigningSession(
            qr_code_base64="qr_image_data",
            data_url="https://sigex.kz/api/egovQr/test/data",
            sign_url="https://sigex.kz/api/egovQr/test/sign",
            egov_mobile_link="egov://sign",
            egov_business_link="egovbiz://sign",
        )
        mock_get_svc.return_value = mock_svc

        response = auth_client.post(
            "/api/signing/initiate/",
            {"document_id": doc_id},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["qr_code_base64"] == "qr_image_data"
        assert response.data["egov_mobile_link"] == "egov://sign"
        assert response.data["egov_business_link"] == "egovbiz://sign"
        assert response.data["data_url"] == "https://sigex.kz/api/egovQr/test/data"
        assert response.data["sign_url"] == "https://sigex.kz/api/egovQr/test/sign"
        # Data is NOT sent during initiation — it's long-polling, done during completion
        mock_svc.send_data_for_signing.assert_not_called()


@pytest.mark.django_db
class TestPackageAPI:
    def test_create_package(self, auth_client):
        response = auth_client.post(
            "/api/packages/create/",
            {"title": "Test Package", "description": "A test"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "Test Package"
        assert response.data["status"] == "draft"

    def test_list_packages(self, auth_client):
        auth_client.post(
            "/api/packages/create/",
            {"title": "Pkg1"},
            format="json",
        )
        response = auth_client.get("/api/packages/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_add_document_to_package(self, auth_client, sample_pdf):
        # Create package
        pkg_resp = auth_client.post(
            "/api/packages/create/",
            {"title": "Pkg"},
            format="json",
        )
        pkg_id = pkg_resp.data["id"]

        # Upload document
        pdf_file = io.BytesIO(sample_pdf)
        pdf_file.name = "test.pdf"
        doc_resp = auth_client.post(
            "/api/documents/upload/",
            {"file": pdf_file, "title": "Doc"},
            format="multipart",
        )
        doc_id = doc_resp.data["document_id"]

        # Add to package
        response = auth_client.post(
            f"/api/packages/{pkg_id}/add-document/",
            {"document_id": doc_id},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "added"

    @patch("app.interfaces.api.views.get_signing_service")
    @patch("app.interfaces.api.views.get_file_storage")
    def test_package_download_signed_zip(
        self, mock_get_storage, mock_get_svc, auth_client, sample_pdf,
    ):
        # Create package + upload 2 docs + add to package
        pkg_resp = auth_client.post(
            "/api/packages/create/",
            {"title": "ZipPkg"},
            format="json",
        )
        pkg_id = pkg_resp.data["id"]

        doc_ids = []
        for name in ("a.pdf", "b.pdf"):
            f = io.BytesIO(sample_pdf)
            f.name = name
            resp = auth_client.post(
                "/api/documents/upload/",
                {"file": f, "title": name},
                format="multipart",
            )
            doc_id = resp.data["document_id"]
            doc_ids.append(doc_id)
            auth_client.post(
                f"/api/packages/{pkg_id}/add-document/",
                {"document_id": doc_id},
                format="json",
            )

        # Mark documents as signed manually via the DB
        from app.infrastructure.persistence.models import DocumentModel
        for doc_id in doc_ids:
            dm = DocumentModel.objects.get(id=doc_id)
            dm.status = "signed"
            dm.signature_file_path = dm.file_path  # reuse original as stub
            dm.save()

        # Mock file storage to return data
        mock_storage = MagicMock()
        mock_storage.read_file.return_value = sample_pdf
        mock_get_storage.return_value = mock_storage

        response = auth_client.get(f"/api/packages/{pkg_id}/download-signed/")
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/zip"

        with zipfile.ZipFile(io.BytesIO(b"".join(response.streaming_content)
                                         if hasattr(response, 'streaming_content')
                                         else response.content)) as z:
            names = z.namelist()
            assert any("originals/" in n for n in names)
            assert any("signatures/" in n for n in names)

    def test_package_download_signed_not_found(self, auth_client):
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = auth_client.get(f"/api/packages/{fake_id}/download-signed/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_document_download_original_alias(self, auth_client, sample_pdf):
        pdf_file = io.BytesIO(sample_pdf)
        pdf_file.name = "test.pdf"
        upload = auth_client.post(
            "/api/documents/upload/",
            {"file": pdf_file, "title": "Test"},
            format="multipart",
        )
        doc_id = upload.data["document_id"]

        response = auth_client.get(f"/api/documents/{doc_id}/download/original/")
        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/pdf"

    def test_document_download_signature_no_signature(self, auth_client, sample_pdf):
        pdf_file = io.BytesIO(sample_pdf)
        pdf_file.name = "test.pdf"
        upload = auth_client.post(
            "/api/documents/upload/",
            {"file": pdf_file, "title": "Test"},
            format="multipart",
        )
        doc_id = upload.data["document_id"]

        response = auth_client.get(f"/api/documents/{doc_id}/download/signature/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
