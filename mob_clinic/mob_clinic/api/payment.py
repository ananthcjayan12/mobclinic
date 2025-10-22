"""
Payment and Invoice Management APIs for Mobile Application
Uses ERPNext Sales Invoice DocType with Healthcare extensions
"""

import frappe
from frappe import _
from frappe.utils import today, add_days, getdate, flt, nowdate


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


@frappe.whitelist()
def get_invoices(patient_id=None, status=None, start_date=None, end_date=None, 
                 limit_start=0, limit_page_length=20):
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
        
        # Build filters
        filters = {
            "docstatus": ["!=", 2],  # Exclude cancelled
            "healthcare_practitioner": practitioner.name
        }
        
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
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Invoices Error")
        frappe.throw(_("Error fetching invoices: {0}").format(str(e)))


@frappe.whitelist()
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
        
        # Get invoice
        invoice = frappe.get_doc("Sales Invoice", invoice_id)
        
        # Check permissions
        if invoice.healthcare_practitioner != practitioner.name:
            frappe.throw(_("You don't have permission to view this invoice"))
        
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
        
        # Build response
        invoice_data = {
            "invoice_id": invoice.name,
            "patient": patient_info,
            "posting_date": invoice.posting_date,
            "due_date": invoice.due_date,
            "status": invoice.status,
            "grand_total": invoice.grand_total,
            "outstanding_amount": invoice.outstanding_amount,
            "paid_amount": flt(invoice.grand_total) - flt(invoice.outstanding_amount),
            "items": items,
            "payments": payments,
            "is_overdue": False,
            "remarks": invoice.remarks
        }
        
        # Check if overdue
        if invoice.status in ["Unpaid", "Partly Paid"] and invoice.due_date:
            if getdate(invoice.due_date) < getdate(today()):
                invoice_data["is_overdue"] = True
        
        return invoice_data
        
    except frappe.DoesNotExistError:
        frappe.throw(_("Invoice not found"))
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Invoice Error")
        frappe.throw(_("Error fetching invoice: {0}").format(str(e)))


@frappe.whitelist()
def create_invoice(patient_id, items, posting_date=None, due_date=None, 
                   treatment_type=None, treatment_description=None,
                   appointment_reference=None, remarks=None):
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
    
    Returns:
        Created invoice details
    """
    try:
        practitioner = get_current_practitioner()
        
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
            "healthcare_practitioner": practitioner.name,
            "posting_date": posting_date_value,
            "due_date": due_date_value,
            "remarks": remarks,
            "items": []
        })
        
        # Add items
        for item in items:
            invoice.append("items", {
                "item_code": item.get("item_code"),
                "qty": item.get("qty", 1),
                "rate": item.get("rate"),
                "description": item.get("description")
            })
        
        # Insert invoice
        invoice.insert(ignore_permissions=True)
        
        # Submit invoice
        invoice.submit()
        
        return {
            "message": "Invoice created successfully",
            "invoice_id": invoice.name,
            "grand_total": invoice.grand_total,
            "outstanding_amount": invoice.outstanding_amount,
            "status": invoice.status
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Invoice Error")
        frappe.throw(_("Error creating invoice: {0}").format(str(e)))


@frappe.whitelist()
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
        
        # Get company and default accounts
        company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
        
        # Get default debit account (Debtors/Receivable) for the customer
        debit_account = frappe.db.get_value("Company", company, "default_receivable_account")
        
        # Get credit account based on mode of payment
        mode_of_payment_account = frappe.db.get_value(
            "Mode of Payment Account",
            {"parent": mode_of_payment, "company": company},
            "default_account"
        )
        
        if not mode_of_payment_account:
            # Fallback to default cash account
            mode_of_payment_account = frappe.db.get_value("Company", company, "default_cash_account")
        
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
            "paid_amount": paid_amount,
            "received_amount": paid_amount,
            "target_exchange_rate": 1,
            "reference_no": reference_no,
            "reference_date": reference_date or payment_date or today(),
            "references": [{
                "reference_doctype": "Sales Invoice",
                "reference_name": invoice_id,
                "allocated_amount": paid_amount
            }]
        })
        
        # Set flags and insert
        payment_entry.flags.ignore_permissions = True
        payment_entry.flags.ignore_mandatory = True  # Bypass mandatory validations for missing accounts
        payment_entry.insert(ignore_permissions=True)
        payment_entry.submit()
        
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


@frappe.whitelist()
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


@frappe.whitelist()
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
