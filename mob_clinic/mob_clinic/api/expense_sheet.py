from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Tuple

import frappe
from erpnext.accounts.utils import get_fiscal_year, get_fiscal_years
from frappe import _
from frappe.utils import add_months, cint, flt, formatdate, get_first_day, get_last_day, getdate, nowdate

from mob_clinic.mob_clinic.api import clinic as clinic_helper
from mob_clinic.mob_clinic.api.role_access import assert_page_access, get_practitioner_permissions


FILTER_MODE_MONTH = "specific_month"
FILTER_MODE_FY = "financial_year"

EXPENSE_CATEGORY_FIXED = "Recurring Fixed"
EXPENSE_CATEGORY_VARIABLE = "Recurring Variable"
EXPENSE_CATEGORY_ONE_TIME = "One-Time"
SYSTEM_CATEGORY = "System Generated"

SYSTEM_VENDOR_PAYMENT = "Vendor Payment"
SYSTEM_PRACTITIONER_SALARY = "Practitioner Salary"

CONSULTANT_TYPE_EXTERNAL = "External"
CONSULTANT_TYPE_INTERNAL = "Internal"


@dataclass
class PeriodContext:
    filter_mode: str
    selected_month: Optional[date]
    month_start: Optional[date]
    month_end: Optional[date]
    fiscal_year_name: str
    fiscal_year_start: date
    fiscal_year_end: date
    fiscal_years: List[Dict[str, Any]]


def _parse_decimal_amount(value: Any, *, required: bool = True) -> Optional[float]:
    if value in (None, ""):
        if required:
            frappe.throw(_("Amount is required"), frappe.ValidationError)
        return None

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        frappe.throw(_("Amount must be numeric"), frappe.ValidationError)

    if decimal_value < 0:
        frappe.throw(_("Amount cannot be negative"), frappe.ValidationError)

    if decimal_value != decimal_value.quantize(Decimal("0.01")):
        frappe.throw(_("Amount can have at most 2 decimal places"), frappe.ValidationError)

    return float(decimal_value)


def _normalize_string(value: Any) -> str:
    return (value or "").strip()


def _month_to_date(month: Any, year: Any) -> date:
    try:
        month_value = int(month)
        year_value = int(year)
    except (TypeError, ValueError):
        frappe.throw(_("Month and year are required"), frappe.ValidationError)

    if month_value < 1 or month_value > 12:
        frappe.throw(_("Month is invalid"), frappe.ValidationError)

    return getdate(f"{year_value:04d}-{month_value:02d}-01")


def _parse_month_input(month_value: Any, field_label: str) -> date:
    value = _normalize_string(month_value)
    if not value:
        frappe.throw(_("{0} is required").format(field_label), frappe.ValidationError)
    try:
        if len(value) == 7:
            parsed = getdate(f"{value}-01")
        else:
            parsed = getdate(value)
    except Exception:
        frappe.throw(_("{0} is invalid").format(field_label), frappe.ValidationError)
    return get_first_day(parsed)


def _previous_month(period_month: date) -> date:
    return get_first_day(add_months(period_month, -1))


def _month_key(period_month: date) -> str:
    return period_month.strftime("%Y-%m")


def _display_month(period_month: date) -> str:
    return formatdate(period_month, "MMMM yyyy")


def _has_month_started(period_month: date) -> bool:
    current_month_start = get_first_day(getdate(nowdate()))
    return get_first_day(period_month) <= current_month_start


def _get_dashboard_context(clinic: Optional[str] = None, require_admin: bool = False) -> Tuple[Any, str]:
    practitioner = frappe.db.get_value(
        "Healthcare Practitioner",
        {"user_id": frappe.session.user},
        ["name", "practitioner_name", "is_clinic_admin", "allowed_pages_json"],
        as_dict=True,
    )
    if not practitioner:
        frappe.local.response["http_status_code"] = 403
        frappe.throw(_("Healthcare Practitioner profile not found"), frappe.PermissionError)

    assert_page_access("financial_dashboard", practitioner_name=practitioner.name)

    resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name, clinic)
    if not resolved_clinic:
        frappe.throw(_("Clinic is required"), frappe.ValidationError)

    if not clinic_helper.validate_practitioner_access(practitioner.name, resolved_clinic):
        frappe.local.response["http_status_code"] = 403
        frappe.throw(_("Clinic access denied"), frappe.PermissionError)

    if require_admin and not get_practitioner_permissions(practitioner).get("is_clinic_admin"):
        frappe.local.response["http_status_code"] = 403
        frappe.throw(_("Clinic admin access required"), frappe.PermissionError)

    return practitioner, resolved_clinic


def _get_accessible_fiscal_years(clinic: str) -> List[Dict[str, Any]]:
    fiscal_years = get_fiscal_years(company=clinic, as_dict=True)
    return [
        {
            "name": row.get("name"),
            "label": row.get("name"),
            "year_start_date": str(row.get("year_start_date")),
            "year_end_date": str(row.get("year_end_date")),
        }
        for row in fiscal_years
    ]


