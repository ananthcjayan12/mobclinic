import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import (
    add_days,
    flt,
    get_first_day,
    get_last_day,
    getdate,
    nowdate,
    today,
)

from mob_clinic.mob_clinic.api import clinic as clinic_helper
from mob_clinic.mob_clinic.api.payment import (
    _get_clinic_consultant,
    create_invoice,
    update_payment,
)
from mob_clinic.mob_clinic.api.role_access import (
    assert_page_access,
    get_practitioner_permissions,
)


ACTIVE_CASE_STATUSES = {"Planned", "Active", "On Hold"}
COMPLETED_CASE_STATUSES = {"Completed", "Cancelled"}


def _parse_json(value, default=None):
    if value is None:
        return default
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return default
        return json.loads(value)
    return value


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _get_context(page_key="patients", clinic=None, require_admin=False):
    practitioner = assert_page_access(page_key)
    resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name, clinic)
    if clinic and resolved_clinic and not clinic_helper.validate_practitioner_access(
        practitioner.name, resolved_clinic
    ):
        frappe.throw(
            _("Practitioner does not have access to the requested clinic"),
            frappe.PermissionError,
        )

    if require_admin:
        permissions = get_practitioner_permissions(practitioner)
        if not permissions.get("is_clinic_admin"):
            frappe.throw(_("Clinic admin access required"), frappe.PermissionError)

    return practitioner, resolved_clinic


def _build_client_permissions(practitioner):
    permissions = get_practitioner_permissions(practitioner)
    return {
        "is_clinic_admin": bool(permissions.get("is_clinic_admin")),
        "can_manage_commission": bool(permissions.get("is_clinic_admin")),
        "can_edit_case": True,
        "can_add_visit": True,
    }


def _assert_invoice_access(practitioner, message=None):
    try:
        assert_page_access("invoice", practitioner_name=practitioner.name)
    except frappe.PermissionError:
        frappe.throw(
            message
            or _("Invoice access is required to record orthodontic payments"),
            frappe.PermissionError,
        )


def _ensure_patient(patient_id):
    if not frappe.db.exists("Patient", patient_id):
        frappe.throw(_("Patient not found"))
    return frappe.get_doc("Patient", patient_id)


def _ensure_practitioner(practitioner_id, clinic=None):
    if not frappe.db.exists("Healthcare Practitioner", practitioner_id):
        frappe.throw(_("Associated doctor not found"))

    if clinic and not clinic_helper.validate_practitioner_access(practitioner_id, clinic):
        frappe.throw(_("Selected doctor does not belong to the active clinic"))

    return frappe.get_doc("Healthcare Practitioner", practitioner_id)


def _get_case_doc(case_id):
    if not frappe.db.exists("Orthodontic Case", case_id):
        frappe.throw(_("Orthodontic case not found"))
    return frappe.get_doc("Orthodontic Case", case_id)


def _assert_case_access(case_doc, practitioner):
    if case_doc.company and not clinic_helper.validate_practitioner_access(
        practitioner.name, case_doc.company
    ):
        frappe.throw(_("Clinic access denied"), frappe.PermissionError)


def _ledger_order_by():
    return "visit_date asc, creation asc, name asc"


def _commission_status(accrued, paid):
    accrued = round(flt(accrued), 2)
    paid = round(flt(paid), 2)

    if accrued <= 0:
        return "Not Applicable"
    if paid <= 0:
        return "Unpaid"
    if paid >= accrued:
        return "Paid"
    return "Partly Paid"


def _get_latest_invoice_snapshot(invoice_id):
    if not invoice_id:
        return {}

    invoice = frappe.get_doc("Sales Invoice", invoice_id)
    if not invoice.items:
        return {}

    item = invoice.items[0]
    return {
        "consultant_id": item.get("consultant_id"),
        "consultant_name": item.get("consultant_name"),
        "consultant_type": item.get("consultant_type"),
        "consultant_practitioner": item.get("consultant_practitioner"),
        "consultant_commission_type": item.get("consultant_commission_type"),
        "consultant_commission_value": flt(item.get("consultant_commission_value")),
        "consultant_commission_amount": flt(item.get("consultant_commission_amount")),
        "consultant_commission_source": item.get("consultant_commission_source"),
    }


def _serialize_case(case_doc):
    case_doc.reload()
    return {
        "case_id": case_doc.name,
        "company": case_doc.company,
        "patient_id": case_doc.patient,
        "patient_name": case_doc.patient_name,
        "practitioner_id": case_doc.practitioner,
        "practitioner_name": case_doc.practitioner_name,
        "case_type": case_doc.case_type,
        "start_date": str(case_doc.start_date) if case_doc.start_date else None,
        "estimated_duration_months": case_doc.estimated_duration_months,
        "estimated_end_date": str(case_doc.estimated_end_date)
        if case_doc.estimated_end_date
        else None,
        "package_fee": flt(case_doc.package_fee),
        "discount_amount": flt(case_doc.discount_amount),
        "discount_percentage": flt(case_doc.discount_percentage),
        "advance_paid": flt(case_doc.advance_paid),
        "net_fee": flt(case_doc.net_fee),
        "total_paid": flt(case_doc.total_paid),
        "balance_amount": flt(case_doc.balance_amount),
        "next_appointment_date": str(case_doc.next_appointment_date)
        if case_doc.next_appointment_date
        else None,
        "last_visit_date": str(case_doc.last_visit_date)
        if case_doc.last_visit_date
        else None,
        "last_payment_date": str(case_doc.last_payment_date)
        if case_doc.last_payment_date
        else None,
        "status": case_doc.status,
        "notes": case_doc.notes,
        "default_followup_days": case_doc.default_followup_days,
        "is_active": int(case_doc.is_active or 0),
        "consultant_id": case_doc.consultant_id,
        "consultant_name": case_doc.consultant_name,
        "consultant_type": case_doc.consultant_type,
        "consultant_practitioner": case_doc.consultant_practitioner,
        "commission_model": case_doc.commission_model,
        "commission_type": case_doc.commission_type,
        "commission_value": flt(case_doc.commission_value),
        "commission_basis": case_doc.commission_basis,
        "total_commission_accrued": flt(case_doc.total_commission_accrued),
        "total_commission_paid": flt(case_doc.total_commission_paid),
        "pending_commission_amount": flt(case_doc.pending_commission_amount),
    }


