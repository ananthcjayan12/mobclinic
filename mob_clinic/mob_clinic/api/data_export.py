import csv
import io
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import frappe
from frappe.utils import flt, getdate, now_datetime

from mob_clinic.mob_clinic.api import clinic as clinic_helper
from mob_clinic.mob_clinic.api import role_access

EXPORT_PATIENT_STATISTICS = "patient_statistics"
EXPORT_FINANCIAL_DATA = "financial_data"
EXPORT_TREATMENT_WISE = "treatment_wise_data"

EXPORT_TYPES = [
    {
        "key": EXPORT_PATIENT_STATISTICS,
        "label": "Patient Statistics",
        "description": "Patient master with visit and billing summary metrics.",
        "status_options": [
            "All",
            "Open",
            "Scheduled",
            "Confirmed",
            "Waiting",
            "In Progress",
            "Pending Payment",
            "Completed",
            "Cancelled",
        ],
    },
    {
        "key": EXPORT_FINANCIAL_DATA,
        "label": "Financial Data",
        "description": "Invoice-level financial records with payment status and balances.",
        "status_options": ["All", "Draft", "Unpaid", "Partly Paid", "Paid", "Overdue", "Cancelled"],
    },
    {
        "key": EXPORT_TREATMENT_WISE,
        "label": "Treatment-wise Data",
        "description": "Treatment/procedure summary aggregated from invoice items.",
        "status_options": ["All", "Unpaid", "Partly Paid", "Paid", "Overdue"],
    },
]

MAX_EXPORT_ROWS = 50000


def _parse_date_value(value: Optional[str], fieldname: str) -> Optional[date]:
    if not value:
        return None
    try:
        return getdate(value)
    except Exception:
        frappe.throw(f"Invalid {fieldname}: {value}", frappe.ValidationError)


def _normalize_optional_filter(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value).strip() or None

    stripped = value.strip()
    if not stripped or stripped.lower() == "all":
        return None
    return stripped


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _format_csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return value


def _build_csv_content(
    rows: List[Dict[str, Any]],
    columns: List[Tuple[str, str]],
    summary: Optional[Dict[str, Any]] = None,
    include_summary: bool = False,
) -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    if include_summary and summary:
        writer.writerow(["Summary Metric", "Value"])
        for key, value in summary.items():
            label = str(key).replace("_", " ").title()
            writer.writerow([label, _format_csv_value(value)])
        writer.writerow([])

    writer.writerow([label for _, label in columns])

    for row in rows:
        writer.writerow([_format_csv_value(row.get(key)) for key, _ in columns])

    # UTF-8 BOM for Excel compatibility
    return "\ufeff" + output.getvalue()


def _sanitize_filename_part(value: Optional[str]) -> str:
    if not value:
        return "all"
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value.strip())
    safe = safe.strip("_")
    return safe or "all"


def _resolve_export_context(clinic: Optional[str]) -> Tuple[Any, str, str]:
    practitioner = role_access.get_current_practitioner_doc()
    if not practitioner:
        frappe.local.response["http_status_code"] = 403
        frappe.throw("Practitioner profile is required", frappe.PermissionError)

    # Reuse existing page-access semantics: settings tab is admin-only in this app.
    try:
        role_access.assert_page_access("settings", practitioner_name=practitioner.name)
    except Exception:
        frappe.local.response["http_status_code"] = 403
        frappe.throw("Clinic admin access required", frappe.PermissionError)

    resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name, clinic)
    if not resolved_clinic:
        frappe.local.response["http_status_code"] = 400
        frappe.throw("Clinic is required", frappe.ValidationError)

    if not clinic_helper.validate_practitioner_access(practitioner.name, resolved_clinic):
        frappe.local.response["http_status_code"] = 403
        frappe.throw("Clinic access denied", frappe.PermissionError)

    patient_scope = role_access.get_practitioner_patient_scope(practitioner)
    return practitioner, resolved_clinic, patient_scope


def _get_practitioner_patient_ids(practitioner_id: str, clinic: Optional[str]) -> List[str]:
    filters: Dict[str, Any] = {"practitioner": practitioner_id}
    if clinic:
        filters["company"] = clinic

    rows = frappe.get_all(
        "Patient Appointment",
        filters=filters,
        fields=["patient"],
        limit_page_length=0,
    )
    return sorted({row.get("patient") for row in rows if row.get("patient")})