def _get_fiscal_year_for_date(target_date: date, clinic: str) -> Dict[str, Any]:
    row = get_fiscal_year(date=target_date, company=clinic, as_dict=True)
    return {
        "name": row.get("name"),
        "label": row.get("name"),
        "year_start_date": getdate(row.get("year_start_date")),
        "year_end_date": getdate(row.get("year_end_date")),
    }


def _get_fiscal_year_by_name(fiscal_year_name: str, clinic: str) -> Dict[str, Any]:
    row = get_fiscal_year(fiscal_year=fiscal_year_name, company=clinic, as_dict=True)
    return {
        "name": row.get("name"),
        "label": row.get("name"),
        "year_start_date": getdate(row.get("year_start_date")),
        "year_end_date": getdate(row.get("year_end_date")),
    }


def _resolve_period_context(
    clinic: str,
    filter_mode: Optional[str],
    month: Optional[Any],
    year: Optional[Any],
    fiscal_year: Optional[str],
) -> PeriodContext:
    filter_mode = filter_mode or FILTER_MODE_MONTH
    fiscal_years = _get_accessible_fiscal_years(clinic)

    if filter_mode == FILTER_MODE_FY:
        if not fiscal_year:
            fiscal_year = _get_fiscal_year_for_date(getdate(nowdate()), clinic)["name"]
        fiscal_year_doc = _get_fiscal_year_by_name(fiscal_year, clinic)
        return PeriodContext(
            filter_mode=FILTER_MODE_FY,
            selected_month=None,
            month_start=None,
            month_end=None,
            fiscal_year_name=fiscal_year_doc["name"],
            fiscal_year_start=fiscal_year_doc["year_start_date"],
            fiscal_year_end=fiscal_year_doc["year_end_date"],
            fiscal_years=fiscal_years,
        )

    selected_month = _month_to_date(month or getdate(nowdate()).month, year or getdate(nowdate()).year)
    fiscal_year_doc = _get_fiscal_year_for_date(selected_month, clinic)
    return PeriodContext(
        filter_mode=FILTER_MODE_MONTH,
        selected_month=selected_month,
        month_start=get_first_day(selected_month),
        month_end=get_last_day(selected_month),
        fiscal_year_name=fiscal_year_doc["name"],
        fiscal_year_start=fiscal_year_doc["year_start_date"],
        fiscal_year_end=fiscal_year_doc["year_end_date"],
        fiscal_years=fiscal_years,
    )


def _iter_fiscal_year_months(context: PeriodContext) -> List[date]:
    months = []
    current = get_first_day(context.fiscal_year_start)
    end = get_first_day(context.fiscal_year_end)
    while current <= end:
        months.append(current)
        current = get_first_day(add_months(current, 1))
    return months


def _rule_overlaps_period(rule: Dict[str, Any], start_month: date, end_month: date) -> bool:
    rule_start = getdate(rule.get("effective_from_month"))
    rule_end = getdate(rule.get("effective_to_month")) if rule.get("effective_to_month") else None
    if rule_start > end_month:
        return False
    if rule_end and rule_end < start_month:
        return False
    return True


def _build_manual_row_key(rule_id: str, period_token: str) -> str:
    return f"manual:{rule_id}:{period_token}"


def _build_system_row_key(system_key: str, period_token: str) -> str:
    return f"system:{system_key}:{period_token}"


def _serialize_manual_row(
    rule: Dict[str, Any],
    period_token: str,
    amount: Optional[float],
    payment_date: Optional[date],
    *,
    is_editable: bool,
    is_month_view: bool,
) -> Dict[str, Any]:
    can_edit_rule = bool(is_month_view and rule.get("expense_category") == EXPENSE_CATEGORY_FIXED)
    can_edit_amount = bool(is_month_view and is_editable)
    can_delete = bool(is_month_view)
    return {
        "row_key": _build_manual_row_key(rule["name"], period_token),
        "row_type": "manual",
        "expense_rule_id": rule["name"],
        "expense_name": rule["expense_name"],
        "expense_category": rule["expense_category"],
        "is_system_generated": False,
        "amount": amount,
        "payment_date": str(payment_date) if payment_date else None,
        "can_edit_amount": can_edit_amount,
        "can_edit_rule": can_edit_rule,
        "can_delete": can_delete,
        "is_read_only": not (can_edit_amount or can_edit_rule or can_delete),
        "is_blank": amount is None,
        "effective_from_month": str(rule["effective_from_month"]),
        "effective_to_month": str(rule["effective_to_month"]) if rule.get("effective_to_month") else None,
    }


def _load_manual_rules(clinic: str, start_month: date, end_month: date) -> List[Dict[str, Any]]:
    rules = frappe.get_all(
        "Expense Rule",
        filters={"clinic": clinic, "is_active": 1},
        fields=[
            "name",
            "expense_name",
            "expense_category",
            "effective_from_month",
            "effective_to_month",
            "fixed_amount",
            "clinic",
        ],
        order_by="expense_name asc, effective_from_month asc",
        limit_page_length=0,
    )
    return [rule for rule in rules if _rule_overlaps_period(rule, start_month, end_month)]


