"""
Financial Dashboard APIs for Mobile Application
Provides aggregate financial stats, revenue trends, payment breakdowns, and recent transactions.
"""

import frappe
from frappe import _
from frappe.utils import today, nowdate, getdate, flt, add_days, add_months, get_first_day, get_last_day
from datetime import datetime, timedelta
from mob_clinic.mob_clinic.api import clinic as clinic_helper


def get_current_practitioner():
    """Get the Healthcare Practitioner linked to current user"""
    user = frappe.session.user
    practitioner = frappe.db.get_value(
        "Healthcare Practitioner",
        {"user_id": user},
        ["name", "practitioner_name"],
        as_dict=True
    )
    return practitioner


@frappe.whitelist(methods=['GET'])
def get_financial_stats(from_date=None, to_date=None, clinic=None):
    """
    Get comprehensive financial dashboard statistics.

    Args:
        from_date (str): Start date (YYYY-MM-DD). Defaults to beginning of current month.
        to_date (str): End date (YYYY-MM-DD). Defaults to today.
        clinic (str): Optional clinic/company filter.

    Returns:
        dict: {
            "message": "Success",
            "data": {
                "summary": {...},
                "revenue_trend": [...],
                "payment_modes": [...],
                "top_procedures": [...],
                "recent_transactions": [...]
            }
        }
    """
    try:
        practitioner = get_current_practitioner()
        if not practitioner:
            frappe.local.response["http_status_code"] = 403
            return {
                "exc_type": "PermissionError",
                "message": "Healthcare Practitioner profile not found"
            }

        # Resolve clinic (company) scope
        resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name, clinic)

        # Default date range: beginning of current month to today
        today_date = getdate(nowdate())
        if not to_date:
            to_date = today_date
        else:
            to_date = getdate(to_date)

        if not from_date:
            from_date = get_first_day(today_date)
        else:
            from_date = getdate(from_date)

        # Build base filters for practitioner and clinic
        base_filters = {"healthcare_practitioner": practitioner.name, "docstatus": 1}
        if resolved_clinic:
            base_filters["company"] = resolved_clinic

        # --------------------------
        # SUMMARY STATS
        # --------------------------
        summary = _calculate_summary(base_filters, today_date, from_date, to_date)

        # --------------------------
        # REVENUE TREND (daily breakdown for the period)
        # --------------------------
        revenue_trend = _calculate_revenue_trend(base_filters, from_date, to_date)

        # --------------------------
        # PAYMENT MODES BREAKDOWN
        # --------------------------
        payment_modes = _calculate_payment_modes(base_filters, from_date, to_date)

        # --------------------------
        # TOP PROCEDURES (Revenue by item/service)
        # --------------------------
        top_procedures = _calculate_top_procedures(base_filters, from_date, to_date)

        # --------------------------
        # RECENT TRANSACTIONS
        # --------------------------
        recent_transactions = _get_recent_transactions(base_filters, limit=10)

        return {
            "message": "Success",
            "data": {
                "summary": summary,
                "revenue_trend": revenue_trend,
                "payment_modes": payment_modes,
                "top_procedures": top_procedures,
                "recent_transactions": recent_transactions,
            }
        }

    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Financial Stats Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error retrieving financial statistics"
        }


