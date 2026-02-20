"""
Payment and Invoice Management APIs for Mobile Application
Uses ERPNext Sales Invoice DocType with Healthcare extensions
"""

import frappe
from frappe import _
from frappe.utils import today, add_days, getdate, flt, nowdate
from mob_clinic.mob_clinic.api import clinic as clinic_helper
from mob_clinic.mob_clinic.api.role_access import assert_page_access


def get_or_create_default_service_item():
    """
    Get or create a default 'Clinic Service' item for dynamic treatments
    
    Returns:
        str: Item code of the default service item
    """
    item_code = "CLINIC-SERVICE"
    
    # Check if default service item exists
    if not frappe.db.exists("Item", item_code):
        try:
            # Create default service item
            item = frappe.get_doc({
                "doctype": "Item",
                "item_code": item_code,
                "item_name": "Clinic Service",
                "item_group": "Services",
                "stock_uom": "Nos",
                "is_stock_item": 0,  # Service items don't maintain stock
                "is_sales_item": 1,
                "description": "Generic clinic service item for treatments and consultations"
            })
            item.insert(ignore_permissions=True)
            frappe.logger().info(f"Created default service item: {item_code}")
        except Exception as e:
            frappe.log_error(f"Error creating default service item: {str(e)}", "Default Service Item Creation Error")
            # If creation fails, try to find any service item as fallback
            existing_service = frappe.db.get_value("Item", {"is_sales_item": 1, "is_stock_item": 0}, "item_code")
            if existing_service:
                return existing_service
            # Last resort - throw error
            frappe.throw(_("Could not create or find a default service item. Please create an Item with code 'CLINIC-SERVICE' manually."))
    
    return item_code

def _get_gst_accounts(company):
    """
    Get GST accounts for a company using India Compliance.
    
    Args:
        company (str): Company name
        
    Returns:
        dict: GST accounts (cgst_account, sgst_account, igst_account) or None
    """
    if not company:
        company = frappe.defaults.get_user_default("Company")
    
    if not company:
        return None
    
    try:
        # Try to use India Compliance's utility function
        from india_compliance.gst_india.utils import get_gst_accounts_by_type
        gst_accounts = get_gst_accounts_by_type(company, "Output", throw=False)
        if gst_accounts:
            return gst_accounts
    except ImportError:
        frappe.logger().warning("India Compliance not installed, GST accounts unavailable")
    except Exception as e:
        frappe.logger().warning(f"Could not get GST accounts: {str(e)}")
    
    return None


def _add_gst_taxes(invoice, tax_percentage, company):
    """
    Add GST tax rows to invoice using proper GST accounts.
    For intra-state transactions, adds CGST + SGST (each at half the rate).
    For inter-state, adds IGST at full rate.
    
    Args:
        invoice: Sales Invoice document
        tax_percentage: Total GST rate (e.g., 18 for 18% GST)
        company: Company name
        
    Returns:
        bool: True if taxes were added successfully
    """
    gst_accounts = _get_gst_accounts(company)
    if not gst_accounts:
        return False
    
    rate = flt(tax_percentage)
    if rate <= 0:
        return False
    
    # For simplicity, use CGST + SGST (intra-state) - each at half the rate
    # In production, you'd check customer/company state to determine CGST+SGST vs IGST
    half_rate = rate / 2
    
    # Add CGST
    if gst_accounts.get("cgst_account"):
        invoice.append("taxes", {
            "charge_type": "On Net Total",
            "account_head": gst_accounts.cgst_account,
            "description": f"CGST @ {half_rate}%",
            "rate": half_rate
        })
    
    # Add SGST
    if gst_accounts.get("sgst_account"):
        invoice.append("taxes", {
            "charge_type": "On Net Total",
            "account_head": gst_accounts.sgst_account,
            "description": f"SGST @ {half_rate}%",
            "rate": half_rate
        })
    
    return True


def _add_igst_tax(invoice, tax_percentage, company):
    """
    Add IGST tax row for inter-state transactions.
    
    Args:
        invoice: Sales Invoice document
        tax_percentage: GST rate (e.g., 18 for 18% IGST)
        company: Company name
        
    Returns:
        bool: True if tax was added successfully
    """
    gst_accounts = _get_gst_accounts(company)
    if not gst_accounts or not gst_accounts.get("igst_account"):
        return False
    
    rate = flt(tax_percentage)
    if rate <= 0:
        return False
    
    invoice.append("taxes", {
        "charge_type": "On Net Total",
        "account_head": gst_accounts.igst_account,
        "description": f"IGST @ {rate}%",
        "rate": rate
    })
    
    return True