def _serialize_ledger(entry_doc):
    return {
        "ledger_entry_id": entry_doc.name,
        "case_id": entry_doc.orthodontic_case,
        "visit_date": str(entry_doc.visit_date) if entry_doc.visit_date else None,
        "visit_notes": entry_doc.visit_notes,
        "payment_amount": flt(entry_doc.payment_amount),
        "payment_mode": entry_doc.payment_mode,
        "balance_after_entry": flt(entry_doc.balance_after_entry),
        "next_appointment_date": str(entry_doc.next_appointment_date)
        if entry_doc.next_appointment_date
        else None,
        "sales_invoice": entry_doc.sales_invoice,
        "payment_entry": entry_doc.payment_entry,
        "receipt_number": entry_doc.receipt_number,
        "created_by": entry_doc.created_by,
        "is_adjustment": int(entry_doc.is_adjustment or 0),
        "adjustment_reason": entry_doc.adjustment_reason,
        "consultant_id": entry_doc.consultant_id,
        "consultant_name": entry_doc.consultant_name,
        "consultant_type": entry_doc.consultant_type,
        "consultant_practitioner": entry_doc.consultant_practitioner,
        "commission_type": entry_doc.consultant_commission_type,
        "commission_value": flt(entry_doc.consultant_commission_value),
        "commission_amount": flt(entry_doc.consultant_commission_amount),
        "commission_source": entry_doc.consultant_commission_source,
        "commission_basis": entry_doc.commission_basis,
        "commission_status": entry_doc.commission_status,
        "commission_payout_reference": entry_doc.commission_payout_reference,
        "commission_paid_date": str(entry_doc.commission_paid_date)
        if entry_doc.commission_paid_date
        else None,
        "commission_paid_amount": flt(entry_doc.commission_paid_amount),
        "commission_note": entry_doc.commission_note,
    }


def _serialize_payout(payout_doc):
    return {
        "payout_id": payout_doc.name,
        "case_id": payout_doc.orthodontic_case,
        "company": payout_doc.company,
        "consultant_id": payout_doc.consultant_id,
        "consultant_name": payout_doc.consultant_name,
        "consultant_practitioner": payout_doc.consultant_practitioner,
        "posting_date": str(payout_doc.posting_date) if payout_doc.posting_date else None,
        "paid_amount": flt(payout_doc.paid_amount),
        "payment_mode": payout_doc.payment_mode,
        "reference_no": payout_doc.reference_no,
        "notes": payout_doc.notes,
        "paid_by": payout_doc.paid_by,
        "status": payout_doc.status,
        "reversal_notes": payout_doc.reversal_notes,
        "allocations": [
            {
                "ledger_entry": row.ledger_entry,
                "commission_accrued_amount": flt(row.commission_accrued_amount),
                "commission_paid_amount": flt(row.commission_paid_amount),
            }
            for row in payout_doc.get("allocations") or []
        ],
    }


def recalculate_orthodontic_case(case_id):
    case_doc = _get_case_doc(case_id)
    ledger_rows = frappe.get_all(
        "Orthodontic Ledger Entry",
        filters={"orthodontic_case": case_id},
        fields=[
            "name",
            "visit_date",
            "payment_amount",
            "next_appointment_date",
            "consultant_commission_amount",
            "commission_paid_amount",
        ],
        order_by=_ledger_order_by(),
    )

    running_paid = 0.0
    last_visit_date = None
    last_payment_date = None
    next_appointment_date = None
    total_commission_accrued = 0.0
    total_commission_paid = 0.0

    for row in ledger_rows:
        payment_amount = flt(row.payment_amount)
        running_paid += payment_amount
        balance_after_entry = round(max(flt(case_doc.net_fee) - running_paid, 0), 2)
        total_commission_accrued += flt(row.consultant_commission_amount)
        total_commission_paid += flt(row.commission_paid_amount)

        updates = {
            "balance_after_entry": balance_after_entry,
            "commission_status": _commission_status(
                row.consultant_commission_amount, row.commission_paid_amount
            ),
        }
        frappe.db.set_value(
            "Orthodontic Ledger Entry",
            row.name,
            updates,
            update_modified=False,
        )

        if row.visit_date:
            last_visit_date = row.visit_date
            if payment_amount > 0:
                last_payment_date = row.visit_date

        if row.next_appointment_date:
            next_appointment_date = row.next_appointment_date

    case_doc.total_paid = round(running_paid, 2)
    case_doc.balance_amount = round(max(flt(case_doc.net_fee) - running_paid, 0), 2)
    case_doc.last_visit_date = last_visit_date
    case_doc.last_payment_date = last_payment_date
    case_doc.next_appointment_date = next_appointment_date
    case_doc.total_commission_accrued = round(total_commission_accrued, 2)
    case_doc.total_commission_paid = round(total_commission_paid, 2)
    case_doc.pending_commission_amount = round(
        max(total_commission_accrued - total_commission_paid, 0), 2
    )
    case_doc.is_active = 0 if case_doc.status in COMPLETED_CASE_STATUSES else 1
    case_doc.save(ignore_permissions=True)
    return case_doc


def _calculate_commission_amount(case_doc, payment_amount, commission_type, commission_value):
    payment_amount = flt(payment_amount)
    commission_value = flt(commission_value)

    if payment_amount <= 0:
        return 0.0

    if commission_type == "Percentage":
        return round((payment_amount * commission_value) / 100.0, 2)

    if case_doc.commission_model == "Fixed per case":
        case_total = flt(case_doc.net_fee)
        if case_total <= 0 or commission_value <= 0:
            return 0.0

        current_accrued = flt(case_doc.total_commission_accrued)
        running_paid = flt(case_doc.total_paid) + payment_amount
        target_accrual = min(
            commission_value,
            round((running_paid / case_total) * commission_value, 2),
        )
        return round(max(target_accrual - current_accrued, 0), 2)

    return round(commission_value, 2)


def _build_case_commission_snapshot(case_doc, payment_amount, override=None):
    snapshot = {
        "consultant_id": case_doc.consultant_id,
        "consultant_name": case_doc.consultant_name,
        "consultant_type": case_doc.consultant_type,
        "consultant_practitioner": case_doc.consultant_practitioner,
        "consultant_commission_type": "",
        "consultant_commission_value": 0.0,
        "consultant_commission_amount": 0.0,
        "consultant_commission_source": "None",
        "commission_basis": case_doc.commission_basis or "",
    }

    if not case_doc.consultant_id or case_doc.commission_model == "None":
        return snapshot

    override = override or {}
    payment_amount = flt(payment_amount)
    if payment_amount <= 0:
        return snapshot

    if override:
        commission_type = override.get("commission_type")
        commission_value = flt(override.get("commission_value"))
        if commission_type not in {"Percentage", "Fixed"}:
            frappe.throw(_("Invalid override commission type"))
        if commission_value < 0:
            frappe.throw(_("Commission value cannot be negative"))
        if commission_type == "Percentage" and commission_value > 100:
            frappe.throw(_("Percentage commission cannot exceed 100"))

        snapshot.update(
            {
                "consultant_commission_type": commission_type,
                "consultant_commission_value": commission_value,
                "consultant_commission_amount": _calculate_commission_amount(
                    case_doc, payment_amount, commission_type, commission_value
                ),
                "consultant_commission_source": "Override",
                "commission_basis": override.get("commission_basis")
                or case_doc.commission_basis
                or "On collected amount",
            }
        )
        return snapshot

    commission_type = case_doc.commission_type or (
        "Percentage" if case_doc.commission_model == "Percentage" else "Fixed"
    )
    commission_value = flt(case_doc.commission_value)

    snapshot.update(
        {
            "consultant_commission_type": commission_type,
            "consultant_commission_value": commission_value,
            "consultant_commission_amount": _calculate_commission_amount(
                case_doc, payment_amount, commission_type, commission_value
            ),
            "consultant_commission_source": "Default",
            "commission_basis": case_doc.commission_basis or "On collected amount",
        }
    )
    return snapshot