def _load_monthly_values(rule_ids: Iterable[str], start_month: date, end_month: date) -> Dict[Tuple[str, str], Dict[str, Any]]:
    rule_ids = [rule_id for rule_id in rule_ids if rule_id]
    if not rule_ids:
        return {}

    rows = frappe.get_all(
        "Expense Monthly Value",
        filters={
            "expense_rule": ["in", rule_ids],
            "period_month": ["between", [start_month, end_month]],
        },
        fields=[
            "name",
            "expense_rule",
            "expense_name_snapshot",
            "period_month",
            "fiscal_year",
            "amount",
            "payment_date",
        ],
        limit_page_length=0,
    )
    return {
        (row["expense_rule"], _month_key(getdate(row["period_month"]))): row
        for row in rows
    }


def _build_manual_month_rows(clinic: str, context: PeriodContext) -> List[Dict[str, Any]]:
    rules = _load_manual_rules(clinic, context.month_start, context.month_start)
    monthly_values = _load_monthly_values([rule["name"] for rule in rules], context.month_start, context.month_start)

    rows = []
    for rule in rules:
        month_key = _month_key(context.month_start)
        row_value = monthly_values.get((rule["name"], month_key))

        amount = None
        payment_date = None
        is_editable = False

        if rule["expense_category"] == EXPENSE_CATEGORY_FIXED:
            # For recurring fixed, surface amount only when the selected month has started.
            # Future months remain unfilled until their month begins.
            if _has_month_started(context.month_start):
                amount = flt(rule.get("fixed_amount"), 2)
        elif rule["expense_category"] == EXPENSE_CATEGORY_VARIABLE:
            if row_value:
                amount = flt(row_value.get("amount"), 2)
                payment_date = getdate(row_value.get("payment_date")) if row_value.get("payment_date") else None
            is_editable = True
        elif rule["expense_category"] == EXPENSE_CATEGORY_ONE_TIME:
            if not row_value:
                continue
            amount = flt(row_value.get("amount"), 2)
            payment_date = getdate(row_value.get("payment_date")) if row_value.get("payment_date") else None
            is_editable = True

        rows.append(
            _serialize_manual_row(
                rule,
                _month_key(context.month_start),
                amount,
                payment_date,
                is_editable=is_editable,
                is_month_view=True,
            )
        )

    return rows


def _build_manual_fy_rows(clinic: str, context: PeriodContext) -> List[Dict[str, Any]]:
    rules = _load_manual_rules(clinic, context.fiscal_year_start, context.fiscal_year_end)
    monthly_values = _load_monthly_values(
        [rule["name"] for rule in rules],
        context.fiscal_year_start,
        context.fiscal_year_end,
    )
    fy_months = _iter_fiscal_year_months(context)

    rows = []
    for rule in rules:
        total_amount = 0.0
        has_visible_month = False
        for fy_month in fy_months:
            if not _rule_overlaps_period(rule, fy_month, fy_month):
                continue
            has_visible_month = True
            if rule["expense_category"] == EXPENSE_CATEGORY_FIXED:
                if _has_month_started(fy_month):
                    total_amount += flt(rule.get("fixed_amount"), 2)
                continue

            row_value = monthly_values.get((rule["name"], _month_key(fy_month)))
            if row_value:
                total_amount += flt(row_value.get("amount"), 2)

        if not has_visible_month:
            continue

        rows.append(
            _serialize_manual_row(
                rule,
                context.fiscal_year_name,
                round(total_amount, 2),
                None,
                is_editable=False,
                is_month_view=False,
            )
        )

    return rows


def _system_row_template(expense_name: str, system_key: str, period_token: str, amount: float) -> Dict[str, Any]:
    return {
        "row_key": _build_system_row_key(system_key, period_token),
        "row_type": "system",
        "expense_rule_id": None,
        "expense_name": expense_name,
        "expense_category": SYSTEM_CATEGORY,
        "is_system_generated": True,
        "amount": round(amount, 2),
        "payment_date": None,
        "can_edit_amount": False,
        "can_edit_rule": False,
        "can_delete": False,
        "is_read_only": True,
        "is_blank": False,
        "effective_from_month": None,
        "effective_to_month": None,
    }


