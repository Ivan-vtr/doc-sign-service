from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.application.use_cases import (
    AddDocumentToPackageUseCase,
    CompletePackageQRSigningUseCase,
    CompleteQRSigningUseCase,
    CreatePackageUseCase,
    DownloadDocumentUseCase,
    DownloadSignatureUseCase,
    DownloadSignedPackageUseCase,
    GetDocumentStatusUseCase,
    InitiateQRSigningUseCase,
    ListDocumentsUseCase,
    ListPackagesUseCase,
    UploadDocumentUseCase,
    VerifyDocumentUseCase,
)
from app.domain.exceptions import SigningError
from app.domain.entities import (
    Document,
    DocumentStatus,
    Package,
    PackageStatus,
    QRSigningSession,
    Signature,
    SignatureStatus,
    SignerIdentity,
    SignerType,
)
from app.domain.exceptions import (
    AccessDeniedError,
    DocumentNotFoundError,
    InvalidDocumentError,
    PackageNotFoundError,
)


@pytest.fixture
def mock_doc_repo():
    return MagicMock()


@pytest.fixture
def mock_sig_repo():
    return MagicMock()


@pytest.fixture
def mock_pkg_repo():
    return MagicMock()


@pytest.fixture
def mock_file_storage():
    return MagicMock()


@pytest.fixture
def mock_signing_service():
    return MagicMock()


@pytest.fixture
def signer():
    return SignerIdentity(
        iin="123456789012",
        full_name="Test User",
        signer_type=SignerType.INDIVIDUAL,
    )


@pytest.fixture
def legal_signer():
    return SignerIdentity(
        iin="987654321098",
        full_name="Legal User",
        signer_type=SignerType.LEGAL_ENTITY,
        bin="111222333444",
        company_name="Test LLP",
    )


@pytest.fixture
def sample_document():
    return Document(
        id="doc-123",
        title="Test Document",
        filename="test.pdf",
        mime_type="application/pdf",
        file_size=1000,
        file_path="documents/doc-123/test.pdf",
        sha256="abc123",
        status=DocumentStatus.UPLOADED,
        owner_id=1,
    )


class TestUploadDocumentUseCase:
    def test_upload_pdf_success(self, mock_doc_repo, mock_file_storage):
        mock_doc_repo.save.side_effect = lambda d: d
        mock_file_storage.save_file.return_value = "documents/x/test.pdf"

        uc = UploadDocumentUseCase(mock_doc_repo, mock_file_storage)
        result = uc.execute(
            file_data=b"pdf data",
            filename="test.pdf",
            mime_type="application/pdf",
            title="Test Doc",
            owner_id=1,
        )

        assert result.filename == "test.pdf"
        assert result.title == "Test Doc"
        assert result.status == "uploaded"
        mock_file_storage.save_file.assert_called_once()
        mock_doc_repo.save.assert_called_once()

    def test_upload_png_success(self, mock_doc_repo, mock_file_storage):
        mock_doc_repo.save.side_effect = lambda d: d
        uc = UploadDocumentUseCase(mock_doc_repo, mock_file_storage)
        result = uc.execute(
            file_data=b"png data",
            filename="scan.png",
            mime_type="image/png",
            title="Scan",
            owner_id=1,
        )
        assert result.filename == "scan.png"

    def test_upload_unsupported_type_fails(self, mock_doc_repo, mock_file_storage):
        uc = UploadDocumentUseCase(mock_doc_repo, mock_file_storage)
        with pytest.raises(InvalidDocumentError, match="Unsupported file type"):
            uc.execute(
                file_data=b"data",
                filename="test.docx",
                mime_type="application/msword",
                title="Test",
                owner_id=1,
            )

    def test_upload_with_package_id(self, mock_doc_repo, mock_file_storage):
        mock_doc_repo.save.side_effect = lambda d: d
        uc = UploadDocumentUseCase(mock_doc_repo, mock_file_storage)
        result = uc.execute(
            file_data=b"pdf data",
            filename="test.pdf",
            mime_type="application/pdf",
            title="Test",
            owner_id=1,
            package_id="pkg-123",
        )
        assert result.document_id is not None

    def test_sha256_computed(self, mock_doc_repo, mock_file_storage):
        mock_doc_repo.save.side_effect = lambda d: d
        uc = UploadDocumentUseCase(mock_doc_repo, mock_file_storage)
        result = uc.execute(
            file_data=b"test",
            filename="test.pdf",
            mime_type="application/pdf",
            title="Test",
            owner_id=1,
        )
        assert len(result.sha256) == 64  # SHA-256 hex length