def _normalize_invoice_commission_type(commission_type):
    commission_type = (commission_type or "").strip()
    if commission_type in {"Percentage", "Fixed"}:
        return commission_type
    if commission_type in {"Fixed per payment", "Fixed per case"}:
        return "Fixed"
    return ""


def _build_invoice_consultant_payload(case_doc, commission_snapshot):
    if not case_doc.consultant_id:
        return None

    commission_source = (commission_snapshot.get("consultant_commission_source") or "").strip()
    commission_type = _normalize_invoice_commission_type(
        commission_snapshot.get("consultant_commission_type")
    )
    commission_value = flt(commission_snapshot.get("consultant_commission_value"))

    if commission_source in {"", "None"} or not commission_type:
        return None

    if case_doc.commission_model == "Fixed per case" and commission_type == "Fixed":
        return None

    override_required = True
    try:
        consultant = _get_clinic_consultant(case_doc.consultant_id, case_doc.company)
        if (
            commission_type == consultant.get("commission_type")
            and commission_value == flt(consultant.get("commission_value"))
        ):
            override_required = False
    except Exception:
        override_required = True

    payload = {"consultant_id": case_doc.consultant_id}
    if override_required:
        payload.update(
            {
                "override": True,
                "commission_type": commission_type,
                "commission_value": commission_value,
            }
        )
    return payload


def _build_invoice_item(case_doc, payment_amount, visit_notes, commission_snapshot):
    item = {
        "item_name": case_doc.case_type or "Orthodontic Payment",
        "description": visit_notes
        or _("Orthodontic installment for case {0}").format(case_doc.name),
        "qty": 1,
        "rate": payment_amount,
    }
    consultant_payload = _build_invoice_consultant_payload(case_doc, commission_snapshot)
    if consultant_payload:
        item["consultant"] = consultant_payload
    return item


def _create_linked_receipt(case_doc, visit_date, payment_amount, payment_mode, visit_notes, commission_snapshot):
    if payment_amount <= 0:
        return {}

    if not payment_mode:
        frappe.throw(_("Payment mode is required when receipt creation is enabled"))

    invoice_result = create_invoice(
        patient_id=case_doc.patient,
        practitioner_id=case_doc.practitioner,
        items=[_build_invoice_item(case_doc, payment_amount, visit_notes, commission_snapshot)],
        posting_date=visit_date,
        due_date=visit_date,
        remarks=visit_notes or _("Orthodontic case payment"),
        clinic=case_doc.company,
    )

    payment_result = update_payment(
        invoice_id=invoice_result["invoice_id"],
        paid_amount=payment_amount,
        mode_of_payment=payment_mode,
        payment_date=visit_date,
        reference_no=case_doc.name,
    )

    receipt_data = {
        "sales_invoice": invoice_result["invoice_id"],
        "payment_entry": payment_result["payment_id"],
        "receipt_number": payment_result["payment_id"],
    }
    receipt_data.update(_get_latest_invoice_snapshot(invoice_result["invoice_id"]))
    return receipt_data


def _insert_ledger_entry(
    case_doc,
    practitioner,
    visit_date,
    visit_notes,
    payment_amount,
    payment_mode,
    next_appointment_date,
    is_adjustment=False,
    adjustment_reason=None,
    commission_snapshot=None,
    commission_note=None,
    receipt_data=None,
):
    commission_snapshot = commission_snapshot or {}
    receipt_data = receipt_data or {}
    ledger = frappe.get_doc(
        {
            "doctype": "Orthodontic Ledger Entry",
            "orthodontic_case": case_doc.name,
            "visit_date": getdate(visit_date) if visit_date else getdate(today()),
            "visit_notes": visit_notes,
            "payment_amount": flt(payment_amount),
            "payment_mode": payment_mode,
            "next_appointment_date": getdate(next_appointment_date)
            if next_appointment_date
            else None,
            "sales_invoice": receipt_data.get("sales_invoice"),
            "payment_entry": receipt_data.get("payment_entry"),
            "receipt_number": receipt_data.get("receipt_number"),
            "created_by": practitioner.user_id if getattr(practitioner, "user_id", None) else frappe.session.user,
            "is_adjustment": 1 if _parse_bool(is_adjustment) else 0,
            "adjustment_reason": adjustment_reason,
            "consultant_id": receipt_data.get("consultant_id")
            or commission_snapshot.get("consultant_id"),
            "consultant_name": receipt_data.get("consultant_name")
            or commission_snapshot.get("consultant_name"),
            "consultant_type": receipt_data.get("consultant_type")
            or commission_snapshot.get("consultant_type"),
            "consultant_practitioner": receipt_data.get("consultant_practitioner")
            or commission_snapshot.get("consultant_practitioner"),
            "consultant_commission_type": receipt_data.get("consultant_commission_type")
            or commission_snapshot.get("consultant_commission_type"),
            "consultant_commission_value": receipt_data.get("consultant_commission_value")
            or commission_snapshot.get("consultant_commission_value"),
            "consultant_commission_amount": receipt_data.get("consultant_commission_amount")
            or commission_snapshot.get("consultant_commission_amount"),
            "consultant_commission_source": receipt_data.get("consultant_commission_source")
            or commission_snapshot.get("consultant_commission_source"),
            "commission_basis": commission_snapshot.get("commission_basis"),
            "commission_status": _commission_status(
                commission_snapshot.get("consultant_commission_amount"), 0
            ),
            "commission_paid_amount": 0,
            "commission_note": commission_note,
        }
    )
    ledger.insert(ignore_permissions=True)
    case_doc = recalculate_orthodontic_case(case_doc.name)
    ledger.reload()
    return ledger, case_doc