def _coerce_practitioner_filter(
    requested_practitioner: Optional[str],
    active_practitioner: str,
    patient_scope: str,
) -> Optional[str]:
    if patient_scope == role_access.PATIENT_SCOPE_USER:
        return active_practitioner
    return requested_practitioner


def _build_patient_statistics_rows(
    clinic: str,
    patient_scope: str,
    active_practitioner: str,
    practitioner_filter: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
    status_filter: Optional[str],
) -> List[Dict[str, Any]]:
    selected_practitioner = _coerce_practitioner_filter(
        practitioner_filter, active_practitioner, patient_scope
    )

    ownership_patient_ids: Optional[List[str]] = None
    if selected_practitioner:
        ownership_patient_ids = _get_practitioner_patient_ids(selected_practitioner, clinic)
        if not ownership_patient_ids:
            return []

    patient_filters: Dict[str, Any] = {"primary_clinic": clinic}
    if ownership_patient_ids is not None:
        patient_filters["name"] = ["in", ownership_patient_ids]

    patients = frappe.get_all(
        "Patient",
        filters=patient_filters,
        fields=[
            "name",
            "patient_name",
            "mobile",
            "email",
            "sex",
            "dob",
            "status",
            "registration_date",
            "primary_clinic",
        ],
        order_by="patient_name asc",
        limit_page_length=0,
    )

    if not patients:
        return []

    patient_ids = [row["name"] for row in patients]
    appointment_filters: Dict[str, Any] = {
        "patient": ["in", patient_ids],
        "company": clinic,
    }
    if selected_practitioner:
        appointment_filters["practitioner"] = selected_practitioner
    if status_filter:
        appointment_filters["status"] = status_filter
    if date_from and date_to:
        appointment_filters["appointment_date"] = ["between", [date_from, date_to]]
    elif date_from:
        appointment_filters["appointment_date"] = [">=", date_from]
    elif date_to:
        appointment_filters["appointment_date"] = ["<=", date_to]

    appointments = frappe.get_all(
        "Patient Appointment",
        filters=appointment_filters,
        fields=[
            "patient",
            "practitioner",
            "practitioner_name",
            "appointment_date",
            "appointment_time",
            "status",
        ],
        order_by="appointment_date desc, appointment_time desc, creation desc",
        limit_page_length=0,
    )

    appointment_summary: Dict[str, Dict[str, Any]] = {}
    for appt in appointments:
        patient_id = appt.get("patient")
        if not patient_id:
            continue

        summary = appointment_summary.setdefault(
            patient_id,
            {
                "total_visits": 0,
                "completed_visits": 0,
                "last_visit": None,
                "last_practitioner_id": "",
                "last_practitioner_name": "",
            },
        )
        summary["total_visits"] += 1
        if appt.get("status") == "Completed":
            summary["completed_visits"] += 1

        if not summary["last_visit"]:
            appointment_date = appt.get("appointment_date")
            appointment_time = appt.get("appointment_time")
            if appointment_date and appointment_time:
                summary["last_visit"] = f"{appointment_date} {appointment_time}"
            else:
                summary["last_visit"] = appointment_date
            summary["last_practitioner_id"] = appt.get("practitioner") or ""
            summary["last_practitioner_name"] = appt.get("practitioner_name") or ""

    invoice_filters: Dict[str, Any] = {
        "docstatus": 1,
        "patient": ["in", patient_ids],
        "company": clinic,
    }
    if date_from and date_to:
        invoice_filters["posting_date"] = ["between", [date_from, date_to]]
    elif date_from:
        invoice_filters["posting_date"] = [">=", date_from]
    elif date_to:
        invoice_filters["posting_date"] = ["<=", date_to]

    if selected_practitioner:
        invoice_filters["healthcare_practitioner"] = selected_practitioner

    invoices = frappe.get_all(
        "Sales Invoice",
        filters=invoice_filters,
        fields=["patient", "grand_total", "outstanding_amount"],
        limit_page_length=0,
    )

    invoice_summary: Dict[str, Dict[str, float]] = {}
    for inv in invoices:
        patient_id = inv.get("patient")
        if not patient_id:
            continue
        summary = invoice_summary.setdefault(
            patient_id,
            {"total_invoiced": 0.0, "total_paid": 0.0, "outstanding_amount": 0.0},
        )
        grand_total = flt(inv.get("grand_total"))
        outstanding = flt(inv.get("outstanding_amount"))
        summary["total_invoiced"] += grand_total
        summary["outstanding_amount"] += outstanding
        summary["total_paid"] += (grand_total - outstanding)

    rows: List[Dict[str, Any]] = []
    for patient in patients:
        patient_id = patient.get("name")
        appt = appointment_summary.get(patient_id, {})
        inv = invoice_summary.get(patient_id, {})
        rows.append(
            {
                "patient_id": patient_id,
                "patient_name": patient.get("patient_name"),
                "mobile": patient.get("mobile"),
                "email": patient.get("email"),
                "sex": patient.get("sex"),
                "dob": patient.get("dob"),
                "status": patient.get("status"),
                "registration_date": patient.get("registration_date"),
                "primary_clinic": patient.get("primary_clinic"),
                "total_visits": int(appt.get("total_visits") or 0),
                "completed_visits": int(appt.get("completed_visits") or 0),
                "last_visit": appt.get("last_visit") or "",
                "last_practitioner_id": appt.get("last_practitioner_id") or "",
                "last_practitioner_name": appt.get("last_practitioner_name") or "",
                "total_invoiced": round(flt(inv.get("total_invoiced")), 2),
                "total_paid": round(flt(inv.get("total_paid")), 2),
                "outstanding_amount": round(flt(inv.get("outstanding_amount")), 2),
            }
        )

    return rows