class TestInitiateQRSigningUseCase:
    def test_success(self, mock_doc_repo, mock_signing_service, signer, sample_document):
        mock_doc_repo.get_by_id.return_value = sample_document
        mock_doc_repo.update.side_effect = lambda d: d
        mock_signing_service.register_qr_signing.return_value = QRSigningSession(
            qr_code_base64="qr_data",
            data_url="https://sigex.kz/data/123",
            sign_url="https://sigex.kz/sign/123",
            egov_mobile_link="egov://link",
            egov_business_link="egovbiz://link",
        )

        uc = InitiateQRSigningUseCase(mock_doc_repo, mock_signing_service)
        result = uc.execute("doc-123", owner_id=1, signer=signer)

        assert result.qr_code_base64 == "qr_data"
        assert result.egov_mobile_link == "egov://link"
        assert result.egov_business_link == "egovbiz://link"
        assert result.data_url == "https://sigex.kz/data/123"
        assert result.sign_url == "https://sigex.kz/sign/123"
        mock_signing_service.register_qr_signing.assert_called_once()
        # Data is NOT sent during initiation — it's sent during completion
        mock_signing_service.send_data_for_signing.assert_not_called()

    def test_document_not_found(self, mock_doc_repo, mock_signing_service, signer):
        mock_doc_repo.get_by_id.return_value = None
        uc = InitiateQRSigningUseCase(mock_doc_repo, mock_signing_service)
        with pytest.raises(DocumentNotFoundError):
            uc.execute("missing", owner_id=1, signer=signer)

    def test_access_denied(self, mock_doc_repo, mock_signing_service, signer, sample_document):
        sample_document.owner_id = 999  # Different owner
        mock_doc_repo.get_by_id.return_value = sample_document
        uc = InitiateQRSigningUseCase(mock_doc_repo, mock_signing_service)
        with pytest.raises(AccessDeniedError):
            uc.execute("doc-123", owner_id=1, signer=signer)


class TestCompleteQRSigningUseCase:
    def test_success(
        self,
        mock_doc_repo,
        mock_sig_repo,
        mock_file_storage,
        mock_signing_service,
        signer,
        sample_document,
    ):
        mock_doc_repo.get_by_id.return_value = sample_document
        mock_doc_repo.update.side_effect = lambda d: d
        mock_sig_repo.save.side_effect = lambda s: s
        mock_file_storage.read_file.return_value = b"pdf data"
        mock_file_storage.save_file.return_value = "path"
        mock_signing_service.send_data_for_signing.return_value = None
        mock_signing_service.poll_signatures.return_value = ["dGVzdHNpZw=="]
        mock_signing_service.register_document.return_value = "sigex-doc-1"
        mock_signing_service.upload_document_data.return_value = {}

        session = QRSigningSession(
            data_url="https://sigex.kz/data/1",
            sign_url="https://sigex.kz/sign/1",
        )

        uc = CompleteQRSigningUseCase(
            mock_doc_repo, mock_sig_repo, mock_file_storage, mock_signing_service
        )
        result = uc.execute("doc-123", owner_id=1, signer=signer, qr_session=session)

        assert result["status"] == "signed"
        assert result["document_id"] == "doc-123"
        mock_signing_service.send_data_for_signing.assert_called_once()
        mock_signing_service.poll_signatures.assert_called_once()
        mock_sig_repo.save.assert_called_once()


class TestGetDocumentStatusUseCase:
    def test_success(self, mock_doc_repo, mock_sig_repo, sample_document):
        mock_doc_repo.get_by_id.return_value = sample_document
        sig = Signature(
            document_id="doc-123",
            signer_iin="123456789012",
            signer_name="Test",
            status=SignatureStatus.COMPLETED,
        )
        mock_sig_repo.list_by_document.return_value = [sig]

        uc = GetDocumentStatusUseCase(mock_doc_repo, mock_sig_repo)
        result = uc.execute("doc-123", owner_id=1)

        assert result.document_id == "doc-123"
        assert result.status == "uploaded"
        assert len(result.signatures) == 1

    def test_not_found(self, mock_doc_repo, mock_sig_repo):
        mock_doc_repo.get_by_id.return_value = None
        uc = GetDocumentStatusUseCase(mock_doc_repo, mock_sig_repo)
        with pytest.raises(DocumentNotFoundError):
            uc.execute("missing", owner_id=1)