def _allocate_pending_amount(case_doc, paid_amount, ledger_entries=None):
    ledger_entries = _parse_json(ledger_entries, default=None)
    pending_rows = frappe.get_all(
        "Orthodontic Ledger Entry",
        filters={"orthodontic_case": case_doc.name},
        fields=[
            "name",
            "consultant_commission_amount",
            "commission_paid_amount",
            "visit_date",
        ],
        order_by=_ledger_order_by(),
    )

    if ledger_entries:
        requested = {}
        for row in ledger_entries:
            ledger_key = row["ledger_entry_id"] if "ledger_entry_id" in row else row["ledger_entry"]
            requested[ledger_key] = row.get("commission_paid_amount")
        selected_names = set(requested)
        pending_rows = [row for row in pending_rows if row.name in selected_names]
    else:
        requested = None

    allocations = []
    remaining = round(flt(paid_amount), 2)

    for row in pending_rows:
        accrued = flt(row.consultant_commission_amount)
        already_paid = flt(row.commission_paid_amount)
        pending = round(max(accrued - already_paid, 0), 2)
        if pending <= 0:
            continue

        if requested is not None:
            requested_amount = requested.get(row.name)
            allocate = pending if requested_amount in (None, "", 0, 0.0) else round(
                flt(requested_amount), 2
            )
            if allocate > pending:
                frappe.throw(
                    _("Paid commission cannot exceed the pending commission for ledger entry {0}").format(
                        row.name
                    )
                )
        else:
            allocate = min(pending, remaining)

        allocations.append(
            {
                "ledger_entry": row.name,
                "commission_accrued_amount": accrued,
                "commission_paid_amount": allocate,
            }
        )
        remaining = round(remaining - allocate, 2)

        if requested is None and remaining <= 0:
            break

    if requested is None and remaining > 0:
        frappe.throw(_("Paid amount exceeds pending commission"))

    allocated_total = round(
        sum(flt(row["commission_paid_amount"]) for row in allocations), 2
    )
    if allocated_total != round(flt(paid_amount), 2):
        frappe.throw(_("Allocated amount must match paid amount"))

    return allocations


@frappe.whitelist(methods=["POST"])
def create_orthodontic_case(
    patient_id,
    practitioner_id=None,
    consultant_id=None,
    case_type=None,
    start_date=None,
    estimated_duration_months=None,
    package_fee=0,
    discount_amount=0,
    discount_percentage=0,
    advance_paid=0,
    advance_payment_mode=None,
    default_followup_days=30,
    status="Active",
    notes=None,
    commission_model="None",
    commission_type=None,
    commission_value=0,
    commission_basis="On collected amount",
    clinic=None,
):
    practitioner, resolved_clinic = _get_context("patients", clinic=clinic)
    patient = _ensure_patient(patient_id)
    associated_practitioner = _ensure_practitioner(
        practitioner_id or practitioner.name, resolved_clinic
    )

    case_doc = frappe.get_doc(
        {
            "doctype": "Orthodontic Case",
            "company": resolved_clinic,
            "patient": patient.name,
            "practitioner": associated_practitioner.name,
            "consultant_id": consultant_id,
            "case_type": case_type,
            "start_date": getdate(start_date) if start_date else getdate(today()),
            "estimated_duration_months": estimated_duration_months,
            "package_fee": flt(package_fee),
            "discount_amount": flt(discount_amount),
            "discount_percentage": flt(discount_percentage),
            "advance_paid": flt(advance_paid),
            "default_followup_days": default_followup_days,
            "status": status or "Active",
            "notes": notes,
            "commission_model": commission_model or "None",
            "commission_type": commission_type,
            "commission_value": flt(commission_value),
            "commission_basis": commission_basis,
        }
    )
    case_doc.insert(ignore_permissions=True)

    if flt(advance_paid) > 0:
        _assert_invoice_access(
            practitioner,
            _("Invoice access is required to record the opening advance"),
        )
        if not advance_payment_mode:
            frappe.throw(_("Payment mode is required when opening advance is collected"))

        commission_snapshot = _build_case_commission_snapshot(case_doc, advance_paid)
        receipt_data = _create_linked_receipt(
            case_doc,
            case_doc.start_date,
            flt(advance_paid),
            advance_payment_mode,
            _("Opening advance"),
            commission_snapshot,
        )
        _insert_ledger_entry(
            case_doc=case_doc,
            practitioner=practitioner,
            visit_date=case_doc.start_date,
            visit_notes=_("Opening advance"),
            payment_amount=advance_paid,
            payment_mode=advance_payment_mode,
            next_appointment_date=None,
            is_adjustment=True,
            adjustment_reason=_("Opening advance"),
            commission_snapshot=commission_snapshot,
            commission_note=_("Accrued from opening advance"),
            receipt_data=receipt_data,
        )

    case_doc = recalculate_orthodontic_case(case_doc.name)
    return {
        "message": "Orthodontic case created successfully",
        "case": _serialize_case(case_doc),
    }


@frappe.whitelist(methods=["GET"])
def get_orthodontic_case(case_id):
    practitioner, _resolved_clinic = _get_context("patients")
    case_doc = _get_case_doc(case_id)
    _assert_case_access(case_doc, practitioner)
    return {
        "message": "Success",
        "case": _serialize_case(case_doc),
        "permissions": _build_client_permissions(practitioner),
    }


@frappe.whitelist(methods=["POST"])
def update_orthodontic_case(case_id, **kwargs):
    practitioner, _resolved_clinic = _get_context("patients", clinic=kwargs.get("clinic"))
    case_doc = _get_case_doc(case_id)
    _assert_case_access(case_doc, practitioner)

    mutable_fields = {
        "practitioner": "practitioner_id",
        "consultant_id": "consultant_id",
        "case_type": "case_type",
        "start_date": "start_date",
        "estimated_duration_months": "estimated_duration_months",
        "package_fee": "package_fee",
        "discount_amount": "discount_amount",
        "discount_percentage": "discount_percentage",
        "default_followup_days": "default_followup_days",
        "status": "status",
        "notes": "notes",
        "commission_model": "commission_model",
        "commission_type": "commission_type",
        "commission_value": "commission_value",
        "commission_basis": "commission_basis",
    }

    for fieldname, argname in mutable_fields.items():
        if argname not in kwargs or kwargs.get(argname) is None:
            continue
        value = kwargs.get(argname)
        if fieldname == "practitioner":
            _ensure_practitioner(value, case_doc.company)
        if fieldname in {"start_date"} and value:
            value = getdate(value)
        if fieldname in {
            "package_fee",
            "discount_amount",
            "discount_percentage",
            "commission_value",
        }:
            value = flt(value)
        case_doc.set(fieldname, value)

    case_doc.save(ignore_permissions=True)
    case_doc = recalculate_orthodontic_case(case_doc.name)
    return {
        "message": "Orthodontic case updated successfully",
        "case": _serialize_case(case_doc),
    }


@frappe.whitelist(methods=["GET"])
def list_orthodontic_cases(
    patient_id=None,
    status=None,
    practitioner_id=None,
    consultant_id=None,
    clinic=None,
    limit_page_length=20,
    limit_start=0,
):
    practitioner, resolved_clinic = _get_context("patients", clinic=clinic)
    filters = {}
    if resolved_clinic:
        filters["company"] = resolved_clinic
    if patient_id:
        filters["patient"] = patient_id
    if status:
        filters["status"] = status
    if practitioner_id:
        filters["practitioner"] = practitioner_id
    if consultant_id:
        filters["consultant_id"] = consultant_id

    rows = frappe.get_all(
        "Orthodontic Case",
        filters=filters,
        fields=["name"],
        order_by="modified desc",
        limit_start=int(limit_start or 0),
        limit_page_length=int(limit_page_length or 20),
    )

    cases = []
    for row in rows:
        case_doc = frappe.get_doc("Orthodontic Case", row.name)
        _assert_case_access(case_doc, practitioner)
        cases.append(_serialize_case(case_doc))

    return {"message": "Success", "cases": cases}


