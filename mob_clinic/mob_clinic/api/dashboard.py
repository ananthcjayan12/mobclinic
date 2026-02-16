"""
Financial Dashboard APIs for Mobile Application
Provides aggregate financial stats, revenue trends, payment breakdowns, and recent transactions.
"""

import frappe
from frappe import _
from frappe.utils import today, nowdate, getdate, flt, add_days, add_months, get_first_day, get_last_day
from datetime import datetime, timedelta
from mob_clinic.mob_clinic.api import clinic as clinic_helper
from mob_clinic.mob_clinic.api.role_access import assert_page_access





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

        assert_page_access("financial_dashboard", practitioner_name=practitioner.name)

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

        # Prepare response data
        response_data = {
            "summary": summary,
            "revenue_trend": revenue_trend,
            "payment_modes": payment_modes,
            "top_procedures": top_procedures,
            "recent_transactions": recent_transactions,
        }

        return {
            "message": "Success",
            "data": response_data
        }

    except frappe.PermissionError:
        frappe.local.response["http_status_code"] = 403
        return {
            "exc_type": "PermissionError",
            "message": "Not permitted"
        }
    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Financial Stats Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error retrieving financial statistics"
        }


def _get_payments_for_period(practitioner, company, from_date, to_date):
    """Get all payment allocations for practitioner's invoices in date range."""
    
    # First get all practitioner invoices (no date filter on invoices)
    invoice_filters = {"healthcare_practitioner": practitioner, "docstatus": 1}
    if company:
        invoice_filters["company"] = company
    
    practitioner_invoices = frappe.get_all(
        "Sales Invoice",
        filters=invoice_filters,
        fields=["name"],
        pluck="name"
    )
    
    if not practitioner_invoices:
        return []
    
    # Get payments allocated to these invoices within the date range
    payments = frappe.db.sql("""
        SELECT 
            pe.name,
            pe.posting_date,
            pe.mode_of_payment,
            per.allocated_amount,
            per.reference_name as invoice_id
        FROM `tabPayment Entry` pe
        INNER JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
        WHERE pe.docstatus = 1
            AND pe.payment_type = 'Receive'
            AND pe.posting_date BETWEEN %s AND %s
            AND per.reference_doctype = 'Sales Invoice'
            AND per.reference_name IN %s
    """, (from_date, to_date, practitioner_invoices), as_dict=True)
    
    return payments


def _calculate_summary(base_filters, today_date, from_date, to_date):
    """Calculate dashboard summary metrics with corrected collection logic."""
    
    practitioner = base_filters.get("healthcare_practitioner")
    company = base_filters.get("company")
    
    # TODAY'S METRICS
    # Get actual payments received today (not invoice status)
    today_payments = _get_payments_for_period(practitioner, company, today_date, today_date)
    today_collection = sum(flt(p.get('allocated_amount', 0)) for p in today_payments)
    
    # Get today's invoices for context
    today_filters = dict(base_filters)
    today_filters["posting_date"] = today_date
    today_invoices = frappe.get_all(
        "Sales Invoice",
        filters=today_filters,
        fields=["grand_total", "outstanding_amount"]
    )
    today_invoiced = sum(flt(inv.grand_total) for inv in today_invoices)

    # Yesterday's collection (for growth comparison)
    yesterday = add_days(today_date, -1)
    yesterday_payments = _get_payments_for_period(practitioner, company, yesterday, yesterday)
    yesterday_collection = sum(flt(p.get('allocated_amount', 0)) for p in yesterday_payments)

    # Today's growth percentage
    if yesterday_collection > 0:
        today_growth = round(((today_collection - yesterday_collection) / yesterday_collection) * 100, 1)
    else:
        today_growth = 100.0 if today_collection > 0 else 0.0

    # PERIOD METRICS (from_date to to_date)
    period_payments = _get_payments_for_period(practitioner, company, from_date, to_date)
    period_collection = sum(flt(p.get('allocated_amount', 0)) for p in period_payments)
    
    # Period invoices for context
    month_filters = dict(base_filters)
    month_filters["posting_date"] = ["between", [from_date, to_date]]
    month_invoices = frappe.get_all(
        "Sales Invoice",
        filters=month_filters,
        fields=["grand_total", "outstanding_amount"]
    )
    period_invoiced = sum(flt(inv.grand_total) for inv in month_invoices)

    # PREVIOUS PERIOD COMPARISON (same number of days)
    days_diff = (to_date - from_date).days
    prev_end = add_days(from_date, -1)
    prev_start = add_days(prev_end, -days_diff)
    
    prev_payments = _get_payments_for_period(practitioner, company, prev_start, prev_end)
    prev_collection = sum(flt(p.get('allocated_amount', 0)) for p in prev_payments)

    # Period growth percentage
    if prev_collection > 0:
        period_growth = round(((period_collection - prev_collection) / prev_collection) * 100, 1)
    else:
        period_growth = 100.0 if period_collection > 0 else 0.0

    # Total outstanding (all time, not just period)
    outstanding_filters = dict(base_filters)
    outstanding_filters["outstanding_amount"] = [">", 0]
    outstanding_invoices = frappe.get_all(
        "Sales Invoice",
        filters=outstanding_filters,
        fields=["outstanding_amount", "posting_date"]
    )
    total_outstanding = sum(flt(inv.outstanding_amount) for inv in outstanding_invoices)
    
    # Aging analysis
    aging_30 = sum(flt(inv.outstanding_amount) for inv in outstanding_invoices 
                   if (today_date - getdate(inv.posting_date)).days <= 30)
    aging_60 = sum(flt(inv.outstanding_amount) for inv in outstanding_invoices 
                   if 30 < (today_date - getdate(inv.posting_date)).days <= 60)
    aging_90_plus = sum(flt(inv.outstanding_amount) for inv in outstanding_invoices 
                        if (today_date - getdate(inv.posting_date)).days > 60)

    # Patient counts (total, new, returning in the date range)
    patient_stats = _calculate_patient_stats_optimized(base_filters, from_date, to_date)
    
    # ADDITIONAL KEY METRICS
    collection_rate = round((period_collection / period_invoiced * 100), 1) if period_invoiced > 0 else 0
    avg_transaction = round((period_collection / len(period_payments)), 2) if period_payments else 0

    return {
        # Today
        "today_collection": round(today_collection, 2),
        "today_invoiced": round(today_invoiced, 2),
        "today_growth": today_growth,
        
        # Period (keeping old keys for backward compatibility)
        "month_collection": round(period_collection, 2),
        "month_growth": period_growth,
        
        # New period keys
        "period_collection": round(period_collection, 2),
        "period_invoiced": round(period_invoiced, 2),
        "period_growth": period_growth,
        "collection_rate": collection_rate,
        
        # Outstanding
        "total_outstanding": round(total_outstanding, 2),
        "outstanding_count": len(outstanding_invoices),
        "aging_analysis": {
            "0_30_days": round(aging_30, 2),
            "31_60_days": round(aging_60, 2),
            "60_plus_days": round(aging_90_plus, 2)
        },
        
        # Patients
        "total_patients": patient_stats["total_patients"],
        "new_patients": patient_stats["new_patients"],
        "returning_patients": patient_stats["returning_patients"],
        
        # Additional insights
        "avg_transaction_value": avg_transaction,
        "total_transactions": len(period_payments)
    }