class TestVerifyDocumentUseCase:
    def test_checksum_match(
        self, mock_doc_repo, mock_file_storage, mock_signing_service
    ):
        data = b"test data"
        doc = Document(
            id="doc-1",
            sha256=Document.compute_sha256(data),
            file_path="test.pdf",
            owner_id=1,
        )
        mock_doc_repo.get_by_id.return_value = doc
        mock_file_storage.read_file.return_value = data

        uc = VerifyDocumentUseCase(
            mock_doc_repo, mock_file_storage, mock_signing_service
        )
        result = uc.execute("doc-1", owner_id=1)

        assert result.checksum_match is True
        assert result.verified is True

    def test_checksum_mismatch(
        self, mock_doc_repo, mock_file_storage, mock_signing_service
    ):
        doc = Document(
            id="doc-1",
            sha256="wrong_hash",
            file_path="test.pdf",
            owner_id=1,
        )
        mock_doc_repo.get_by_id.return_value = doc
        mock_file_storage.read_file.return_value = b"test data"

        uc = VerifyDocumentUseCase(
            mock_doc_repo, mock_file_storage, mock_signing_service
        )
        result = uc.execute("doc-1", owner_id=1)

        assert result.checksum_match is False
        assert result.verified is False

    def test_sigex_verification(
        self, mock_doc_repo, mock_file_storage, mock_signing_service
    ):
        data = b"test data"
        doc = Document(
            id="doc-1",
            sha256=Document.compute_sha256(data),
            file_path="test.pdf",
            owner_id=1,
            sigex_document_id="sigex-1",
        )
        mock_doc_repo.get_by_id.return_value = doc
        mock_file_storage.read_file.return_value = data
        mock_signing_service.verify_document.return_value = True

        uc = VerifyDocumentUseCase(
            mock_doc_repo, mock_file_storage, mock_signing_service
        )
        result = uc.execute("doc-1", owner_id=1)

        assert result.sigex_verified is True
        assert result.verified is True


class TestDownloadDocumentUseCase:
    def test_success(self, mock_doc_repo, mock_file_storage, sample_document):
        mock_doc_repo.get_by_id.return_value = sample_document
        mock_file_storage.read_file.return_value = b"file data"

        uc = DownloadDocumentUseCase(mock_doc_repo, mock_file_storage)
        data, filename, mime = uc.execute("doc-123", owner_id=1)

        assert data == b"file data"
        assert filename == "test.pdf"
        assert mime == "application/pdf"

    def test_not_found(self, mock_doc_repo, mock_file_storage):
        mock_doc_repo.get_by_id.return_value = None
        uc = DownloadDocumentUseCase(mock_doc_repo, mock_file_storage)
        with pytest.raises(DocumentNotFoundError):
            uc.execute("missing", owner_id=1)


class TestListDocumentsUseCase:
    def test_returns_list(self, mock_doc_repo, mock_pkg_repo, sample_document):
        mock_doc_repo.list_by_owner.return_value = [sample_document]
        mock_pkg_repo.list_by_owner.return_value = []
        uc = ListDocumentsUseCase(mock_doc_repo, mock_pkg_repo)
        result = uc.execute(owner_id=1)
        assert len(result) == 1
        assert result[0]["id"] == "doc-123"


class TestCreatePackageUseCase:
    def test_success(self, mock_pkg_repo):
        mock_pkg_repo.save.side_effect = lambda p: p
        uc = CreatePackageUseCase(mock_pkg_repo)
        result = uc.execute("Test Package", "Description", owner_id=1)
        assert result["title"] == "Test Package"
        assert result["status"] == "draft"


class TestAddDocumentToPackageUseCase:
    def test_success(self, mock_doc_repo, mock_pkg_repo, sample_document):
        pkg = Package(id="pkg-1", title="Test", owner_id=1)
        mock_pkg_repo.get_by_id.return_value = pkg
        mock_doc_repo.get_by_id.return_value = sample_document
        mock_doc_repo.update.side_effect = lambda d: d

        uc = AddDocumentToPackageUseCase(mock_doc_repo, mock_pkg_repo)
        result = uc.execute("pkg-1", "doc-123", owner_id=1)
        assert result["status"] == "added"

    def test_package_not_found(self, mock_doc_repo, mock_pkg_repo):
        mock_pkg_repo.get_by_id.return_value = None
        uc = AddDocumentToPackageUseCase(mock_doc_repo, mock_pkg_repo)
        with pytest.raises(PackageNotFoundError):
            uc.execute("missing", "doc-1", owner_id=1)


