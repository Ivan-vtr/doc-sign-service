"""
Application layer use cases.

Each use case receives ports (repositories, services) via constructor injection
and contains only orchestration logic — no framework-specific code.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import uuid
import zipfile
from dataclasses import dataclass
from typing import Optional

from app.domain.entities import (
    ALLOWED_MIME_TYPES,
    Document,
    DocumentStatus,
    Package,
    QRSigningSession,
    Signature,
    SignerIdentity,
    SignerType,
)
from app.domain.exceptions import (
    AccessDeniedError,
    DocumentNotFoundError,
    InvalidDocumentError,
    PackageNotFoundError,
    SigningError,
    UserAlreadyExistsError,
    VerificationError,
)
from app.domain.ports import (
    DocumentRepository,
    FileStorage,
    PackageRepository,
    SignatureRepository,
    SigningService,
    UserRepository,
)

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────


def _process_document_after_signing(
    document: Document,
    file_data: bytes,
    signature_b64: str,
    signer: SignerIdentity,
    document_repo: DocumentRepository,
    signature_repo: SignatureRepository,
    file_storage: FileStorage,
    signing_service: SigningService,
) -> dict:
    """Post-signing processing for a single document.

    Registers the document in Sigex, saves the signature record and files,
    marks the document as signed.  Returns a result dict.
    """
    sigex_doc_id = signing_service.register_document(
        title=document.title,
        description=f"Document: {document.filename}",
        signature=signature_b64,
    )
    signing_service.upload_document_data(sigex_doc_id, file_data)
    document.mark_registered(sigex_doc_id)

    # Save signature record
    signature = Signature(
        document_id=document.id,
        signer_iin=signer.iin,
        signer_name=signer.full_name,
        signer_type=signer.signer_type,
        signer_bin=signer.bin,
        signer_company=signer.company_name,
    )
    signature.mark_completed(signature_b64)
    signature_repo.save(signature)

    # Save signature file
    sig_path = f"documents/{document.id}/signatures/{signature.id}.cms"
    sig_data = base64.b64decode(signature_b64)
    file_storage.save_file(sig_path, sig_data)
    document.signature_file_path = sig_path

    # Save signed copy
    name, ext = os.path.splitext(document.filename)
    signed_filename = f"{name}-sigex{sigex_doc_id}{ext}"
    signed_file_path = f"documents/{document.id}/{signed_filename}"
    file_storage.save_file(signed_file_path, file_data)
    document.signed_file_path = signed_file_path

    document.mark_signed()
    document_repo.update(document)

    return {
        "document_id": document.id,
        "signature_id": signature.id,
        "sigex_document_id": sigex_doc_id,
    }


# ── DTOs ─────────────────────────────────────────────────────────────


@dataclass
class UploadResult:
    document_id: str
    title: str
    filename: str
    sha256: str
    status: str


@dataclass
class QRSigningResult:
    session_id: str
    document_id: str
    qr_code_base64: str
    egov_mobile_link: str
    egov_business_link: str
    data_url: str = ""
    sign_url: str = ""


@dataclass
class SigningStatusResult:
    document_id: str
    status: str
    signatures: list[dict]


@dataclass
class VerificationResult:
    document_id: str
    verified: bool
    checksum_match: bool
    sigex_verified: bool


# ── Use Cases ────────────────────────────────────────────────────────


class UploadDocumentUseCase:
    def __init__(
        self,
        document_repo: DocumentRepository,
        file_storage: FileStorage,
    ):
        self.document_repo = document_repo
        self.file_storage = file_storage

    def execute(
        self,
        file_data: bytes,
        filename: str,
        mime_type: str,
        title: str,
        owner_id: int,
        package_id: Optional[str] = None,
    ) -> UploadResult:
        if mime_type not in ALLOWED_MIME_TYPES:
            raise InvalidDocumentError(
                f"Unsupported file type: {mime_type}. "
                f"Allowed: {', '.join(ALLOWED_MIME_TYPES)}"
            )

        doc_id = str(uuid.uuid4())
        sha256 = Document.compute_sha256(file_data)

        # Store file: documents/{doc_id}/{filename}
        file_path = f"documents/{doc_id}/{filename}"
        self.file_storage.save_file(file_path, file_data)

        document = Document(
            id=doc_id,
            title=title,
            filename=filename,
            mime_type=mime_type,
            file_size=len(file_data),
            file_path=file_path,
            sha256=sha256,
            status=DocumentStatus.UPLOADED,
            owner_id=owner_id,
            package_id=package_id,
        )

        saved = self.document_repo.save(document)

        return UploadResult(
            document_id=saved.id,
            title=saved.title,
            filename=saved.filename,
            sha256=saved.sha256,
            status=saved.status.value,
        )


class InitiateQRSigningUseCase:
    """
    Initiate eGov QR signing for a document.

    Flow:
    1. Register QR signing session → get QR code + data/sign URLs
    2. Return QR code + URLs to frontend
    3. Frontend IMMEDIATELY calls CompleteQRSigningUseCase (before user scans!)
    4. CompleteQRSigningUseCase sends data (long-polling) and polls for signatures
    """

    def __init__(
        self,
        document_repo: DocumentRepository,
        signing_service: SigningService,
    ):
        self.document_repo = document_repo
        self.signing_service = signing_service

    def execute(
        self,
        document_id: str,
        owner_id: int,
        signer: SignerIdentity,
    ) -> QRSigningResult:
        document = self.document_repo.get_by_id(document_id)
        if not document:
            raise DocumentNotFoundError(document_id)
        if document.owner_id != owner_id:
            raise AccessDeniedError("You do not own this document")

        description = f"Подписание: {document.title}"
        session = self.signing_service.register_qr_signing(description)
        session.document_id = document_id
        session.signer_iin = signer.iin
        session.signer_type = signer.signer_type

        document.mark_signing()
        self.document_repo.update(document)

        return QRSigningResult(
            session_id=session.id,
            document_id=document_id,
            qr_code_base64=session.qr_code_base64,
            egov_mobile_link=session.egov_mobile_link,
            egov_business_link=session.egov_business_link,
            data_url=session.data_url,
            sign_url=session.sign_url,
        )


class CompleteQRSigningUseCase:
    """
    Complete the QR signing: send data, poll for signatures, store results.

    The sigex dataURL uses long-polling — the POST blocks until the user
    scans the QR code.  The frontend must call this IMMEDIATELY after
    initiation, before the user scans.

    This use case:
    1. Reads the document and sends data to sigex (long-polling POST)
    2. Polls for the signature (via signURL)
    3. Stores the signature
    4. Optionally registers the document in Sigex
    """

    def __init__(
        self,
        document_repo: DocumentRepository,
        signature_repo: SignatureRepository,
        file_storage: FileStorage,
        signing_service: SigningService,
    ):
        self.document_repo = document_repo
        self.signature_repo = signature_repo
        self.file_storage = file_storage
        self.signing_service = signing_service

    def execute(
        self,
        document_id: str,
        owner_id: int,
        signer: SignerIdentity,
        qr_session: QRSigningSession,
    ) -> dict:
        document = self.document_repo.get_by_id(document_id)
        if not document:
            raise DocumentNotFoundError(document_id)
        if document.owner_id != owner_id:
            raise AccessDeniedError("You do not own this document")

        file_data = self.file_storage.read_file(document.file_path)

        try:
            # Send data to sigex (long-polling — blocks until user scans QR)
            data_b64 = base64.b64encode(file_data).decode("ascii")
            documents_payload = [{
                "id": 1,
                "nameRu": document.title,
                "data": data_b64,
                "isPDF": document.mime_type == "application/pdf",
            }]
            self.signing_service.send_data_for_signing(
                qr_session, documents_payload, attach_data=False
            )

            # Poll for signatures
            signatures_b64 = self.signing_service.poll_signatures(qr_session)
            if not signatures_b64:
                raise SigningError("No signatures received")

            result = _process_document_after_signing(
                document=document,
                file_data=file_data,
                signature_b64=signatures_b64[0],
                signer=signer,
                document_repo=self.document_repo,
                signature_repo=self.signature_repo,
                file_storage=self.file_storage,
                signing_service=self.signing_service,
            )

        except SigningError as e:
            logger.error("Signing failed for document %s: %s", document_id, e)
            document.mark_failed(str(e))
            self.document_repo.update(document)
            raise

        return {
            "document_id": document_id,
            "signature_id": result["signature_id"],
            "signer": signer.full_name,
            "sigex_document_id": result["sigex_document_id"],
            "status": "signed",
        }


class InitiatePackageQRSigningUseCase:
    """Initiate QR signing for all documents in a package at once."""

    def __init__(
        self,
        document_repo: DocumentRepository,
        package_repo: PackageRepository,
        signing_service: SigningService,
    ):
        self.document_repo = document_repo
        self.package_repo = package_repo
        self.signing_service = signing_service

    def execute(
        self,
        package_id: str,
        owner_id: int,
        signer: SignerIdentity,
    ) -> QRSigningResult:
        package = self.package_repo.get_by_id(package_id)
        if not package:
            raise PackageNotFoundError(package_id)
        if package.owner_id != owner_id:
            raise AccessDeniedError("You do not own this package")
        if not package.document_ids:
            raise InvalidDocumentError("Package has no documents")

        description = f"Подписание пакета: {package.title}"
        session = self.signing_service.register_qr_signing(description)

        package.mark_signing()
        self.package_repo.update(package)

        return QRSigningResult(
            session_id=session.id,
            document_id=package_id,
            qr_code_base64=session.qr_code_base64,
            egov_mobile_link=session.egov_mobile_link,
            egov_business_link=session.egov_business_link,
            data_url=session.data_url,
            sign_url=session.sign_url,
        )


class CompletePackageQRSigningUseCase:
    """Complete QR signing for all documents in a package.

    The frontend must call this IMMEDIATELY after initiation, before the
    user scans the QR code.  Data sending uses long-polling.
    """

    def __init__(
        self,
        document_repo: DocumentRepository,
        signature_repo: SignatureRepository,
        package_repo: PackageRepository,
        file_storage: FileStorage,
        signing_service: SigningService,
    ):
        self.document_repo = document_repo
        self.signature_repo = signature_repo
        self.package_repo = package_repo
        self.file_storage = file_storage
        self.signing_service = signing_service

    def execute(
        self,
        package_id: str,
        owner_id: int,
        signer: SignerIdentity,
        qr_session: QRSigningSession,
    ) -> dict:
        package = self.package_repo.get_by_id(package_id)
        if not package:
            raise PackageNotFoundError(package_id)
        if package.owner_id != owner_id:
            raise AccessDeniedError("You do not own this package")

        # Prepare all documents
        documents_payload = []
        doc_entities = []
        file_data_map: dict[str, bytes] = {}
        for i, doc_id in enumerate(package.document_ids):
            doc = self.document_repo.get_by_id(doc_id)
            if not doc:
                continue
            file_data = self.file_storage.read_file(doc.file_path)
            file_data_map[doc.id] = file_data
            data_b64 = base64.b64encode(file_data).decode("ascii")
            documents_payload.append({
                "id": i + 1,
                "nameRu": doc.title,
                "data": data_b64,
                "isPDF": doc.mime_type == "application/pdf",
            })
            doc_entities.append(doc)

        if not documents_payload:
            raise InvalidDocumentError("No valid documents in package")

        try:
            # Send all data for signing (long-polling — blocks until user scans QR)
            self.signing_service.send_data_for_signing(
                qr_session, documents_payload, attach_data=False
            )

            # Poll for signatures
            signatures_b64 = self.signing_service.poll_signatures(qr_session)

            if len(signatures_b64) != len(doc_entities):
                raise SigningError(
                    f"Expected {len(doc_entities)} signatures, "
                    f"got {len(signatures_b64)}"
                )
        except SigningError as e:
            logger.error("Signing failed for package %s: %s", package_id, e)
            for doc in doc_entities:
                doc.mark_failed(str(e))
                self.document_repo.update(doc)
            package.mark_failed()
            self.package_repo.update(package)
            raise

        # Process each document independently — one failure does not stop others
        results = []
        failed_count = 0
        for doc, sig_b64 in zip(doc_entities, signatures_b64):
            try:
                result = _process_document_after_signing(
                    document=doc,
                    file_data=file_data_map[doc.id],
                    signature_b64=sig_b64,
                    signer=signer,
                    document_repo=self.document_repo,
                    signature_repo=self.signature_repo,
                    file_storage=self.file_storage,
                    signing_service=self.signing_service,
                )
                results.append(result)
            except Exception as e:
                logger.error(
                    "Post-signing failed for document %s: %s", doc.id, e,
                )
                doc.mark_failed(str(e))
                self.document_repo.update(doc)
                failed_count += 1
                results.append({
                    "document_id": doc.id,
                    "status": "failed",
                    "error": str(e),
                })

        # Determine package status
        if failed_count == 0:
            package.mark_signed()
        elif failed_count < len(doc_entities):
            package.mark_partially_signed()
        else:
            package.mark_failed()
        self.package_repo.update(package)

        return {
            "package_id": package_id,
            "status": package.status.value,
            "documents": results,
        }


class GetDocumentStatusUseCase:
    def __init__(
        self,
        document_repo: DocumentRepository,
        signature_repo: SignatureRepository,
    ):
        self.document_repo = document_repo
        self.signature_repo = signature_repo

    def execute(self, document_id: str, owner_id: int) -> SigningStatusResult:
        document = self.document_repo.get_by_id(document_id)
        if not document:
            raise DocumentNotFoundError(document_id)
        if document.owner_id != owner_id:
            raise AccessDeniedError("You do not own this document")

        sigs = self.signature_repo.list_by_document(document_id)
        sig_dicts = [
            {
                "id": s.id,
                "signer_name": s.signer_name,
                "signer_iin": s.signer_iin,
                "signer_type": s.signer_type.value,
                "status": s.status.value,
                "signed_at": s.signed_at.isoformat() if s.signed_at else None,
            }
            for s in sigs
        ]

        return SigningStatusResult(
            document_id=document_id,
            status=document.status.value,
            signatures=sig_dicts,
        )


class VerifyDocumentUseCase:
    def __init__(
        self,
        document_repo: DocumentRepository,
        file_storage: FileStorage,
        signing_service: SigningService,
    ):
        self.document_repo = document_repo
        self.file_storage = file_storage
        self.signing_service = signing_service

    def execute(self, document_id: str, owner_id: int) -> VerificationResult:
        document = self.document_repo.get_by_id(document_id)
        if not document:
            raise DocumentNotFoundError(document_id)
        if document.owner_id != owner_id:
            raise AccessDeniedError("You do not own this document")

        file_data = self.file_storage.read_file(document.file_path)

        # Verify checksum
        checksum_match = document.verify_checksum(file_data)

        # Verify via Sigex if registered
        sigex_verified = False
        if document.sigex_document_id:
            try:
                self.signing_service.verify_document(
                    document.sigex_document_id, file_data
                )
                sigex_verified = True
            except VerificationError:
                sigex_verified = False

        return VerificationResult(
            document_id=document_id,
            verified=checksum_match and (sigex_verified or not document.sigex_document_id),
            checksum_match=checksum_match,
            sigex_verified=sigex_verified,
        )


class ListDocumentsUseCase:
    def __init__(
        self,
        document_repo: DocumentRepository,
        package_repo: PackageRepository,
    ):
        self.document_repo = document_repo
        self.package_repo = package_repo

    def execute(self, owner_id: int) -> list[dict]:
        docs = self.document_repo.list_by_owner(owner_id)
        packages = self.package_repo.list_by_owner(owner_id)
        package_names = {p.id: p.title for p in packages}
        return [
            {
                "id": d.id,
                "title": d.title,
                "filename": d.filename,
                "mime_type": d.mime_type,
                "file_size": d.file_size,
                "sha256": d.sha256,
                "status": d.status.value,
                "sigex_document_id": d.sigex_document_id,
                "package_id": d.package_id,
                "package_name": package_names.get(d.package_id),
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ]


class DownloadDocumentUseCase:
    def __init__(
        self,
        document_repo: DocumentRepository,
        file_storage: FileStorage,
    ):
        self.document_repo = document_repo
        self.file_storage = file_storage

    def execute(self, document_id: str, owner_id: int) -> tuple[bytes, str, str]:
        """Returns (file_data, filename, mime_type)."""
        document = self.document_repo.get_by_id(document_id)
        if not document:
            raise DocumentNotFoundError(document_id)
        if document.owner_id != owner_id:
            raise AccessDeniedError("You do not own this document")

        file_data = self.file_storage.read_file(document.file_path)
        return file_data, document.filename, document.mime_type


class DownloadSignedDocumentUseCase:
    def __init__(
        self,
        document_repo: DocumentRepository,
        file_storage: FileStorage,
    ):
        self.document_repo = document_repo
        self.file_storage = file_storage

    def execute(self, document_id: str, owner_id: int) -> tuple[bytes, str, str]:
        """Returns (file_data, signed_filename, mime_type)."""
        document = self.document_repo.get_by_id(document_id)
        if not document:
            raise DocumentNotFoundError(document_id)
        if document.owner_id != owner_id:
            raise AccessDeniedError("You do not own this document")
        if not document.signed_file_path:
            raise DocumentNotFoundError(
                f"Signed copy not available for document {document_id}"
            )

        file_data = self.file_storage.read_file(document.signed_file_path)
        signed_filename = os.path.basename(document.signed_file_path)
        return file_data, signed_filename, document.mime_type


class CreatePackageUseCase:
    def __init__(self, package_repo: PackageRepository):
        self.package_repo = package_repo

    def execute(self, title: str, description: str, owner_id: int) -> dict:
        package = Package(
            title=title,
            description=description,
            owner_id=owner_id,
        )
        saved = self.package_repo.save(package)
        return {
            "id": saved.id,
            "title": saved.title,
            "description": saved.description,
            "status": saved.status.value,
        }


class AddDocumentToPackageUseCase:
    def __init__(
        self,
        document_repo: DocumentRepository,
        package_repo: PackageRepository,
    ):
        self.document_repo = document_repo
        self.package_repo = package_repo

    def execute(
        self, package_id: str, document_id: str, owner_id: int
    ) -> dict:
        package = self.package_repo.get_by_id(package_id)
        if not package:
            raise PackageNotFoundError(package_id)
        if package.owner_id != owner_id:
            raise AccessDeniedError("You do not own this package")

        document = self.document_repo.get_by_id(document_id)
        if not document:
            raise DocumentNotFoundError(document_id)
        if document.owner_id != owner_id:
            raise AccessDeniedError("You do not own this document")

        document.package_id = package_id
        self.document_repo.update(document)

        return {
            "package_id": package_id,
            "document_id": document_id,
            "status": "added",
        }


class ListPackagesUseCase:
    def __init__(self, package_repo: PackageRepository):
        self.package_repo = package_repo

    def execute(self, owner_id: int) -> list[dict]:
        packages = self.package_repo.list_by_owner(owner_id)
        return [
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "status": p.status.value,
                "document_count": len(p.document_ids),
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in packages
        ]


class DownloadSignatureUseCase:
    def __init__(
        self,
        document_repo: DocumentRepository,
        file_storage: FileStorage,
    ):
        self.document_repo = document_repo
        self.file_storage = file_storage

    def execute(self, document_id: str, owner_id: int) -> tuple[bytes, str]:
        """Returns (signature_cms_bytes, filename)."""
        document = self.document_repo.get_by_id(document_id)
        if not document:
            raise DocumentNotFoundError(document_id)
        if document.owner_id != owner_id:
            raise AccessDeniedError("You do not own this document")
        if not document.signature_file_path:
            raise DocumentNotFoundError(
                f"Signature not available for document {document_id}"
            )

        sig_data = self.file_storage.read_file(document.signature_file_path)
        filename = f"{document.filename}.cms"
        return sig_data, filename


class DownloadSignedPackageUseCase:
    def __init__(
        self,
        document_repo: DocumentRepository,
        package_repo: PackageRepository,
        file_storage: FileStorage,
    ):
        self.document_repo = document_repo
        self.package_repo = package_repo
        self.file_storage = file_storage

    def execute(self, package_id: str, owner_id: int) -> tuple[bytes, str]:
        """Returns (zip_bytes, zip_filename)."""
        package = self.package_repo.get_by_id(package_id)
        if not package:
            raise PackageNotFoundError(package_id)
        if package.owner_id != owner_id:
            raise AccessDeniedError("You do not own this package")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for doc_id in package.document_ids:
                doc = self.document_repo.get_by_id(doc_id)
                if not doc or doc.status != DocumentStatus.SIGNED:
                    continue

                original_data = self.file_storage.read_file(doc.file_path)
                zf.writestr(f"originals/{doc.filename}", original_data)

                if doc.signature_file_path:
                    sig_data = self.file_storage.read_file(doc.signature_file_path)
                    zf.writestr(f"signatures/{doc.filename}.cms", sig_data)

        zip_filename = f"package_{package_id}_signed.zip"
        return buf.getvalue(), zip_filename


class RegisterUserUseCase:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def execute(
        self,
        username: str,
        password: str,
        email: str = "",
        iin: str = "",
        full_name: str = "",
        signer_type: str = "individual",
        bin: str = "",
        company_name: str = "",
    ) -> dict:
        if not username:
            raise InvalidDocumentError("Имя пользователя обязательно")
        if len(password) < 8:
            raise InvalidDocumentError("Пароль должен содержать минимум 8 символов")
        if not iin or len(iin) != 12 or not iin.isdigit():
            raise InvalidDocumentError("ИИН должен содержать ровно 12 цифр")
        if not full_name:
            raise InvalidDocumentError("ФИО обязательно")
        if signer_type == "legal_entity":
            if not bin or len(bin) != 12 or not bin.isdigit():
                raise InvalidDocumentError(
                    "БИН должен содержать ровно 12 цифр для юридических лиц"
                )
            if not company_name:
                raise InvalidDocumentError(
                    "Название компании обязательно для юридических лиц"
                )

        if self.user_repo.exists_by_username(username):
            raise UserAlreadyExistsError(
                "Имя пользователя уже занято"
            )

        user_id = self.user_repo.create_user(
            username=username,
            password=password,
            email=email,
            iin=iin,
            full_name=full_name,
            signer_type=signer_type,
            bin=bin,
            company_name=company_name,
        )
        return {"id": user_id, "username": username}
