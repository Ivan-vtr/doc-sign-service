from __future__ import annotations

import logging

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.application.use_cases import (
    AddDocumentToPackageUseCase,
    CompletePackageQRSigningUseCase,
    CompleteQRSigningUseCase,
    CreatePackageUseCase,
    DownloadDocumentUseCase,
    DownloadSignatureUseCase,
    DownloadSignedDocumentUseCase,
    DownloadSignedPackageUseCase,
    GetDocumentStatusUseCase,
    InitiatePackageQRSigningUseCase,
    InitiateQRSigningUseCase,
    ListDocumentsUseCase,
    ListPackagesUseCase,
    RegisterUserUseCase,
    UploadDocumentUseCase,
    VerifyDocumentUseCase,
)
from app.domain.entities import QRSigningSession, SignerIdentity, SignerType
from app.domain.exceptions import (
    AccessDeniedError,
    DocumentNotFoundError,
    DomainError,
    InvalidDocumentError,
    PackageNotFoundError,
    SigningError,
    UserAlreadyExistsError,
    VerificationError,
)
from app.infrastructure.container import (
    get_document_repository,
    get_file_storage,
    get_package_repository,
    get_signature_repository,
    get_signing_service,
    get_user_repository,
)
from app.infrastructure.persistence.models import UserProfile
from app.interfaces.api.serializers import (
    CompletePackageSigningSerializer,
    CompleteSigningSerializer,
    DocumentUploadSerializer,
    InitiatePackageSigningSerializer,
    InitiateSigningSerializer,
    LoginSerializer,
    PackageAddDocumentSerializer,
    PackageCreateSerializer,
    UserRegistrationSerializer,
)

logger = logging.getLogger(__name__)


def _get_signer_identity(user: User) -> SignerIdentity:
    """Build SignerIdentity from the user's profile."""
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        raise DomainError("User profile not configured. Please update your profile.")

    return SignerIdentity(
        iin=profile.iin,
        full_name=profile.full_name,
        signer_type=SignerType(profile.signer_type),
        bin=profile.bin or None,
        company_name=profile.company_name or None,
    )


def _error_response(exc: Exception) -> tuple[dict, int]:
    """Map domain exceptions to HTTP status codes."""
    if isinstance(exc, (DocumentNotFoundError, PackageNotFoundError)):
        return {"error": str(exc)}, status.HTTP_404_NOT_FOUND
    if isinstance(exc, AccessDeniedError):
        return {"error": str(exc)}, status.HTTP_403_FORBIDDEN
    if isinstance(exc, InvalidDocumentError):
        return {"error": str(exc)}, status.HTTP_400_BAD_REQUEST
    if isinstance(exc, VerificationError):
        return {"error": str(exc)}, status.HTTP_422_UNPROCESSABLE_ENTITY
    if isinstance(exc, SigningError):
        return {"status": "failed", "error": str(exc)}, status.HTTP_400_BAD_REQUEST
    if isinstance(exc, DomainError):
        return {"error": str(exc)}, status.HTTP_400_BAD_REQUEST
    return {"error": "Internal server error"}, status.HTTP_500_INTERNAL_SERVER_ERROR