@frappe.whitelist(methods=["POST"])
def close_orthodontic_case(case_id, status="Completed", force=0, notes=None):
    practitioner, _resolved_clinic = _get_context("patients")
    case_doc = _get_case_doc(case_id)
    _assert_case_access(case_doc, practitioner)

    force = _parse_bool(force)
    if status not in COMPLETED_CASE_STATUSES:
        frappe.throw(_("Invalid closing status"))

    if flt(case_doc.balance_amount) > 0 and not force:
        frappe.throw(_("Case cannot be closed while balance remains unpaid"))

    case_doc.status = status
    case_doc.is_active = 0
    if notes:
        case_doc.notes = "\n".join(
            part for part in [case_doc.notes, str(notes).strip()] if part
        )
    case_doc.save(ignore_permissions=True)
    case_doc = recalculate_orthodontic_case(case_doc.name)

    return {"message": "Orthodontic case closed successfully", "case": _serialize_case(case_doc)}


@frappe.whitelist(methods=["GET"])
def get_orthodontic_case_commission_summary(case_id):
    practitioner, _resolved_clinic = _get_context("patients")
    case_doc = _get_case_doc(case_id)
    _assert_case_access(case_doc, practitioner)

    return {
        "message": "Success",
        "summary": {
            "case_id": case_doc.name,
            "consultant_id": case_doc.consultant_id,
            "consultant_name": case_doc.consultant_name,
            "commission_model": case_doc.commission_model,
            "commission_type": case_doc.commission_type,
            "commission_value": flt(case_doc.commission_value),
            "commission_basis": case_doc.commission_basis,
            "total_commission_accrued": flt(case_doc.total_commission_accrued),
            "total_commission_paid": flt(case_doc.total_commission_paid),
            "pending_commission_amount": flt(case_doc.pending_commission_amount),
        },
    }


@frappe.whitelist(methods=["POST"])
def add_orthodontic_ledger_entry(
    case_id,
    visit_date=None,
    visit_notes=None,
    payment_amount=0,
    payment_mode=None,
    next_appointment_date=None,
    create_receipt=0,
    commission_override=0,
    commission_type=None,
    commission_value=0,
    commission_basis=None,
    commission_note=None,
    is_adjustment=0,
    adjustment_reason=None,
):
    practitioner, _resolved_clinic = _get_context("patients")
    case_doc = _get_case_doc(case_id)
    _assert_case_access(case_doc, practitioner)

    payment_amount = flt(payment_amount)
    if payment_amount < 0:
        frappe.throw(_("Payment amount cannot be negative"))

    if payment_amount > flt(case_doc.balance_amount):
        frappe.throw(_("Payment amount cannot exceed the current balance"))

    if case_doc.status in COMPLETED_CASE_STATUSES:
        frappe.throw(_("Cannot add visits to a closed orthodontic case"))

    override = None
    if _parse_bool(commission_override):
        override = {
            "commission_type": commission_type,
            "commission_value": commission_value,
            "commission_basis": commission_basis,
        }

    commission_snapshot = _build_case_commission_snapshot(case_doc, payment_amount, override=override)
    receipt_data = {}
    if payment_amount > 0:
        _assert_invoice_access(practitioner)
        receipt_data = _create_linked_receipt(
            case_doc,
            getdate(visit_date) if visit_date else getdate(today()),
            payment_amount,
            payment_mode,
            visit_notes,
            commission_snapshot,
        )

    ledger, case_doc = _insert_ledger_entry(
        case_doc=case_doc,
        practitioner=practitioner,
        visit_date=visit_date,
        visit_notes=visit_notes,
        payment_amount=payment_amount,
        payment_mode=payment_mode,
        next_appointment_date=next_appointment_date,
        is_adjustment=is_adjustment,
        adjustment_reason=adjustment_reason,
        commission_snapshot=commission_snapshot,
        commission_note=commission_note,
        receipt_data=receipt_data,
    )

    return {
        "message": "Orthodontic ledger entry created successfully",
        "case": _serialize_case(case_doc),
        "ledger_entry": _serialize_ledger(ledger),
    }


@frappe.whitelist(methods=["POST"])
def update_orthodontic_ledger_entry(
    ledger_entry_id,
    visit_date=None,
    visit_notes=None,
    payment_mode=None,
    next_appointment_date=None,
    commission_note=None,
):
    practitioner, _resolved_clinic = _get_context("patients")
    if not frappe.db.exists("Orthodontic Ledger Entry", ledger_entry_id):
        frappe.throw(_("Orthodontic ledger entry not found"))

    ledger = frappe.get_doc("Orthodontic Ledger Entry", ledger_entry_id)
    case_doc = _get_case_doc(ledger.orthodontic_case)
    _assert_case_access(case_doc, practitioner)

    has_accounting_link = bool(ledger.payment_entry or ledger.sales_invoice)
    if has_accounting_link:
        if visit_date and getdate(visit_date) != ledger.visit_date:
            frappe.throw(
                _("Cannot change the visit date for a payment linked to accounting records")
            )
        if payment_mode is not None and payment_mode != (ledger.payment_mode or ""):
            frappe.throw(
                _("Cannot change the payment mode for a payment linked to accounting records")
            )

    if visit_date:
        ledger.visit_date = getdate(visit_date)
    if visit_notes is not None:
        ledger.visit_notes = visit_notes
    if payment_mode is not None:
        ledger.payment_mode = payment_mode
    if next_appointment_date is not None:
        ledger.next_appointment_date = (
            getdate(next_appointment_date) if next_appointment_date else None
        )
    if commission_note is not None:
        ledger.commission_note = commission_note

    ledger.save(ignore_permissions=True)
    case_doc = recalculate_orthodontic_case(case_doc.name)
    ledger.reload()

    return {
        "message": "Orthodontic ledger entry updated successfully",
        "case": _serialize_case(case_doc),
        "ledger_entry": _serialize_ledger(ledger),
    }


@frappe.whitelist(methods=["POST"])
def delete_orthodontic_ledger_entry(ledger_entry_id):
    practitioner, _resolved_clinic = _get_context("financial_dashboard", require_admin=True)
    if not frappe.db.exists("Orthodontic Ledger Entry", ledger_entry_id):
        frappe.throw(_("Orthodontic ledger entry not found"))

    ledger = frappe.get_doc("Orthodontic Ledger Entry", ledger_entry_id)
    case_doc = _get_case_doc(ledger.orthodontic_case)
    _assert_case_access(case_doc, practitioner)

    if ledger.payment_entry or ledger.sales_invoice:
        frappe.throw(_("Cannot delete a ledger entry linked to accounting records"))

    if flt(ledger.commission_paid_amount) > 0:
        frappe.throw(_("Cannot delete a ledger entry with paid commission history"))

    frappe.delete_doc("Orthodontic Ledger Entry", ledger.name, force=True, ignore_permissions=True)
    case_doc = recalculate_orthodontic_case(case_doc.name)
    return {
        "message": "Orthodontic ledger entry deleted successfully",
        "case": _serialize_case(case_doc),
    }