def _fetch_system_rows(clinic: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
    rows = frappe.db.sql(
        """
        SELECT
            si.posting_date,
            si.name AS invoice_id,
            si.patient,
            si.patient_name,
            sii.item_code,
            sii.item_name,
            sii.description,
            sii.consultant_id,
            sii.consultant_name,
            sii.consultant_type,
            sii.consultant_commission_amount,
            sii.consultant_commission_source
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE si.docstatus = 1
          AND si.company = %s
          AND si.posting_date BETWEEN %s AND %s
          AND COALESCE(sii.consultant_commission_amount, 0) > 0
          AND COALESCE(sii.consultant_type, '') IN (%s, %s)
        ORDER BY si.posting_date ASC, si.name ASC, sii.idx ASC
        """,
        (clinic, start_date, end_date, CONSULTANT_TYPE_EXTERNAL, CONSULTANT_TYPE_INTERNAL),
        as_dict=True,
    )
    return rows


def _build_system_rows_for_month(clinic: str, context: PeriodContext) -> List[Dict[str, Any]]:
    invoice_rows = _fetch_system_rows(clinic, context.month_start, context.month_end)
    totals = {
        CONSULTANT_TYPE_EXTERNAL: 0.0,
        CONSULTANT_TYPE_INTERNAL: 0.0,
    }
    for row in invoice_rows:
        totals[row.consultant_type] = totals.get(row.consultant_type, 0.0) + flt(row.consultant_commission_amount, 2)

    return [
        _system_row_template(SYSTEM_VENDOR_PAYMENT, "vendor_payment", _month_key(context.month_start), totals[CONSULTANT_TYPE_EXTERNAL]),
        _system_row_template(SYSTEM_PRACTITIONER_SALARY, "practitioner_salary", _month_key(context.month_start), totals[CONSULTANT_TYPE_INTERNAL]),
    ]


def _build_system_rows_for_fy(clinic: str, context: PeriodContext) -> List[Dict[str, Any]]:
    invoice_rows = _fetch_system_rows(clinic, context.fiscal_year_start, context.fiscal_year_end)
    totals = {
        CONSULTANT_TYPE_EXTERNAL: 0.0,
        CONSULTANT_TYPE_INTERNAL: 0.0,
    }
    for row in invoice_rows:
        totals[row.consultant_type] = totals.get(row.consultant_type, 0.0) + flt(row.consultant_commission_amount, 2)

    return [
        _system_row_template(SYSTEM_VENDOR_PAYMENT, "vendor_payment", context.fiscal_year_name, totals[CONSULTANT_TYPE_EXTERNAL]),
        _system_row_template(SYSTEM_PRACTITIONER_SALARY, "practitioner_salary", context.fiscal_year_name, totals[CONSULTANT_TYPE_INTERNAL]),
    ]


def _sort_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda row: (row.get("expense_name") or "").lower())


def _summarize_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    manual_amount = 0.0
    system_amount = 0.0
    blank_manual_rows = 0

    for row in rows:
        amount = row.get("amount")
        if row.get("row_type") == "system":
            system_amount += flt(amount, 2)
            continue

        if amount is None:
            blank_manual_rows += 1
            continue
        manual_amount += flt(amount, 2)

    total_amount = round(manual_amount + system_amount, 2)
    return {
        "total_amount": total_amount,
        "manual_amount": round(manual_amount, 2),
        "system_amount": round(system_amount, 2),
        "row_count": len(rows),
        "blank_manual_rows": blank_manual_rows,
        "editable_row_count": sum(1 for row in rows if row.get("can_edit_amount") or row.get("can_edit_rule") or row.get("can_delete")),
        "read_only_row_count": sum(1 for row in rows if row.get("is_read_only")),
    }


def _parse_manual_row_key(row_key: str) -> Tuple[str, str]:
    parts = (row_key or "").split(":")
    if len(parts) != 3 or parts[0] != "manual":
        frappe.throw(_("Expense row key is invalid"), frappe.ValidationError)
    return parts[1], parts[2]


def _parse_system_row_key(row_key: str) -> Tuple[str, str]:
    parts = (row_key or "").split(":")
    if len(parts) != 3 or parts[0] != "system":
        frappe.throw(_("Expense row key is invalid"), frappe.ValidationError)
    return parts[1], parts[2]


def _get_rule(rule_id: str, clinic: str) -> Any:
    rule = frappe.get_doc("Expense Rule", rule_id)
    if rule.clinic != clinic:
        frappe.throw(_("Expense rule is invalid for this clinic"), frappe.PermissionError)
    return rule


def _get_or_create_monthly_value(
    rule: Any,
    period_month: date,
    fiscal_year_name: str,
    expense_name: str,
) -> Any:
    existing = frappe.db.get_value(
        "Expense Monthly Value",
        {"expense_rule": rule.name, "period_month": period_month},
        "name",
    )
    if existing:
        return frappe.get_doc("Expense Monthly Value", existing)

    return frappe.get_doc(
        {
            "doctype": "Expense Monthly Value",
            "clinic": rule.clinic,
            "expense_rule": rule.name,
            "expense_name_snapshot": expense_name,
            "period_month": period_month,
            "fiscal_year": fiscal_year_name,
            "source_type": "Manual",
        }
    )


def _upsert_monthly_value(
    rule: Any,
    period_month: date,
    fiscal_year_name: str,
    expense_name: str,
    amount: float,
    payment_date: Optional[date],
) -> Any:
    monthly_value = _get_or_create_monthly_value(rule, period_month, fiscal_year_name, expense_name)
    monthly_value.expense_name_snapshot = expense_name
    monthly_value.fiscal_year = fiscal_year_name
    monthly_value.amount = amount
    monthly_value.payment_date = payment_date
    if monthly_value.is_new():
        monthly_value.insert(ignore_permissions=True)
    else:
        monthly_value.save(ignore_permissions=True)
    return monthly_value