def _build_patient_statistics_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "total_patients": len(rows),
        "total_visits": sum(int(row.get("total_visits") or 0) for row in rows),
        "completed_visits": sum(int(row.get("completed_visits") or 0) for row in rows),
        "total_invoiced_amount": round(sum(flt(row.get("total_invoiced")) for row in rows), 2),
        "total_paid_amount": round(sum(flt(row.get("total_paid")) for row in rows), 2),
        "total_outstanding_amount": round(sum(flt(row.get("outstanding_amount")) for row in rows), 2),
    }


def _fetch_invoices_for_export(
    clinic: str,
    patient_scope: str,
    active_practitioner: str,
    practitioner_filter: Optional[str],
    date_from: Optional[date],
    date_to: Optional[date],
    status_filter: Optional[str],
) -> List[Dict[str, Any]]:
    selected_practitioner = _coerce_practitioner_filter(
        practitioner_filter, active_practitioner, patient_scope
    )

    filters: Dict[str, Any] = {"company": clinic}

    if status_filter == "Cancelled":
        filters["docstatus"] = 2
    else:
        filters["docstatus"] = ["!=", 2]
    if date_from and date_to:
        filters["posting_date"] = ["between", [date_from, date_to]]
    elif date_from:
        filters["posting_date"] = [">=", date_from]
    elif date_to:
        filters["posting_date"] = ["<=", date_to]

    if status_filter:
        filters["status"] = status_filter

    if selected_practitioner:
        filters["healthcare_practitioner"] = selected_practitioner

    if patient_scope == role_access.PATIENT_SCOPE_USER:
        allowed_patients = _get_practitioner_patient_ids(active_practitioner, clinic)
        if not allowed_patients:
            return []
        filters["patient"] = ["in", allowed_patients]

    return frappe.get_all(
        "Sales Invoice",
        filters=filters,
        fields=[
            "name",
            "docstatus",
            "posting_date",
            "due_date",
            "status",
            "patient",
            "patient_name",
            "company",
            "healthcare_practitioner",
            "grand_total",
            "outstanding_amount",
            "total_taxes_and_charges",
            "net_total",
            "currency",
            "creation",
        ],
        order_by="posting_date desc, creation desc",
        limit_page_length=0,
    )


