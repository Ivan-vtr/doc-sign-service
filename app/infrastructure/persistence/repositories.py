from __future__ import annotations

import uuid
from typing import Optional

from app.domain.entities import (
    Document,
    DocumentStatus,
    Package,
    PackageStatus,
    Signature,
    SignatureStatus,
    SignerType,
)
from django.contrib.auth.models import User

from app.domain.ports import (
    DocumentRepository,
    PackageRepository,
    SignatureRepository,
    UserRepository,
)
from app.infrastructure.persistence.models import (
    DocumentModel,
    PackageModel,
    SignatureModel,
    UserProfile,
)


class DjangoDocumentRepository(DocumentRepository):
    @staticmethod
    def _to_entity(model: DocumentModel) -> Document:
        return Document(
            id=str(model.id),
            title=model.title,
            filename=model.filename,
            mime_type=model.mime_type,
            file_size=model.file_size,
            file_path=model.file_path,
            sha256=model.sha256,
            status=DocumentStatus(model.status),
            sigex_document_id=model.sigex_document_id,
            signed_file_path=model.signed_file_path,
            signature_file_path=model.signature_file_path,
            error_message=model.error_message,
            owner_id=model.owner_id,
            package_id=str(model.package_id) if model.package_id else None,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def save(self, document: Document) -> Document:
        model = DocumentModel(
            id=uuid.UUID(document.id),
            title=document.title,
            filename=document.filename,
            mime_type=document.mime_type,
            file_size=document.file_size,
            file_path=document.file_path,
            sha256=document.sha256,
            status=document.status.value,
            sigex_document_id=document.sigex_document_id,
            signed_file_path=document.signed_file_path,
            signature_file_path=document.signature_file_path,
            error_message=document.error_message,
            owner_id=document.owner_id,
            package_id=uuid.UUID(document.package_id) if document.package_id else None,
        )
        model.save()
        return self._to_entity(model)

    def get_by_id(self, document_id: str) -> Optional[Document]:
        try:
            model = DocumentModel.objects.get(id=uuid.UUID(document_id))
            return self._to_entity(model)
        except DocumentModel.DoesNotExist:
            return None

    def list_by_owner(self, owner_id: int) -> list[Document]:
        models = DocumentModel.objects.filter(owner_id=owner_id)
        return [self._to_entity(m) for m in models]

    def update(self, document: Document) -> Document:
        DocumentModel.objects.filter(id=uuid.UUID(document.id)).update(
            title=document.title,
            filename=document.filename,
            mime_type=document.mime_type,
            file_size=document.file_size,
            file_path=document.file_path,
            sha256=document.sha256,
            status=document.status.value,
            sigex_document_id=document.sigex_document_id,
            signed_file_path=document.signed_file_path,
            signature_file_path=document.signature_file_path,
            error_message=document.error_message,
            package_id=uuid.UUID(document.package_id) if document.package_id else None,
        )
        return self.get_by_id(document.id)

    def delete(self, document_id: str) -> None:
        DocumentModel.objects.filter(id=uuid.UUID(document_id)).delete()


class DjangoSignatureRepository(SignatureRepository):
    @staticmethod
    def _to_entity(model: SignatureModel) -> Signature:
        return Signature(
            id=str(model.id),
            document_id=str(model.document_id),
            signer_iin=model.signer_iin,
            signer_name=model.signer_name,
            signer_type=SignerType(model.signer_type),
            signer_bin=model.signer_bin,
            signer_company=model.signer_company,
            signature_data=model.signature_data,
            sigex_sign_id=model.sigex_sign_id,
            status=SignatureStatus(model.status),
            signed_at=model.signed_at,
            created_at=model.created_at,
        )

    def save(self, signature: Signature) -> Signature:
        model = SignatureModel(
            id=uuid.UUID(signature.id),
            document_id=uuid.UUID(signature.document_id),
            signer_iin=signature.signer_iin,
            signer_name=signature.signer_name,
            signer_type=signature.signer_type.value,
            signer_bin=signature.signer_bin,
            signer_company=signature.signer_company,
            signature_data=signature.signature_data,
            sigex_sign_id=signature.sigex_sign_id,
            status=signature.status.value,
            signed_at=signature.signed_at,
        )
        model.save()
        return self._to_entity(model)

    def get_by_id(self, signature_id: str) -> Optional[Signature]:
        try:
            model = SignatureModel.objects.get(id=uuid.UUID(signature_id))
            return self._to_entity(model)
        except SignatureModel.DoesNotExist:
            return None

    def list_by_document(self, document_id: str) -> list[Signature]:
        models = SignatureModel.objects.filter(document_id=uuid.UUID(document_id))
        return [self._to_entity(m) for m in models]

    def update(self, signature: Signature) -> Signature:
        SignatureModel.objects.filter(id=uuid.UUID(signature.id)).update(
            signature_data=signature.signature_data,
            sigex_sign_id=signature.sigex_sign_id,
            status=signature.status.value,
            signed_at=signature.signed_at,
        )
        return self.get_by_id(signature.id)


class DjangoPackageRepository(PackageRepository):
    @staticmethod
    def _to_entity(model: PackageModel) -> Package:
        doc_ids = list(
            model.documents.values_list("id", flat=True)
        )
        return Package(
            id=str(model.id),
            title=model.title,
            description=model.description,
            status=PackageStatus(model.status),
            owner_id=model.owner_id,
            document_ids=[str(d) for d in doc_ids],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def save(self, package: Package) -> Package:
        model = PackageModel(
            id=uuid.UUID(package.id),
            title=package.title,
            description=package.description,
            status=package.status.value,
            owner_id=package.owner_id,
        )
        model.save()
        return self._to_entity(model)

    def get_by_id(self, package_id: str) -> Optional[Package]:
        try:
            model = PackageModel.objects.get(id=uuid.UUID(package_id))
            return self._to_entity(model)
        except PackageModel.DoesNotExist:
            return None

    def list_by_owner(self, owner_id: int) -> list[Package]:
        models = PackageModel.objects.filter(owner_id=owner_id)
        return [self._to_entity(m) for m in models]

    def update(self, package: Package) -> Package:
        PackageModel.objects.filter(id=uuid.UUID(package.id)).update(
            title=package.title,
            description=package.description,
            status=package.status.value,
        )
        return self.get_by_id(package.id)

    def delete(self, package_id: str) -> None:
        PackageModel.objects.filter(id=uuid.UUID(package_id)).delete()


class DjangoUserRepository(UserRepository):
    def exists_by_username(self, username: str) -> bool:
        return User.objects.filter(username=username).exists()

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
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
        )
        UserProfile.objects.create(
            user=user,
            iin=iin,
            full_name=full_name,
            signer_type=signer_type,
            bin=bin,
            company_name=company_name,
        )
        return user.id
