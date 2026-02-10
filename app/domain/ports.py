from __future__ import annotations

import abc
from typing import Optional

from app.domain.entities import (
    Document,
    Package,
    QRSigningSession,
    Signature,
    SignerIdentity,
)


class DocumentRepository(abc.ABC):
    @abc.abstractmethod
    def save(self, document: Document) -> Document:
        ...

    @abc.abstractmethod
    def get_by_id(self, document_id: str) -> Optional[Document]:
        ...

    @abc.abstractmethod
    def list_by_owner(self, owner_id: int) -> list[Document]:
        ...

    @abc.abstractmethod
    def update(self, document: Document) -> Document:
        ...

    @abc.abstractmethod
    def delete(self, document_id: str) -> None:
        ...


class SignatureRepository(abc.ABC):
    @abc.abstractmethod
    def save(self, signature: Signature) -> Signature:
        ...

    @abc.abstractmethod
    def get_by_id(self, signature_id: str) -> Optional[Signature]:
        ...

    @abc.abstractmethod
    def list_by_document(self, document_id: str) -> list[Signature]:
        ...

    @abc.abstractmethod
    def update(self, signature: Signature) -> Signature:
        ...


class PackageRepository(abc.ABC):
    @abc.abstractmethod
    def save(self, package: Package) -> Package:
        ...

    @abc.abstractmethod
    def get_by_id(self, package_id: str) -> Optional[Package]:
        ...

    @abc.abstractmethod
    def list_by_owner(self, owner_id: int) -> list[Package]:
        ...

    @abc.abstractmethod
    def update(self, package: Package) -> Package:
        ...

    @abc.abstractmethod
    def delete(self, package_id: str) -> None:
        ...


class UserRepository(abc.ABC):
    @abc.abstractmethod
    def exists_by_username(self, username: str) -> bool:
        ...

    @abc.abstractmethod
    def create_user(
        self,
        username: str,
        password: str,
        email: str,
        iin: str,
        full_name: str,
        signer_type: str,
        bin: str = "",
        company_name: str = "",
    ) -> int:
        """Create user with profile. Returns user ID."""
        ...


class FileStorage(abc.ABC):
    @abc.abstractmethod
    def save_file(self, file_path: str, data: bytes) -> str:
        """Save file and return the storage path."""
        ...

    @abc.abstractmethod
    def read_file(self, file_path: str) -> bytes:
        ...

    @abc.abstractmethod
    def delete_file(self, file_path: str) -> None:
        ...

    @abc.abstractmethod
    def file_exists(self, file_path: str) -> bool:
        ...


class SigningService(abc.ABC):
    """Port for external signing service (Sigex)."""

    @abc.abstractmethod
    def register_qr_signing(self, description: str) -> QRSigningSession:
        """Register a new QR signing procedure. Returns session with QR code."""
        ...

    @abc.abstractmethod
    def send_data_for_signing(
        self,
        session: QRSigningSession,
        documents: list[dict],
        attach_data: bool = False,
    ) -> None:
        """Send document data to the signing session."""
        ...

    @abc.abstractmethod
    def poll_signatures(self, session: QRSigningSession) -> list[str]:
        """Poll for completed signatures. Returns list of base64 CMS signatures."""
        ...

    @abc.abstractmethod
    def register_document(
        self,
        title: str,
        description: str,
        signature: Optional[str] = None,
    ) -> str:
        """Register document in sigex. Returns sigex document ID."""
        ...

    @abc.abstractmethod
    def upload_document_data(self, sigex_document_id: str, data: bytes) -> dict:
        """Upload document binary data. Returns digests."""
        ...

    @abc.abstractmethod
    def add_signature(
        self, sigex_document_id: str, signature_b64: str
    ) -> int:
        """Add CMS signature to document. Returns sign ID."""
        ...

    @abc.abstractmethod
    def verify_document(self, sigex_document_id: str, data: bytes) -> bool:
        """Verify document signatures against data."""
        ...

    @abc.abstractmethod
    def get_document_info(self, sigex_document_id: str) -> dict:
        """Get document information including signatures."""
        ...