@frappe.whitelist(methods=["GET"])
def get_orthodontic_ledger(case_id, start_date=None, end_date=None, commission_status=None):
    practitioner, _resolved_clinic = _get_context("patients")
    case_doc = _get_case_doc(case_id)
    _assert_case_access(case_doc, practitioner)

    filters = {"orthodontic_case": case_id}
    if start_date:
        filters["visit_date"] = [">=", getdate(start_date)]
    if end_date:
        if "visit_date" in filters and isinstance(filters["visit_date"], list):
            filters["visit_date"] = ["between", [getdate(start_date), getdate(end_date)]]
        else:
            filters["visit_date"] = ["<=", getdate(end_date)]
    if commission_status:
        filters["commission_status"] = commission_status

    ledger_rows = frappe.get_all(
        "Orthodontic Ledger Entry",
        filters=filters,
        order_by="visit_date desc, creation desc",
        pluck="name",
    )

    return {
        "message": "Success",
        "case": _serialize_case(case_doc),
        "ledger": [
            _serialize_ledger(frappe.get_doc("Orthodontic Ledger Entry", name))
            for name in ledger_rows
        ],
    }


def _create_payout(
    case_doc,
    paid_amount,
    posting_date=None,
    payment_mode=None,
    reference_no=None,
    notes=None,
    allocations=None,
):
    payout = frappe.get_doc(
        {
            "doctype": "Orthodontic Commission Payout",
            "orthodontic_case": case_doc.name,
            "company": case_doc.company,
            "consultant_id": case_doc.consultant_id,
            "consultant_name": case_doc.consultant_name,
            "consultant_practitioner": case_doc.consultant_practitioner,
            "posting_date": getdate(posting_date) if posting_date else getdate(today()),
            "paid_amount": flt(paid_amount),
            "payment_mode": payment_mode,
            "reference_no": reference_no,
            "notes": notes,
            "status": "Submitted",
            "allocations": allocations,
        }
    )
    payout.insert(ignore_permissions=True)

    for row in allocations:
        ledger = frappe.get_doc("Orthodontic Ledger Entry", row["ledger_entry"])
        ledger.commission_paid_amount = round(
            flt(ledger.commission_paid_amount) + flt(row["commission_paid_amount"]), 2
        )
        ledger.commission_paid_date = payout.posting_date
        ledger.commission_payout_reference = payout.name
        ledger.commission_status = _commission_status(
            ledger.consultant_commission_amount, ledger.commission_paid_amount
        )
        ledger.save(ignore_permissions=True)

    case_doc = recalculate_orthodontic_case(case_doc.name)
    payout.reload()
    return payout, case_doc


@frappe.whitelist(methods=["POST"])
def create_orthodontic_commission_payout(
    case_id,
    paid_amount,
    posting_date=None,
    payment_mode=None,
    reference_no=None,
    notes=None,
    ledger_entries=None,
):
    practitioner, _resolved_clinic = _get_context("financial_dashboard", require_admin=True)
    case_doc = _get_case_doc(case_id)
    _assert_case_access(case_doc, practitioner)
    case_doc = recalculate_orthodontic_case(case_doc.name)

    allocations = _allocate_pending_amount(case_doc, paid_amount, ledger_entries=ledger_entries)
    payout, case_doc = _create_payout(
        case_doc=case_doc,
        paid_amount=paid_amount,
        posting_date=posting_date,
        payment_mode=payment_mode,
        reference_no=reference_no,
        notes=notes,
        allocations=allocations,
    )

    return {
        "message": "Orthodontic commission payout recorded successfully",
        "case": _serialize_case(case_doc),
        "payout": _serialize_payout(payout),
    }


@frappe.whitelist(methods=["POST"])
def mark_orthodontic_commission_paid(
    case_id,
    paid_amount,
    posting_date=None,
    payment_mode=None,
    reference_no=None,
    notes=None,
    ledger_entry_ids=None,
):
    ledger_entries = None
    parsed_ids = _parse_json(ledger_entry_ids, default=None)
    if parsed_ids:
        ledger_entries = [
            {"ledger_entry": ledger_id, "commission_paid_amount": 0}
            for ledger_id in parsed_ids
        ]

    if ledger_entries:
        practitioner, _resolved_clinic = _get_context("financial_dashboard", require_admin=True)
        case_doc = _get_case_doc(case_id)
        _assert_case_access(case_doc, practitioner)
        case_doc = recalculate_orthodontic_case(case_doc.name)
        allocations = _allocate_pending_amount(case_doc, paid_amount, ledger_entries=ledger_entries)
        payout, case_doc = _create_payout(
            case_doc=case_doc,
            paid_amount=paid_amount,
            posting_date=posting_date,
            payment_mode=payment_mode,
            reference_no=reference_no,
            notes=notes,
            allocations=allocations,
        )
        return {
            "message": "Orthodontic commission payout recorded successfully",
            "case": _serialize_case(case_doc),
            "payout": _serialize_payout(payout),
        }

    return create_orthodontic_commission_payout(
        case_id=case_id,
        paid_amount=paid_amount,
        posting_date=posting_date,
        payment_mode=payment_mode,
        reference_no=reference_no,
        notes=notes,
    )


@frappe.whitelist(methods=["GET"])
def get_orthodontic_commission_payout(case_id=None, payout_id=None):
    practitioner, _resolved_clinic = _get_context("financial_dashboard", require_admin=True)
    if payout_id:
        if not frappe.db.exists("Orthodontic Commission Payout", payout_id):
            frappe.throw(_("Orthodontic commission payout not found"))
        payout = frappe.get_doc("Orthodontic Commission Payout", payout_id)
    elif case_id:
        payout_name = frappe.db.get_value(
            "Orthodontic Commission Payout",
            {"orthodontic_case": case_id},
            "name",
            order_by="posting_date desc, creation desc",
        )
        if not payout_name:
            frappe.throw(_("Orthodontic commission payout not found"))
        payout = frappe.get_doc("Orthodontic Commission Payout", payout_name)
    else:
        frappe.throw(_("case_id or payout_id is required"))

    case_doc = _get_case_doc(payout.orthodontic_case)
    _assert_case_access(case_doc, practitioner)
    return {"message": "Success", "payout": _serialize_payout(payout)}


@frappe.whitelist(methods=["GET"])
def list_orthodontic_commission_payouts(case_id=None, consultant_id=None, clinic=None):
    practitioner, resolved_clinic = _get_context(
        "financial_dashboard", clinic=clinic, require_admin=True
    )
    filters = {}
    if resolved_clinic:
        filters["company"] = resolved_clinic
    if case_id:
        filters["orthodontic_case"] = case_id
    if consultant_id:
        filters["consultant_id"] = consultant_id

    payout_names = frappe.get_all(
        "Orthodontic Commission Payout",
        filters=filters,
        order_by="posting_date desc, creation desc",
        pluck="name",
    )

    payouts = []
    for payout_name in payout_names:
        payout = frappe.get_doc("Orthodontic Commission Payout", payout_name)
        case_doc = _get_case_doc(payout.orthodontic_case)
        _assert_case_access(case_doc, practitioner)
        payouts.append(_serialize_payout(payout))

    return {"message": "Success", "payouts": payouts}


