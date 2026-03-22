import json
from typing import Any, Dict, List, Optional, Tuple

import frappe

from mob_clinic.mob_clinic.api import clinic as clinic_helper

DEFAULT_ALLOWED_PAGES = [
    "home",
    "appointments",
    "patients",
    "prescriptions",
    "invoice",
    "financial_dashboard",
    "whatsapp-manager",
    "settings",
]

NON_ADMIN_DEFAULT_PAGES = [page for page in DEFAULT_ALLOWED_PAGES if page != "settings"]
PATIENT_SCOPE_ALL = "patients_all"
PATIENT_SCOPE_USER = "patients_user"
PATIENT_SCOPE_KEYS = [PATIENT_SCOPE_ALL, PATIENT_SCOPE_USER]
ALLOWED_PERMISSION_KEYS = DEFAULT_ALLOWED_PAGES + PATIENT_SCOPE_KEYS


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def sanitize_allowed_pages(allowed_pages: Any) -> List[str]:
    parsed = allowed_pages

    if isinstance(allowed_pages, str):
        stripped = allowed_pages.strip()
        if not stripped:
            parsed = []
        else:
            try:
                parsed = json.loads(stripped)
            except Exception:
                parsed = [item.strip() for item in stripped.split(",") if item.strip()]

    if not isinstance(parsed, (list, tuple)):
        return []

    filtered: List[str] = []
    seen = set()
    for item in parsed:
        if not isinstance(item, str):
            continue
        key = item.strip()
        if key in ALLOWED_PERMISSION_KEYS and key not in seen:
            seen.add(key)
            filtered.append(key)

    return filtered


def _normalize_patient_scope_access(allowed_pages: List[str]) -> Tuple[List[str], str]:
    has_patients_access = "patients" in allowed_pages or any(scope in allowed_pages for scope in PATIENT_SCOPE_KEYS)
    patient_scope = PATIENT_SCOPE_USER if PATIENT_SCOPE_USER in allowed_pages else PATIENT_SCOPE_ALL

    normalized = [page for page in allowed_pages if page not in PATIENT_SCOPE_KEYS]
    if has_patients_access:
        if "patients" not in normalized:
            normalized.append("patients")
        if patient_scope not in normalized:
            normalized.append(patient_scope)
    else:
        normalized = [page for page in normalized if page != "patients"]

    return normalized, patient_scope


def get_practitioner_permissions(practitioner_doc) -> Dict[str, Any]:
    is_clinic_admin = _parse_bool(getattr(practitioner_doc, "is_clinic_admin", 0))
    allowed_pages = sanitize_allowed_pages(getattr(practitioner_doc, "allowed_pages_json", None))

    if not allowed_pages:
        allowed_pages = DEFAULT_ALLOWED_PAGES if is_clinic_admin else NON_ADMIN_DEFAULT_PAGES

    if is_clinic_admin and "settings" not in allowed_pages:
        allowed_pages.append("settings")

    if not is_clinic_admin and "settings" in allowed_pages:
        allowed_pages = [page for page in allowed_pages if page != "settings"]

    allowed_pages, patient_scope = _normalize_patient_scope_access(allowed_pages)

    return {
        "is_clinic_admin": is_clinic_admin,
        "allowed_pages": allowed_pages,
        "patient_scope": patient_scope,
    }


def get_practitioner_patient_scope(practitioner_doc) -> str:
    try:
        permissions = get_practitioner_permissions(practitioner_doc)
        return permissions.get("patient_scope") or PATIENT_SCOPE_ALL
    except Exception:
        return PATIENT_SCOPE_ALL


def _get_requester_practitioner():
    user = frappe.session.user
    if not user or user == "Guest":
        return None

    try:
        return frappe.get_doc("Healthcare Practitioner", {"user_id": user})
    except Exception:
        return None


def get_current_practitioner_doc():
    return _get_requester_practitioner()


def assert_page_access(page_key: str, practitioner_name: Optional[str] = None):
    if page_key not in DEFAULT_ALLOWED_PAGES:
        frappe.throw("Not permitted", frappe.PermissionError)

    practitioner_doc = None
    if practitioner_name:
        try:
            practitioner_doc = frappe.get_doc("Healthcare Practitioner", practitioner_name)
        except Exception:
            practitioner_doc = None
    else:
        practitioner_doc = _get_requester_practitioner()

    if not practitioner_doc:
        frappe.throw("Not permitted", frappe.PermissionError)

    permissions = get_practitioner_permissions(practitioner_doc)

    if page_key == "settings" and not permissions.get("is_clinic_admin"):
        frappe.throw("Not permitted", frappe.PermissionError)

    if page_key not in permissions.get("allowed_pages", []):
        frappe.throw("Not permitted", frappe.PermissionError)

    return practitioner_doc


