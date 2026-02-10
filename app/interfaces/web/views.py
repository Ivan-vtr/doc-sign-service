from __future__ import annotations

import logging

from collections import defaultdict
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from app.application.use_cases import (
    AddDocumentToPackageUseCase,
    CreatePackageUseCase,
    GetDocumentStatusUseCase,
    ListDocumentsUseCase,
    ListPackagesUseCase,
    RegisterUserUseCase,
)
from app.domain.exceptions import DomainError
from app.infrastructure.container import (
    get_document_repository,
    get_package_repository,
    get_signature_repository,
    get_user_repository,
)
import locale

logger = logging.getLogger(__name__)
locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")


# ── Auth Views ───────────────────────────────────────────────────────


def login_view(request):
    if request.user.is_authenticated:
        return redirect("web-dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            messages.error(request, "Пожалуйста, заполните все поля.")
            return render(request, "web/login.html")

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            next_url = request.GET.get("next", "/")
            return redirect(next_url)
        else:
            messages.error(request, "Неверное имя пользователя или пароль.")

    return render(request, "web/login.html")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("web-dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        email = request.POST.get("email", "").strip()
        iin = request.POST.get("iin", "").strip()
        full_name = request.POST.get("full_name", "").strip()
        signer_type = request.POST.get("signer_type", "individual")
        bin_number = request.POST.get("bin", "").strip()
        company_name = request.POST.get("company_name", "").strip()

        try:
            use_case = RegisterUserUseCase(get_user_repository())
            result = use_case.execute(
                username=username,
                password=password,
                email=email,
                iin=iin,
                full_name=full_name,
                signer_type=signer_type,
                bin=bin_number,
                company_name=company_name,
            )
        except (DomainError,) as e:
            messages.error(request, str(e))
            return render(request, "web/register.html", {
                "form_data": request.POST,
            })

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
        messages.success(request, "Регистрация прошла успешно!")
        return redirect("web-dashboard")

    return render(request, "web/register.html")


def logout_view(request):
    if request.method == "POST":
        logout(request)
    return redirect("web-login")


# ── Dashboard ────────────────────────────────────────────────────────


@login_required
def dashboard_view(request):
    use_case = ListDocumentsUseCase(get_document_repository(), get_package_repository())
    documents = use_case.execute(request.user.id)

    grouped_packages = defaultdict(list)
    ungrouped_documents = []

    for doc in documents:
        created_at_str = doc.get("created_at")
        if created_at_str:
            try:
                # Конвертируем строку в datetime
                created_at_dt = datetime.fromisoformat(created_at_str)
                # Форматируем дату и время
                doc["created_at_formatted"] = created_at_dt.strftime("%-d %B %Y года, %H:%M")
            except ValueError:
                doc["created_at_formatted"] = created_at_str  # оставляем как есть, если не получилось
        else:
            doc["created_at_formatted"] = ""

        package_id = doc.get("package_id")
        if package_id:
            grouped_packages[package_id].append(doc)
        else:
            ungrouped_documents.append(doc)

    packages = []
    for package_id, docs in grouped_packages.items():
        packages.append({
            "id": package_id,
            "name": docs[0].get("package_name"),
            "documents": docs,
        })

    return render(
        request,
        "web/dashboard.html",
        {
            "packages": packages,
            "documents": ungrouped_documents,
        },
    )



# ── Document Detail ──────────────────────────────────────────────────


@login_required
def document_detail_view(request, document_id):
    use_case = GetDocumentStatusUseCase(
        get_document_repository(), get_signature_repository()
    )
    try:
        result = use_case.execute(str(document_id), request.user.id)
    except DomainError as e:
        messages.error(request, str(e))
        return redirect("web-dashboard")

    # Also fetch full document info for display
    doc_repo = get_document_repository()
    document = doc_repo.get_by_id(str(document_id))

    return render(request, "web/document_detail.html", {
        "document": document,
        "status_result": result,
    })


# ── Upload ───────────────────────────────────────────────────────────


@login_required
def upload_view(request):
    packages_uc = ListPackagesUseCase(get_package_repository())
    packages = packages_uc.execute(request.user.id)
    return render(request, "web/upload.html", {"packages": packages})


# ── Signing ──────────────────────────────────────────────────────────


@login_required
def signing_view(request, document_id):
    doc_repo = get_document_repository()
    document = doc_repo.get_by_id(str(document_id))
    if not document or document.owner_id != request.user.id:
        messages.error(request, "Документ не найден.")
        return redirect("web-dashboard")

    return render(request, "web/signing.html", {
        "document_id": str(document_id),
        "document_title": document.title,
        "is_package": False,
    })


# ── Packages ─────────────────────────────────────────────────────────


@login_required
def packages_view(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()

        if not title:
            messages.error(request, "Название пакета обязательно.")
        else:
            use_case = CreatePackageUseCase(get_package_repository())
            use_case.execute(title=title, description=description, owner_id=request.user.id)
            messages.success(request, f'Пакет «{title}» создан.')
            return redirect("web-packages")

    packages_uc = ListPackagesUseCase(get_package_repository())
    packages = packages_uc.execute(request.user.id)
    return render(request, "web/packages.html", {"packages": packages})


@login_required
def package_detail_view(request, package_id):
    pkg_repo = get_package_repository()
    package = pkg_repo.get_by_id(str(package_id))
    if not package or package.owner_id != request.user.id:
        messages.error(request, "Пакет не найден.")
        return redirect("web-packages")

    if request.method == "POST":
        document_id = request.POST.get("document_id", "").strip()
        if document_id:
            try:
                use_case = AddDocumentToPackageUseCase(
                    get_document_repository(), get_package_repository()
                )
                use_case.execute(
                    package_id=str(package_id),
                    document_id=document_id,
                    owner_id=request.user.id,
                )
                messages.success(request, "Документ добавлен в пакет.")
            except DomainError as e:
                messages.error(request, str(e))
        return redirect("web-package-detail", package_id=package_id)

    # Get documents in this package
    doc_repo = get_document_repository()
    all_docs = doc_repo.list_by_owner(request.user.id)
    package_docs = [d for d in all_docs if d.package_id == str(package_id)]
    available_docs = [d for d in all_docs if not d.package_id and d.status != "signed"]

    return render(request, "web/package_detail.html", {
        "package": package,
        "package_docs": package_docs,
        "available_docs": available_docs,
    })


@login_required
def package_signing_view(request, package_id):
    pkg_repo = get_package_repository()
    package = pkg_repo.get_by_id(str(package_id))
    if not package or package.owner_id != request.user.id:
        messages.error(request, "Пакет не найден.")
        return redirect("web-packages")

    return render(request, "web/signing.html", {
        "document_id": str(package_id),
        "document_title": package.title,
        "is_package": True,
    })