@frappe.whitelist(methods=["POST"])
def reverse_orthodontic_commission_payout(payout_id, notes=None):
    practitioner, _resolved_clinic = _get_context("financial_dashboard", require_admin=True)
    if not frappe.db.exists("Orthodontic Commission Payout", payout_id):
        frappe.throw(_("Orthodontic commission payout not found"))

    payout = frappe.get_doc("Orthodontic Commission Payout", payout_id)
    case_doc = _get_case_doc(payout.orthodontic_case)
    _assert_case_access(case_doc, practitioner)

    if payout.status == "Reversed":
        frappe.throw(_("This payout has already been reversed"))

    for row in payout.get("allocations") or []:
        ledger = frappe.get_doc("Orthodontic Ledger Entry", row.ledger_entry)
        ledger.commission_paid_amount = round(
            max(
                flt(ledger.commission_paid_amount) - flt(row.commission_paid_amount),
                0,
            ),
            2,
        )
        ledger.commission_status = _commission_status(
            ledger.consultant_commission_amount, ledger.commission_paid_amount
        )
        if flt(ledger.commission_paid_amount) <= 0:
            ledger.commission_paid_date = None
            ledger.commission_payout_reference = None
        ledger.save(ignore_permissions=True)

    payout.status = "Reversed"
    payout.reversal_notes = notes
    payout.save(ignore_permissions=True)
    case_doc = recalculate_orthodontic_case(case_doc.name)
    payout.reload()

    return {
        "message": "Orthodontic commission payout reversed successfully",
        "case": _serialize_case(case_doc),
        "payout": _serialize_payout(payout),
    }


def _get_patient_active_case(patient_id, clinic=None):
    filters = {
        "patient": patient_id,
        "status": ["in", list(ACTIVE_CASE_STATUSES)],
        "is_active": 1,
    }
    if clinic:
        filters["company"] = clinic

    case_name = frappe.db.get_value("Orthodontic Case", filters, "name", order_by="modified desc")
    if case_name:
        return frappe.get_doc("Orthodontic Case", case_name)

    latest_case = frappe.db.get_value(
        "Orthodontic Case",
        {"patient": patient_id, **({"company": clinic} if clinic else {})},
        "name",
        order_by="modified desc",
    )
    return frappe.get_doc("Orthodontic Case", latest_case) if latest_case else None


@frappe.whitelist(methods=["GET"])
def get_patient_orthodontic_summary(patient_id, clinic=None):
    practitioner, resolved_clinic = _get_context("patients", clinic=clinic)
    if resolved_clinic and not clinic_helper.validate_practitioner_access(
        practitioner.name, resolved_clinic
    ):
        frappe.throw(_("Clinic access denied"), frappe.PermissionError)

    case_doc = _get_patient_active_case(patient_id, clinic=resolved_clinic)
    if not case_doc:
        return {"message": "Success", "summary": None}

    recent_ledger = frappe.get_all(
        "Orthodontic Ledger Entry",
        filters={"orthodontic_case": case_doc.name},
        order_by="visit_date desc, creation desc",
        limit_page_length=5,
        pluck="name",
    )

    return {
        "message": "Success",
        "summary": {
            **_serialize_case(case_doc),
            "recent_ledger": [
                _serialize_ledger(frappe.get_doc("Orthodontic Ledger Entry", name))
                for name in recent_ledger
            ],
        },
        "permissions": _build_client_permissions(practitioner),
    }


@frappe.whitelist(methods=["GET"])
def get_orthodontic_dashboard(clinic=None, from_date=None, to_date=None):
    practitioner, resolved_clinic = _get_context(
        "financial_dashboard", clinic=clinic, require_admin=True
    )
    from_date = getdate(from_date) if from_date else get_first_day(getdate(nowdate()))
    to_date = getdate(to_date) if to_date else get_last_day(getdate(nowdate()))

    case_filters = {"company": resolved_clinic} if resolved_clinic else {}
    active_filters = dict(case_filters)
    active_filters.update({"status": ["in", list(ACTIVE_CASE_STATUSES)], "is_active": 1})

    active_cases = frappe.get_all(
        "Orthodontic Case",
        filters=active_filters,
        fields=[
            "name",
            "patient",
            "patient_name",
            "practitioner",
            "practitioner_name",
            "balance_amount",
            "next_appointment_date",
            "last_visit_date",
            "pending_commission_amount",
        ],
        order_by="balance_amount desc, modified desc",
    )

    ledger_filters = {"visit_date": ["between", [from_date, to_date]]}
    if resolved_clinic:
        ledger_filters["company"] = resolved_clinic

    collection_rows = frappe.get_all(
        "Orthodontic Ledger Entry",
        filters=ledger_filters,
        fields=["payment_amount", "consultant_commission_amount"],
    )
    payout_filters = {"posting_date": ["between", [from_date, to_date]], "status": "Submitted"}
    if resolved_clinic:
        payout_filters["company"] = resolved_clinic
    payout_rows = frappe.get_all(
        "Orthodontic Commission Payout",
        filters=payout_filters,
        fields=["paid_amount"],
    )

    overdue_cases = []
    due_this_week = []
    for row in active_cases:
        if row.next_appointment_date and getdate(row.next_appointment_date) <= add_days(getdate(nowdate()), 7):
            due_this_week.append(row)
        if row.next_appointment_date and getdate(row.next_appointment_date) < getdate(nowdate()):
            overdue_cases.append(row)

    return {
        "message": "Success",
        "data": {
            "filters": {
                "clinic": resolved_clinic,
                "from_date": str(from_date),
                "to_date": str(to_date),
            },
            "summary": {
                "active_cases": len(active_cases),
                "total_outstanding": round(
                    sum(flt(row.balance_amount) for row in active_cases), 2
                ),
                "collected_in_period": round(
                    sum(flt(row.payment_amount) for row in collection_rows), 2
                ),
                "new_cases_in_period": frappe.db.count(
                    "Orthodontic Case",
                    {**case_filters, "start_date": ["between", [from_date, to_date]]},
                ),
                "patients_due_this_week": len(due_this_week),
                "overdue_cases": len(overdue_cases),
                "commission_accrued_in_period": round(
                    sum(flt(row.consultant_commission_amount) for row in collection_rows),
                    2,
                ),
                "commission_unpaid": round(
                    sum(flt(row.pending_commission_amount) for row in active_cases), 2
                ),
                "commission_paid_in_period": round(
                    sum(flt(row.paid_amount) for row in payout_rows), 2
                ),
            },
            "active_cases": active_cases[:20],
            "due_this_week": due_this_week[:20],
            "overdue_cases": overdue_cases[:20],
        },
    }


