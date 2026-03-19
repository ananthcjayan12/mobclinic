import json
import re
from typing import Dict, Iterable, List, Optional

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import get_datetime


PLAYWRIGHT_NAMESPACE_FIELD = "playwright_seed_namespace"
PLAYWRIGHT_MULTI_CLINIC_FIELD = "accessible_companies_json"
PLAYWRIGHT_REQUEST_HEADER = "X-Playwright-Seed-Namespace"
PLAYWRIGHT_REQUEST_PARAM = "playwright_seed_namespace"

PLAYWRIGHT_TAGGED_DOCTYPES = [
    "Company",
    "Clinic Settings",
    "User",
    "Healthcare Practitioner",
    "Patient",
    "Patient Appointment",
    "Patient Encounter",
    "Sales Invoice",
    "Payment Entry",
    "Customer",
    "Item",
    "File",
    "Orthodontic Case",
    "Orthodontic Ledger Entry",
    "Orthodontic Commission Payout",
    "WhatsApp Message Log",
    "WhatsApp Conversation",
    "WhatsApp Conversation Message",
    "Clinic Consultant",
    "Dental Chart",
    "Dental Chart Condition",
    "Dental Chart Procedure",
    "Dental Chart Condition History",
    "Dental Chart Procedure Timeline",
]

INSERT_AFTER_BY_DOCTYPE = {
    "Company": "abbr",
    "Clinic Settings": "clinic",
    "User": "email",
    "Healthcare Practitioner": "primary_company",
    "Patient": "primary_clinic",
    "Patient Appointment": "company",
    "Patient Encounter": "company",
    "Sales Invoice": "company",
    "Payment Entry": "company",
    "Customer": "customer_name",
    "Item": "item_name",
    "File": "attached_to_name",
    "Orthodontic Case": "company",
    "Orthodontic Ledger Entry": "company",
    "Orthodontic Commission Payout": "company",
    "WhatsApp Message Log": "clinic",
    "WhatsApp Conversation": "clinic",
    "WhatsApp Conversation Message": "clinic",
    "Clinic Consultant": "consultant_name",
    "Dental Chart": "patient",
    "Dental Chart Condition": "tooth_number",
    "Dental Chart Procedure": "tooth_number",
    "Dental Chart Condition History": "notes",
    "Dental Chart Procedure Timeline": "notes",
}