def _calculate_summary(base_filters, today_date, from_date, to_date):
    """Calculate dashboard summary metrics."""

    # Today's collection
    today_filters = dict(base_filters)
    today_filters["posting_date"] = today_date
    today_invoices = frappe.get_all(
        "Sales Invoice",
        filters=today_filters,
        fields=["grand_total", "outstanding_amount"]
    )
    today_collection = sum(flt(inv.grand_total - inv.outstanding_amount) for inv in today_invoices)

    # Yesterday's collection (for growth comparison)
    yesterday = add_days(today_date, -1)
    yesterday_filters = dict(base_filters)
    yesterday_filters["posting_date"] = yesterday
    yesterday_invoices = frappe.get_all(
        "Sales Invoice",
        filters=yesterday_filters,
        fields=["grand_total", "outstanding_amount"]
    )
    yesterday_collection = sum(flt(inv.grand_total - inv.outstanding_amount) for inv in yesterday_invoices)

    # Today's growth percentage
    if yesterday_collection > 0:
        today_growth = round(((today_collection - yesterday_collection) / yesterday_collection) * 100, 1)
    else:
        today_growth = 100.0 if today_collection > 0 else 0.0

    # Month collection (from_date to to_date)
    month_filters = dict(base_filters)
    month_filters["posting_date"] = ["between", [from_date, to_date]]
    month_invoices = frappe.get_all(
        "Sales Invoice",
        filters=month_filters,
        fields=["grand_total", "outstanding_amount"]
    )
    month_collection = sum(flt(inv.grand_total - inv.outstanding_amount) for inv in month_invoices)

    # Last month same period (for month growth comparison)
    last_month_start = add_months(from_date, -1)
    last_month_end = add_months(to_date, -1)
    last_month_filters = dict(base_filters)
    last_month_filters["posting_date"] = ["between", [last_month_start, last_month_end]]
    last_month_invoices = frappe.get_all(
        "Sales Invoice",
        filters=last_month_filters,
        fields=["grand_total", "outstanding_amount"]
    )
    last_month_collection = sum(flt(inv.grand_total - inv.outstanding_amount) for inv in last_month_invoices)

    # Month growth percentage
    if last_month_collection > 0:
        month_growth = round(((month_collection - last_month_collection) / last_month_collection) * 100, 1)
    else:
        month_growth = 100.0 if month_collection > 0 else 0.0

    # Total outstanding
    outstanding_filters = dict(base_filters)
    outstanding_filters["outstanding_amount"] = [">", 0]
    outstanding_invoices = frappe.get_all(
        "Sales Invoice",
        filters=outstanding_filters,
        fields=["outstanding_amount"]
    )
    total_outstanding = sum(flt(inv.outstanding_amount) for inv in outstanding_invoices)

    # Patient counts (total, new, returning in the date range)
    patient_stats = _calculate_patient_stats(base_filters, from_date, to_date)

    return {
        "today_collection": round(today_collection, 2),
        "today_growth": today_growth,
        "month_collection": round(month_collection, 2),
        "month_growth": month_growth,
        "total_outstanding": round(total_outstanding, 2),
        "total_patients": patient_stats["total_patients"],
        "new_patients": patient_stats["new_patients"],
        "returning_patients": patient_stats["returning_patients"]
    }


def _calculate_patient_stats(base_filters, from_date, to_date):
    """Calculate patient statistics for the date range."""
    # Get all unique patients invoiced in the date range
    invoice_filters = dict(base_filters)
    invoice_filters["posting_date"] = ["between", [from_date, to_date]]
    invoiced_patients = frappe.get_all(
        "Sales Invoice",
        filters=invoice_filters,
        fields=["patient"],
        distinct=True
    )

    patient_ids = list(set([p.patient for p in invoiced_patients if p.patient]))
    total_patients = len(patient_ids)

    # Determine new vs returning
    # New patient = first invoice ever falls within the date range
    # Returning patient = has invoices before the date range
    new_patients = 0
    returning_patients = 0

    for patient_id in patient_ids:
        # Check if patient had any invoices before from_date
        check_filters = {"patient": patient_id, "docstatus": 1, "posting_date": ["<", from_date]}
        if "healthcare_practitioner" in base_filters:
            check_filters["healthcare_practitioner"] = base_filters["healthcare_practitioner"]
        if "company" in base_filters:
            check_filters["company"] = base_filters["company"]

        previous_invoices = frappe.db.count("Sales Invoice", check_filters)
        if previous_invoices > 0:
            returning_patients += 1
        else:
            new_patients += 1

    return {
        "total_patients": total_patients,
        "new_patients": new_patients,
        "returning_patients": returning_patients
    }