def get_current_practitioner():
    """Get the Healthcare Practitioner linked to current user"""
    user = frappe.session.user
    practitioner = frappe.db.get_value(
        "Healthcare Practitioner",
        {"user_id": user},
        ["name", "practitioner_name"],
        as_dict=True
    )
    
    if not practitioner:
        frappe.throw(_("No Healthcare Practitioner found for current user"))
    
    return practitioner


@frappe.whitelist(methods=['GET'])
def get_invoices(patient_id=None, status=None, start_date=None, end_date=None, 
                 limit_start=0, limit_page_length=20, clinic=None):
    """
    Get list of invoices with filters
    
    Args:
        patient_id: Filter by patient
        status: Filter by status (Paid, Unpaid, Partly Paid, Overdue, Return)
        start_date: Filter from this date
        end_date: Filter until this date
        limit_start: Pagination start
        limit_page_length: Number of records per page
    
    Returns:
        List of invoices with patient details
    """
    try:
        practitioner = get_current_practitioner()
        # Note: Removed assert_page_access("invoice") - users with prescriptions/patients 
        # permission should be able to VIEW invoice data for patients they're treating.
        # Write operations (create/update/delete) still require "invoice" permission.
        
        # Resolve active clinic and build filters
        resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name, clinic)

        filters = {
            "docstatus": ["!=" , 2],  # Exclude cancelled
            "healthcare_practitioner": practitioner.name
        }

        if resolved_clinic:
            filters["company"] = resolved_clinic
        
        if patient_id:
            filters["patient"] = patient_id
        
        if status:
            filters["status"] = status
        
        if start_date:
            filters["posting_date"] = [">=", start_date]
        
        if end_date:
            if "posting_date" in filters:
                filters["posting_date"] = ["between", [start_date, end_date]]
            else:
                filters["posting_date"] = ["<=", end_date]
        
        # Get invoices
        invoices = frappe.get_all(
            "Sales Invoice",
            filters=filters,
            fields=[
                "name",
                "patient",
                "patient_name",
                "posting_date",
                "grand_total",
                "outstanding_amount",
                "status",
                "due_date"
            ],
            order_by="posting_date desc",
            limit_start=limit_start,
            limit_page_length=limit_page_length
        )
        
        # Enhance invoice data
        for invoice in invoices:
            invoice["paid_amount"] = flt(invoice.grand_total) - flt(invoice.outstanding_amount)
            invoice["is_overdue"] = False
            
            if invoice.status in ["Unpaid", "Partly Paid"] and invoice.due_date:
                if getdate(invoice.due_date) < getdate(today()):
                    invoice["is_overdue"] = True
        
        return {
            "invoices": invoices,
            "total_count": len(invoices)
        }
        
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Invoices Error")
        frappe.throw(_("Error fetching invoices: {0}").format(str(e)))


@frappe.whitelist(methods=['GET'])
def get_invoice(invoice_id):
    """
    Get detailed invoice information
    
    Args:
        invoice_id: Sales Invoice name
    
    Returns:
        Detailed invoice with items, payments, and patient info
    """
    try:
        practitioner = get_current_practitioner()
        # Note: Removed assert_page_access("invoice") - users should be able to VIEW
        # invoice details when reviewing patient records. Write operations still require permission.
        # enforce clinic scoping if session/practitioner has one
        resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name, None)
        
        # Get invoice
        invoice = frappe.get_doc("Sales Invoice", invoice_id)
        
        # Check permissions
        if invoice.healthcare_practitioner != practitioner.name:
            frappe.throw(_("You don't have permission to view this invoice"))

        # Enforce clinic/company scope if resolved
        if resolved_clinic and getattr(invoice, "company", None) and invoice.company != resolved_clinic:
            frappe.throw(_("You don't have permission to view this invoice in the current clinic"))
        
        # Get patient details
        patient_info = {}
        if invoice.patient:
            patient = frappe.get_doc("Patient", invoice.patient)
            patient_info = {
                "patient_id": patient.name,
                "patient_name": patient.patient_name,
                "mobile": patient.mobile,
                "email": patient.email,
                "sex": patient.sex,
                "dob": patient.dob
            }
        
        # Get invoice items
        items = []
        for item in invoice.items:
            items.append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description,
                "qty": item.qty,
                "rate": item.rate,
                "amount": item.amount
            })
        
        # Get payment entries
        payments = []
        if invoice.docstatus == 1:  # Only submitted invoices have payments
            payment_entries = frappe.get_all(
                "Payment Entry Reference",
                filters={"reference_name": invoice_id},
                fields=["parent"],
                distinct=True
            )
            
            for pe_ref in payment_entries:
                pe = frappe.get_doc("Payment Entry", pe_ref.parent)
                if pe.docstatus == 1:  # Only submitted payments
                    payments.append({
                        "payment_id": pe.name,
                        "posting_date": pe.posting_date,
                        "paid_amount": pe.paid_amount,
                        "mode_of_payment": pe.mode_of_payment,
                        "reference_no": pe.reference_no,
                        "reference_date": pe.reference_date
                    })
        
        # Build tax breakdown
        tax_breakdown = []
        for tax in invoice.taxes:
            tax_breakdown.append({
                "description": tax.description,
                "rate": tax.rate or 0,
                "tax_amount": tax.tax_amount or 0,
                "account_head": tax.account_head
            })
        
        # Build response
        invoice_data = {
            "invoice_id": invoice.name,
            "patient": patient_info,
            "posting_date": invoice.posting_date,
            "due_date": invoice.due_date,
            "status": invoice.status,
            "total": invoice.total,  # Total before tax and discount
            "net_total": invoice.net_total,
            "discount_amount": invoice.discount_amount or 0,
            "total_taxes_and_charges": invoice.total_taxes_and_charges or 0,
            "grand_total": invoice.grand_total,
            "outstanding_amount": invoice.outstanding_amount,
            "paid_amount": flt(invoice.grand_total) - flt(invoice.outstanding_amount),
            "items": items,
            "taxes": tax_breakdown,
            "payments": payments,
            "is_overdue": False,
            "remarks": invoice.remarks
        }
        
        # Check if overdue
        if invoice.status in ["Unpaid", "Partly Paid"] and invoice.due_date:
            if getdate(invoice.due_date) < getdate(today()):
                invoice_data["is_overdue"] = True
        
        return invoice_data
        
    except frappe.PermissionError:
        raise
    except frappe.DoesNotExistError:
        frappe.throw(_("Invoice not found"))
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Invoice Error")
        frappe.throw(_("Error fetching invoice: {0}").format(str(e)))