def _resolve_create_month(
    clinic: str,
    filter_mode: Optional[str],
    month: Optional[Any],
    year: Optional[Any],
    fiscal_year: Optional[str],
    payment_date: Optional[Any],
) -> Tuple[date, date, str]:
    context = _resolve_period_context(clinic, filter_mode, month, year, fiscal_year)
    parsed_payment_date = getdate(payment_date) if payment_date else None

    if context.filter_mode == FILTER_MODE_MONTH:
        effective_month = context.month_start
        chosen_payment_date = parsed_payment_date or effective_month
        if get_first_day(chosen_payment_date) != effective_month:
            frappe.throw(_("Payment date must fall inside the selected month"), frappe.ValidationError)
        return effective_month, chosen_payment_date, context.fiscal_year_name

    chosen_payment_date = parsed_payment_date or getdate(nowdate())
    if not (context.fiscal_year_start <= chosen_payment_date <= context.fiscal_year_end):
        chosen_payment_date = context.fiscal_year_start
    return get_first_day(chosen_payment_date), chosen_payment_date, _get_fiscal_year_for_date(chosen_payment_date, clinic)["name"]


def _build_manual_breakdown(rule_id: str, period_token: str, clinic: str, context: PeriodContext) -> Dict[str, Any]:
    rule = _get_rule(rule_id, clinic)
    if context.filter_mode == FILTER_MODE_MONTH:
        period_month = context.month_start
        value_name = frappe.db.get_value(
            "Expense Monthly Value",
            {"expense_rule": rule_id, "period_month": period_month},
            "name",
        )
        monthly_value = frappe.get_doc("Expense Monthly Value", value_name) if value_name else None
        amount = flt(rule.fixed_amount, 2) if rule.expense_category == EXPENSE_CATEGORY_FIXED else (flt(monthly_value.amount, 2) if monthly_value else None)
        return {
            "row_key": _build_manual_row_key(rule_id, period_token),
            "expense_name": rule.expense_name,
            "expense_category": rule.expense_category,
            "breakdown_mode": FILTER_MODE_MONTH,
            "summary": {
                "total_amount": amount or 0,
                "month_count": 1,
            },
            "groups": [
                {
                    "group_key": _month_key(period_month),
                    "group_label": _display_month(period_month),
                    "total_amount": amount or 0,
                    "contributors": [
                        {
                            "label": "Manual Entry",
                            "amount": amount,
                            "payment_date": str(monthly_value.payment_date) if monthly_value and monthly_value.payment_date else None,
                            "source": "Manual",
                            "is_blank": amount is None,
                        }
                    ],
                }
            ],
        }

    fy_months = _iter_fiscal_year_months(context)
    values = _load_monthly_values([rule_id], context.fiscal_year_start, context.fiscal_year_end)
    groups = []
    total_amount = 0.0
    for fy_month in fy_months:
        if not _rule_overlaps_period(
            {
                "effective_from_month": rule.effective_from_month,
                "effective_to_month": rule.effective_to_month,
            },
            fy_month,
            fy_month,
        ):
            continue

        amount = None
        payment_date = None
        if rule.expense_category == EXPENSE_CATEGORY_FIXED:
            if _has_month_started(fy_month):
                amount = flt(rule.fixed_amount, 2)
        else:
            row_value = values.get((rule_id, _month_key(fy_month)))
            if row_value:
                amount = flt(row_value.get("amount"), 2)
                payment_date = row_value.get("payment_date")

        total_amount += flt(amount, 2)
        groups.append(
            {
                "group_key": _month_key(fy_month),
                "group_label": _display_month(fy_month),
                "total_amount": flt(amount, 2),
                "contributors": [
                    {
                        "label": "Manual Entry",
                        "amount": amount,
                        "payment_date": str(payment_date) if payment_date else None,
                        "source": "Manual",
                        "is_blank": amount is None,
                    }
                ],
            }
        )

    return {
        "row_key": _build_manual_row_key(rule_id, period_token),
        "expense_name": rule.expense_name,
        "expense_category": rule.expense_category,
        "breakdown_mode": FILTER_MODE_FY,
        "summary": {
            "total_amount": round(total_amount, 2),
            "month_count": len(groups),
        },
        "groups": groups,
    }


def _system_breakdown_name(system_key: str) -> str:
    if system_key == "vendor_payment":
        return SYSTEM_VENDOR_PAYMENT
    if system_key == "practitioner_salary":
        return SYSTEM_PRACTITIONER_SALARY
    frappe.throw(_("Expense row key is invalid"), frappe.ValidationError)


