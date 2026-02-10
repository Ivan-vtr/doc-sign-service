from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SignerType(str, Enum):
    INDIVIDUAL = "individual"
    LEGAL_ENTITY = "legal_entity"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    REGISTERED = "registered"
    SIGNING = "signing"
    SIGNED = "signed"
    FAILED = "failed"


class SignatureStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PackageStatus(str, Enum):
    DRAFT = "draft"
    SIGNING = "signing"
    SIGNED = "signed"
    PARTIALLY_SIGNED = "partially_signed"
    FAILED = "failed"


ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
}


@dataclass
class SignerIdentity:
    iin: str
    full_name: str
    signer_type: SignerType
    bin: Optional[str] = None
    company_name: Optional[str] = None

    def __post_init__(self):
        if not self.iin or len(self.iin) != 12 or not self.iin.isdigit():
            raise ValueError("IIN must be a 12-digit string")
        if self.signer_type == SignerType.LEGAL_ENTITY:
            if not self.bin or len(self.bin) != 12 or not self.bin.isdigit():
                raise ValueError("BIN must be a 12-digit string for legal entities")
            if not self.company_name:
                raise ValueError("Company name is required for legal entities")


@dataclass
class Document:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    filename: str = ""
    mime_type: str = ""
    file_size: int = 0
    file_path: str = ""
    sha256: str = ""
    status: DocumentStatus = DocumentStatus.UPLOADED
    sigex_document_id: Optional[str] = None
    signed_file_path: Optional[str] = None
    signature_file_path: Optional[str] = None
    error_message: Optional[str] = None
    owner_id: Optional[int] = None
    package_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def validate_mime_type(self) -> bool:
        return self.mime_type in ALLOWED_MIME_TYPES

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def verify_checksum(self, data: bytes) -> bool:
        return self.sha256 == self.compute_sha256(data)

    def mark_registered(self, sigex_document_id: str):
        self.sigex_document_id = sigex_document_id
        self.status = DocumentStatus.REGISTERED
        self.updated_at = datetime.now()

    def mark_signing(self):
        self.status = DocumentStatus.SIGNING
        self.updated_at = datetime.now()

    def mark_signed(self):
        self.status = DocumentStatus.SIGNED
        self.updated_at = datetime.now()

    def mark_failed(self, reason: Optional[str] = None):
        self.status = DocumentStatus.FAILED
        self.error_message = reason
        self.updated_at = datetime.now()


@dataclass
class Signature:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    signer_iin: str = ""
    signer_name: str = ""
    signer_type: SignerType = SignerType.INDIVIDUAL
    signer_bin: Optional[str] = None
    signer_company: Optional[str] = None
    signature_data: str = ""  # Base64 CMS signature
    sigex_sign_id: Optional[int] = None
    status: SignatureStatus = SignatureStatus.PENDING
    signed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    def mark_completed(self, signature_data: str, sigex_sign_id: Optional[int] = None):
        self.signature_data = signature_data
        self.sigex_sign_id = sigex_sign_id
        self.status = SignatureStatus.COMPLETED
        self.signed_at = datetime.now()

    def mark_failed(self):
        self.status = SignatureStatus.FAILED

    def mark_cancelled(self):
        self.status = SignatureStatus.CANCELLED


@dataclass
class QRSigningSession:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    signer_iin: str = ""
    signer_type: SignerType = SignerType.INDIVIDUAL
    qr_code_base64: str = ""
    data_url: str = ""
    sign_url: str = ""
    egov_mobile_link: str = ""
    egov_business_link: str = ""
    status: SignatureStatus = SignatureStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Package:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    status: PackageStatus = PackageStatus.DRAFT
    owner_id: Optional[int] = None
    document_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_document(self, document_id: str):
        if document_id not in self.document_ids:
            self.document_ids.append(document_id)
            self.updated_at = datetime.now()

    def mark_signing(self):
        self.status = PackageStatus.SIGNING
        self.updated_at = datetime.now()

    def mark_signed(self):
        self.status = PackageStatus.SIGNED
        self.updated_at = datetime.now()

    def mark_partially_signed(self):
        self.status = PackageStatus.PARTIALLY_SIGNED
        self.updated_at = datetime.now()

    def mark_failed(self):
        self.status = PackageStatus.FAILED
        self.updated_at = datetime.now()