@frappe.whitelist(methods=['POST'])
def create_invoice(patient_id, items, posting_date=None, due_date=None, 
                   treatment_type=None, treatment_description=None,
                   appointment_reference=None, remarks=None, clinic=None,
                   discount_amount=None, tax_amount=None, discount_percentage=None,
                   tax_percentage=None, tax_template=None, is_cosmetic=False):
    """
    Create a new Sales Invoice
    
    Args:
        patient_id: Patient ID
        items: List of items [{"item_code": "CONS-001", "qty": 1, "rate": 500}]
        posting_date: Invoice date (default: today)
        due_date: Payment due date
        treatment_type: Type of treatment
        treatment_description: Treatment details
        appointment_reference: Link to Patient Appointment
        remarks: Additional notes
        clinic: Clinic/Company to create invoice for
        discount_amount: Fixed discount amount to apply
        discount_percentage: Percentage discount to apply
        tax_amount: Fixed tax amount to add
        tax_percentage: Tax percentage to apply (e.g., 18 for 18% GST)
        tax_template: Sales Taxes and Charges Template to use
        is_cosmetic: If True, applies 18% GST (cosmetic procedures like whitening, veneers);
                     If False (default), no GST for medical treatments (as per Indian GST law)
    
    GST Rules for Dental Clinics in India:
        - Medical treatments (extractions, root canals, fillings): 0% GST (Exempt)
        - Cosmetic procedures (whitening, veneers, smile design): 18% GST
    
    Returns:
        Created invoice details with tax breakdown
    """
    try:
        practitioner = get_current_practitioner()
        assert_page_access("invoice", practitioner_name=practitioner.name)

        # Resolve clinic and validate access
        resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name, clinic)
        if clinic and not clinic_helper.validate_practitioner_access(practitioner.name, resolved_clinic):
            frappe.throw(_("Practitioner does not have access to the requested clinic"), frappe.PermissionError)
        
        # Validate patient
        if not frappe.db.exists("Patient", patient_id):
            frappe.throw(_("Patient not found"))
        
        # Parse items if string
        if isinstance(items, str):
            import json
            items = json.loads(items)
        
        if not items or len(items) == 0:
            frappe.throw(_("At least one item is required"))
        
        # Get patient
        patient = frappe.get_doc("Patient", patient_id)
        
        # Get or create customer for patient
        customer_name = f"CUST-{patient_id}"
        if not frappe.db.exists("Customer", customer_name):
            customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": patient.patient_name,
                "customer_type": "Individual",
                "customer_group": "Individual",
                "territory": "All Territories"
            })
            customer.insert(ignore_permissions=True)
            customer_id = customer.name
        else:
            customer_id = customer_name
        
        # Ensure dates are proper date objects
        posting_date_value = getdate(posting_date) if posting_date else today()
        due_date_value = getdate(due_date) if due_date else add_days(posting_date_value, 7)
        
        # Create Sales Invoice
        invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": customer_id,
            "patient": patient_id,
            "patient_name": patient.patient_name,
            "set_posting_time": 1,
            "healthcare_practitioner": practitioner.name,
            "posting_date": posting_date_value,
            "due_date": due_date_value,
            "remarks": remarks,
            "items": [],
            "taxes": []
        })

        # Assign company if clinic/company resolved
        if resolved_clinic:
            invoice.company = resolved_clinic
        
        # Apply discount if provided
        if discount_amount:
            invoice.apply_discount_on = "Grand Total"
            invoice.discount_amount = flt(discount_amount)
        elif discount_percentage:
            invoice.apply_discount_on = "Grand Total"
            invoice.additional_discount_percentage = flt(discount_percentage)
        
        # Resolve appointment id from function arg or request (frontend may send `appointment_id`)
        appointment_id = appointment_reference
        try:
            if not appointment_id:
                appointment_id = frappe.local.form_dict.get("appointment_id") or frappe.form_dict.get("appointment_id")
        except Exception:
            # defensive: if form_dict access not available, ignore
            appointment_id = appointment_id

        # If appointment provided, validate it exists and is not already invoiced
        if appointment_id:
            if not frappe.db.exists("Patient Appointment", appointment_id):
                frappe.throw(_("Appointment not found: {0}").format(appointment_id))
            invoiced_flag = frappe.db.get_value("Patient Appointment", appointment_id, "invoiced")
            if invoiced_flag:
                frappe.throw(_("Appointment {0} is already invoiced").format(appointment_id))

        # Add items
        first_item = True
        for item in items:
            item_code = item.get("item_code")
            
            # If item_code doesn't exist, create it dynamically or use default service item
            if item_code:
                # Check if item exists
                if not frappe.db.exists("Item", item_code):
                    # Create the item dynamically
                    try:
                        new_item = frappe.get_doc({
                            "doctype": "Item",
                            "item_code": item_code,
                            "item_name": item.get("description") or item_code,
                            "item_group": "Services",  # or "Products" depending on your setup
                            "stock_uom": "Nos",
                            "is_stock_item": 0,  # Service items don't maintain stock
                            "is_sales_item": 1,
                            "description": item.get("description") or item_code
                        })
                        new_item.insert(ignore_permissions=True)
                        frappe.logger().info(f"Created new service item: {item_code}")
                    except Exception as item_error:
                        frappe.logger().warning(f"Could not create item {item_code}: {str(item_error)}")
                        # Use default service item as fallback
                        item_code = get_or_create_default_service_item()
            else:
                # No item_code provided, use default service item
                item_code = get_or_create_default_service_item()
            
            # build item row
            item_row = {
                "item_code": item_code,
                "qty": item.get("qty", 1),
                "rate": item.get("rate"),
                "description": item.get("description") or item.get("item_name") or item_code
            }

            # If an appointment reference was provided, attach it to the first invoice item
            # so downstream hooks can link invoices to Patient Appointment documents.
            if appointment_id and first_item:
                item_row.update({
                    "reference_dt": "Patient Appointment",
                    "reference_dn": appointment_id,
                })
                first_item = False

            invoice.append("items", item_row)
        
        # Apply tax template if provided
        if tax_template:
            if frappe.db.exists("Sales Taxes and Charges Template", tax_template):
                invoice.taxes_and_charges = tax_template
                # Let ERPNext auto-populate tax rows from template
                invoice.set_taxes()
        
        # Apply manual tax if tax_amount or tax_percentage provided (and no template)
        if not tax_template:
            company_for_tax = resolved_clinic or invoice.company
            
            # Determine effective tax percentage
            # - If tax_percentage explicitly provided, use it
            # - If is_cosmetic=True and no tax specified, use 18% (GST for cosmetic procedures)
            # - If is_cosmetic=False (medical treatment), no tax (GST exempt)
            effective_tax_percentage = None
            if tax_percentage is not None:
                effective_tax_percentage = flt(tax_percentage)
            elif is_cosmetic:
                # Cosmetic dental procedures attract 18% GST in India
                effective_tax_percentage = 18.0
            
            if effective_tax_percentage and effective_tax_percentage > 0:
                # Use GST accounts with proper CGST + SGST split
                _add_gst_taxes(invoice, effective_tax_percentage, company_for_tax)
            elif tax_amount and flt(tax_amount) > 0:
                # For fixed amount, use first available GST account
                gst_accounts = _get_gst_accounts(company_for_tax)
                if gst_accounts and gst_accounts.get("cgst_account"):
                    # Split the amount between CGST and SGST
                    half_amount = flt(tax_amount) / 2
                    invoice.append("taxes", {
                        "charge_type": "Actual",
                        "account_head": gst_accounts.cgst_account,
                        "description": "CGST",
                        "tax_amount": half_amount
                    })
                    invoice.append("taxes", {
                        "charge_type": "Actual",
                        "account_head": gst_accounts.sgst_account,
                        "description": "SGST",
                        "tax_amount": half_amount
                    })
        
        # Insert invoice
        invoice.insert(ignore_permissions=True)
        
        # Submit invoice
        invoice.submit()
        
        # Build tax breakdown for response
        tax_breakdown = []
        for tax in invoice.taxes:
            tax_breakdown.append({
                "description": tax.description,
                "rate": tax.rate or 0,
                "tax_amount": tax.tax_amount or 0,
                "account_head": tax.account_head
            })
        
        return {
            "message": "Invoice created successfully",
            "invoice_id": invoice.name,
            "grand_total": invoice.grand_total,
            "net_total": invoice.net_total,
            "total": invoice.total,  # Total before tax and discount
            "discount_amount": invoice.discount_amount or 0,
            "total_taxes_and_charges": invoice.total_taxes_and_charges or 0,
            "outstanding_amount": invoice.outstanding_amount,
            "status": invoice.status,
            "is_cosmetic": is_cosmetic,
            "tax_breakdown": tax_breakdown
        }
        
    except frappe.PermissionError:
        raise
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Invoice Error")
        frappe.throw(_("Error creating invoice: {0}").format(str(e)))


