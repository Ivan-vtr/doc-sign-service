from rest_framework import serializers


class UserRegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=False, default="")
    iin = serializers.CharField(max_length=12, min_length=12)
    full_name = serializers.CharField(max_length=255)
    signer_type = serializers.ChoiceField(
        choices=["individual", "legal_entity"], default="individual"
    )
    bin = serializers.CharField(max_length=12, min_length=12, required=False, default="")
    company_name = serializers.CharField(max_length=255, required=False, default="")


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    title = serializers.CharField(max_length=255)
    package_id = serializers.UUIDField(required=False, allow_null=True)


class MultiDocumentUploadSerializer(serializers.Serializer):
    files = serializers.ListField(child=serializers.FileField(), min_length=1)
    title = serializers.CharField(max_length=255)
    package_id = serializers.UUIDField(required=False, allow_null=True)


class InitiateSigningSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()


class InitiatePackageSigningSerializer(serializers.Serializer):
    package_id = serializers.UUIDField()


class CompleteSigningSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()
    session_id = serializers.CharField()
    data_url = serializers.URLField()
    sign_url = serializers.URLField()


class CompletePackageSigningSerializer(serializers.Serializer):
    package_id = serializers.UUIDField()
    session_id = serializers.CharField()
    data_url = serializers.URLField()
    sign_url = serializers.URLField()


class PackageCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, default="")


class PackageAddDocumentSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()


class DocumentResponseSerializer(serializers.Serializer):
    id = serializers.CharField()
    title = serializers.CharField()
    filename = serializers.CharField()
    mime_type = serializers.CharField()
    file_size = serializers.IntegerField()
    sha256 = serializers.CharField()
    status = serializers.CharField()
    sigex_document_id = serializers.CharField(allow_null=True)
    package_id = serializers.CharField(allow_null=True)
    created_at = serializers.CharField(allow_null=True)


class SignatureResponseSerializer(serializers.Serializer):
    id = serializers.CharField()
    signer_name = serializers.CharField()
    signer_iin = serializers.CharField()
    signer_type = serializers.CharField()
    status = serializers.CharField()
    signed_at = serializers.CharField(allow_null=True)


class QRSigningResponseSerializer(serializers.Serializer):
    session_id = serializers.CharField()
    document_id = serializers.CharField()
    qr_code_base64 = serializers.CharField()
    egov_mobile_link = serializers.CharField()
    egov_business_link = serializers.CharField()
    data_url = serializers.URLField()
    sign_url = serializers.URLField()


class VerificationResponseSerializer(serializers.Serializer):
    document_id = serializers.CharField()
    verified = serializers.BooleanField()
    checksum_match = serializers.BooleanField()
    sigex_verified = serializers.BooleanField()


class UserProfileSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.CharField()
    iin = serializers.CharField()
    full_name = serializers.CharField()
    signer_type = serializers.CharField()
    bin = serializers.CharField(allow_blank=True)
    company_name = serializers.CharField(allow_blank=True)