def _build_financial_rows(invoices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not invoices:
        return []

    practitioner_ids = sorted(
        {
            row.get("healthcare_practitioner")
            for row in invoices
            if row.get("healthcare_practitioner")
        }
    )
    practitioner_names: Dict[str, str] = {}
    if practitioner_ids:
        practitioners = frappe.get_all(
            "Healthcare Practitioner",
            filters={"name": ["in", practitioner_ids]},
            fields=["name", "practitioner_name"],
            limit_page_length=0,
        )
        practitioner_names = {
            row.get("name"): row.get("practitioner_name") or row.get("name")
            for row in practitioners
        }

    invoice_ids = [row["name"] for row in invoices]
    refs = frappe.get_all(
        "Payment Entry Reference",
        filters={
            "reference_doctype": "Sales Invoice",
            "reference_name": ["in", invoice_ids],
        },
        fields=["reference_name", "parent", "allocated_amount"],
        order_by="modified desc",
        limit_page_length=0,
    )

    payment_entry_ids = sorted({row.get("parent") for row in refs if row.get("parent")})
    payments_by_id: Dict[str, Dict[str, Any]] = {}
    if payment_entry_ids:
        payments = frappe.get_all(
            "Payment Entry",
            filters={"name": ["in", payment_entry_ids], "docstatus": 1},
            fields=["name", "mode_of_payment", "posting_date"],
            limit_page_length=0,
        )
        payments_by_id = {row["name"]: row for row in payments}

    refs_by_invoice: Dict[str, List[Dict[str, Any]]] = {}
    for row in refs:
        refs_by_invoice.setdefault(row.get("reference_name"), []).append(row)

    rows: List[Dict[str, Any]] = []
    for inv in invoices:
        ref_rows = refs_by_invoice.get(inv.get("name"), [])
        latest_payment_date = None
        latest_payment_mode = ""
        for ref in ref_rows:
            payment = payments_by_id.get(ref.get("parent"))
            if not payment:
                continue
            payment_date = payment.get("posting_date")
            if latest_payment_date is None or (payment_date and payment_date > latest_payment_date):
                latest_payment_date = payment_date
                latest_payment_mode = payment.get("mode_of_payment") or ""

        grand_total = flt(inv.get("grand_total"))
        outstanding = flt(inv.get("outstanding_amount"))
        rows.append(
            {
                "invoice_id": inv.get("name"),
                "posting_date": inv.get("posting_date"),
                "due_date": inv.get("due_date"),
                "status": inv.get("status"),
                "company": inv.get("company"),
                "patient_id": inv.get("patient"),
                "patient_name": inv.get("patient_name"),
                "practitioner_name": practitioner_names.get(
                    inv.get("healthcare_practitioner"), inv.get("healthcare_practitioner") or ""
                ),
                "currency": inv.get("currency"),
                "net_total": round(flt(inv.get("net_total")), 2),
                "tax_amount": round(flt(inv.get("total_taxes_and_charges")), 2),
                "gross_total": round(grand_total, 2),
                "paid_amount": round(grand_total - outstanding, 2),
                "outstanding_amount": round(outstanding, 2),
                "last_payment_mode": latest_payment_mode,
                "last_payment_date": latest_payment_date or "",
            }
        )

    return rows


def _build_financial_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    paid_rows = [row for row in rows if (row.get("status") or "").lower() == "paid"]
    outstanding_rows = [row for row in rows if flt(row.get("outstanding_amount")) > 0]
    return {
        "total_invoices": len(rows),
        "paid_invoices": len(paid_rows),
        "invoices_with_outstanding": len(outstanding_rows),
        "total_net_amount": round(sum(flt(row.get("net_total")) for row in rows), 2),
        "total_tax_amount": round(sum(flt(row.get("tax_amount")) for row in rows), 2),
        "total_gross_amount": round(sum(flt(row.get("gross_total")) for row in rows), 2),
        "total_paid_amount": round(sum(flt(row.get("paid_amount")) for row in rows), 2),
        "total_outstanding_amount": round(sum(flt(row.get("outstanding_amount")) for row in rows), 2),
    }


def _build_treatment_wise_rows(invoices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    submitted_invoices = [row for row in invoices if int(row.get("docstatus") or 0) == 1]
    if not submitted_invoices:
        return []

    invoice_map = {row["name"]: row for row in submitted_invoices}
    invoice_ids = list(invoice_map.keys())

    items = frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": ["in", invoice_ids]},
        fields=[
            "parent",
            "item_code",
            "item_name",
            "qty",
            "rate",
            "amount",
            "net_amount",
        ],
        limit_page_length=0,
    )

    practitioner_ids = sorted(
        {
            row.get("healthcare_practitioner")
            for row in submitted_invoices
            if row.get("healthcare_practitioner")
        }
    )
    practitioner_names: Dict[str, str] = {}
    if practitioner_ids:
        practitioners = frappe.get_all(
            "Healthcare Practitioner",
            filters={"name": ["in", practitioner_ids]},
            fields=["name", "practitioner_name"],
            limit_page_length=0,
        )
        practitioner_names = {
            row.get("name"): row.get("practitioner_name") or row.get("name")
            for row in practitioners
        }

    grouped: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    for item in items:
        parent = item.get("parent")
        invoice = invoice_map.get(parent)
        if not invoice:
            continue

        item_code = item.get("item_code") or ""
        item_name = item.get("item_name") or ""
        company = invoice.get("company") or ""
        practitioner_id = invoice.get("healthcare_practitioner") or ""
        key = (item_code, item_name, company, practitioner_id)

        row = grouped.setdefault(
            key,
            {
                "treatment_code": item_code,
                "treatment_name": item_name,
                "company": company,
                "practitioner_id": practitioner_id,
                "practitioner_name": practitioner_names.get(practitioner_id, practitioner_id),
                "line_count": 0,
                "invoice_ids": set(),
                "total_quantity": 0.0,
                "total_revenue": 0.0,
            },
        )
        row["line_count"] += 1
        row["invoice_ids"].add(parent)
        row["total_quantity"] += flt(item.get("qty"))
        row["total_revenue"] += flt(item.get("amount") or item.get("net_amount"))

    rows: List[Dict[str, Any]] = []
    for _, agg in grouped.items():
        invoice_count = len(agg["invoice_ids"])
        line_count = agg["line_count"]
        total_revenue = agg["total_revenue"]
        rows.append(
            {
                "treatment_code": agg["treatment_code"],
                "treatment_name": agg["treatment_name"],
                "company": agg["company"],
                "practitioner_name": agg["practitioner_name"],
                "invoice_count": invoice_count,
                "line_count": line_count,
                "total_quantity": round(agg["total_quantity"], 2),
                "total_revenue": round(total_revenue, 2),
                "avg_revenue_per_line": round((total_revenue / line_count) if line_count else 0.0, 2),
            }
        )

    rows.sort(key=lambda row: (row["total_revenue"], row["line_count"]), reverse=True)
    return rows


def _build_treatment_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "total_treatment_groups": len(rows),
        "total_invoice_count": sum(int(row.get("invoice_count") or 0) for row in rows),
        "total_line_count": sum(int(row.get("line_count") or 0) for row in rows),
        "total_quantity": round(sum(flt(row.get("total_quantity")) for row in rows), 2),
        "total_revenue": round(sum(flt(row.get("total_revenue")) for row in rows), 2),
    }