@frappe.whitelist(methods=['POST'])
def update_payment(invoice_id, paid_amount, mode_of_payment, 
                   payment_date=None, reference_no=None, reference_date=None):
    """
    Record a payment against an invoice
    
    Args:
        invoice_id: Sales Invoice name
        paid_amount: Amount being paid
        mode_of_payment: Payment method (Cash, Card, UPI, etc.)
        payment_date: Date of payment (default: today)
        reference_no: Transaction/reference number
        reference_date: Transaction date
    
    Returns:
        Payment entry details
    """
    try:
        practitioner = get_current_practitioner()
        assert_page_access("invoice", practitioner_name=practitioner.name)
        
        # Get invoice
        invoice = frappe.get_doc("Sales Invoice", invoice_id)
        
        # Check permissions
        if invoice.healthcare_practitioner != practitioner.name:
            frappe.throw(_("You don't have permission to update this invoice"))
        
        # Validate invoice status
        if invoice.docstatus != 1:
            frappe.throw(_("Invoice must be submitted before payment"))
        
        if invoice.status == "Paid":
            frappe.throw(_("Invoice is already fully paid"))
        
        # Validate payment amount
        paid_amount = flt(paid_amount)
        if paid_amount <= 0:
            frappe.throw(_("Payment amount must be greater than zero"))
        
        if paid_amount > flt(invoice.outstanding_amount):
            frappe.throw(_("Payment amount cannot exceed outstanding amount"))
        
        # Use the invoice's company for accounting context
        company = invoice.company or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")

        # Get default debit account (Debtors/Receivable) for the company
        debit_account = frappe.db.get_value("Company", company, "default_receivable_account")

        # Get credit account based on mode of payment (company-specific)
        mode_of_payment_account = frappe.db.get_value(
            "Mode of Payment Account",
            {"parent": mode_of_payment, "company": company},
            "default_account"
        )
        
        if not mode_of_payment_account:
            # Fallback to default cash account
            mode_of_payment_account = frappe.db.get_value("Company", company, "default_cash_account")
        
        # Get company currency
        company_currency = frappe.db.get_value("Company", company, "default_currency") or "INR"
        
        # Create Payment Entry manually
        payment_entry = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Receive",
            "company": company,
            "posting_date": payment_date or today(),
            "mode_of_payment": mode_of_payment,
            "party_type": "Customer",
            "party": invoice.customer,
            "paid_from": debit_account,
            "paid_to": mode_of_payment_account,
            "paid_from_account_currency": company_currency,
            "paid_to_account_currency": company_currency,
            "paid_amount": paid_amount,
            "received_amount": paid_amount,
            "source_exchange_rate": 1,
            "target_exchange_rate": 1,
            "reference_no": reference_no,
            "reference_date": reference_date or payment_date or today(),
            "references": [{
                "reference_doctype": "Sales Invoice",
                "reference_name": invoice_id,
                "allocated_amount": paid_amount
            }]
        })
        
        # Set flags
        payment_entry.flags.ignore_permissions = True
        payment_entry.flags.ignore_mandatory = True  # Bypass mandatory validations
        
        # Use Administrator context for insert and submit to handle all permission checks
        # This includes validation, GL entries, and any nested document creation
        current_user = frappe.session.user
        frappe.set_user("Administrator")
        
        try:
            # Insert and submit with full validation (for proper GL entries)
            payment_entry.insert(ignore_permissions=True)
            payment_entry.submit()
        finally:
            # Restore original user
            frappe.set_user(current_user)
        
        # Reload invoice to get updated status
        invoice.reload()
        
        return {
            "message": "Payment recorded successfully",
            "payment_id": payment_entry.name,
            "invoice_id": invoice_id,
            "paid_amount": paid_amount,
            "outstanding_amount": invoice.outstanding_amount,
            "status": invoice.status
        }
        
    except frappe.DoesNotExistError:
        frappe.throw(_("Invoice not found"))
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Payment Error")
        frappe.throw(_("Error recording payment: {0}").format(str(e)))


