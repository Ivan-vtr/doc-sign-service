import hashlib

import pytest

from app.domain.entities import (
    ALLOWED_MIME_TYPES,
    Document,
    DocumentStatus,
    Package,
    PackageStatus,
    Signature,
    SignatureStatus,
    SignerIdentity,
    SignerType,
)


class TestSignerIdentity:
    def test_valid_individual(self):
        signer = SignerIdentity(
            iin="123456789012",
            full_name="Test User",
            signer_type=SignerType.INDIVIDUAL,
        )
        assert signer.iin == "123456789012"
        assert signer.signer_type == SignerType.INDIVIDUAL

    def test_valid_legal_entity(self):
        signer = SignerIdentity(
            iin="123456789012",
            full_name="Test User",
            signer_type=SignerType.LEGAL_ENTITY,
            bin="111222333444",
            company_name="Test LLP",
        )
        assert signer.bin == "111222333444"

    def test_invalid_iin_length(self):
        with pytest.raises(ValueError, match="IIN must be a 12-digit"):
            SignerIdentity(
                iin="12345",
                full_name="Test",
                signer_type=SignerType.INDIVIDUAL,
            )

    def test_invalid_iin_non_digit(self):
        with pytest.raises(ValueError, match="IIN must be a 12-digit"):
            SignerIdentity(
                iin="12345678901a",
                full_name="Test",
                signer_type=SignerType.INDIVIDUAL,
            )

    def test_empty_iin(self):
        with pytest.raises(ValueError, match="IIN must be a 12-digit"):
            SignerIdentity(
                iin="",
                full_name="Test",
                signer_type=SignerType.INDIVIDUAL,
            )

    def test_legal_entity_missing_bin(self):
        with pytest.raises(ValueError, match="BIN must be a 12-digit"):
            SignerIdentity(
                iin="123456789012",
                full_name="Test",
                signer_type=SignerType.LEGAL_ENTITY,
            )

    def test_legal_entity_missing_company(self):
        with pytest.raises(ValueError, match="Company name is required"):
            SignerIdentity(
                iin="123456789012",
                full_name="Test",
                signer_type=SignerType.LEGAL_ENTITY,
                bin="111222333444",
            )

    def test_legal_entity_invalid_bin(self):
        with pytest.raises(ValueError, match="BIN must be a 12-digit"):
            SignerIdentity(
                iin="123456789012",
                full_name="Test",
                signer_type=SignerType.LEGAL_ENTITY,
                bin="short",
                company_name="Test LLP",
            )


class TestDocument:
    def test_compute_sha256(self):
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        assert Document.compute_sha256(data) == expected

    def test_verify_checksum_valid(self):
        data = b"test data"
        doc = Document(sha256=Document.compute_sha256(data))
        assert doc.verify_checksum(data) is True

    def test_verify_checksum_invalid(self):
        doc = Document(sha256="wrong_hash")
        assert doc.verify_checksum(b"test data") is False

    def test_validate_mime_type_pdf(self):
        doc = Document(mime_type="application/pdf")
        assert doc.validate_mime_type() is True

    def test_validate_mime_type_png(self):
        doc = Document(mime_type="image/png")
        assert doc.validate_mime_type() is True

    def test_validate_mime_type_jpeg(self):
        doc = Document(mime_type="image/jpeg")
        assert doc.validate_mime_type() is True

    def test_validate_mime_type_invalid(self):
        doc = Document(mime_type="application/msword")
        assert doc.validate_mime_type() is False

    def test_mark_registered(self):
        doc = Document()
        doc.mark_registered("sigex-123")
        assert doc.status == DocumentStatus.REGISTERED
        assert doc.sigex_document_id == "sigex-123"

    def test_mark_signing(self):
        doc = Document()
        doc.mark_signing()
        assert doc.status == DocumentStatus.SIGNING

    def test_mark_signed(self):
        doc = Document()
        doc.mark_signed()
        assert doc.status == DocumentStatus.SIGNED

    def test_mark_failed(self):
        doc = Document()
        doc.mark_failed()
        assert doc.status == DocumentStatus.FAILED

    def test_default_status(self):
        doc = Document()
        assert doc.status == DocumentStatus.UPLOADED

    def test_uuid_generation(self):
        doc1 = Document()
        doc2 = Document()
        assert doc1.id != doc2.id


class TestSignature:
    def test_mark_completed(self):
        sig = Signature()
        sig.mark_completed("base64data", sigex_sign_id=42)
        assert sig.status == SignatureStatus.COMPLETED
        assert sig.signature_data == "base64data"
        assert sig.sigex_sign_id == 42
        assert sig.signed_at is not None

    def test_mark_failed(self):
        sig = Signature()
        sig.mark_failed()
        assert sig.status == SignatureStatus.FAILED

    def test_mark_cancelled(self):
        sig = Signature()
        sig.mark_cancelled()
        assert sig.status == SignatureStatus.CANCELLED

    def test_default_status(self):
        sig = Signature()
        assert sig.status == SignatureStatus.PENDING


class TestPackage:
    def test_add_document(self):
        pkg = Package()
        pkg.add_document("doc-1")
        assert "doc-1" in pkg.document_ids

    def test_add_document_no_duplicates(self):
        pkg = Package()
        pkg.add_document("doc-1")
        pkg.add_document("doc-1")
        assert len(pkg.document_ids) == 1

    def test_mark_signing(self):
        pkg = Package()
        pkg.mark_signing()
        assert pkg.status == PackageStatus.SIGNING

    def test_mark_signed(self):
        pkg = Package()
        pkg.mark_signed()
        assert pkg.status == PackageStatus.SIGNED

    def test_mark_partially_signed(self):
        pkg = Package()
        pkg.mark_partially_signed()
        assert pkg.status == PackageStatus.PARTIALLY_SIGNED

    def test_default_status(self):
        pkg = Package()
        assert pkg.status == PackageStatus.DRAFT


class TestAllowedMimeTypes:
    def test_pdf_allowed(self):
        assert "application/pdf" in ALLOWED_MIME_TYPES

    def test_png_allowed(self):
        assert "image/png" in ALLOWED_MIME_TYPES

    def test_jpeg_allowed(self):
        assert "image/jpeg" in ALLOWED_MIME_TYPES

    def test_word_not_allowed(self):
        assert "application/msword" not in ALLOWED_MIME_TYPES
