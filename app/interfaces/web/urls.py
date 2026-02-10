from django.urls import path

from app.interfaces.web import views

urlpatterns = [
    path("", views.dashboard_view, name="web-dashboard"),
    path("login/", views.login_view, name="web-login"),
    path("logout/", views.logout_view, name="web-logout"),
    path("register/", views.register_view, name="web-register"),
    path("upload/", views.upload_view, name="web-upload"),
    path(
        "documents/<uuid:document_id>/",
        views.document_detail_view,
        name="web-document-detail",
    ),
    path(
        "documents/<uuid:document_id>/sign/",
        views.signing_view,
        name="web-signing",
    ),
    path("packages/", views.packages_view, name="web-packages"),
    path(
        "packages/<uuid:package_id>/",
        views.package_detail_view,
        name="web-package-detail",
    ),
    path(
        "packages/<uuid:package_id>/sign/",
        views.package_signing_view,
        name="web-package-signing",
    ),
]