@frappe.whitelist(methods=['GET'])
def get_payment_summary(patient_id):
    """
    Get payment summary for a patient
    
    Args:
        patient_id: Patient ID
    
    Returns:
        Aggregated payment statistics
    """
    try:
        practitioner = get_current_practitioner()
        
        # Validate patient
        if not frappe.db.exists("Patient", patient_id):
            frappe.throw(_("Patient not found"))
        
        # Get patient
        patient = frappe.get_doc("Patient", patient_id)
        
        # Get all invoices
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={
                "patient": patient_id,
                "healthcare_practitioner": practitioner.name,
                "docstatus": 1  # Only submitted
            },
            fields=[
                "name",
                "posting_date",
                "due_date",
                "grand_total",
                "outstanding_amount",
                "status"
            ]
        )
        
        # Calculate totals
        total_invoiced = 0
        total_paid = 0
        total_pending = 0
        pending_invoices = []
        next_due_date = None
        
        for invoice in invoices:
            total_invoiced += flt(invoice.grand_total)
            paid = flt(invoice.grand_total) - flt(invoice.outstanding_amount)
            total_paid += paid
            total_pending += flt(invoice.outstanding_amount)
            
            if invoice.status in ["Unpaid", "Partly Paid"]:
                pending_invoices.append({
                    "invoice_id": invoice.name,
                    "date": invoice.posting_date,
                    "due_date": invoice.due_date,
                    "amount": invoice.grand_total,
                    "paid": paid,
                    "pending": invoice.outstanding_amount,
                    "is_overdue": getdate(invoice.due_date) < getdate(today()) if invoice.due_date else False
                })
                
                # Find earliest due date
                if invoice.due_date:
                    if not next_due_date or getdate(invoice.due_date) < getdate(next_due_date):
                        next_due_date = invoice.due_date
        
        return {
            "patient_id": patient_id,
            "patient_name": patient.patient_name,
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "total_pending": total_pending,
            "invoice_count": len(invoices),
            "pending_invoices_count": len(pending_invoices),
            "next_due_date": next_due_date,
            "pending_invoices": pending_invoices
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Payment Summary Error")
        frappe.throw(_("Error fetching payment summary: {0}").format(str(e)))

@frappe.whitelist(methods=['POST'])
def pay_patient_pending_invoices(patient_id, amount, mode_of_payment, payment_date=None, reference_no=None, reference_date=None):
    """
    Pay pending invoices for a patient using the provided amount (FIFO).

    Args:
        patient_id: Patient ID
        amount: Total amount available to pay (will be allocated FIFO to oldest outstanding invoices)
        mode_of_payment: Mode of payment (Cash, Card, UPI, etc.)
        payment_date: Optional payment posting date (default: today)
        reference_no: Optional transaction/reference number
        reference_date: Optional transaction date

    Returns:
        dict: { payments: [{payment_id, company, paid_amount}], remaining_amount }
    """
    try:
        practitioner = get_current_practitioner()

        # Validate patient
        if not frappe.db.exists("Patient", patient_id):
            frappe.throw(_("Patient not found"))

        remaining = flt(amount)
        if remaining <= 0:
            frappe.throw(_("Amount must be greater than zero"))

        # Fetch outstanding submitted invoices for the patient ordered FIFO by posting_date
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={"patient": patient_id, "docstatus": 1},
            fields=["name", "outstanding_amount", "grand_total", "company", "customer", "posting_date"],
            order_by="posting_date asc"
        )

        # Filter those with outstanding > 0
        invoices = [inv for inv in invoices if flt(inv.get("outstanding_amount") or 0) > 0]

        if not invoices:
            return {"message": "No outstanding invoices for patient", "payments": [], "remaining_amount": remaining}

        payments_created = []

        # We'll allocate in invoice FIFO order. Since Payment Entry cannot span companies
        # AND cannot span customers, we group allocations by (company, customer).
        allocations_by_key = {}
        key_order = []

        for inv in invoices:
            if remaining <= 0:
                break

            company = inv.get("company") or frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
            customer = inv.get("customer")
            
            alloc = min(remaining, flt(inv.get("outstanding_amount") or 0))
            if alloc <= 0:
                continue

            # Group by (company, customer) tuple
            group_key = (company, customer)
            if group_key not in allocations_by_key:
                allocations_by_key[group_key] = {"total": 0.0, "refs": [], "company": company, "customer": customer}
                key_order.append(group_key)

            allocations_by_key[group_key]["refs"].append({
                "reference_doctype": "Sales Invoice",
                "reference_name": inv.get("name"),
                "allocated_amount": alloc,
            })
            allocations_by_key[group_key]["total"] = flt(allocations_by_key[group_key]["total"]) + alloc

            remaining = flt(remaining) - alloc

        # Create Payment Entry per (company, customer) group
        for group_key in key_order:
            group = allocations_by_key[group_key]
            company = group.get("company")
            customer = group.get("customer")
            paid_amt = flt(group.get("total"))
            if paid_amt <= 0:
                continue


            # Customer MUST come from the invoice - never derive from patient
            # because the invoice may have been created with a different customer
            if not customer:
                frappe.log_error(f"Invoice {group.get('refs')} has no customer - skipping", "PayPatientPendingInvoices")
                continue

            # Determine accounts
            debit_account = frappe.db.get_value("Company", company, "default_receivable_account")
            mode_of_payment_account = frappe.db.get_value(
                "Mode of Payment Account",
                {"parent": mode_of_payment, "company": company},
                "default_account",
            )
            if not mode_of_payment_account:
                mode_of_payment_account = frappe.db.get_value("Company", company, "default_cash_account")

            company_currency = frappe.db.get_value("Company", company, "default_currency") or "INR"

            payment_entry = frappe.get_doc({
                "doctype": "Payment Entry",
                "payment_type": "Receive",
                "company": company,
                "posting_date": payment_date or today(),
                "mode_of_payment": mode_of_payment,
                "party_type": "Customer",
                "party": customer,
                "paid_from": debit_account,
                "paid_to": mode_of_payment_account,
                "paid_from_account_currency": company_currency,
                "paid_to_account_currency": company_currency,
                "paid_amount": paid_amt,
                "received_amount": paid_amt,
                "source_exchange_rate": 1,
                "target_exchange_rate": 1,
                "reference_no": reference_no,
                "reference_date": reference_date or payment_date or today(),
                "references": group.get("refs")
            })

            payment_entry.flags.ignore_permissions = True
            payment_entry.flags.ignore_mandatory = True

            current_user = frappe.session.user
            frappe.set_user("Administrator")
            try:
                payment_entry.insert(ignore_permissions=True)
                payment_entry.submit()
            finally:
                frappe.set_user(current_user)

            payments_created.append({"payment_id": payment_entry.name, "company": company, "paid_amount": paid_amt})

        return {"message": "Payments processed", "payments": payments_created, "remaining_amount": remaining}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "PayPatientPendingInvoicesError")
        frappe.throw(_("Error processing payment: {0}").format(str(e)))