# ── Auth Views ───────────────────────────────────────────────────────


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            use_case = RegisterUserUseCase(get_user_repository())
            result = use_case.execute(
                username=data["username"],
                password=data["password"],
                email=data.get("email", ""),
                iin=data["iin"],
                full_name=data["full_name"],
                signer_type=data.get("signer_type", "individual"),
                bin=data.get("bin", ""),
                company_name=data.get("company_name", ""),
            )
        except UserAlreadyExistsError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_409_CONFLICT
            )
        except InvalidDocumentError as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(result, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if not user:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        return Response({"username": user.username, "id": user.id})


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({"detail": "Logged out"})


class ProfileView(APIView):
    def get(self, request):
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        return Response({
            "username": request.user.username,
            "email": request.user.email,
            "iin": profile.iin,
            "full_name": profile.full_name,
            "signer_type": profile.signer_type,
            "bin": profile.bin,
            "company_name": profile.company_name,
        })


# ── Document Views ───────────────────────────────────────────────────


class DocumentListView(APIView):
    def get(self, request):
        use_case = ListDocumentsUseCase(get_document_repository(), get_package_repository())
        docs = use_case.execute(request.user.id)
        return Response(docs)


class DocumentUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data["file"]
        file_data = uploaded_file.read()

        use_case = UploadDocumentUseCase(
            get_document_repository(), get_file_storage()
        )

        try:
            result = use_case.execute(
                file_data=file_data,
                filename=uploaded_file.name,
                mime_type=uploaded_file.content_type,
                title=serializer.validated_data["title"],
                owner_id=request.user.id,
                package_id=str(serializer.validated_data["package_id"])
                if serializer.validated_data.get("package_id")
                else None,
            )
        except DomainError as e:
            body, code = _error_response(e)
            return Response(body, status=code)

        return Response(
            {
                "document_id": result.document_id,
                "title": result.title,
                "filename": result.filename,
                "sha256": result.sha256,
                "status": result.status,
            },
            status=status.HTTP_201_CREATED,
        )


class MultiDocumentUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        files = request.FILES.getlist("files")
        title = request.data.get("title", "")
        package_id = request.data.get("package_id")

        if not files:
            return Response(
                {"error": "No files provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        use_case = UploadDocumentUseCase(
            get_document_repository(), get_file_storage()
        )

        results = []
        for f in files:
            try:
                result = use_case.execute(
                    file_data=f.read(),
                    filename=f.name,
                    mime_type=f.content_type,
                    title=title or f.name,
                    owner_id=request.user.id,
                    package_id=str(package_id) if package_id else None,
                )
                results.append({
                    "document_id": result.document_id,
                    "title": result.title,
                    "filename": result.filename,
                    "sha256": result.sha256,
                    "status": result.status,
                })
            except DomainError as e:
                results.append({"filename": f.name, "error": str(e)})

        return Response({"documents": results}, status=status.HTTP_201_CREATED)


class DocumentDetailView(APIView):
    def get(self, request, document_id):
        use_case = GetDocumentStatusUseCase(
            get_document_repository(), get_signature_repository()
        )
        try:
            result = use_case.execute(str(document_id), request.user.id)
        except DomainError as e:
            body, code = _error_response(e)
            return Response(body, status=code)

        return Response({
            "document_id": result.document_id,
            "status": result.status,
            "signatures": result.signatures,
        })


class DocumentDownloadView(APIView):
    def get(self, request, document_id):
        use_case = DownloadDocumentUseCase(
            get_document_repository(), get_file_storage()
        )
        try:
            file_data, filename, mime_type = use_case.execute(
                str(document_id), request.user.id
            )
        except DomainError as e:
            body, code = _error_response(e)
            return Response(body, status=code)

        response = HttpResponse(file_data, content_type=mime_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class DocumentDownloadSignedView(APIView):
    def get(self, request, document_id):
        use_case = DownloadSignedDocumentUseCase(
            get_document_repository(), get_file_storage()
        )
        try:
            file_data, filename, mime_type = use_case.execute(
                str(document_id), request.user.id
            )
        except DomainError as e:
            body, code = _error_response(e)
            return Response(body, status=code)

        response = HttpResponse(file_data, content_type=mime_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class DocumentVerifyView(APIView):
    def post(self, request, document_id):
        use_case = VerifyDocumentUseCase(
            get_document_repository(), get_file_storage(), get_signing_service()
        )
        try:
            result = use_case.execute(str(document_id), request.user.id)
        except DomainError as e:
            body, code = _error_response(e)
            return Response(body, status=code)

        return Response({
            "document_id": result.document_id,
            "verified": result.verified,
            "checksum_match": result.checksum_match,
            "sigex_verified": result.sigex_verified,
        })


# ── Signing Views ────────────────────────────────────────────────────


class InitiateSigningView(APIView):
    def post(self, request):
        serializer = InitiateSigningSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            signer = _get_signer_identity(request.user)
            use_case = InitiateQRSigningUseCase(
                get_document_repository(),
                get_signing_service(),
            )
            result = use_case.execute(
                document_id=str(serializer.validated_data["document_id"]),
                owner_id=request.user.id,
                signer=signer,
            )
        except DomainError as e:
            body, code = _error_response(e)
            return Response(body, status=code)

        return Response({
            "session_id": result.session_id,
            "document_id": result.document_id,
            "qr_code_base64": result.qr_code_base64,
            "egov_mobile_link": result.egov_mobile_link,
            "egov_business_link": result.egov_business_link,
            "data_url": result.data_url,
            "sign_url": result.sign_url,
        })


class CompleteSigningView(APIView):
    def post(self, request):
        serializer = CompleteSigningSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        qr_session = QRSigningSession(
            id=data["session_id"],
            data_url=data["data_url"],
            sign_url=data["sign_url"],
        )

        try:
            signer = _get_signer_identity(request.user)
            use_case = CompleteQRSigningUseCase(
                get_document_repository(),
                get_signature_repository(),
                get_file_storage(),
                get_signing_service(),
            )
            result = use_case.execute(
                document_id=str(data["document_id"]),
                owner_id=request.user.id,
                signer=signer,
                qr_session=qr_session,
            )
        except DomainError as e:
            body, code = _error_response(e)
            return Response(body, status=code)

        return Response(result)


# ── Package Views ────────────────────────────────────────────────────


class PackageListView(APIView):
    def get(self, request):
        use_case = ListPackagesUseCase(get_package_repository())
        result = use_case.execute(request.user.id)
        return Response(result)


class PackageCreateView(APIView):
    def post(self, request):
        serializer = PackageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        use_case = CreatePackageUseCase(get_package_repository())
        result = use_case.execute(
            title=serializer.validated_data["title"],
            description=serializer.validated_data.get("description", ""),
            owner_id=request.user.id,
        )
        return Response(result, status=status.HTTP_201_CREATED)


class PackageAddDocumentView(APIView):
    def post(self, request, package_id):
        serializer = PackageAddDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        use_case = AddDocumentToPackageUseCase(
            get_document_repository(), get_package_repository()
        )
        try:
            result = use_case.execute(
                package_id=str(package_id),
                document_id=str(serializer.validated_data["document_id"]),
                owner_id=request.user.id,
            )
        except DomainError as e:
            body, code = _error_response(e)
            return Response(body, status=code)

        return Response(result)


class InitiatePackageSigningView(APIView):
    def post(self, request):
        serializer = InitiatePackageSigningSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            signer = _get_signer_identity(request.user)
            use_case = InitiatePackageQRSigningUseCase(
                get_document_repository(),
                get_package_repository(),
                get_signing_service(),
            )
            result = use_case.execute(
                package_id=str(serializer.validated_data["package_id"]),
                owner_id=request.user.id,
                signer=signer,
            )
        except DomainError as e:
            body, code = _error_response(e)
            return Response(body, status=code)

        return Response({
            "session_id": result.session_id,
            "document_id": result.document_id,
            "qr_code_base64": result.qr_code_base64,
            "egov_mobile_link": result.egov_mobile_link,
            "egov_business_link": result.egov_business_link,
            "data_url": result.data_url,
            "sign_url": result.sign_url,
        })


class CompletePackageSigningView(APIView):
    def post(self, request):
        serializer = CompletePackageSigningSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        qr_session = QRSigningSession(
            id=data["session_id"],
            data_url=data["data_url"],
            sign_url=data["sign_url"],
        )

        try:
            signer = _get_signer_identity(request.user)
            use_case = CompletePackageQRSigningUseCase(
                get_document_repository(),
                get_signature_repository(),
                get_package_repository(),
                get_file_storage(),
                get_signing_service(),
            )
            result = use_case.execute(
                package_id=str(data["package_id"]),
                owner_id=request.user.id,
                signer=signer,
                qr_session=qr_session,
            )
        except DomainError as e:
            body, code = _error_response(e)
            return Response(body, status=code)

        return Response(result)


class DocumentDownloadSignatureView(APIView):
    def get(self, request, document_id):
        use_case = DownloadSignatureUseCase(
            get_document_repository(), get_file_storage()
        )
        try:
            sig_data, filename = use_case.execute(
                str(document_id), request.user.id
            )
        except DomainError as e:
            body, code = _error_response(e)
            return Response(body, status=code)

        response = HttpResponse(sig_data, content_type="application/pkcs7-signature")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class PackageDownloadSignedView(APIView):
    def get(self, request, package_id):
        use_case = DownloadSignedPackageUseCase(
            get_document_repository(),
            get_package_repository(),
            get_file_storage(),
        )
        try:
            zip_data, zip_filename = use_case.execute(
                str(package_id), request.user.id
            )
        except DomainError as e:
            body, code = _error_response(e)
            return Response(body, status=code)

        response = HttpResponse(zip_data, content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{zip_filename}"'
        return response