class TestListPackagesUseCase:
    def test_returns_list(self, mock_pkg_repo):
        pkg = Package(id="pkg-1", title="Test", owner_id=1)
        mock_pkg_repo.list_by_owner.return_value = [pkg]
        uc = ListPackagesUseCase(mock_pkg_repo)
        result = uc.execute(owner_id=1)
        assert len(result) == 1
        assert result[0]["id"] == "pkg-1"


class TestCompletePackageQRSigningUseCase:
    @pytest.fixture
    def _setup(
        self,
        mock_doc_repo,
        mock_sig_repo,
        mock_pkg_repo,
        mock_file_storage,
        mock_signing_service,
    ):
        self.doc1 = Document(
            id="doc-1", title="Doc 1", filename="doc1.pdf",
            mime_type="application/pdf", file_path="documents/doc-1/doc1.pdf",
            owner_id=1,
        )
        self.doc2 = Document(
            id="doc-2", title="Doc 2", filename="doc2.pdf",
            mime_type="application/pdf", file_path="documents/doc-2/doc2.pdf",
            owner_id=1,
        )
        self.pkg = Package(
            id="pkg-1", title="Test Pkg", owner_id=1,
            document_ids=["doc-1", "doc-2"],
        )
        mock_pkg_repo.get_by_id.return_value = self.pkg
        mock_doc_repo.get_by_id.side_effect = lambda did: {
            "doc-1": self.doc1, "doc-2": self.doc2,
        }.get(did)
        mock_doc_repo.update.side_effect = lambda d: d
        mock_sig_repo.save.side_effect = lambda s: s
        mock_file_storage.read_file.return_value = b"pdf data"
        mock_file_storage.save_file.return_value = "path"
        mock_signing_service.send_data_for_signing.return_value = None
        mock_signing_service.poll_signatures.return_value = [
            "dGVzdHNpZw==", "dGVzdHNpZw==",
        ]
        mock_signing_service.register_document.return_value = "sigex-1"
        mock_signing_service.upload_document_data.return_value = {}
        self.session = QRSigningSession(
            data_url="https://sigex.kz/data/1",
            sign_url="https://sigex.kz/sign/1",
        )

    @pytest.mark.usefixtures("_setup")
    def test_all_documents_signed(
        self, mock_doc_repo, mock_sig_repo, mock_pkg_repo,
        mock_file_storage, mock_signing_service, signer,
    ):
        uc = CompletePackageQRSigningUseCase(
            mock_doc_repo, mock_sig_repo, mock_pkg_repo,
            mock_file_storage, mock_signing_service,
        )
        result = uc.execute(
            "pkg-1", owner_id=1, signer=signer, qr_session=self.session,
        )
        assert result["status"] == "signed"
        assert len(result["documents"]) == 2
        assert all("document_id" in d for d in result["documents"])

    @pytest.mark.usefixtures("_setup")
    def test_partial_failure_marks_partially_signed(
        self, mock_doc_repo, mock_sig_repo, mock_pkg_repo,
        mock_file_storage, mock_signing_service, signer,
    ):
        # First doc registers fine, second fails
        mock_signing_service.register_document.side_effect = [
            "sigex-1",
            SigningError("Sigex registration error"),
        ]
        uc = CompletePackageQRSigningUseCase(
            mock_doc_repo, mock_sig_repo, mock_pkg_repo,
            mock_file_storage, mock_signing_service,
        )
        result = uc.execute(
            "pkg-1", owner_id=1, signer=signer, qr_session=self.session,
        )
        assert result["status"] == "partially_signed"
        signed = [d for d in result["documents"] if d.get("sigex_document_id")]
        failed = [d for d in result["documents"] if d.get("status") == "failed"]
        assert len(signed) == 1
        assert len(failed) == 1

    @pytest.mark.usefixtures("_setup")
    def test_all_documents_fail_marks_package_failed(
        self, mock_doc_repo, mock_sig_repo, mock_pkg_repo,
        mock_file_storage, mock_signing_service, signer,
    ):
        mock_signing_service.register_document.side_effect = SigningError("fail")
        uc = CompletePackageQRSigningUseCase(
            mock_doc_repo, mock_sig_repo, mock_pkg_repo,
            mock_file_storage, mock_signing_service,
        )
        result = uc.execute(
            "pkg-1", owner_id=1, signer=signer, qr_session=self.session,
        )
        assert result["status"] == "failed"

    @pytest.mark.usefixtures("_setup")
    def test_sigex_poll_failure_raises(
        self, mock_doc_repo, mock_sig_repo, mock_pkg_repo,
        mock_file_storage, mock_signing_service, signer,
    ):
        mock_signing_service.poll_signatures.side_effect = SigningError("timeout")
        uc = CompletePackageQRSigningUseCase(
            mock_doc_repo, mock_sig_repo, mock_pkg_repo,
            mock_file_storage, mock_signing_service,
        )
        with pytest.raises(SigningError):
            uc.execute(
                "pkg-1", owner_id=1, signer=signer, qr_session=self.session,
            )

    def test_package_not_found(
        self, mock_doc_repo, mock_sig_repo, mock_pkg_repo,
        mock_file_storage, mock_signing_service, signer,
    ):
        mock_pkg_repo.get_by_id.return_value = None
        uc = CompletePackageQRSigningUseCase(
            mock_doc_repo, mock_sig_repo, mock_pkg_repo,
            mock_file_storage, mock_signing_service,
        )
        with pytest.raises(PackageNotFoundError):
            uc.execute(
                "missing", owner_id=1, signer=signer,
                qr_session=QRSigningSession(),
            )

    def test_access_denied(
        self, mock_doc_repo, mock_sig_repo, mock_pkg_repo,
        mock_file_storage, mock_signing_service, signer,
    ):
        pkg = Package(id="pkg-1", title="Test", owner_id=999)
        mock_pkg_repo.get_by_id.return_value = pkg
        uc = CompletePackageQRSigningUseCase(
            mock_doc_repo, mock_sig_repo, mock_pkg_repo,
            mock_file_storage, mock_signing_service,
        )
        with pytest.raises(AccessDeniedError):
            uc.execute(
                "pkg-1", owner_id=1, signer=signer,
                qr_session=QRSigningSession(),
            )