def _build_system_breakdown(system_key: str, period_token: str, clinic: str, context: PeriodContext) -> Dict[str, Any]:
    expense_name = _system_breakdown_name(system_key)
    consultant_type = CONSULTANT_TYPE_EXTERNAL if system_key == "vendor_payment" else CONSULTANT_TYPE_INTERNAL
    start_date = context.month_start if context.filter_mode == FILTER_MODE_MONTH else context.fiscal_year_start
    end_date = context.month_end if context.filter_mode == FILTER_MODE_MONTH else context.fiscal_year_end

    rows = [row for row in _fetch_system_rows(clinic, start_date, end_date) if row.consultant_type == consultant_type]
    grouped = defaultdict(list)
    for row in rows:
        grouped[_month_key(get_first_day(getdate(row.posting_date)))].append(row)

    groups = []
    for month_key, month_rows in sorted(grouped.items()):
        month_date = get_first_day(getdate(f"{month_key}-01"))
        contributors = []
        total_amount = 0.0
        for row in month_rows:
            commission_amount = flt(row.consultant_commission_amount, 2)
            total_amount += commission_amount
            contributors.append(
                {
                    "label": row.consultant_name or "Unknown Consultant",
                    "amount": commission_amount,
                    "date": str(row.posting_date),
                    "invoice_id": row.invoice_id,
                    "patient": row.patient,
                    "patient_name": row.patient_name,
                    "procedure_name": row.item_name or row.description or row.item_code,
                    "commission_source": row.consultant_commission_source,
                    "consultant_type": row.consultant_type,
                }
            )
        groups.append(
            {
                "group_key": month_key,
                "group_label": _display_month(month_date),
                "total_amount": round(total_amount, 2),
                "contributors": contributors,
            }
        )

    if context.filter_mode == FILTER_MODE_MONTH and not groups:
        groups.append(
            {
                "group_key": _month_key(context.month_start),
                "group_label": _display_month(context.month_start),
                "total_amount": 0,
                "contributors": [],
            }
        )

    return {
        "row_key": _build_system_row_key(system_key, period_token),
        "expense_name": expense_name,
        "expense_category": SYSTEM_CATEGORY,
        "breakdown_mode": context.filter_mode,
        "summary": {
            "total_amount": round(sum(group["total_amount"] for group in groups), 2),
            "month_count": len(groups),
        },
        "groups": groups,
    }


@frappe.whitelist(methods=["GET"])
def get_expense_sheet(filter_mode=None, month=None, year=None, fiscal_year=None, clinic=None):
    _, resolved_clinic = _get_dashboard_context(clinic=clinic, require_admin=False)
    context = _resolve_period_context(resolved_clinic, filter_mode, month, year, fiscal_year)

    manual_rows = (
        _build_manual_month_rows(resolved_clinic, context)
        if context.filter_mode == FILTER_MODE_MONTH
        else _build_manual_fy_rows(resolved_clinic, context)
    )
    system_rows = (
        _build_system_rows_for_month(resolved_clinic, context)
        if context.filter_mode == FILTER_MODE_MONTH
        else _build_system_rows_for_fy(resolved_clinic, context)
    )
    rows = _sort_rows(manual_rows + system_rows)
    summary = _summarize_rows(rows)

    return {
        "message": "Success",
        "data": {
            "summary": summary,
            "totals": {
                "total_amount": summary["total_amount"],
                "manual_amount": summary["manual_amount"],
                "system_amount": summary["system_amount"],
            },
            "rows": rows,
            "filters": {
                "filter_mode": context.filter_mode,
                "selected_month": str(context.month_start) if context.month_start else None,
                "selected_year": context.month_start.year if context.month_start else None,
                "selected_month_number": context.month_start.month if context.month_start else None,
                "selected_fiscal_year": context.fiscal_year_name,
                "available_fiscal_years": context.fiscal_years,
            },
            "default_selected_row_key": rows[0]["row_key"] if rows else None,
        },
    }


@frappe.whitelist(methods=["GET"])
def get_expense_breakdown(row_key, filter_mode=None, month=None, year=None, fiscal_year=None, clinic=None):
    _, resolved_clinic = _get_dashboard_context(clinic=clinic, require_admin=False)
    context = _resolve_period_context(resolved_clinic, filter_mode, month, year, fiscal_year)

    if row_key.startswith("manual:"):
        rule_id, period_token = _parse_manual_row_key(row_key)
        data = _build_manual_breakdown(rule_id, period_token, resolved_clinic, context)
    elif row_key.startswith("system:"):
        system_key, period_token = _parse_system_row_key(row_key)
        data = _build_system_breakdown(system_key, period_token, resolved_clinic, context)
    else:
        frappe.throw(_("Expense row key is invalid"), frappe.ValidationError)

    return {
        "message": "Success",
        "data": data,
    }