def _resolve_target_clinic(requester_practitioner, clinic: Optional[str]) -> Optional[str]:
    if clinic:
        return clinic

    return clinic_helper.resolve_active_clinic(
        practitioner_name=requester_practitioner.name if requester_practitioner else None,
        clinic_param=None,
    )


def _check_admin_access(requester_practitioner, clinic: str) -> Optional[Dict[str, Any]]:
    if not requester_practitioner:
        frappe.local.response["http_status_code"] = 403
        return {"exc_type": "PermissionError", "message": "Practitioner profile is required"}

    if not clinic_helper.validate_practitioner_access(requester_practitioner.name, clinic):
        frappe.local.response["http_status_code"] = 403
        return {"exc_type": "PermissionError", "message": "Clinic access denied"}

    requester_permissions = get_practitioner_permissions(requester_practitioner)
    if not requester_permissions["is_clinic_admin"]:
        frappe.local.response["http_status_code"] = 403
        return {"exc_type": "PermissionError", "message": "Clinic admin access required"}

    return None


@frappe.whitelist(methods=["GET"])
def get_clinic_practitioner_permissions(clinic: Optional[str] = None):
    try:
        requester_practitioner = _get_requester_practitioner()
        clinic_name = _resolve_target_clinic(requester_practitioner, clinic)

        if not clinic_name:
            frappe.local.response["http_status_code"] = 400
            return {"exc_type": "ValidationError", "message": "Clinic is required"}

        permission_error = _check_admin_access(requester_practitioner, clinic_name)
        if permission_error:
            return permission_error

        practitioners = frappe.get_all(
            "Healthcare Practitioner",
            filters={"primary_company": clinic_name},
            fields=["name", "practitioner_name", "user_id", "is_clinic_admin", "allowed_pages_json", "primary_company"],
            order_by="practitioner_name asc",
        )

        data = []
        for row in practitioners:
            practitioner_doc = frappe._dict(row)
            permissions = get_practitioner_permissions(practitioner_doc)
            data.append(
                {
                    "practitioner_id": row.get("name"),
                    "practitioner_name": row.get("practitioner_name"),
                    "user_id": row.get("user_id"),
                    "primary_company": row.get("primary_company"),
                    "is_clinic_admin": permissions["is_clinic_admin"],
                    "allowed_pages": permissions["allowed_pages"],
                    "patient_scope": permissions.get("patient_scope", PATIENT_SCOPE_ALL),
                }
            )

        return {
            "message": "success",
            "data": {
                "clinic": clinic_name,
                "practitioners": data,
            },
        }

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Get Clinic Practitioner Permissions Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": "Error retrieving practitioner permissions"}


@frappe.whitelist(methods=["POST"])
def update_practitioner_permissions(
    clinic: Optional[str] = None,
    practitioner_id: Optional[str] = None,
    is_clinic_admin: Any = 0,
    allowed_pages: Any = None,
):
    try:
        if not practitioner_id:
            frappe.local.response["http_status_code"] = 400
            return {"exc_type": "ValidationError", "message": "practitioner_id is required"}

        requester_practitioner = _get_requester_practitioner()
        clinic_name = _resolve_target_clinic(requester_practitioner, clinic)

        if not clinic_name:
            frappe.local.response["http_status_code"] = 400
            return {"exc_type": "ValidationError", "message": "Clinic is required"}

        permission_error = _check_admin_access(requester_practitioner, clinic_name)
        if permission_error:
            return permission_error

        target = frappe.get_doc("Healthcare Practitioner", practitioner_id)
        if target.primary_company != clinic_name:
            frappe.local.response["http_status_code"] = 403
            return {"exc_type": "PermissionError", "message": "Target practitioner is outside the selected clinic"}

        target_admin = _parse_bool(is_clinic_admin)
        filtered_pages = sanitize_allowed_pages(allowed_pages)

        if not filtered_pages:
            filtered_pages = DEFAULT_ALLOWED_PAGES if target_admin else NON_ADMIN_DEFAULT_PAGES

        if target_admin and "settings" not in filtered_pages:
            filtered_pages.append("settings")

        if not target_admin and "settings" in filtered_pages:
            filtered_pages = [page for page in filtered_pages if page != "settings"]

        filtered_pages, patient_scope = _normalize_patient_scope_access(filtered_pages)

        frappe.db.set_value(
            "Healthcare Practitioner",
            target.name,
            {
                "is_clinic_admin": 1 if target_admin else 0,
                "allowed_pages_json": json.dumps(filtered_pages),
            },
            update_modified=True,
        )
        frappe.db.commit()

        return {
            "message": "Permissions updated successfully",
            "data": {
                "clinic": clinic_name,
                "practitioner_id": target.name,
                "is_clinic_admin": target_admin,
                "allowed_pages": filtered_pages,
                "patient_scope": patient_scope,
            },
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"exc_type": "NotFound", "message": "Practitioner not found"}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Update Practitioner Permissions Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": "Error updating practitioner permissions"}
