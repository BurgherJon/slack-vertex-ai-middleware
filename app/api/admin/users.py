# Copyright (C) 2025 Comites.ai
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin UI user administration (rendered HTML, form-encoded POSTs).

Users are auto-created on first message, so there is no "create" form here —
only a list and an edit view for the fields an operator may want to change
(primary name, email used for auto-linking, default timezone). Identity
linking stays in scripts/link_identities.py.
"""
import logging
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.core.dependencies import get_firestore_service, require_admin_user
from app.api.admin._common import PLATFORM_LABELS, TIMEZONES, get_templates
from app.services.firestore_service import FirestoreService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users")


@router.get("")
async def list_users(
    request: Request,
    _email: str = Depends(require_admin_user),
    firestore: FirestoreService = Depends(get_firestore_service),
):
    users = await firestore.list_users()
    return get_templates(request).TemplateResponse(
        request,
        "admin/users_list.html",
        {
            "users": users,
            "platform_labels": PLATFORM_LABELS,
        },
    )


@router.get("/{user_id}/edit")
async def edit_user_form(
    user_id: str,
    request: Request,
    _email: str = Depends(require_admin_user),
    firestore: FirestoreService = Depends(get_firestore_service),
):
    user = await firestore.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return get_templates(request).TemplateResponse(
        request,
        "admin/user_form.html",
        {
            "user": user,
            "form": {},
            "error": None,
            "timezones": TIMEZONES,
            "platform_labels": PLATFORM_LABELS,
        },
    )


@router.post("/{user_id}/edit")
async def update_user(
    user_id: str,
    request: Request,
    _email: str = Depends(require_admin_user),
    firestore: FirestoreService = Depends(get_firestore_service),
    primary_name: str = Form(...),
    email: str = Form(""),
    default_timezone: str = Form(""),
):
    user = await firestore.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    primary_name = primary_name.strip()
    email = email.strip()
    default_timezone = default_timezone.strip()

    error = None
    if not primary_name:
        error = "Primary name is required."
    elif default_timezone:
        try:
            ZoneInfo(default_timezone)
        except (KeyError, ValueError):
            error = f"Unknown timezone: {default_timezone}"

    if error:
        return get_templates(request).TemplateResponse(
            request,
            "admin/user_form.html",
            {
                "user": user,
                "form": {
                    "primary_name": primary_name,
                    "email": email,
                    "default_timezone": default_timezone,
                },
                "error": error,
                "timezones": TIMEZONES,
                "platform_labels": PLATFORM_LABELS,
            },
            status_code=400,
        )

    await firestore.update_user(user_id, {
        "primary_name": primary_name,
        "email": email or None,
        "default_timezone": default_timezone or None,
    })
    logger.info(f"Admin updated user {user_id}")
    return RedirectResponse("/admin/users", status_code=303)
