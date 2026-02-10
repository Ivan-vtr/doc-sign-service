class DomainError(Exception):
    """Base domain error."""


class DocumentNotFoundError(DomainError):
    def __init__(self, document_id: str):
        super().__init__(f"Document not found: {document_id}")
        self.document_id = document_id


class PackageNotFoundError(DomainError):
    def __init__(self, package_id: str):
        super().__init__(f"Package not found: {package_id}")
        self.package_id = package_id


class SigningError(DomainError):
    """Error during signing operation."""


class SigningTimeoutError(SigningError):
    """Signing operation timed out (user did not sign in time)."""


class SigningCancelledError(SigningError):
    """Signing operation was cancelled."""


class VerificationError(DomainError):
    """Error during signature verification."""


class FileStorageError(DomainError):
    """Error during file storage operations."""


class InvalidDocumentError(DomainError):
    """Document data is invalid."""


class AccessDeniedError(DomainError):
    """User does not have access to this resource."""


class UserAlreadyExistsError(DomainError):
    """User with this username already exists."""
