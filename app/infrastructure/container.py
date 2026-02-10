"""Simple dependency injection container."""

from __future__ import annotations

from django.conf import settings

from app.domain.ports import (
    DocumentRepository,
    FileStorage,
    PackageRepository,
    SignatureRepository,
    SigningService,
    UserRepository,
)
from app.infrastructure.persistence.repositories import (
    DjangoDocumentRepository,
    DjangoPackageRepository,
    DjangoSignatureRepository,
    DjangoUserRepository,
)
from app.infrastructure.sigex.client import SigexClient
from app.infrastructure.storage.local import LocalFileStorage


def get_document_repository() -> DocumentRepository:
    return DjangoDocumentRepository()


def get_signature_repository() -> SignatureRepository:
    return DjangoSignatureRepository()


def get_package_repository() -> PackageRepository:
    return DjangoPackageRepository()


def get_user_repository() -> UserRepository:
    return DjangoUserRepository()


def get_file_storage() -> FileStorage:
    backend = getattr(settings, "FILE_STORAGE_BACKEND", "local")
    if backend == "s3":
        from app.infrastructure.storage.s3 import S3FileStorage
        return S3FileStorage()
    return LocalFileStorage()


def get_signing_service() -> SigningService:
    return SigexClient(
        base_url=getattr(settings, "SIGEX_BASE_URL", "https://sigex.kz"),
        timeout=getattr(settings, "SIGEX_TIMEOUT", 30),
        poll_retries=getattr(settings, "SIGEX_QR_POLL_RETRIES", 60),
        poll_interval=getattr(settings, "SIGEX_QR_POLL_INTERVAL", 3),
    )