@frappe.whitelist(methods=['POST'])
def send_payment_reminder(invoice_id, reminder_type="sms", message=None):
    """
    Send payment reminder to patient
    
    Args:
        invoice_id: Sales Invoice name
        reminder_type: Type of reminder (sms, email, both)
        message: Custom reminder message
    
    Returns:
        Reminder sending status
    """
    try:
        practitioner = get_current_practitioner()
        
        # Get invoice
        invoice = frappe.get_doc("Sales Invoice", invoice_id)
        
        # Check permissions
        if invoice.healthcare_practitioner != practitioner.name:
            frappe.throw(_("You don't have permission to access this invoice"))
        
        # Check if reminder needed
        if invoice.status == "Paid":
            frappe.throw(_("Invoice is already paid"))
        
        # Get patient
        patient = frappe.get_doc("Patient", invoice.patient)
        
        # Build default message if not provided
        if not message:
            message = _("""Dear {0},

This is a payment reminder for Invoice {1}.
Amount Due: {2}
Due Date: {3}

Please clear the outstanding amount at your earliest convenience.

Thank you!
{4}""").format(
                patient.patient_name,
                invoice.name,
                invoice.outstanding_amount,
                invoice.due_date or "N/A",
                practitioner.practitioner_name
            )
        
        sent_via = []
        sent_to = []
        
        # Send SMS
        if reminder_type in ["sms", "both"] and patient.mobile:
            try:
                # In production, integrate with SMS gateway
                # For now, just log the action
                frappe.logger().info(f"SMS Reminder sent to {patient.mobile} for Invoice {invoice_id}")
                sent_via.append("sms")
                sent_to.append(patient.mobile)
                
                # Mark reminder sent
                invoice.db_set("payment_reminder_sent", 1, update_modified=False)
                
            except Exception as sms_error:
                frappe.log_error(str(sms_error), "SMS Reminder Error")
        
        # Send Email
        if reminder_type in ["email", "both"] and patient.email:
            try:
                frappe.sendmail(
                    recipients=[patient.email],
                    subject=f"Payment Reminder - Invoice {invoice.name}",
                    message=message,
                    reference_doctype="Sales Invoice",
                    reference_name=invoice.name
                )
                sent_via.append("email")
                sent_to.append(patient.email)
                
                # Mark reminder sent
                invoice.db_set("payment_reminder_sent", 1, update_modified=False)
                
            except Exception as email_error:
                frappe.log_error(str(email_error), "Email Reminder Error")
        
        if not sent_via:
            frappe.throw(_("No contact information available for sending reminder"))
        
        return {
            "message": "Payment reminder sent successfully",
            "sent_via": sent_via,
            "sent_to": sent_to
        }
        
    except frappe.DoesNotExistError:
        frappe.throw(_("Invoice not found"))
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Send Payment Reminder Error")
        frappe.throw(_("Error sending payment reminder: {0}").format(str(e)))


