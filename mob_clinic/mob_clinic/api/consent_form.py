import base64
import json
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe.utils import add_to_date, get_url, now_datetime

from mob_clinic.mob_clinic.api import clinic as clinic_helper
from mob_clinic.mob_clinic.api import file_upload
from mob_clinic.mob_clinic.api import patient as patient_api
from mob_clinic.mob_clinic.api import role_access


DEFAULT_DECLARATION_EN = (
    "I confirm that I have read and understood the treatment details, risks, alternatives, and benefits. "
    "I voluntarily consent to proceed with the advised dental treatment."
)
DEFAULT_DECLARATION_EN_GUARDIAN = (
    "I am the parent/legal guardian of the minor patient. I confirm that I have read and understood the "
    "treatment details, risks, alternatives, and benefits, and I consent for the advised treatment."
)
DEFAULT_DECLARATION_ML = (
    "നിർദ്ദേശിച്ച ചികിത്സ, അപകടസാധ്യതകൾ, ബദൽ ചികിത്സാമാർഗങ്ങൾ, ഗുണഫലങ്ങൾ എന്നിവ ഞാൻ വായിച്ചും "
    "മനസ്സിലാക്കിയുമുണ്ട്. നിർദ്ദേശിച്ച ചികിത്സയ്ക്ക് ഞാൻ സമ്മതിക്കുന്നു."
)
DEFAULT_DECLARATION_ML_GUARDIAN = (
    "ഞാൻ പ്രായപൂർത്തിയാകാത്ത രോഗിയുടെ രക്ഷിതാവാണ്. നിർദ്ദേശിച്ച ചികിത്സയും അപകടസാധ്യതകളും ഞാൻ "
    "മനസ്സിലാക്കിയിട്ടുണ്ട്; ചികിത്സയ്ക്ക് ഞാൻ സമ്മതിക്കുന്നു."
)


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _parse_json(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return json.loads(stripped)
        except Exception:
            return default
    return default


def _resolve_context(
    clinic: Optional[str] = None,
    require_admin: bool = False,
    page_key: Optional[str] = None,
) -> Tuple[Any, str]:
    practitioner = role_access.get_current_practitioner_doc()
    if not practitioner:
        frappe.throw("Practitioner profile is required", frappe.PermissionError)

    clinic_name = clinic_helper.resolve_active_clinic(practitioner.name, clinic)
    if not clinic_name:
        frappe.throw("Clinic is required")

    if not clinic_helper.validate_practitioner_access(practitioner.name, clinic_name):
        frappe.throw("Clinic access denied", frappe.PermissionError)

    if page_key:
        role_access.assert_page_access(page_key, practitioner_name=practitioner.name)

    if require_admin:
        permissions = role_access.get_practitioner_permissions(practitioner)
        if not permissions.get("is_clinic_admin"):
            frappe.throw("Clinic admin access required", frappe.PermissionError)

    return practitioner, clinic_name


def _get_seed_templates() -> Dict[str, Any]:
    candidate_paths = [
        frappe.get_app_path("mob_clinic", "data", "consent_template_source.json"),
        frappe.get_app_path("mob_clinic", "mob_clinic", "data", "consent_template_source.json"),
    ]

    for path in candidate_paths:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            continue

    frappe.throw("Consent template source data is missing. Expected consent_template_source.json in app data directory.")


def _normalize_sections(language: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_sections = payload.get("sections") or []
    normalized: List[Dict[str, Any]] = []

    if language == "en":
        for row in raw_sections:
            if isinstance(row, str):
                normalized.append({"heading": None, "body": row})
                continue

            if not isinstance(row, dict):
                continue

            normalized.append(
                {
                    "heading": row.get("heading"),
                    "body": row.get("body"),
                    "items": row.get("items") if isinstance(row.get("items"), list) else [],
                    "numbered": row.get("numbered") if isinstance(row.get("numbered"), list) else [],
                    "footer": row.get("footer"),
                }
            )
        return normalized

    for row in raw_sections:
        if isinstance(row, str):
            normalized.append({"heading": None, "body": row})
        elif isinstance(row, dict):
            normalized.append({"heading": row.get("heading"), "body": row.get("body")})

    return normalized


def _build_ml_summary(payload: Dict[str, Any]) -> str:
    if (payload.get("text") or "").strip():
        return str(payload.get("text")).strip()

    parts: List[str] = []
    for entry in payload.get("sections") or []:
        if isinstance(entry, str) and entry.strip():
            parts.append(entry.strip())
        elif isinstance(entry, dict) and entry.get("body"):
            parts.append(str(entry.get("body")).strip())
        if len(parts) >= 2:
            break
    return "\n\n".join(parts)


def _should_refresh_seed_template(existing_doc, seed_row: Dict[str, Any]) -> bool:
    if (existing_doc.doctor or None) is not None:
        return False

    if (existing_doc.source or "").strip().lower() != "seed":
        return False

    current_sections = _parse_json(existing_doc.sections_json, default=[])
    target_sections = _parse_json(seed_row.get("sections_json"), default=[])

    if isinstance(current_sections, list) and isinstance(target_sections, list):
        if len(current_sections) < len(target_sections):
            return True

    if (existing_doc.summary_text or "").strip() != (seed_row.get("summary_text") or "").strip():
        return True

    if not (existing_doc.summary_text or "").strip() and (seed_row.get("summary_text") or "").strip():
        return True

    return False


def _ensure_seed_templates(clinic: str):
    seed = _get_seed_templates()
    english = seed.get("en") or {}
    malayalam = seed.get("ml") or {}

    sort_order = 0
    for consent_type_id, en_payload in english.items():
        ml_payload = malayalam.get(consent_type_id) or {}
        label = en_payload.get("label") or en_payload.get("short") or consent_type_id.replace("_", " ").title()

        docs = [
            {
                "language": "en",
                "summary_text": en_payload.get("text") or "",
                "sections_json": json.dumps(_normalize_sections("en", en_payload), ensure_ascii=False),
                "meta_json": json.dumps({"short": en_payload.get("short")}, ensure_ascii=False),
                "declaration_text": DEFAULT_DECLARATION_EN,
                "guardian_declaration_text": DEFAULT_DECLARATION_EN_GUARDIAN,
            }
        ]

        if ml_payload:
            docs.append(
                {
                    "language": "ml",
                    "summary_text": _build_ml_summary(ml_payload),
                    "sections_json": json.dumps(_normalize_sections("ml", ml_payload), ensure_ascii=False),
                    "meta_json": json.dumps({"title": ml_payload.get("title")}, ensure_ascii=False),
                    "declaration_text": DEFAULT_DECLARATION_ML,
                    "guardian_declaration_text": DEFAULT_DECLARATION_ML_GUARDIAN,
                }
            )

        for row in docs:
            existing = frappe.get_all(
                "Consent Form Template",
                filters={
                    "clinic": clinic,
                    "consent_type_id": consent_type_id,
                    "language": row["language"],
                },
                fields=["name", "doctor"],
                limit=5,
            )

            clinic_default = next((candidate for candidate in existing if (candidate.get("doctor") or None) is None), None)
            if clinic_default:
                existing_doc = frappe.get_doc("Consent Form Template", clinic_default["name"])
                if _should_refresh_seed_template(existing_doc, row):
                    existing_doc.consent_type_label = label
                    existing_doc.is_active = 1
                    existing_doc.sort_order = sort_order
                    existing_doc.summary_text = row["summary_text"]
                    existing_doc.sections_json = row["sections_json"]
                    existing_doc.declaration_text = row["declaration_text"]
                    existing_doc.guardian_declaration_text = row["guardian_declaration_text"]
                    existing_doc.meta_json = row["meta_json"]
                    existing_doc.flags.ignore_permissions = True
                    existing_doc.save(ignore_permissions=True)
                sort_order += 1
                continue

            doc = frappe.get_doc(
                {
                    "doctype": "Consent Form Template",
                    "clinic": clinic,
                    "doctor": None,
                    "consent_type_id": consent_type_id,
                    "consent_type_label": label,
                    "language": row["language"],
                    "is_active": 1,
                    "sort_order": sort_order,
                    "source": "seed",
                    "summary_text": row["summary_text"],
                    "sections_json": row["sections_json"],
                    "declaration_text": row["declaration_text"],
                    "guardian_declaration_text": row["guardian_declaration_text"],
                    "meta_json": row["meta_json"],
                }
            )
            doc.insert(ignore_permissions=True)
            sort_order += 1


def _parse_sections(value: Any) -> List[Dict[str, Any]]:
    parsed = _parse_json(value, default=value)
    if isinstance(parsed, str):
        parsed = _parse_json(parsed, default=[])

    if not isinstance(parsed, list):
        frappe.throw("Sections must be provided as an array")

    normalized = []
    for row in parsed:
        if isinstance(row, str):
            normalized.append({"heading": None, "body": row})
        elif isinstance(row, dict):
            normalized.append(
                {
                    "heading": row.get("heading"),
                    "body": row.get("body"),
                    "items": row.get("items") if isinstance(row.get("items"), list) else [],
                    "numbered": row.get("numbered") if isinstance(row.get("numbered"), list) else [],
                    "footer": row.get("footer"),
                }
            )
    return normalized


def _serialize_template(doc: Dict[str, Any]) -> Dict[str, Any]:
    sections = _parse_json(doc.get("sections_json"), default=[])
    meta = _parse_json(doc.get("meta_json"), default={})
    return {
        "name": doc.get("name"),
        "clinic": doc.get("clinic"),
        "doctor": doc.get("doctor"),
        "consent_type_id": doc.get("consent_type_id"),
        "consent_type_label": doc.get("consent_type_label"),
        "language": doc.get("language"),
        "is_active": int(doc.get("is_active") or 0),
        "sort_order": doc.get("sort_order") or 0,
        "source": doc.get("source") or "custom",
        "summary_text": doc.get("summary_text") or "",
        "sections": sections if isinstance(sections, list) else [],
        "declaration_text": doc.get("declaration_text") or "",
        "guardian_declaration_text": doc.get("guardian_declaration_text") or "",
        "meta": meta if isinstance(meta, dict) else {},
    }


def _list_templates(
    clinic: str,
    doctor: Optional[str],
    language: Optional[str],
    include_inactive: bool,
    for_settings: bool,
) -> List[Dict[str, Any]]:
    filters: Dict[str, Any] = {"clinic": clinic}
    if language:
        filters["language"] = language
    if not include_inactive:
        filters["is_active"] = 1

    fields = [
        "name",
        "clinic",
        "doctor",
        "consent_type_id",
        "consent_type_label",
        "language",
        "is_active",
        "sort_order",
        "source",
        "summary_text",
        "sections_json",
        "declaration_text",
        "guardian_declaration_text",
        "meta_json",
    ]

    rows = frappe.get_all(
        "Consent Form Template",
        filters=filters,
        fields=fields,
        order_by="sort_order asc, consent_type_label asc, modified desc",
    )

    if for_settings:
        return [_serialize_template(row) for row in rows]

    clinic_defaults: Dict[Tuple[str, str], Dict[str, Any]] = {}
    doctor_overrides: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for row in rows:
        key = (row.get("consent_type_id"), row.get("language"))
        if row.get("doctor") and doctor and row.get("doctor") == doctor:
            doctor_overrides[key] = row
        elif not row.get("doctor"):
            clinic_defaults[key] = row

    merged = dict(clinic_defaults)
    merged.update(doctor_overrides)

    return [_serialize_template(row) for row in merged.values()]


def _can_access_patient(practitioner, patient_id: str, clinic_name: str) -> bool:
    if not frappe.db.exists("Patient", patient_id):
        return False

    patient_clinic = frappe.db.get_value("Patient", patient_id, "primary_clinic")
    if patient_clinic and not clinic_helper.validate_practitioner_access(practitioner.name, patient_clinic):
        return False

    if patient_api._is_user_patient_scope(practitioner):
        return patient_api._practitioner_can_access_patient(patient_id, practitioner.name, clinic_name)

    return True


def _extract_base64_payload(data_url_or_base64: str) -> str:
    if not data_url_or_base64:
        return ""
    if "," in data_url_or_base64:
        return data_url_or_base64.split(",", 1)[1]
    return data_url_or_base64


def _upload_consent_file(
    patient_id: str,
    file_name: str,
    content_b64: str,
    description: str,
    is_private: int = 1,
) -> Dict[str, Any]:
    response = file_upload.upload_file(
        file_name=file_name,
        content=content_b64,
        decode_base64=True,
        is_private=is_private,
        reference_doctype="Patient",
        reference_name=patient_id,
        file_category="consent",
        description=description,
    )

    if isinstance(response, tuple):
        response = response[0]

    if not isinstance(response, dict):
        frappe.throw("Unexpected file upload response")

    if response.get("exc_type"):
        frappe.throw(response.get("message") or "Failed to upload consent file")

    return response.get("data") or {}


def _upload_consent_pdf(
    patient_id: str,
    consent_type_id: str,
    content_b64: str,
    file_name: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    suffix = frappe.utils.now_datetime().strftime("%Y%m%d%H%M%S")
    safe_name = (file_name or "").strip() or f"consent-document-{patient_id}-{suffix}.pdf"
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"

    return _upload_consent_file(
        patient_id=patient_id,
        file_name=safe_name,
        content_b64=content_b64,
        description=description or f"Consent document ({consent_type_id})",
        is_private=1,
    )


def _build_consent_session_payload(payload: Any) -> Dict[str, Any]:
    parsed_payload = _parse_json(payload, default={})
    return parsed_payload if isinstance(parsed_payload, dict) else {}


def _serialize_consent_record(doc: Dict[str, Any]) -> Dict[str, Any]:
    payload = _parse_json(doc.get("payload_json"), default={})
    return {
        "name": doc.get("name"),
        "status": doc.get("status"),
        "language": doc.get("language"),
        "consent_type_id": doc.get("consent_type_id"),
        "consent_type_label": doc.get("consent_type_label"),
        "doctor": doc.get("doctor"),
        "doctor_name": doc.get("doctor_name"),
        "summary_text": doc.get("summary_text") or "",
        "signed_on": doc.get("signed_on"),
        "signed_by": doc.get("signed_by"),
        "signer_role": doc.get("signer_role"),
        "creation": doc.get("creation"),
        "modified": doc.get("modified"),
        "consent_file_id": doc.get("consent_file"),
        "payload": payload if isinstance(payload, dict) else {},
    }


def _session_from_token(token: str):
    session_name = frappe.db.get_value("Consent Form Session", {"token": token}, "name")
    if not session_name:
        frappe.throw("Invalid or expired consent link")
    return frappe.get_doc("Consent Form Session", session_name)


def _maybe_expire_session(session_doc) -> bool:
    if session_doc.status == "Expired":
        return True

    if session_doc.expires_on and now_datetime() > session_doc.expires_on:
        session_doc.status = "Expired"
        session_doc.save(ignore_permissions=True)
        return True

    return False


@frappe.whitelist(methods=["GET"])
def get_consent_templates(clinic=None, doctor=None, include_inactive=0, language=None, for_settings=0):
    try:
        practitioner, clinic_name = _resolve_context(clinic=clinic)
        _ensure_seed_templates(clinic_name)

        selected_doctor = doctor or practitioner.name
        templates = _list_templates(
            clinic=clinic_name,
            doctor=selected_doctor,
            language=(language or "").strip().lower() or None,
            include_inactive=_parse_bool(include_inactive),
            for_settings=_parse_bool(for_settings),
        )

        consent_types: Dict[str, Dict[str, Any]] = {}
        for row in templates:
            key = row["consent_type_id"]
            existing = consent_types.get(key) or {
                "consent_type_id": key,
                "consent_type_label": row.get("consent_type_label"),
                "languages": [],
            }
            if row.get("language") and row["language"] not in existing["languages"]:
                existing["languages"].append(row["language"])
            consent_types[key] = existing

        return {
            "message": "success",
            "data": {
                "clinic": clinic_name,
                "doctor": selected_doctor,
                "templates": templates,
                "consent_types": sorted(consent_types.values(), key=lambda d: d.get("consent_type_label") or ""),
            },
        }
    except frappe.PermissionError:
        frappe.local.response["http_status_code"] = 403
        return {"exc_type": "PermissionError", "message": "Not permitted"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Consent Templates API Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": str(e)}


@frappe.whitelist(methods=["POST"])
def save_consent_template(template=None, clinic=None):
    try:
        _, clinic_name = _resolve_context(clinic=clinic, require_admin=True, page_key="settings")
        payload = _parse_json(template, default=template)
        if not isinstance(payload, dict):
            frappe.throw("Template payload is required")

        consent_type_id = (payload.get("consent_type_id") or "").strip().lower().replace(" ", "_")
        if not consent_type_id:
            frappe.throw("consent_type_id is required")

        language = (payload.get("language") or "en").strip().lower()
        if language not in {"en", "ml"}:
            frappe.throw("language must be either 'en' or 'ml'")

        sections = _parse_sections(payload.get("sections"))
        if not sections:
            frappe.throw("At least one section is required")

        name = payload.get("name")
        if name:
            doc = frappe.get_doc("Consent Form Template", name)
            if doc.clinic != clinic_name:
                frappe.throw("Template belongs to a different clinic", frappe.PermissionError)
        else:
            doc = frappe.new_doc("Consent Form Template")
            doc.clinic = clinic_name

        doc.clinic = clinic_name
        doc.doctor = payload.get("doctor") or None
        doc.consent_type_id = consent_type_id
        doc.consent_type_label = (payload.get("consent_type_label") or "").strip() or consent_type_id.replace("_", " ").title()
        doc.language = language
        doc.is_active = 1 if _parse_bool(payload.get("is_active", True)) else 0
        doc.sort_order = int(payload.get("sort_order") or 0)
        doc.source = (payload.get("source") or "custom").strip() or "custom"
        doc.summary_text = payload.get("summary_text") or ""
        doc.sections_json = json.dumps(sections, ensure_ascii=False)
        doc.declaration_text = payload.get("declaration_text") or (
            DEFAULT_DECLARATION_ML if language == "ml" else DEFAULT_DECLARATION_EN
        )
        doc.guardian_declaration_text = payload.get("guardian_declaration_text") or (
            DEFAULT_DECLARATION_ML_GUARDIAN if language == "ml" else DEFAULT_DECLARATION_EN_GUARDIAN
        )
        doc.meta_json = json.dumps(_parse_json(payload.get("meta"), default={}), ensure_ascii=False)

        doc.flags.ignore_permissions = True
        if doc.is_new():
            doc.insert(ignore_permissions=True)
        else:
            doc.save(ignore_permissions=True)

        return {
            "message": "Consent template saved",
            "data": _serialize_template(doc.as_dict()),
        }
    except frappe.PermissionError:
        frappe.local.response["http_status_code"] = 403
        return {"exc_type": "PermissionError", "message": "Not permitted"}
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Save Consent Template Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": str(e)}


@frappe.whitelist(methods=["POST"])
def delete_consent_template(name, clinic=None):
    try:
        _, clinic_name = _resolve_context(clinic=clinic, require_admin=True, page_key="settings")
        if not name:
            frappe.throw("Template name is required")

        doc = frappe.get_doc("Consent Form Template", name)
        if doc.clinic != clinic_name:
            frappe.throw("Template belongs to a different clinic", frappe.PermissionError)

        doc.delete(ignore_permissions=True)
        return {"message": "Consent template deleted", "data": {"name": name}}
    except frappe.PermissionError:
        frappe.local.response["http_status_code"] = 403
        return {"exc_type": "PermissionError", "message": "Not permitted"}
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Delete Consent Template Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": str(e)}


@frappe.whitelist(methods=["POST"])
def create_consent_share_link(
    patient_id,
    consent_type_id,
    language="en",
    clinic=None,
    doctor=None,
    payload=None,
    summary_text=None,
    expires_in_hours=48,
    app_base_url=None,
):
    try:
        practitioner, clinic_name = _resolve_context(clinic=clinic, page_key="consent_forms")

        if not _can_access_patient(practitioner, patient_id, clinic_name):
            frappe.throw("Not permitted to access this patient", frappe.PermissionError)

        if not consent_type_id:
            frappe.throw("consent_type_id is required")

        parsed_payload = _parse_json(payload, default={})
        if not isinstance(parsed_payload, dict):
            parsed_payload = {}

        expires_hours = int(expires_in_hours or 48)
        if expires_hours < 1:
            expires_hours = 1
        if expires_hours > 24 * 30:
            expires_hours = 24 * 30

        token = frappe.generate_hash(length=32)
        expires_on = add_to_date(now_datetime(), hours=expires_hours, as_datetime=True)

        doctor_name = None
        selected_doctor = doctor or practitioner.name
        if selected_doctor and frappe.db.exists("Healthcare Practitioner", selected_doctor):
            doctor_name = frappe.db.get_value("Healthcare Practitioner", selected_doctor, "practitioner_name")

        doc = frappe.get_doc(
            {
                "doctype": "Consent Form Session",
                "token": token,
                "status": "Created",
                "clinic": clinic_name,
                "patient": patient_id,
                "doctor": selected_doctor,
                "doctor_name": doctor_name,
                "consent_type_id": consent_type_id,
                "consent_type_label": parsed_payload.get("consent_type_label") or consent_type_id,
                "language": (language or "en").strip().lower() or "en",
                "payload_json": json.dumps(parsed_payload, ensure_ascii=False),
                "summary_text": summary_text or parsed_payload.get("summary_text") or "",
                "expires_on": expires_on,
            }
        )
        doc.insert(ignore_permissions=True)

        relative_path = f"/consent-review/{token}"
        base = (app_base_url or "").strip().rstrip("/")
        share_url = f"{base}{relative_path}" if base else get_url(relative_path)

        return {
            "message": "Consent share link created",
            "data": {
                "session_id": doc.name,
                "token": token,
                "share_url": share_url,
                "relative_path": relative_path,
                "expires_on": expires_on,
            },
        }
    except frappe.PermissionError:
        frappe.local.response["http_status_code"] = 403
        return {"exc_type": "PermissionError", "message": "Not permitted"}
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Create Consent Share Link Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": str(e)}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_shared_consent(token):
    try:
        if not token:
            frappe.throw("token is required")

        session_doc = _session_from_token(token)
        if _maybe_expire_session(session_doc):
            frappe.local.response["http_status_code"] = 410
            return {"exc_type": "Expired", "message": "This consent link has expired"}

        patient = frappe.db.get_value(
            "Patient",
            session_doc.patient,
            ["name", "patient_name", "mobile", "sex", "dob", "age", "primary_clinic"],
            as_dict=True,
        )

        templates = _list_templates(
            clinic=session_doc.clinic,
            doctor=session_doc.doctor,
            language=session_doc.language,
            include_inactive=True,
            for_settings=False,
        )
        selected_template = next(
            (item for item in templates if item["consent_type_id"] == session_doc.consent_type_id),
            None,
        )

        payload = _parse_json(session_doc.payload_json, default={})
        if not isinstance(payload, dict):
            payload = {}

        return {
            "message": "success",
            "data": {
                "session": {
                    "name": session_doc.name,
                    "token": session_doc.token,
                    "status": session_doc.status,
                    "language": session_doc.language,
                    "consent_type_id": session_doc.consent_type_id,
                    "consent_type_label": session_doc.consent_type_label,
                    "doctor": session_doc.doctor,
                    "doctor_name": session_doc.doctor_name,
                    "summary_text": session_doc.summary_text or "",
                    "expires_on": session_doc.expires_on,
                },
                "patient": patient,
                "payload": payload,
                "template": selected_template,
            },
        }
    except Exception as e:
        if not frappe.local.response.get("http_status_code"):
            frappe.local.response["http_status_code"] = 500
        frappe.log_error(frappe.get_traceback(), "Get Shared Consent Error")
        return {"exc_type": "ServerError", "message": str(e)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def accept_shared_consent(
    token,
    signer_name=None,
    signer_role="Patient",
    signer_phone=None,
    signature_data_url=None,
    consent_html=None,
    consent_pdf_base64=None,
    consent_pdf_filename=None,
    summary_text=None,
):
    try:
        if not token:
            frappe.throw("token is required")

        session_doc = _session_from_token(token)

        if _maybe_expire_session(session_doc):
            frappe.local.response["http_status_code"] = 410
            return {"exc_type": "Expired", "message": "This consent link has expired"}

        if session_doc.status == "Signed":
            return {
                "message": "Consent already signed",
                "data": {"session_id": session_doc.name, "status": session_doc.status},
            }

        if not signature_data_url:
            frappe.throw("signature_data_url is required")

        signature_b64 = _extract_base64_payload(signature_data_url)
        if not signature_b64:
            frappe.throw("Invalid signature payload")

        consent_upload = {}
        pdf_b64 = _extract_base64_payload(consent_pdf_base64 or "")
        if pdf_b64:
            consent_upload = _upload_consent_pdf(
                patient_id=session_doc.patient,
                consent_type_id=session_doc.consent_type_id,
                content_b64=pdf_b64,
                file_name=consent_pdf_filename,
                description=f"Signed consent document ({session_doc.consent_type_id})",
            )
        elif consent_html:
            suffix = frappe.utils.now_datetime().strftime("%Y%m%d%H%M%S")
            encoded_html = base64.b64encode((consent_html or "").encode("utf-8")).decode("utf-8")
            consent_upload = _upload_consent_file(
                patient_id=session_doc.patient,
                file_name=f"consent-document-{session_doc.patient}-{suffix}.html",
                content_b64=encoded_html,
                description=f"Signed consent document ({session_doc.consent_type_id})",
                is_private=1,
            )

        session_doc.status = "Signed"
        session_doc.signed_on = now_datetime()
        session_doc.signed_by = signer_name or ""
        session_doc.signer_role = signer_role if signer_role in {"Patient", "Parent/Guardian"} else "Patient"
        session_doc.signer_phone = signer_phone or ""
        session_doc.summary_text = summary_text or session_doc.summary_text
        session_doc.signature_file = None
        if consent_upload.get("file_id"):
            session_doc.consent_file = consent_upload.get("file_id")
        session_doc.ip_address = getattr(frappe.local, "request_ip", None)
        session_doc.save(ignore_permissions=True)

        return {
            "message": "Consent signed successfully",
            "data": {
                "session_id": session_doc.name,
                "status": session_doc.status,
                "signature_file_id": None,
                "consent_file_id": consent_upload.get("file_id"),
            },
        }
    except Exception as e:
        frappe.db.rollback()
        if not frappe.local.response.get("http_status_code"):
            frappe.local.response["http_status_code"] = 500
        frappe.log_error(frappe.get_traceback(), "Accept Shared Consent Error")
        return {"exc_type": "ServerError", "message": str(e)}


@frappe.whitelist(methods=["POST"])
def save_consent_artifacts(
    patient_id,
    consent_type_id,
    consent_type_label=None,
    language="en",
    clinic=None,
    summary_text=None,
    signature_data_url=None,
    consent_html=None,
    consent_pdf_base64=None,
    consent_pdf_filename=None,
    payload=None,
    signer_name=None,
    signer_role="Patient",
):
    try:
        practitioner, clinic_name = _resolve_context(clinic=clinic, page_key="consent_forms")

        if not _can_access_patient(practitioner, patient_id, clinic_name):
            frappe.throw("Not permitted to access this patient", frappe.PermissionError)

        consent_upload = {}
        pdf_b64 = _extract_base64_payload(consent_pdf_base64 or "")
        if pdf_b64:
            consent_upload = _upload_consent_pdf(
                patient_id=patient_id,
                consent_type_id=consent_type_id,
                content_b64=pdf_b64,
                file_name=consent_pdf_filename,
                description=f"Consent document ({consent_type_id}, {language})",
            )
        elif consent_html:
            suffix = frappe.utils.now_datetime().strftime("%Y%m%d%H%M%S")
            encoded_html = base64.b64encode((consent_html or "").encode("utf-8")).decode("utf-8")
            consent_upload = _upload_consent_file(
                patient_id=patient_id,
                file_name=f"consent-document-{patient_id}-{suffix}.html",
                content_b64=encoded_html,
                description=f"Consent document ({consent_type_id}, {language})",
                is_private=1,
            )

        parsed_payload = _build_consent_session_payload(payload)
        status = "Signed" if _extract_base64_payload(signature_data_url or "") else "Created"
        if consent_upload.get("file_id"):
            doctor_name = None
            if practitioner.name and frappe.db.exists("Healthcare Practitioner", practitioner.name):
                doctor_name = frappe.db.get_value("Healthcare Practitioner", practitioner.name, "practitioner_name")

            session_doc = frappe.get_doc(
                {
                    "doctype": "Consent Form Session",
                    "token": frappe.generate_hash(length=32),
                    "status": status,
                    "clinic": clinic_name,
                    "patient": patient_id,
                    "doctor": practitioner.name,
                    "doctor_name": doctor_name,
                    "consent_type_id": consent_type_id,
                    "consent_type_label": consent_type_label or parsed_payload.get("consent_type_label") or consent_type_id,
                    "language": (language or "en").strip().lower() or "en",
                    "payload_json": json.dumps(parsed_payload, ensure_ascii=False),
                    "summary_text": summary_text or "",
                    "signed_on": now_datetime() if status == "Signed" else None,
                    "signed_by": signer_name or "",
                    "signer_role": signer_role if signer_role in {"Patient", "Parent/Guardian"} else "Patient",
                    "consent_file": consent_upload.get("file_id"),
                }
            )
            session_doc.insert(ignore_permissions=True)

            return {
                "message": "Consent artifacts saved",
                "data": {
                    "summary_text": summary_text or "",
                    "signature_file_id": None,
                    "consent_file_id": consent_upload.get("file_id"),
                    "consent_record": _serialize_consent_record(session_doc.as_dict()),
                },
            }

        return {
            "message": "Consent artifacts saved",
            "data": {
                "summary_text": summary_text or "",
                "signature_file_id": None,
                "consent_file_id": consent_upload.get("file_id"),
            },
        }
    except frappe.PermissionError:
        frappe.local.response["http_status_code"] = 403
        return {"exc_type": "PermissionError", "message": "Not permitted"}
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Save Consent Artifacts Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": str(e)}


@frappe.whitelist(methods=["GET"])
def list_patient_consents(patient_id, clinic=None):
    try:
        practitioner, clinic_name = _resolve_context(clinic=clinic, page_key="consent_forms")

        if not _can_access_patient(practitioner, patient_id, clinic_name):
            frappe.throw("Not permitted to access this patient", frappe.PermissionError)

        rows = frappe.get_all(
            "Consent Form Session",
            filters={
                "clinic": clinic_name,
                "patient": patient_id,
                "consent_file": ["is", "set"],
            },
            fields=[
                "name",
                "status",
                "language",
                "doctor",
                "doctor_name",
                "consent_type_id",
                "consent_type_label",
                "summary_text",
                "payload_json",
                "signed_on",
                "signed_by",
                "signer_role",
                "consent_file",
                "creation",
                "modified",
            ],
            order_by="creation desc",
        )

        return {
            "message": "success",
            "data": {
                "patient_id": patient_id,
                "records": [_serialize_consent_record(row) for row in rows],
            },
        }
    except frappe.PermissionError:
        frappe.local.response["http_status_code"] = 403
        return {"exc_type": "PermissionError", "message": "Not permitted"}
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "List Patient Consents Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": str(e)}