def _calculate_revenue_trend(base_filters, from_date, to_date):
    """Calculate daily revenue trend for the date range."""
    revenue_trend = []

    # Iterate through each day in the date range
    current_date = from_date
    while current_date <= to_date:
        day_filters = dict(base_filters)
        day_filters["posting_date"] = current_date

        day_invoices = frappe.get_all(
            "Sales Invoice",
            filters=day_filters,
            fields=["grand_total", "outstanding_amount"]
        )
        day_amount = sum(flt(inv.grand_total - inv.outstanding_amount) for inv in day_invoices)

        revenue_trend.append({
            "date": str(current_date),
            "amount": round(day_amount, 2)
        })

        current_date = add_days(current_date, 1)

    return revenue_trend


def _calculate_payment_modes(base_filters, from_date, to_date):
    """Calculate payment breakdown by mode of payment."""
    # Get all payment entries in the date range linked to invoices from this practitioner
    practitioner = base_filters.get("healthcare_practitioner")
    company = base_filters.get("company")

    # Build SQL query to get payments linked to our practitioner's invoices
    conditions = ["pe.docstatus = 1", f"pe.posting_date BETWEEN '{from_date}' AND '{to_date}'"]
    if company:
        conditions.append(f"pe.company = '{company}'")

    # Get invoices for this practitioner to filter payment references
    invoice_filter = {"healthcare_practitioner": practitioner, "docstatus": 1}
    if company:
        invoice_filter["company"] = company

    practitioner_invoices = frappe.get_all(
        "Sales Invoice",
        filters=invoice_filter,
        fields=["name"]
    )
    invoice_names = [inv.name for inv in practitioner_invoices]

    if not invoice_names:
        return []

    # Get payments linked to these invoices
    payments_by_mode = frappe.db.sql("""
        SELECT 
            pe.mode_of_payment,
            SUM(per.allocated_amount) as total_amount
        FROM `tabPayment Entry` pe
        INNER JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
        WHERE pe.docstatus = 1
            AND pe.payment_type = 'Receive'
            AND pe.posting_date BETWEEN %s AND %s
            AND per.reference_doctype = 'Sales Invoice'
            AND per.reference_name IN %s
        GROUP BY pe.mode_of_payment
        ORDER BY total_amount DESC
    """, (from_date, to_date, tuple(invoice_names)), as_dict=True)

    # Calculate percentages
    total_amount = sum(flt(p.total_amount) for p in payments_by_mode)
    payment_modes = []

    for p in payments_by_mode:
        amount = flt(p.total_amount)
        percentage = round((amount / total_amount) * 100, 1) if total_amount > 0 else 0
        payment_modes.append({
            "mode": p.mode_of_payment or "Unknown",
            "amount": round(amount, 2),
            "percentage": percentage
        })

    return payment_modes


def _calculate_top_procedures(base_filters, from_date, to_date, limit=10):
    """Calculate top revenue-generating procedures/services."""
    practitioner = base_filters.get("healthcare_practitioner")
    company = base_filters.get("company")

    # Build query with parameterized values to avoid SQL injection
    conditions = ["si.docstatus = 1", "si.posting_date BETWEEN %s AND %s"]
    params = [from_date, to_date]

    if practitioner:
        conditions.append("si.healthcare_practitioner = %s")
        params.append(practitioner)
    if company:
        conditions.append("si.company = %s")
        params.append(company)

    where_clause = " AND ".join(conditions)
    params.append(limit)

    # Get top items by revenue using parameterized query
    top_items = frappe.db.sql(f"""
        SELECT 
            sii.item_name as name,
            SUM(sii.amount) as revenue,
            SUM(sii.qty) as count
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON sii.parent = si.name
        WHERE {where_clause}
        GROUP BY sii.item_code, sii.item_name
        ORDER BY revenue DESC
        LIMIT %s
    """, tuple(params), as_dict=True)

    top_procedures = []
    for item in top_items:
        top_procedures.append({
            "name": item.name or "Unknown",
            "revenue": round(flt(item.revenue), 2),
            "count": int(flt(item.count))
        })

    return top_procedures