def normalize_seed_namespace(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    normalized = re.sub(r"[^a-zA-Z0-9-]+", "-", str(value).strip()).strip("-").lower()
    return normalized or None


def _doctype_has_field(doctype: str, fieldname: str) -> bool:
    try:
        return bool(frappe.get_meta(doctype).has_field(fieldname))
    except Exception:
        return False


def _namespace_field_definition(doctype: str) -> dict:
    return {
        "fieldname": PLAYWRIGHT_NAMESPACE_FIELD,
        "label": "Playwright Seed Namespace",
        "fieldtype": "Data",
        "insert_after": INSERT_AFTER_BY_DOCTYPE[doctype],
        "hidden": 1,
        "read_only": 1,
        "no_copy": 1,
        "translatable": 0,
    }


def ensure_playwright_custom_fields():
    custom_fields = {
        doctype: [_namespace_field_definition(doctype)]
        for doctype in PLAYWRIGHT_TAGGED_DOCTYPES
    }

    custom_fields.setdefault("Healthcare Practitioner", []).append(
        {
            "fieldname": PLAYWRIGHT_MULTI_CLINIC_FIELD,
            "label": "Accessible Companies JSON",
            "fieldtype": "Small Text",
            "insert_after": "primary_company",
            "hidden": 1,
            "no_copy": 1,
            "translatable": 0,
        }
    )

    create_custom_fields(custom_fields, update=True)
    ensure_appointment_status_options()
    frappe.clear_cache()
    frappe.db.commit()


def ensure_appointment_status_options():
    meta = frappe.get_meta("Patient Appointment")
    status_field = meta.get_field("status")
    options = [opt.strip() for opt in (status_field.options or "").split("\n") if opt.strip()]

    required_statuses = ["To Be Invoiced", "Files To Be Uploaded"]
    needs_update = False
    for status in required_statuses:
        if status not in options:
            options.append(status)
            needs_update = True

    if not needs_update:
        return

    value = "\n".join(options)
    filters = {"doc_type": "Patient Appointment", "field_name": "status", "property": "options"}
    if not frappe.db.exists("Property Setter", filters):
        frappe.get_doc(
            {
                "doctype": "Property Setter",
                "doctype_or_field": "DocField",
                "doc_type": "Patient Appointment",
                "field_name": "status",
                "property": "options",
                "value": value,
            }
        ).insert(ignore_permissions=True)
    else:
        setter = frappe.get_doc("Property Setter", filters)
        setter.value = value
        setter.save(ignore_permissions=True)

    frappe.clear_cache(doctype="Patient Appointment")
    frappe.db.commit()


def get_request_seed_namespace() -> Optional[str]:
    namespace = None

    try:
        namespace = frappe.get_request_header(PLAYWRIGHT_REQUEST_HEADER)
    except Exception:
        namespace = None

    if not namespace:
        try:
            namespace = (
                frappe.form_dict.get(PLAYWRIGHT_REQUEST_PARAM)
                or frappe.form_dict.get(PLAYWRIGHT_NAMESPACE_FIELD)
            )
        except Exception:
            namespace = None

    return normalize_seed_namespace(namespace)


def set_seed_namespace(doctype: str, name: Optional[str], seed_namespace: Optional[str]) -> Optional[str]:
    namespace = normalize_seed_namespace(seed_namespace)
    if not namespace or not name or not _doctype_has_field(doctype, PLAYWRIGHT_NAMESPACE_FIELD):
        return namespace

    frappe.db.set_value(
        doctype,
        name,
        PLAYWRIGHT_NAMESPACE_FIELD,
        namespace,
        update_modified=False,
    )
    return namespace


def tag_document(doc, seed_namespace: Optional[str]) -> Optional[str]:
    name = getattr(doc, "name", None)
    doctype = getattr(doc, "doctype", None)
    if not doctype:
        return normalize_seed_namespace(seed_namespace)
    return set_seed_namespace(doctype, name, seed_namespace)


def tag_documents(doctype: str, names: Iterable[str], seed_namespace: Optional[str]) -> Optional[str]:
    namespace = normalize_seed_namespace(seed_namespace)
    if not namespace or not _doctype_has_field(doctype, PLAYWRIGHT_NAMESPACE_FIELD):
        return namespace

    for name in names:
        if name:
            frappe.db.set_value(
                doctype,
                name,
                PLAYWRIGHT_NAMESPACE_FIELD,
                namespace,
                update_modified=False,
            )

    return namespace


def collect_namespaced_records(
    seed_namespace: str,
    doctypes: Optional[Iterable[str]] = None,
) -> Dict[str, List[str]]:
    namespace = normalize_seed_namespace(seed_namespace)
    records: Dict[str, List[str]] = {}
    if not namespace:
        return records

    for doctype in doctypes or PLAYWRIGHT_TAGGED_DOCTYPES:
        if not _doctype_has_field(doctype, PLAYWRIGHT_NAMESPACE_FIELD):
            continue

        rows = frappe.get_all(
            doctype,
            filters={PLAYWRIGHT_NAMESPACE_FIELD: namespace},
            pluck="name",
            ignore_permissions=True,
            limit_page_length=0,
        )
        if rows:
            records[doctype] = rows

    return records


def list_stale_namespaces(prefix: str, cutoff) -> List[str]:
    namespaces = set()
    namespace_prefix = f"{normalize_seed_namespace(prefix) or 'pw'}%"
    cutoff_dt = get_datetime(cutoff)

    for doctype in PLAYWRIGHT_TAGGED_DOCTYPES:
        if not _doctype_has_field(doctype, PLAYWRIGHT_NAMESPACE_FIELD):
            continue

        rows = frappe.db.sql(
            f"""
            SELECT DISTINCT `{PLAYWRIGHT_NAMESPACE_FIELD}`
            FROM `tab{doctype}`
            WHERE IFNULL(`{PLAYWRIGHT_NAMESPACE_FIELD}`, '') != ''
              AND `{PLAYWRIGHT_NAMESPACE_FIELD}` LIKE %s
              AND modified < %s
            """,
            (namespace_prefix, cutoff_dt),
            as_list=True,
        )

        for row in rows:
            if row and row[0]:
                namespaces.add(row[0])

    return sorted(namespaces)
