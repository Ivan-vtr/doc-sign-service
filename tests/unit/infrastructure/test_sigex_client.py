"""Tests for SigexClient with mocked HTTP responses."""

import json
from unittest.mock import MagicMock, patch

import pytest
import responses

from app.domain.entities import QRSigningSession
from app.domain.exceptions import (
    SigningCancelledError,
    SigningError,
    SigningTimeoutError,
    VerificationError,
)
from app.infrastructure.sigex.client import SigexClient

BASE_URL = "https://sigex.kz"


@pytest.fixture
def client():
    return SigexClient(
        base_url=BASE_URL,
        timeout=5,
        poll_retries=3,
        poll_interval=0,  # No delay in tests
    )


class TestRegisterQRSigning:
    @responses.activate
    def test_success(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/api/egovQr",
            json={
                "qrCode": "base64qrcode",
                "dataURL": f"{BASE_URL}/api/egovQr/123/data",
                "signURL": f"{BASE_URL}/api/egovQr/123/sign",
                "eGovMobileLaunchLink": "egov://sign/123",
                "eGovBusinessLaunchLink": "egovbiz://sign/123",
            },
            status=200,
        )

        session = client.register_qr_signing("Test signing")

        assert session.qr_code_base64 == "base64qrcode"
        assert session.data_url == f"{BASE_URL}/api/egovQr/123/data"
        assert session.sign_url == f"{BASE_URL}/api/egovQr/123/sign"
        assert session.egov_mobile_link == "egov://sign/123"
        assert session.egov_business_link == "egovbiz://sign/123"

    @responses.activate
    def test_error_response(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/api/egovQr",
            json={"message": "Service unavailable"},
            status=200,
        )

        with pytest.raises(SigningError, match="Service unavailable"):
            client.register_qr_signing("Test")

    @responses.activate
    def test_http_error(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/api/egovQr",
            status=500,
        )

        with pytest.raises(Exception):
            client.register_qr_signing("Test")


class TestSendDataForSigning:
    @responses.activate
    def test_success(self, client):
        data_url = f"{BASE_URL}/api/egovQr/123/data"
        responses.add(
            responses.POST,
            data_url,
            json={},
            status=200,
        )

        session = QRSigningSession(data_url=data_url, sign_url="")
        documents = [{"id": 1, "nameRu": "Test", "data": "base64data"}]
        client.send_data_for_signing(session, documents)

        assert len(responses.calls) == 1
        body = json.loads(responses.calls[0].request.body)
        assert body["signMethod"] == "CMS_SIGN_ONLY"
        assert len(body["documentsToSign"]) == 1

    @responses.activate
    def test_with_attach_data(self, client):
        data_url = f"{BASE_URL}/api/egovQr/123/data"
        responses.add(responses.POST, data_url, json={}, status=200)

        session = QRSigningSession(data_url=data_url, sign_url="")
        documents = [{"id": 1, "nameRu": "Test", "data": "base64data"}]
        client.send_data_for_signing(session, documents, attach_data=True)

        body = json.loads(responses.calls[0].request.body)
        assert body["signMethod"] == "CMS_WITH_DATA"

    @responses.activate
    def test_error_message(self, client):
        data_url = f"{BASE_URL}/api/egovQr/123/data"
        responses.add(
            responses.POST,
            data_url,
            json={"message": "Invalid data"},
            status=200,
        )

        session = QRSigningSession(data_url=data_url, sign_url="")
        with pytest.raises(SigningError):
            client.send_data_for_signing(session, [{"id": 1, "nameRu": "T", "data": "x"}])


class TestPollSignatures:
    @responses.activate
    def test_success(self, client):
        sign_url = f"{BASE_URL}/api/egovQr/123/sign"
        responses.add(
            responses.GET,
            sign_url,
            json={
                "documentsToSign": [
                    {"document": {"file": {"data": "cms_signature_base64"}}}
                ]
            },
            status=200,
        )

        session = QRSigningSession(data_url="", sign_url=sign_url)
        sigs = client.poll_signatures(session)

        assert sigs == ["cms_signature_base64"]

    @responses.activate
    def test_timeout(self, client):
        sign_url = f"{BASE_URL}/api/egovQr/123/sign"
        # Always return "not ready"
        for _ in range(5):
            responses.add(
                responses.GET,
                sign_url,
                json={"message": "Not ready yet"},
                status=200,
            )

        session = QRSigningSession(data_url="", sign_url=sign_url)
        with pytest.raises(SigningTimeoutError):
            client.poll_signatures(session)

    @responses.activate
    def test_cancelled(self, client):
        sign_url = f"{BASE_URL}/api/egovQr/123/sign"
        responses.add(
            responses.GET,
            sign_url,
            json={"message": "Operation cancelled by user"},
            status=200,
        )

        session = QRSigningSession(data_url="", sign_url=sign_url)
        with pytest.raises(SigningCancelledError):
            client.poll_signatures(session)

    @responses.activate
    def test_multiple_signatures(self, client):
        sign_url = f"{BASE_URL}/api/egovQr/123/sign"
        responses.add(
            responses.GET,
            sign_url,
            json={
                "documentsToSign": [
                    {"document": {"file": {"data": "sig1"}}},
                    {"document": {"file": {"data": "sig2"}}},
                ]
            },
            status=200,
        )

        session = QRSigningSession(data_url="", sign_url=sign_url)
        sigs = client.poll_signatures(session)
        assert sigs == ["sig1", "sig2"]


class TestRegisterDocument:
    @responses.activate
    def test_success(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/api",
            json={"documentId": "doc-456", "signId": 1},
            status=200,
        )

        doc_id = client.register_document("Title", "Description")
        assert doc_id == "doc-456"

    @responses.activate
    def test_with_signature(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/api",
            json={"documentId": "doc-456", "signId": 1},
            status=200,
        )

        doc_id = client.register_document("Title", "Desc", signature="base64sig")
        body = json.loads(responses.calls[0].request.body)
        assert body["signature"] == "base64sig"
        assert body["signType"] == "cms"


class TestUploadDocumentData:
    @responses.activate
    def test_success(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/api/doc-1/data",
            json={
                "documentId": "doc-1",
                "digests": {"1.2.3": "hash_value"},
            },
            status=200,
        )

        digests = client.upload_document_data("doc-1", b"file content")
        assert "1.2.3" in digests


class TestAddSignature:
    @responses.activate
    def test_success(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/api/doc-1",
            json={"documentId": "doc-1", "signId": 2},
            status=200,
        )

        sign_id = client.add_signature("doc-1", "base64sig")
        assert sign_id == 2


class TestVerifyDocument:
    @responses.activate
    def test_success(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/api/doc-1/verify",
            json={"documentId": "doc-1"},
            status=200,
        )

        result = client.verify_document("doc-1", b"file data")
        assert result is True

    @responses.activate
    def test_failure(self, client):
        responses.add(
            responses.POST,
            f"{BASE_URL}/api/doc-1/verify",
            json={"message": "Verification failed"},
            status=200,
        )

        with pytest.raises(VerificationError):
            client.verify_document("doc-1", b"file data")


class TestGetDocumentInfo:
    @responses.activate
    def test_success(self, client):
        responses.add(
            responses.GET,
            f"{BASE_URL}/api/doc-1",
            json={
                "title": "Test",
                "description": "Desc",
                "signaturesTotal": 1,
                "signatures": [],
            },
            status=200,
        )

        info = client.get_document_info("doc-1")
        assert info["title"] == "Test"