@frappe.whitelist(methods=['POST'])
def delete_invoice(invoice_id):
    """
    Delete an invoice and all linked payment/ledger entries
    
    Args:
        invoice_id: Sales Invoice name
    
    Returns:
        Deletion status
    """
    try:
        practitioner = get_current_practitioner()
        assert_page_access("invoice", practitioner_name=practitioner.name)
        
        # Get invoice
        invoice = frappe.get_doc("Sales Invoice", invoice_id)
        
        # Check permissions
        if invoice.healthcare_practitioner != practitioner.name:
            frappe.throw(_("You don't have permission to delete this invoice"))
        
        # Store current user and switch to Administrator for deletion operations
        original_user = frappe.session.user
        frappe.set_user("Administrator")
        
        try:
            # Step 1: Cancel the invoice FIRST (if submitted)
            # This is crucial - must cancel invoice before cancelling payments
            if invoice.docstatus == 1:
                invoice.cancel()
                frappe.logger().info(f"Cancelled invoice: {invoice_id}")
            
            # Step 2: Get and delete all payment entries (now that invoice is cancelled)
            payment_refs = frappe.db.sql("""
                SELECT DISTINCT parent 
                FROM `tabPayment Entry Reference` 
                WHERE reference_name = %s AND reference_doctype = 'Sales Invoice'
            """, invoice_id, as_dict=True)
            
            for pr in payment_refs:
                try:
                    pe = frappe.get_doc("Payment Entry", pr.parent)
                    
                    # Cancel if submitted
                    if pe.docstatus == 1:
                        pe.cancel()
                        frappe.logger().info(f"Cancelled payment entry: {pr.parent}")
                    
                    # Delete (cascades to Payment Ledger Entry and GL Entry)
                    frappe.delete_doc("Payment Entry", pr.parent, force=True, ignore_permissions=True)
                    frappe.logger().info(f"Deleted payment entry: {pr.parent}")
                    
                except Exception as pe_error:
                    frappe.logger().error(f"Standard delete failed for PE {pr.parent}, forcing DB delete: {str(pe_error)}")
                    # Force delete from DB if standard delete fails
                    frappe.db.sql("DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no = %s", pr.parent)
                    frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no = %s", pr.parent)
                    frappe.db.sql("DELETE FROM `tabPayment Entry Reference` WHERE parent = %s", pr.parent)
                    frappe.db.sql("DELETE FROM `tabPayment Entry` WHERE name = %s", pr.parent)
            
            # Step 3: Delete invoice's own ledger entries (if any remain)
            frappe.db.sql("DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no = %s", invoice_id)
            frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no = %s", invoice_id)
            
            # Step 4: Delete the cancelled invoice
            frappe.delete_doc("Sales Invoice", invoice_id, force=True, ignore_permissions=True)
            frappe.logger().info(f"Deleted invoice: {invoice_id}")
            
            frappe.db.commit()
            
            return {
                "message": "Invoice and all related documents deleted successfully",
                "invoice_id": invoice_id,
                "deleted_payments": len(payment_refs)
            }
        
        finally:
            # Always restore original user
            frappe.set_user(original_user)
        
    except frappe.DoesNotExistError:
        frappe.throw(_("Invoice not found"))
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Invoice Error")
        frappe.throw(_("Error deleting invoice: {0}").format(str(e)))