def _calculate_patient_stats_optimized(base_filters, from_date, to_date):
    """Calculate patient statistics - OPTIMIZED to avoid N+1 queries."""
    
    practitioner = base_filters.get("healthcare_practitioner")
    company = base_filters.get("company")
    
    # Get unique patients in period
    period_patients_query = """
        SELECT DISTINCT patient
        FROM `tabSales Invoice`
        WHERE docstatus = 1
            AND posting_date BETWEEN %s AND %s
            AND healthcare_practitioner = %s
            {company_filter}
            AND patient IS NOT NULL
    """
    
    params = [from_date, to_date, practitioner]
    company_filter = ""
    if company:
        company_filter = "AND company = %s"
        params.append(company)
    
    period_patients = frappe.db.sql(
        period_patients_query.format(company_filter=company_filter),
        tuple(params),
        as_dict=True
    )
    
    patient_ids = [p.patient for p in period_patients]
    total_patients = len(patient_ids)
    
    if total_patients == 0:
        return {"total_patients": 0, "new_patients": 0, "returning_patients": 0}
    
    # Get first invoice date for all patients in ONE query
    first_invoice_query = """
        SELECT 
            patient,
            MIN(posting_date) as first_invoice_date
        FROM `tabSales Invoice`
        WHERE docstatus = 1
            AND healthcare_practitioner = %s
            {company_filter}
            AND patient IN %s
        GROUP BY patient
    """
    
    params = [practitioner]
    if company:
        company_filter = "AND company = %s"
        params.append(company)
    else:
        company_filter = ""
    params.append(patient_ids)
    
    first_invoices = frappe.db.sql(
        first_invoice_query.format(company_filter=company_filter),
        tuple(params),
        as_dict=True
    )
    
    # Count new vs returning
    new_patients = 0
    returning_patients = 0
    
    for record in first_invoices:
        if getdate(record.first_invoice_date) >= from_date:
            new_patients += 1
        else:
            returning_patients += 1
    
    return {
        "total_patients": total_patients,
        "new_patients": new_patients,
        "returning_patients": returning_patients
    }


def _calculate_patient_stats(base_filters, from_date, to_date):
    """Calculate patient statistics for the date range.
    DEPRECATED: Use _calculate_patient_stats_optimized instead to avoid N+1 queries.
    Kept for backward compatibility.
    """
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
    """Calculate daily revenue trend based on actual payments received."""
    
    practitioner = base_filters.get("healthcare_practitioner")
    company = base_filters.get("company")
    
    # Get all payments for the period at once
    all_payments = _get_payments_for_period(practitioner, company, from_date, to_date)
    
    # Group by date
    payments_by_date = {}
    for payment in all_payments:
        date_str = str(payment.posting_date)
        if date_str not in payments_by_date:
            payments_by_date[date_str] = 0
        payments_by_date[date_str] += flt(payment.get('allocated_amount', 0))
    
    revenue_trend = []
    
    # Iterate through each day in the date range
    current_date = from_date
    while current_date <= to_date:
        date_str = str(current_date)
        day_amount = payments_by_date.get(date_str, 0)

        revenue_trend.append({
            "date": date_str,
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

        # Get actual payments for the period
        period_payments = _get_payments_for_period(
            practitioner.name, 
            resolved_clinic, 
            from_date, 
            to_date
        )
        total_collected = sum(flt(p.get('allocated_amount', 0)) for p in period_payments)

        # Get invoices for context
        invoices = frappe.get_all(
            "Sales Invoice",
            filters=filters,
            fields=["grand_total", "outstanding_amount"]
        )

        total_invoiced = sum(flt(inv.grand_total) for inv in invoices)
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
                "invoice_count": len(invoices),
                "transaction_count": len(period_payments)
            }
        }

    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Collection Summary Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error retrieving collection summary"
        }