def _resolve_columns(export_type: str) -> List[Tuple[str, str]]:
    if export_type == EXPORT_PATIENT_STATISTICS:
        return [
            ("patient_id", "Patient ID"),
            ("patient_name", "Patient Name"),
            ("mobile", "Mobile"),
            ("email", "Email"),
            ("sex", "Sex"),
            ("dob", "Date of Birth"),
            ("status", "Patient Status"),
            ("registration_date", "Registration Date"),
            ("primary_clinic", "Primary Clinic"),
            ("total_visits", "Total Visits"),
            ("completed_visits", "Completed Visits"),
            ("last_visit", "Last Visit"),
            ("last_practitioner_name", "Last Practitioner"),
            ("total_invoiced", "Total Invoiced"),
            ("total_paid", "Total Paid"),
            ("outstanding_amount", "Outstanding Amount"),
        ]

    if export_type == EXPORT_FINANCIAL_DATA:
        return [
            ("invoice_id", "Invoice ID"),
            ("posting_date", "Posting Date"),
            ("due_date", "Due Date"),
            ("status", "Invoice Status"),
            ("company", "Clinic"),
            ("patient_id", "Patient ID"),
            ("patient_name", "Patient Name"),
            ("practitioner_name", "Healthcare Practitioner"),
            ("currency", "Currency"),
            ("net_total", "Net Total"),
            ("tax_amount", "Tax Amount"),
            ("gross_total", "Gross Total"),
            ("paid_amount", "Paid Amount"),
            ("outstanding_amount", "Outstanding Amount"),
            ("last_payment_mode", "Last Payment Mode"),
            ("last_payment_date", "Last Payment Date"),
        ]

    return [
        ("treatment_code", "Treatment Code"),
        ("treatment_name", "Treatment Name"),
        ("company", "Clinic"),
        ("practitioner_name", "Healthcare Practitioner"),
        ("invoice_count", "Invoice Count"),
        ("line_count", "Line Count"),
        ("total_quantity", "Total Quantity"),
        ("total_revenue", "Total Revenue"),
        ("avg_revenue_per_line", "Avg Revenue Per Line"),
    ]


