from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """Extended user profile with IIN/BIN data for signing."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    iin = models.CharField(max_length=12)
    full_name = models.CharField(max_length=255)
    signer_type = models.CharField(
        max_length=20,
        choices=[("individual", "Individual"), ("legal_entity", "Legal Entity")],
        default="individual",
    )
    bin = models.CharField(max_length=12, blank=True, default="")
    company_name = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        app_label = "persistence"

    def __str__(self):
        if self.signer_type == "legal_entity":
            return f"{self.full_name} ({self.company_name})"
        return self.full_name


class DocumentModel(models.Model):
    STATUS_CHOICES = [
        ("uploaded", "Uploaded"),
        ("registered", "Registered"),
        ("signing", "Signing"),
        ("signed", "Signed"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True)
    title = models.CharField(max_length=255)
    filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    file_size = models.BigIntegerField(default=0)
    file_path = models.CharField(max_length=500)
    sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="uploaded")
    sigex_document_id = models.CharField(max_length=255, blank=True, null=True)
    signed_file_path = models.CharField(max_length=500, blank=True, null=True)
    signature_file_path = models.CharField(max_length=500, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    package = models.ForeignKey(
        "PackageModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "persistence"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class SignatureModel(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]
    SIGNER_TYPE_CHOICES = [
        ("individual", "Individual"),
        ("legal_entity", "Legal Entity"),
    ]

    id = models.UUIDField(primary_key=True)
    document = models.ForeignKey(
        DocumentModel, on_delete=models.CASCADE, related_name="signatures"
    )
    signer_iin = models.CharField(max_length=12)
    signer_name = models.CharField(max_length=255)
    signer_type = models.CharField(
        max_length=20, choices=SIGNER_TYPE_CHOICES, default="individual"
    )
    signer_bin = models.CharField(max_length=12, blank=True, null=True)
    signer_company = models.CharField(max_length=255, blank=True, null=True)
    signature_data = models.TextField(blank=True, default="")
    sigex_sign_id = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    signed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "persistence"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Signature by {self.signer_name} on {self.document.title}"


class PackageModel(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("signing", "Signing"),
        ("signed", "Signed"),
        ("partially_signed", "Partially Signed"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="packages",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "persistence"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