@frappe.whitelist(methods=["GET"])
def get_orthodontic_overdue_cases(clinic=None):
    dashboard = get_orthodontic_dashboard(clinic=clinic)
    return {
        "message": dashboard["message"],
        "data": dashboard["data"]["overdue_cases"],
    }


@frappe.whitelist(methods=["GET"])
def get_orthodontic_commission_dashboard(clinic=None, from_date=None, to_date=None):
    dashboard = get_orthodontic_dashboard(clinic=clinic, from_date=from_date, to_date=to_date)
    return {
        "message": dashboard["message"],
        "data": {
            "filters": dashboard["data"]["filters"],
            "summary": {
                key: dashboard["data"]["summary"][key]
                for key in [
                    "commission_accrued_in_period",
                    "commission_unpaid",
                    "commission_paid_in_period",
                ]
            },
        },
    }


@frappe.whitelist(methods=["GET"])
def get_orthodontic_consultant_payout_report(clinic=None, consultant_id=None):
    practitioner, resolved_clinic = _get_context(
        "financial_dashboard", clinic=clinic, require_admin=True
    )
    ledger_filters = {}
    if resolved_clinic:
        ledger_filters["company"] = resolved_clinic
    if consultant_id:
        ledger_filters["consultant_id"] = consultant_id

    ledger_rows = frappe.get_all(
        "Orthodontic Ledger Entry",
        filters=ledger_filters,
        fields=[
            "name",
            "orthodontic_case",
            "visit_date",
            "consultant_id",
            "consultant_name",
            "consultant_practitioner",
            "consultant_commission_amount",
            "commission_paid_amount",
            "commission_status",
            "payment_amount",
        ],
        order_by="visit_date desc, creation desc",
    )

    consultant_map = defaultdict(
        lambda: {
            "consultant_id": None,
            "consultant_name": None,
            "consultant_practitioner": None,
            "case_count": set(),
            "ledger_count": 0,
            "total_collected": 0.0,
            "total_commission_accrued": 0.0,
            "total_commission_paid": 0.0,
            "pending_commission": 0.0,
        }
    )

    detail_rows = []
    for row in ledger_rows:
        key = row.consultant_id or "unassigned"
        summary = consultant_map[key]
        summary["consultant_id"] = row.consultant_id
        summary["consultant_name"] = row.consultant_name or "Unassigned"
        summary["consultant_practitioner"] = row.consultant_practitioner
        summary["case_count"].add(row.orthodontic_case)
        summary["ledger_count"] += 1
        summary["total_collected"] += flt(row.payment_amount)
        summary["total_commission_accrued"] += flt(row.consultant_commission_amount)
        summary["total_commission_paid"] += flt(row.commission_paid_amount)
        summary["pending_commission"] += max(
            flt(row.consultant_commission_amount) - flt(row.commission_paid_amount), 0
        )
        detail_rows.append(
            {
                "ledger_entry_id": row.name,
                "case_id": row.orthodontic_case,
                "visit_date": str(row.visit_date) if row.visit_date else None,
                "consultant_id": row.consultant_id,
                "consultant_name": row.consultant_name,
                "payment_amount": flt(row.payment_amount),
                "commission_amount": flt(row.consultant_commission_amount),
                "commission_paid_amount": flt(row.commission_paid_amount),
                "commission_status": row.commission_status,
            }
        )

    consultants = []
    for summary in consultant_map.values():
        summary["case_count"] = len(summary["case_count"])
        for key in [
            "total_collected",
            "total_commission_accrued",
            "total_commission_paid",
            "pending_commission",
        ]:
            summary[key] = round(summary[key], 2)
        consultants.append(summary)

    return {
        "message": "Success",
        "data": {
            "filters": {"clinic": resolved_clinic, "consultant_id": consultant_id},
            "summary": {
                "consultant_count": len(consultants),
                "ledger_count": len(detail_rows),
                "total_commission_accrued": round(
                    sum(row["commission_amount"] for row in detail_rows), 2
                ),
                "total_commission_paid": round(
                    sum(row["commission_paid_amount"] for row in detail_rows), 2
                ),
                "total_pending_commission": round(
                    sum(
                        max(
                            row["commission_amount"] - row["commission_paid_amount"],
                            0,
                        )
                        for row in detail_rows
                    ),
                    2,
                ),
            },
            "consultants": consultants,
            "rows": detail_rows,
        },
    }


@frappe.whitelist(methods=["GET"])
def get_orthodontic_print_data(case_id):
    practitioner, _resolved_clinic = _get_context("patients")
    case_doc = _get_case_doc(case_id)
    _assert_case_access(case_doc, practitioner)
    ledger_rows = frappe.get_all(
        "Orthodontic Ledger Entry",
        filters={"orthodontic_case": case_id},
        order_by=_ledger_order_by(),
        pluck="name",
    )
    patient = frappe.get_doc("Patient", case_doc.patient)
    return {
        "message": "Success",
        "data": {
            "case": _serialize_case(case_doc),
            "patient": {
                "patient_id": patient.name,
                "patient_name": patient.patient_name,
                "sex": patient.sex,
                "dob": str(patient.dob) if patient.dob else None,
                "mobile": patient.mobile,
            },
            "ledger": [
                _serialize_ledger(frappe.get_doc("Orthodontic Ledger Entry", name))
                for name in ledger_rows
            ],
        },
    }


@frappe.whitelist(methods=["POST"])
def share_orthodontic_receipt(case_id=None, ledger_entry_id=None):
    practitioner, _resolved_clinic = _get_context("patients")
    if ledger_entry_id:
        if not frappe.db.exists("Orthodontic Ledger Entry", ledger_entry_id):
            frappe.throw(_("Orthodontic ledger entry not found"))
        ledger = frappe.get_doc("Orthodontic Ledger Entry", ledger_entry_id)
        case_doc = _get_case_doc(ledger.orthodontic_case)
    elif case_id:
        case_doc = _get_case_doc(case_id)
        ledger_name = frappe.db.get_value(
            "Orthodontic Ledger Entry",
            {"orthodontic_case": case_id, "payment_amount": [">", 0]},
            "name",
            order_by="visit_date desc, creation desc",
        )
        if not ledger_name:
            frappe.throw(_("No payment receipt is available for this orthodontic case"))
        ledger = frappe.get_doc("Orthodontic Ledger Entry", ledger_name)
    else:
        frappe.throw(_("case_id or ledger_entry_id is required"))

    _assert_case_access(case_doc, practitioner)
    return {
        "message": "Receipt data prepared successfully",
        "data": {
            "case": _serialize_case(case_doc),
            "ledger_entry": _serialize_ledger(ledger),
            "share_payload": {
                "sales_invoice": ledger.sales_invoice,
                "payment_entry": ledger.payment_entry,
                "receipt_number": ledger.receipt_number,
            },
        },
    }


@frappe.whitelist(methods=["POST"])
def share_orthodontic_card(case_id):
    print_data = get_orthodontic_print_data(case_id)
    return {
        "message": "Orthodontic card data prepared successfully",
        "data": print_data["data"],
    }