class TestDownloadSignatureUseCase:
    def test_success(self, mock_doc_repo, mock_file_storage):
        doc = Document(
            id="doc-1", title="Test", filename="test.pdf",
            owner_id=1, signature_file_path="documents/doc-1/signatures/sig.cms",
        )
        mock_doc_repo.get_by_id.return_value = doc
        mock_file_storage.read_file.return_value = b"cms-data"

        uc = DownloadSignatureUseCase(mock_doc_repo, mock_file_storage)
        data, filename = uc.execute("doc-1", owner_id=1)

        assert data == b"cms-data"
        assert filename == "test.pdf.cms"

    def test_not_found(self, mock_doc_repo, mock_file_storage):
        mock_doc_repo.get_by_id.return_value = None
        uc = DownloadSignatureUseCase(mock_doc_repo, mock_file_storage)
        with pytest.raises(DocumentNotFoundError):
            uc.execute("missing", owner_id=1)

    def test_no_signature_available(self, mock_doc_repo, mock_file_storage):
        doc = Document(id="doc-1", owner_id=1, signature_file_path=None)
        mock_doc_repo.get_by_id.return_value = doc
        uc = DownloadSignatureUseCase(mock_doc_repo, mock_file_storage)
        with pytest.raises(DocumentNotFoundError, match="Signature not available"):
            uc.execute("doc-1", owner_id=1)

    def test_access_denied(self, mock_doc_repo, mock_file_storage):
        doc = Document(
            id="doc-1", owner_id=999,
            signature_file_path="documents/doc-1/signatures/sig.cms",
        )
        mock_doc_repo.get_by_id.return_value = doc
        uc = DownloadSignatureUseCase(mock_doc_repo, mock_file_storage)
        with pytest.raises(AccessDeniedError):
            uc.execute("doc-1", owner_id=1)