@frappe.whitelist(methods=["POST"])
def create_expense(
    expense_name,
    expense_category,
    amount,
    clinic=None,
    filter_mode=None,
    month=None,
    year=None,
    fiscal_year=None,
    payment_date=None,
    apply_backfill=0,
    backfill_start_month=None,
    backfill_end_month=None,
):
    _, resolved_clinic = _get_dashboard_context(clinic=clinic, require_admin=True)

    expense_name = _normalize_string(expense_name)
    expense_category = _normalize_string(expense_category)
    if not expense_name:
        frappe.throw(_("Expense item is required"), frappe.ValidationError)
    if expense_category not in {EXPENSE_CATEGORY_FIXED, EXPENSE_CATEGORY_VARIABLE, EXPENSE_CATEGORY_ONE_TIME}:
        frappe.throw(_("Expense category is invalid"), frappe.ValidationError)

    parsed_amount = _parse_decimal_amount(amount)
    effective_month, chosen_payment_date, fiscal_year_name = _resolve_create_month(
        resolved_clinic,
        filter_mode,
        month,
        year,
        fiscal_year,
        payment_date,
    )

    apply_backfill = cint(apply_backfill) if str(apply_backfill).strip() != "" else 0
    rule_start_month = effective_month
    historical_backfill_to = None
    if expense_category == EXPENSE_CATEGORY_FIXED and apply_backfill:
        backfill_start = _parse_month_input(backfill_start_month, "Backfill start month")
        backfill_end = _parse_month_input(backfill_end_month or str(effective_month), "Backfill end month")
        if backfill_start > backfill_end:
            frappe.throw(_("Backfill start month cannot be after backfill end month"), frappe.ValidationError)
        if backfill_end > effective_month:
            frappe.throw(_("Backfill end month cannot be after selected month"), frappe.ValidationError)
        if backfill_end < effective_month:
            historical_backfill_to = backfill_end
            rule_start_month = effective_month
        else:
            rule_start_month = backfill_start

    rule_doc = frappe.get_doc(
        {
            "doctype": "Expense Rule",
            "clinic": resolved_clinic,
            "expense_name": expense_name,
            "expense_category": expense_category,
            "effective_from_month": rule_start_month,
            "fixed_amount": parsed_amount if expense_category == EXPENSE_CATEGORY_FIXED else 0,
            "is_active": 1,
        }
    )
    rule_doc.insert(ignore_permissions=True)

    historical_rule = None
    if expense_category == EXPENSE_CATEGORY_FIXED and apply_backfill and historical_backfill_to:
        historical_rule = frappe.get_doc(
            {
                "doctype": "Expense Rule",
                "clinic": resolved_clinic,
                "expense_name": expense_name,
                "expense_category": EXPENSE_CATEGORY_FIXED,
                "effective_from_month": backfill_start,
                "effective_to_month": historical_backfill_to,
                "fixed_amount": parsed_amount,
                "is_active": 1,
            }
        )
        historical_rule.insert(ignore_permissions=True)

    monthly_value = None
    if expense_category in {EXPENSE_CATEGORY_VARIABLE, EXPENSE_CATEGORY_ONE_TIME}:
        monthly_value = _upsert_monthly_value(
            rule_doc,
            effective_month,
            fiscal_year_name,
            expense_name,
            parsed_amount,
            chosen_payment_date,
        )

    return {
        "message": "Expense created successfully",
        "data": {
            "expense_rule_id": rule_doc.name,
            "historical_rule_id": historical_rule.name if historical_rule else None,
            "monthly_value_id": monthly_value.name if monthly_value else None,
        },
    }


@frappe.whitelist(methods=["POST"])
def save_expense_changes(changes, clinic=None):
    _, resolved_clinic = _get_dashboard_context(clinic=clinic, require_admin=True)
    parsed_changes = frappe.parse_json(changes) if isinstance(changes, str) else (changes or [])
    if not isinstance(parsed_changes, list):
        frappe.throw(_("Changes payload is invalid"), frappe.ValidationError)

    saved_rows = []
    for change in parsed_changes:
        row_key = change.get("row_key")
        if not row_key or not row_key.startswith("manual:"):
            frappe.throw(_("Only manual expense rows can be saved"), frappe.ValidationError)

        rule_id, period_token = _parse_manual_row_key(row_key)
        period_month = getdate(f"{period_token}-01")
        rule = _get_rule(rule_id, resolved_clinic)

        if rule.expense_category == EXPENSE_CATEGORY_FIXED:
            frappe.throw(_("Recurring fixed rows are read-only. Update the rule instead."), frappe.ValidationError)

        amount = _parse_decimal_amount(change.get("amount"))
        payment_date = getdate(change.get("payment_date")) if change.get("payment_date") else period_month
        if get_first_day(payment_date) != period_month:
            frappe.throw(_("Payment date must fall inside the selected month"), frappe.ValidationError)

        fiscal_year_doc = _get_fiscal_year_for_date(period_month, resolved_clinic)
        monthly_value = _upsert_monthly_value(
            rule,
            period_month,
            fiscal_year_doc["name"],
            change.get("expense_name") or rule.expense_name,
            amount,
            payment_date,
        )
        saved_rows.append(monthly_value.name)

    return {
        "message": "Expense changes saved successfully",
        "data": {
            "saved_rows": saved_rows,
        },
    }


def _retire_rule_from_month(rule: Any, effective_month: date):
    previous_month = _previous_month(effective_month)
    if previous_month < getdate(rule.effective_from_month):
        future_values = frappe.get_all(
            "Expense Monthly Value",
            filters={"expense_rule": rule.name},
            pluck="name",
        )
        for value_name in future_values:
            frappe.delete_doc("Expense Monthly Value", value_name, ignore_permissions=True, force=True)
        frappe.delete_doc("Expense Rule", rule.name, ignore_permissions=True, force=True)
        return

    rule.effective_to_month = previous_month
    rule.save(ignore_permissions=True)
    if rule.expense_category != EXPENSE_CATEGORY_FIXED:
        future_values = frappe.get_all(
            "Expense Monthly Value",
            filters={
                "expense_rule": rule.name,
                "period_month": [">=", effective_month],
            },
            pluck="name",
        )
        for value_name in future_values:
            frappe.delete_doc("Expense Monthly Value", value_name, ignore_permissions=True, force=True)


