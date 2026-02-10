from django.urls import path

from app.interfaces.api.views import (
    CompletePackageSigningView,
    CompleteSigningView,
    DocumentDetailView,
    DocumentDownloadSignatureView,
    DocumentDownloadSignedView,
    DocumentDownloadView,
    DocumentListView,
    DocumentUploadView,
    DocumentVerifyView,
    InitiatePackageSigningView,
    InitiateSigningView,
    LoginView,
    LogoutView,
    MultiDocumentUploadView,
    PackageAddDocumentView,
    PackageCreateView,
    PackageDownloadSignedView,
    PackageListView,
    ProfileView,
    RegisterView,
)

urlpatterns = [
    # Auth
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/profile/", ProfileView.as_view(), name="profile"),
    # Documents
    path("documents/", DocumentListView.as_view(), name="document-list"),
    path("documents/upload/", DocumentUploadView.as_view(), name="document-upload"),
    path(
        "documents/upload-multiple/",
        MultiDocumentUploadView.as_view(),
        name="document-upload-multiple",
    ),
    path(
        "documents/<uuid:document_id>/",
        DocumentDetailView.as_view(),
        name="document-detail",
    ),
    path(
        "documents/<uuid:document_id>/download/",
        DocumentDownloadView.as_view(),
        name="document-download",
    ),
    path(
        "documents/<uuid:document_id>/download/original/",
        DocumentDownloadView.as_view(),
        name="document-download-original",
    ),
    path(
        "documents/<uuid:document_id>/download/signature/",
        DocumentDownloadSignatureView.as_view(),
        name="document-download-signature",
    ),
    path(
        "documents/<uuid:document_id>/download-signed/",
        DocumentDownloadSignedView.as_view(),
        name="document-download-signed",
    ),
    path(
        "documents/<uuid:document_id>/verify/",
        DocumentVerifyView.as_view(),
        name="document-verify",
    ),
    # Signing
    path("signing/initiate/", InitiateSigningView.as_view(), name="signing-initiate"),
    path("signing/complete/", CompleteSigningView.as_view(), name="signing-complete"),
    # Package signing
    path(
        "signing/package/initiate/",
        InitiatePackageSigningView.as_view(),
        name="package-signing-initiate",
    ),
    path(
        "signing/package/complete/",
        CompletePackageSigningView.as_view(),
        name="package-signing-complete",
    ),
    # Packages
    path("packages/", PackageListView.as_view(), name="package-list"),
    path("packages/create/", PackageCreateView.as_view(), name="package-create"),
    path(
        "packages/<uuid:package_id>/add-document/",
        PackageAddDocumentView.as_view(),
        name="package-add-document",
    ),
    path(
        "packages/<uuid:package_id>/download-signed/",
        PackageDownloadSignedView.as_view(),
        name="package-download-signed",
    ),
]
