"""
Sigex API client.

Ported from the official sigex-qr-signing-client JS library:
https://github.com/sigex-kz/sigex-qr-signing-client

Implements both the standalone eGov QR signing flow and the full
document registration / signature management API.
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Optional

import requests

from app.domain.entities import QRSigningSession
from app.domain.exceptions import (
    SigningCancelledError,
    SigningError,
    SigningTimeoutError,
    VerificationError,
)
from app.domain.ports import SigningService

logger = logging.getLogger(__name__)


class SigexClient(SigningService):
    def __init__(
        self,
        base_url: str = "https://sigex.kz",
        timeout: int = 30,
        poll_retries: int = 60,
        poll_interval: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_retries = poll_retries
        self.poll_interval = poll_interval
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # ── eGov QR Signing (standalone, no pre-registration) ────────────

    def register_qr_signing(self, description: str) -> QRSigningSession:
        """
        Register a new QR signing procedure.
        Maps to: POST /api/egovQr
        """
        response = self.session.post(
            f"{self.base_url}/api/egovQr",
            json={"description": description},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        if "message" in data:
            raise SigningError(data["message"])

        return QRSigningSession(
            qr_code_base64=data.get("qrCode", ""),
            data_url=data.get("dataURL", ""),
            sign_url=data.get("signURL", ""),
            egov_mobile_link=data.get("eGovMobileLaunchLink", ""),
            egov_business_link=data.get("eGovBusinessLaunchLink", ""),
        )

    def send_data_for_signing(
        self,
        session: QRSigningSession,
        documents: list[dict],
        attach_data: bool = False,
    ) -> None:
        """
        Send document data to the QR signing session.
        Maps to: POST {dataURL}

        documents: list of dicts with keys:
            - id: int
            - nameRu: str
            - nameKz: str (optional, defaults to nameRu)
            - nameEn: str (optional, defaults to nameRu)
            - data: base64 string of file content
            - meta: list of {"name": str, "value": str} (optional)
            - isPDF: bool (optional)
        """
        documents_to_sign = []
        for i, doc in enumerate(documents):
            documents_to_sign.append({
                "id": doc.get("id", i + 1),
                "nameRu": doc["nameRu"],
                "nameKz": doc.get("nameKz", doc["nameRu"]),
                "nameEn": doc.get("nameEn", doc["nameRu"]),
                "meta": doc.get("meta", []),
                "document": {
                    "file": {
                        "mime": "@file/pdf" if doc.get("isPDF", False) else "",
                        "data": doc["data"],
                    }
                },
            })

        sign_method = "CMS_WITH_DATA" if attach_data else "CMS_SIGN_ONLY"

        last_error = None
        for attempt in range(self.poll_retries):
            try:
                response = self.session.post(
                    session.data_url,
                    json={
                        "signMethod": sign_method,
                        "documentsToSign": documents_to_sign,
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                if "message" in data:
                    raise SigningError(data["message"])
                return
            except SigningError:
                raise
            except requests.RequestException as e:
                last_error = e
                logger.debug(
                    "Attempt %d/%d to send data failed: %s",
                    attempt + 1,
                    self.poll_retries,
                    e,
                )
                if attempt < self.poll_retries - 1:
                    time.sleep(1)

        raise SigningError(
            f"Failed to send data after {self.poll_retries} attempts: {last_error}"
        )

    def poll_signatures(self, session: QRSigningSession) -> list[str]:
        """
        Poll for completed signatures.
        Maps to: GET {signURL}
        Returns list of base64 CMS signatures.
        """
        last_error = None
        for attempt in range(self.poll_retries):
            try:
                response = self.session.get(
                    session.sign_url,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

                if "message" in data:
                    msg = data["message"]
                    if "cancelled" in msg.lower() or "отменен" in msg.lower():
                        raise SigningCancelledError(msg)
                    # Not ready yet, keep polling
                    logger.debug("Polling attempt %d: %s", attempt + 1, msg)
                    time.sleep(self.poll_interval)
                    continue

                signatures = [
                    doc["document"]["file"]["data"]
                    for doc in data.get("documentsToSign", [])
                ]
                return signatures

            except SigningCancelledError:
                raise
            except (requests.RequestException, KeyError) as e:
                last_error = e
                logger.debug(
                    "Polling attempt %d/%d failed: %s",
                    attempt + 1,
                    self.poll_retries,
                    e,
                )
                time.sleep(self.poll_interval)

        raise SigningTimeoutError(
            f"Signing timed out after {self.poll_retries} attempts: {last_error}"
        )

    # ── Document Registration API ────────────────────────────────────

    def register_document(
        self,
        title: str,
        description: str,
        signature: Optional[str] = None,
    ) -> str:
        """
        Register a document in Sigex.
        Maps to: POST /api
        """
        payload = {
            "title": title,
            "description": description,
            "signType": "cms",
        }
        if signature:
            payload["signature"] = signature

        response = self.session.post(
            f"{self.base_url}/api",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        if "message" in data and "documentId" not in data:
            raise SigningError(data["message"])

        return data["documentId"]

    def upload_document_data(self, sigex_document_id: str, data: bytes) -> dict:
        """
        Upload document binary data.
        Maps to: POST /api/{id}/data
        Returns dict with digests.
        """
        response = self.session.post(
            f"{self.base_url}/api/{sigex_document_id}/data",
            data=data,
            headers={"Content-Type": "application/octet-stream"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()

        if "message" in result and "documentId" not in result:
            raise SigningError(result["message"])

        return result.get("digests", {})

    def add_signature(self, sigex_document_id: str, signature_b64: str) -> int:
        """
        Add a CMS signature to a registered document.
        Maps to: POST /api/{id}
        """
        response = self.session.post(
            f"{self.base_url}/api/{sigex_document_id}",
            json={
                "signType": "cms",
                "signature": signature_b64,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        if "message" in data and "signId" not in data:
            raise SigningError(data["message"])

        return data.get("signId", 0)

    def verify_document(self, sigex_document_id: str, data: bytes) -> bool:
        """
        Verify document signatures.
        Maps to: POST /api/{id}/verify
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/{sigex_document_id}/verify",
                data=data,
                headers={"Content-Type": "application/octet-stream"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            if "message" in result and "documentId" not in result:
                raise VerificationError(result["message"])
            return True
        except (requests.RequestException, VerificationError) as e:
            raise VerificationError(f"Verification failed: {e}")

    def get_document_info(self, sigex_document_id: str) -> dict:
        """
        Get document information including signatures.
        Maps to: GET /api/{id}
        """
        response = self.session.get(
            f"{self.base_url}/api/{sigex_document_id}",
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        if "message" in data and "title" not in data:
            raise SigningError(data["message"])

        return data

    # ── Document-based eGov QR signing ───────────────────────────────

    def register_document_qr_signing(
        self, sigex_document_id: str, language: str = "ru"
    ) -> dict:
        """
        Register QR signing for an already-registered document.
        Maps to: POST /api/{id}/egovQr
        """
        response = self.session.post(
            f"{self.base_url}/api/{sigex_document_id}/egovQr",
            json={"language": language},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        if "message" in data:
            raise SigningError(data["message"])
        return data

    def check_egov_operation(
        self, sigex_document_id: str, operation_id: str
    ) -> dict:
        """
        Check eGov operation status.
        Maps to: GET /api/{id}/egovOperation/{operationId}
        """
        response = self.session.get(
            f"{self.base_url}/api/{sigex_document_id}/egovOperation/{operation_id}",
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def cancel_egov_operation(
        self, sigex_document_id: str, operation_id: str
    ) -> None:
        """
        Cancel eGov operation.
        Maps to: DELETE /api/{id}/egovOperation/{operationId}
        """
        response = self.session.delete(
            f"{self.base_url}/api/{sigex_document_id}/egovOperation/{operation_id}",
            timeout=self.timeout,
        )
        response.raise_for_status()

    def get_signature_export(
        self, sigex_document_id: str, sign_id: int
    ) -> dict:
        """
        Export a specific signature.
        Maps to: GET /api/{id}/signature/{signId}
        """
        response = self.session.get(
            f"{self.base_url}/api/{sigex_document_id}/signature/{sign_id}",
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