class TestDownloadSignedPackageUseCase:
    def test_zip_contains_signed_documents(
        self, mock_doc_repo, mock_pkg_repo, mock_file_storage,
    ):
        import zipfile as zf
        import io

        pkg = Package(
            id="pkg-1", title="Test", owner_id=1,
            document_ids=["doc-1", "doc-2"],
        )
        doc1 = Document(
            id="doc-1", title="Doc 1", filename="doc1.pdf",
            file_path="documents/doc-1/doc1.pdf", owner_id=1,
            status=DocumentStatus.SIGNED,
            signature_file_path="documents/doc-1/signatures/s1.cms",
        )
        doc2 = Document(
            id="doc-2", title="Doc 2", filename="doc2.pdf",
            file_path="documents/doc-2/doc2.pdf", owner_id=1,
            status=DocumentStatus.SIGNED,
            signature_file_path="documents/doc-2/signatures/s2.cms",
        )
        mock_pkg_repo.get_by_id.return_value = pkg
        mock_doc_repo.get_by_id.side_effect = lambda did: {
            "doc-1": doc1, "doc-2": doc2,
        }[did]
        mock_file_storage.read_file.side_effect = lambda path: {
            "documents/doc-1/doc1.pdf": b"pdf1",
            "documents/doc-2/doc2.pdf": b"pdf2",
            "documents/doc-1/signatures/s1.cms": b"sig1",
            "documents/doc-2/signatures/s2.cms": b"sig2",
        }[path]

        uc = DownloadSignedPackageUseCase(
            mock_doc_repo, mock_pkg_repo, mock_file_storage,
        )
        zip_bytes, zip_filename = uc.execute("pkg-1", owner_id=1)

        assert zip_filename == "package_pkg-1_signed.zip"

        with zf.ZipFile(io.BytesIO(zip_bytes)) as z:
            names = z.namelist()
            assert "originals/doc1.pdf" in names
            assert "originals/doc2.pdf" in names
            assert "signatures/doc1.pdf.cms" in names
            assert "signatures/doc2.pdf.cms" in names
            assert z.read("originals/doc1.pdf") == b"pdf1"
            assert z.read("signatures/doc1.pdf.cms") == b"sig1"

    def test_zip_excludes_failed_documents(
        self, mock_doc_repo, mock_pkg_repo, mock_file_storage,
    ):
        import zipfile as zf
        import io

        pkg = Package(
            id="pkg-1", title="Test", owner_id=1,
            document_ids=["doc-1", "doc-2"],
        )
        doc1 = Document(
            id="doc-1", title="Doc 1", filename="doc1.pdf",
            file_path="documents/doc-1/doc1.pdf", owner_id=1,
            status=DocumentStatus.SIGNED,
            signature_file_path="documents/doc-1/signatures/s1.cms",
        )
        doc2 = Document(
            id="doc-2", title="Doc 2", filename="doc2.pdf",
            file_path="documents/doc-2/doc2.pdf", owner_id=1,
            status=DocumentStatus.FAILED,
        )
        mock_pkg_repo.get_by_id.return_value = pkg
        mock_doc_repo.get_by_id.side_effect = lambda did: {
            "doc-1": doc1, "doc-2": doc2,
        }[did]
        mock_file_storage.read_file.side_effect = lambda path: {
            "documents/doc-1/doc1.pdf": b"pdf1",
            "documents/doc-1/signatures/s1.cms": b"sig1",
        }[path]

        uc = DownloadSignedPackageUseCase(
            mock_doc_repo, mock_pkg_repo, mock_file_storage,
        )
        zip_bytes, _ = uc.execute("pkg-1", owner_id=1)

        with zf.ZipFile(io.BytesIO(zip_bytes)) as z:
            names = z.namelist()
            assert "originals/doc1.pdf" in names
            assert "originals/doc2.pdf" not in names

    def test_package_not_found(
        self, mock_doc_repo, mock_pkg_repo, mock_file_storage,
    ):
        mock_pkg_repo.get_by_id.return_value = None
        uc = DownloadSignedPackageUseCase(
            mock_doc_repo, mock_pkg_repo, mock_file_storage,
        )
        with pytest.raises(PackageNotFoundError):
            uc.execute("missing", owner_id=1)

    def test_access_denied(
        self, mock_doc_repo, mock_pkg_repo, mock_file_storage,
    ):
        pkg = Package(id="pkg-1", title="Test", owner_id=999)
        mock_pkg_repo.get_by_id.return_value = pkg
        uc = DownloadSignedPackageUseCase(
            mock_doc_repo, mock_pkg_repo, mock_file_storage,
        )
        with pytest.raises(AccessDeniedError):
            uc.execute("pkg-1", owner_id=1)