@frappe.whitelist(methods=["POST"])
def update_expense_rule(rule_id, effective_month, expense_category, amount=None, expense_name=None, clinic=None):
    _, resolved_clinic = _get_dashboard_context(clinic=clinic, require_admin=True)
    rule = _get_rule(rule_id, resolved_clinic)
    if rule.expense_category != EXPENSE_CATEGORY_FIXED:
        frappe.throw(_("Only recurring fixed expenses use rule updates"), frappe.ValidationError)

    new_category = _normalize_string(expense_category)
    if new_category not in {EXPENSE_CATEGORY_FIXED, EXPENSE_CATEGORY_VARIABLE}:
        frappe.throw(_("Rule updates support recurring fixed or recurring variable"), frappe.ValidationError)

    effective_month_date = get_first_day(getdate(effective_month))
    if effective_month_date < getdate(rule.effective_from_month):
        frappe.throw(_("Effective month cannot be before the rule start month"), frappe.ValidationError)

    parsed_amount = _parse_decimal_amount(amount, required=new_category == EXPENSE_CATEGORY_FIXED)
    next_name = _normalize_string(expense_name) or rule.expense_name

    if effective_month_date == getdate(rule.effective_from_month):
        rule.expense_name = next_name
        rule.expense_category = new_category
        rule.fixed_amount = parsed_amount if new_category == EXPENSE_CATEGORY_FIXED else 0
        rule.save(ignore_permissions=True)
        if new_category == EXPENSE_CATEGORY_VARIABLE and amount not in (None, ""):
            fiscal_year_doc = _get_fiscal_year_for_date(effective_month_date, resolved_clinic)
            _upsert_monthly_value(
                rule,
                effective_month_date,
                fiscal_year_doc["name"],
                next_name,
                _parse_decimal_amount(amount),
                effective_month_date,
            )
        return {
            "message": "Expense rule updated successfully",
            "data": {"expense_rule_id": rule.name},
        }

    rule.effective_to_month = _previous_month(effective_month_date)
    rule.save(ignore_permissions=True)

    successor = frappe.get_doc(
        {
            "doctype": "Expense Rule",
            "clinic": resolved_clinic,
            "expense_name": next_name,
            "expense_category": new_category,
            "effective_from_month": effective_month_date,
            "fixed_amount": parsed_amount if new_category == EXPENSE_CATEGORY_FIXED else 0,
            "is_active": 1,
        }
    )
    successor.insert(ignore_permissions=True)

    if new_category == EXPENSE_CATEGORY_VARIABLE and amount not in (None, ""):
        fiscal_year_doc = _get_fiscal_year_for_date(effective_month_date, resolved_clinic)
        _upsert_monthly_value(
            successor,
            effective_month_date,
            fiscal_year_doc["name"],
            next_name,
            _parse_decimal_amount(amount),
            effective_month_date,
        )

    return {
        "message": "Expense rule updated successfully",
        "data": {"expense_rule_id": successor.name},
    }


@frappe.whitelist(methods=["POST"])
def delete_expense(rule_id, effective_month=None, clinic=None, delete_mode=None):
    _, resolved_clinic = _get_dashboard_context(clinic=clinic, require_admin=True)
    rule = _get_rule(rule_id, resolved_clinic)
    effective_month_date = get_first_day(getdate(effective_month)) if effective_month else getdate(rule.effective_from_month)
    delete_mode = (delete_mode or "forward").strip().lower()
    if delete_mode not in {"forward", "all"}:
        frappe.throw(_("Delete mode is invalid"), frappe.ValidationError)

    if delete_mode == "all" or rule.expense_category == EXPENSE_CATEGORY_ONE_TIME:
        value_names = frappe.get_all(
            "Expense Monthly Value",
            filters={"expense_rule": rule.name},
            pluck="name",
        )
        for value_name in value_names:
            frappe.delete_doc("Expense Monthly Value", value_name, ignore_permissions=True, force=True)
        frappe.delete_doc("Expense Rule", rule.name, ignore_permissions=True, force=True)
    else:
        _retire_rule_from_month(rule, effective_month_date)

    return {
        "message": "Expense deleted successfully",
        "data": {"expense_rule_id": rule_id},
    }


@frappe.whitelist(methods=["GET"])
def search_expense_items(q=None, clinic=None):
    _, resolved_clinic = _get_dashboard_context(clinic=clinic, require_admin=False)
    query = f"%{_normalize_string(q)}%"
    names = set()

    for row in frappe.get_all(
        "Expense Rule",
        filters={"clinic": resolved_clinic, "expense_name": ["like", query]},
        fields=["expense_name"],
        order_by="expense_name asc",
        limit_page_length=20,
    ):
        if row.expense_name:
            names.add(row.expense_name)

    for row in frappe.get_all(
        "Expense Monthly Value",
        filters={"clinic": resolved_clinic, "expense_name_snapshot": ["like", query]},
        fields=["expense_name_snapshot"],
        order_by="expense_name_snapshot asc",
        limit_page_length=20,
    ):
        if row.expense_name_snapshot:
            names.add(row.expense_name_snapshot)

    items = [{"id": name, "name": name} for name in sorted(names)]
    return {
        "message": "Success",
        "data": {"items": items},
    }