@frappe.whitelist(methods=["GET"])
def get_data_export_config(clinic: Optional[str] = None):
    try:
        practitioner, clinic_name, _ = _resolve_export_context(clinic)

        practitioners = frappe.get_all(
            "Healthcare Practitioner",
            filters={"primary_company": clinic_name},
            fields=["name", "practitioner_name"],
            order_by="practitioner_name asc",
        )

        default_to = now_datetime().date()
        default_from = default_to.replace(day=1)

        return {
            "message": "success",
            "data": {
                "clinic": clinic_name,
                "requested_by": practitioner.name,
                "export_types": EXPORT_TYPES,
                "practitioners": [
                    {
                        "practitioner_id": row.get("name"),
                        "practitioner_name": row.get("practitioner_name"),
                    }
                    for row in practitioners
                ],
                "default_date_from": str(default_from),
                "default_date_to": str(default_to),
            },
        }
    except Exception as e:
        status_code = frappe.local.response.get("http_status_code")
        if status_code and status_code < 500:
            return {
                "exc_type": type(e).__name__,
                "message": str(e),
            }
        frappe.log_error(frappe.get_traceback(), "Get Data Export Config Error")
        if not status_code:
            frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": "Error loading export configuration"}


@frappe.whitelist(methods=["POST"])
def export_data_csv(
    export_type: Optional[str] = None,
    clinic: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    practitioner: Optional[str] = None,
    status: Optional[str] = None,
    include_summary: Any = 1,
):
    try:
        practitioner_doc, clinic_name, patient_scope = _resolve_export_context(clinic)

        export_type = (export_type or "").strip()
        if export_type not in {EXPORT_PATIENT_STATISTICS, EXPORT_FINANCIAL_DATA, EXPORT_TREATMENT_WISE}:
            frappe.local.response["http_status_code"] = 400
            return {"exc_type": "ValidationError", "message": "Invalid export_type"}

        date_from_value = _parse_date_value(date_from, "date_from")
        date_to_value = _parse_date_value(date_to, "date_to")
        if date_from_value and date_to_value and date_from_value > date_to_value:
            frappe.local.response["http_status_code"] = 400
            return {"exc_type": "ValidationError", "message": "date_from cannot be after date_to"}

        requested_practitioner = _normalize_optional_filter(practitioner)
        requested_status = _normalize_optional_filter(status)
        include_summary_flag = _parse_bool(include_summary)

        if requested_practitioner and not frappe.db.exists("Healthcare Practitioner", requested_practitioner):
            frappe.local.response["http_status_code"] = 400
            return {"exc_type": "ValidationError", "message": "Invalid practitioner filter"}

        rows: List[Dict[str, Any]]
        summary: Dict[str, Any]
        if export_type == EXPORT_PATIENT_STATISTICS:
            rows = _build_patient_statistics_rows(
                clinic=clinic_name,
                patient_scope=patient_scope,
                active_practitioner=practitioner_doc.name,
                practitioner_filter=requested_practitioner,
                date_from=date_from_value,
                date_to=date_to_value,
                status_filter=requested_status,
            )
            summary = _build_patient_statistics_summary(rows)
        else:
            invoices = _fetch_invoices_for_export(
                clinic=clinic_name,
                patient_scope=patient_scope,
                active_practitioner=practitioner_doc.name,
                practitioner_filter=requested_practitioner,
                date_from=date_from_value,
                date_to=date_to_value,
                status_filter=requested_status,
            )
            if export_type == EXPORT_FINANCIAL_DATA:
                rows = _build_financial_rows(invoices)
                summary = _build_financial_summary(rows)
            else:
                rows = _build_treatment_wise_rows(invoices)
                summary = _build_treatment_summary(rows)

        if len(rows) > MAX_EXPORT_ROWS:
            frappe.local.response["http_status_code"] = 400
            return {
                "exc_type": "ValidationError",
                "message": f"Export has {len(rows)} rows. Narrow filters to under {MAX_EXPORT_ROWS} rows.",
            }

        columns = _resolve_columns(export_type)
        csv_content = _build_csv_content(
            rows=rows,
            columns=columns,
            summary=summary,
            include_summary=include_summary_flag,
        )
        generated_at = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
        filename = (
            f"{export_type}_{_sanitize_filename_part(clinic_name)}_"
            f"{now_datetime().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        return {
            "message": "success",
            "data": {
                "export_type": export_type,
                "clinic": clinic_name,
                "patient_scope": patient_scope,
                "filename": filename,
                "row_count": len(rows),
                "generated_at": generated_at,
                "columns": [label for _, label in columns],
                "summary": summary,
                "include_summary": include_summary_flag,
                "csv_content": csv_content,
            },
        }
    except Exception as e:
        status_code = frappe.local.response.get("http_status_code")
        if status_code and status_code < 500:
            return {
                "exc_type": type(e).__name__,
                "message": str(e),
            }
        frappe.log_error(frappe.get_traceback(), "Export Data CSV Error")
        if not status_code:
            frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": "Error generating export"}
