import frappe
import frappe.share

from mob_clinic.mob_clinic.api import clinic as clinic_helper
from mob_clinic.mob_clinic.api import patient as patient_api
from mob_clinic.mob_clinic.api import role_access


SUPPORTED_ATTACHED_DOCTYPES = {
    "Patient",
    "Patient Appointment",
    "Patient Encounter",
    "Patient Prescription",
    "Patient Medical Record",
}


def _get_file_access_context(attached_to_doctype, attached_to_name):
    if not attached_to_doctype or not attached_to_name:
        return {}

    if attached_to_doctype == "Patient":
        patient_doc = frappe.db.get_value(
            "Patient",
            attached_to_name,
            ["name", "primary_clinic"],
            as_dict=True,
        )
        if not patient_doc:
            return {}

        return {
            "patient_id": patient_doc.name,
            "clinic": patient_doc.primary_clinic,
        }

    if not frappe.db.exists(attached_to_doctype, attached_to_name):
        return {}

    context = {}
    meta = frappe.get_meta(attached_to_doctype)
    fieldnames = [fieldname for fieldname in ("patient", "company", "appointment") if meta.has_field(fieldname)]
    if fieldnames:
        context.update(
            frappe.db.get_value(attached_to_doctype, attached_to_name, fieldnames, as_dict=True) or {}
        )

    appointment_id = context.get("appointment")
    if appointment_id and frappe.db.exists("Patient Appointment", appointment_id):
        appointment_context = frappe.db.get_value(
            "Patient Appointment",
            appointment_id,
            ["patient", "company"],
            as_dict=True,
        ) or {}
        context["patient"] = context.get("patient") or appointment_context.get("patient")
        context["company"] = context.get("company") or appointment_context.get("company")

    patient_id = context.get("patient")
    clinic = context.get("company")

    if patient_id and not clinic and frappe.db.exists("Patient", patient_id):
        clinic = frappe.db.get_value("Patient", patient_id, "primary_clinic")

    return {
        "patient_id": patient_id,
        "clinic": clinic,
    }


def _get_practitioner_docs():
    practitioners = frappe.get_all(
        "Healthcare Practitioner",
        filters={"user_id": ["is", "set"]},
        fields=["name", "user_id", "allowed_pages_json", "is_clinic_admin"],
        limit_page_length=0,
    )
    practitioner_docs = {}
    for row in practitioners:
        if row.get("user_id"):
            practitioner_docs[row["name"]] = frappe._dict(row)
    return practitioner_docs


def _get_target_users_for_context(clinic, patient_id, practitioner_docs, access_cache):
    if not clinic:
        return []

    cache_key = (clinic, patient_id or "")
    if cache_key in access_cache:
        return access_cache[cache_key]

    target_users = []
    for practitioner_name, practitioner_doc in practitioner_docs.items():
        user_id = practitioner_doc.get("user_id")
        if not user_id:
            continue

        if not clinic_helper.validate_practitioner_access(practitioner_name, clinic):
            continue

        if role_access.get_practitioner_patient_scope(practitioner_doc) == role_access.PATIENT_SCOPE_USER:
            if not patient_id or not patient_api._practitioner_can_access_patient(patient_id, practitioner_name, clinic):
                continue

        target_users.append(user_id)

    access_cache[cache_key] = target_users
    return target_users


def execute(clinic=None, dry_run=0, limit=None):
    """
    Backfill native DocShare access on attached clinical documents so existing
    private-file APIs work for practitioners who already have mob_clinic access.

    Optional kwargs when run via bench execute:
    - clinic: limit to a single clinic/company
    - dry_run: when truthy, report what would change without writing
    - limit: cap processed private files for debugging
    """
    dry_run = cint(dry_run)
    limit = cint(limit) if limit else 0

    file_filters = {
        "is_private": 1,
        "attached_to_doctype": ["in", sorted(SUPPORTED_ATTACHED_DOCTYPES)],
        "attached_to_name": ["is", "set"],
    }

    private_files = frappe.get_all(
        "File",
        filters=file_filters,
        fields=["name", "attached_to_doctype", "attached_to_name"],
        order_by="creation asc",
        limit_page_length=limit or 0,
    )

    practitioner_docs = _get_practitioner_docs()
    access_cache = {}
    summary = {
        "processed_files": 0,
        "matching_files": 0,
        "shares_created": 0,
        "shares_updated": 0,
        "shares_existing": 0,
        "files_without_context": 0,
        "files_without_targets": 0,
        "clinic": clinic,
        "dry_run": bool(dry_run),
    }

    share_writes = 0
    for file_row in private_files:
        summary["processed_files"] += 1

        context = _get_file_access_context(file_row.attached_to_doctype, file_row.attached_to_name)
        patient_id = context.get("patient_id")
        file_clinic = context.get("clinic")

        if clinic and file_clinic != clinic:
            continue

        if not file_clinic:
            summary["files_without_context"] += 1
            continue

        summary["matching_files"] += 1
        target_users = _get_target_users_for_context(file_clinic, patient_id, practitioner_docs, access_cache)
        if not target_users:
            summary["files_without_targets"] += 1
            continue

        for user_id in target_users:
            existing_share = frappe.db.exists(
                "DocShare",
                {
                    "share_doctype": file_row.attached_to_doctype,
                    "share_name": file_row.attached_to_name,
                    "user": user_id,
                },
            )
            if existing_share:
                existing_docshare = frappe.get_doc("DocShare", existing_share)
                if existing_docshare.read:
                    summary["shares_existing"] += 1
                    continue

                summary["shares_updated"] += 1
                if not dry_run:
                    existing_docshare.read = 1
                    existing_docshare.save(ignore_permissions=True)
                    share_writes += 1
            else:
                summary["shares_created"] += 1
                if dry_run:
                    continue

                frappe.share.add_docshare(
                    file_row.attached_to_doctype,
                    file_row.attached_to_name,
                    user=user_id,
                    read=1,
                    flags={"ignore_share_permission": True},
                    notify=0,
                )
                share_writes += 1

            if share_writes % 200 == 0:
                frappe.db.commit()

    if not dry_run:
        frappe.db.commit()

    return summary


def cint(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