def _get_recent_transactions(base_filters, limit=10):
    """Get recent payment transactions."""
    practitioner = base_filters.get("healthcare_practitioner")
    company = base_filters.get("company")

    # Get practitioner's invoices
    invoice_filter = {"healthcare_practitioner": practitioner, "docstatus": 1}
    if company:
        invoice_filter["company"] = company

    practitioner_invoices = frappe.get_all(
        "Sales Invoice",
        filters=invoice_filter,
        fields=["name", "patient", "patient_name"]
    )

    if not practitioner_invoices:
        return []

    invoice_names = [inv.name for inv in practitioner_invoices]
    invoice_patient_map = {inv.name: {"patient": inv.patient, "patient_name": inv.patient_name} for inv in practitioner_invoices}

    # Get recent payments linked to these invoices
    recent_payments = frappe.db.sql("""
        SELECT 
            pe.name as id,
            per.reference_name as invoice_id,
            pe.posting_date as date,
            per.allocated_amount as amount,
            pe.mode_of_payment as mode,
            pe.docstatus
        FROM `tabPayment Entry` pe
        INNER JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
        WHERE pe.docstatus = 1
            AND pe.payment_type = 'Receive'
            AND per.reference_doctype = 'Sales Invoice'
            AND per.reference_name IN %s
        ORDER BY pe.creation DESC
        LIMIT %s
    """, (tuple(invoice_names), limit), as_dict=True)

    transactions = []
    for payment in recent_payments:
        invoice_info = invoice_patient_map.get(payment.invoice_id, {})
        transactions.append({
            "id": payment.invoice_id,
            "patient_name": invoice_info.get("patient_name", "Unknown"),
            "date": str(payment.date) if payment.date else "",
            "amount": round(flt(payment.amount), 2),
            "mode": payment.mode or "Unknown",
            "status": "Paid"
        })

    return transactions


@frappe.whitelist(methods=['GET'])
def get_collection_summary(period="today", clinic=None):
    """
    Get a quick collection summary for a specific period.

    Args:
        period (str): "today", "week", "month", "year"
        clinic (str): Optional clinic/company filter.

    Returns:
        dict: Collection summary for the period.
    """
    try:
        practitioner = get_current_practitioner()
        if not practitioner:
            frappe.local.response["http_status_code"] = 403
            return {
                "exc_type": "PermissionError",
                "message": "Healthcare Practitioner profile not found"
            }

        resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name, clinic)

        today_date = getdate(nowdate())

        # Determine date range based on period
        if period == "today":
            from_date = today_date
            to_date = today_date
        elif period == "week":
            # Current week (Monday to today)
            from_date = add_days(today_date, -today_date.weekday())
            to_date = today_date
        elif period == "month":
            from_date = get_first_day(today_date)
            to_date = today_date
        elif period == "year":
            from_date = getdate(f"{today_date.year}-01-01")
            to_date = today_date
        else:
            from_date = today_date
            to_date = today_date

        # Build filters
        filters = {
            "healthcare_practitioner": practitioner.name,
            "docstatus": 1,
            "posting_date": ["between", [from_date, to_date]]
        }
        if resolved_clinic:
            filters["company"] = resolved_clinic

        # Get invoices
        invoices = frappe.get_all(
            "Sales Invoice",
            filters=filters,
            fields=["grand_total", "outstanding_amount"]
        )

        total_invoiced = sum(flt(inv.grand_total) for inv in invoices)
        total_collected = sum(flt(inv.grand_total - inv.outstanding_amount) for inv in invoices)
        total_outstanding = sum(flt(inv.outstanding_amount) for inv in invoices)

        return {
            "message": "Success",
            "data": {
                "period": period,
                "from_date": str(from_date),
                "to_date": str(to_date),
                "total_invoiced": round(total_invoiced, 2),
                "total_collected": round(total_collected, 2),
                "total_outstanding": round(total_outstanding, 2),
                "invoice_count": len(invoices)
            }
        }

    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Collection Summary Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error retrieving collection summary"
        }
