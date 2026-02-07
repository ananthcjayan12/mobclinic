"""
WhatsApp Business API Integration
Send messages via Meta WhatsApp Cloud API
"""

import frappe
from frappe import _
import requests
import json
from frappe.utils import now_datetime, get_url


# Meta WhatsApp Cloud API Base URL
WHATSAPP_API_BASE = "https://graph.facebook.com/v18.0"


def _get_whatsapp_credentials(clinic):
    """
    Fetch and validate WhatsApp credentials for a clinic
    
    Args:
        clinic: Company/Clinic name
    
    Returns:
        dict with phone_number_id, business_account_id, access_token
    
    Raises:
        frappe.ValidationError if credentials are missing or invalid
    """
    if not frappe.db.exists("Clinic Settings", clinic):
        frappe.throw(_("WhatsApp not configured for this clinic"))
    
    settings = frappe.get_doc("Clinic Settings", clinic)
    
    if not settings.whatsapp_enabled:
        frappe.throw(_("WhatsApp integration is not enabled for this clinic"))
    
    if not settings.whatsapp_phone_number_id:
        frappe.throw(_("WhatsApp Phone Number ID is not configured"))
    
    if not settings.whatsapp_access_token:
        frappe.throw(_("WhatsApp Access Token is not configured"))
    
    return {
        "phone_number_id": settings.whatsapp_phone_number_id,
        "business_account_id": settings.whatsapp_business_account_id,
        "access_token": settings.get_password("whatsapp_access_token"),
        "templates": {
            "appointment": settings.whatsapp_appointment_template,
            "review": settings.whatsapp_review_template,
            "prescription": settings.whatsapp_prescription_template,
            "invoice": settings.whatsapp_invoice_template
        }
    }


def _format_phone_number(phone):
    """
    Normalize phone number to E.164 format (without + prefix as WhatsApp expects)
    
    Args:
        phone: Phone number string
    
    Returns:
        Formatted phone number (e.g., "919876543210" for Indian number)
    """
    if not phone:
        return None
    
    # Remove all non-numeric characters
    phone = ''.join(filter(str.isdigit, str(phone)))
    
    # If starts with 0, remove it (local format)
    if phone.startswith('0'):
        phone = phone[1:]
    
    # If 10 digits (Indian local), add country code
    if len(phone) == 10:
        phone = '91' + phone  # Default to India
    
    return phone


def _call_whatsapp_api(endpoint, payload, access_token):
    """
    Make HTTP request to WhatsApp Cloud API
    
    Args:
        endpoint: API endpoint (full URL)
        payload: Request body as dict
        access_token: Bearer token
    
    Returns:
        dict with response data
    
    Raises:
        Exception on API error
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
        response_data = response.json()
        
        if response.status_code != 200:
            error_message = response_data.get("error", {}).get("message", "Unknown error")
            raise Exception(f"WhatsApp API Error: {error_message}")
        
        return response_data
    
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error: {str(e)}")


def _log_message(clinic, recipient_phone, template_name, message_type, 
                 reference_doctype=None, reference_name=None, 
                 message_id=None, status="Sent", error_message=None):
    """
    Create a WhatsApp Message Log entry
    """
    try:
        log = frappe.new_doc("WhatsApp Message Log")
        log.clinic = clinic
        log.recipient_phone = recipient_phone
        log.template_name = template_name
        log.message_type = message_type
        log.reference_doctype = reference_doctype
        log.reference_name = reference_name
        log.message_id = message_id
        log.status = status
        log.sent_at = now_datetime()
        log.error_message = error_message
        log.flags.ignore_permissions = True
        log.insert(ignore_permissions=True)
        frappe.db.commit()
        return log.name
    except Exception as e:
        frappe.log_error(f"Failed to log WhatsApp message: {str(e)}")
        return None


@frappe.whitelist()
def send_template_message(clinic, recipient_phone, template_name, template_params=None, 
                          language="en", message_type="Custom", 
                          reference_doctype=None, reference_name=None):
    """
    Send a WhatsApp template message
    
    Args:
        clinic: Company/Clinic name
        recipient_phone: Recipient's phone number
        template_name: Approved template name
        template_params: List of parameter values (optional)
        language: Language code (default: "en")
        message_type: Type for logging (Appointment Reminder, Review Request, etc.)
        reference_doctype: Linked document type
        reference_name: Linked document name
    
    Returns:
        dict with success status and message details
    """
    try:
        # Get credentials
        credentials = _get_whatsapp_credentials(clinic)
        
        # Format phone number
        formatted_phone = _format_phone_number(recipient_phone)
        if not formatted_phone:
            return {"success": False, "error": "Invalid phone number"}
        
        # Build API endpoint
        endpoint = f"{WHATSAPP_API_BASE}/{credentials['phone_number_id']}/messages"
        
        # Build message payload
        payload = {
            "messaging_product": "whatsapp",
            "to": formatted_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language
                }
            }
        }
        
        # Add parameters if provided
        if template_params:
            if isinstance(template_params, str):
                template_params = json.loads(template_params)
            
            components = [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(param)} for param in template_params
                ]
            }]
            payload["template"]["components"] = components
        
        # Send message
        response = _call_whatsapp_api(endpoint, payload, credentials["access_token"])
        
        # Extract message ID
        message_id = None
        if response.get("messages"):
            message_id = response["messages"][0].get("id")
        
        # Log the message
        log_id = _log_message(
            clinic=clinic,
            recipient_phone=formatted_phone,
            template_name=template_name,
            message_type=message_type,
            reference_doctype=reference_doctype,
            reference_name=reference_name,
            message_id=message_id,
            status="Sent"
        )
        
        return {
            "success": True,
            "message_id": message_id,
            "log_id": log_id,
            "recipient": formatted_phone
        }
    
    except Exception as e:
        # Log failure
        _log_message(
            clinic=clinic,
            recipient_phone=recipient_phone,
            template_name=template_name,
            message_type=message_type,
            reference_doctype=reference_doctype,
            reference_name=reference_name,
            status="Failed",
            error_message=str(e)
        )
        
        frappe.log_error(frappe.get_traceback(), "WhatsApp Send Error")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def send_appointment_reminder(appointment_id):
    """
    Send appointment reminder via WhatsApp
    
    Args:
        appointment_id: Patient Appointment name/ID
    """
    try:
        appointment = frappe.get_doc("Patient Appointment", appointment_id)
        
        if not appointment.patient:
            return {"success": False, "error": "No patient linked to appointment"}
        
        patient = frappe.get_doc("Patient", appointment.patient)
        phone = patient.mobile or patient.phone
        
        if not phone:
            return {"success": False, "error": "Patient has no phone number"}
        
        # Get clinic
        clinic = appointment.company
        if not clinic:
            return {"success": False, "error": "No clinic linked to appointment"}
        
        credentials = _get_whatsapp_credentials(clinic)
        template_name = credentials["templates"].get("appointment")
        
        if not template_name:
            return {"success": False, "error": "Appointment reminder template not configured"}
        
        # Get clinic name
        clinic_name = frappe.db.get_value("Company", clinic, "company_name")
        
        # Format date and time
        from frappe.utils import formatdate, format_time
        appt_date = formatdate(appointment.appointment_date, "dd MMM yyyy")
        appt_time = format_time(appointment.appointment_time) if appointment.appointment_time else ""
        
        # Prepare template parameters
        params = [
            patient.patient_name,
            clinic_name,
            appt_date,
            appt_time
        ]
        
        return send_template_message(
            clinic=clinic,
            recipient_phone=phone,
            template_name=template_name,
            template_params=params,
            message_type="Appointment Reminder",
            reference_doctype="Patient Appointment",
            reference_name=appointment_id
        )
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "WhatsApp Appointment Reminder Error")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def send_review_request(appointment_id):
    """
    Send review request after appointment
    
    Args:
        appointment_id: Patient Appointment name/ID
    """
    try:
        appointment = frappe.get_doc("Patient Appointment", appointment_id)
        
        if not appointment.patient:
            return {"success": False, "error": "No patient linked to appointment"}
        
        patient = frappe.get_doc("Patient", appointment.patient)
        phone = patient.mobile or patient.phone
        
        if not phone:
            return {"success": False, "error": "Patient has no phone number"}
        
        clinic = appointment.company
        if not clinic:
            return {"success": False, "error": "No clinic linked to appointment"}
        
        credentials = _get_whatsapp_credentials(clinic)
        template_name = credentials["templates"].get("review")
        
        if not template_name:
            return {"success": False, "error": "Review request template not configured"}
        
        clinic_name = frappe.db.get_value("Company", clinic, "company_name")
        
        # Get Google Maps URL for review
        google_maps_url = ""
        if frappe.db.exists("Clinic Settings", clinic):
            google_maps_url = frappe.db.get_value("Clinic Settings", clinic, "google_maps_url") or ""
        
        params = [
            patient.patient_name,
            clinic_name,
            google_maps_url
        ]
        
        return send_template_message(
            clinic=clinic,
            recipient_phone=phone,
            template_name=template_name,
            template_params=params,
            message_type="Review Request",
            reference_doctype="Patient Appointment",
            reference_name=appointment_id
        )
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "WhatsApp Review Request Error")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def send_prescription(prescription_id, patient_phone=None):
    """
    Share prescription via WhatsApp
    
    Args:
        prescription_id: Prescription record ID
        patient_phone: Override phone number (optional)
    """
    try:
        # Try to get from Patient Prescription first
        if frappe.db.exists("Patient Prescription", prescription_id):
            prescription = frappe.get_doc("Patient Prescription", prescription_id)
            patient_id = prescription.patient
            clinic = prescription.company or prescription.clinic
            prescription_date = prescription.prescription_date or prescription.creation
            practitioner_name = prescription.practitioner_name or "Doctor"
        else:
            return {"success": False, "error": "Prescription not found"}
        
        if not patient_id:
            return {"success": False, "error": "No patient linked to prescription"}
        
        patient = frappe.get_doc("Patient", patient_id)
        phone = patient_phone or patient.mobile or patient.phone
        
        if not phone:
            return {"success": False, "error": "No phone number available"}
        
        if not clinic:
            return {"success": False, "error": "No clinic linked to prescription"}
        
        credentials = _get_whatsapp_credentials(clinic)
        template_name = credentials["templates"].get("prescription")
        
        if not template_name:
            return {"success": False, "error": "Prescription template not configured"}
        
        clinic_name = frappe.db.get_value("Company", clinic, "company_name")
        clinic_phone = frappe.db.get_value("Company", clinic, "phone_no") or ""
        
        # Build prescription link
        from frappe.utils import formatdate
        prescription_link = get_url(f"/api/method/mob_clinic.mob_clinic.api.patient_prescription.get_patient_prescription?prescription_id={prescription_id}")
        
        params = [
            patient.patient_name,
            clinic_name,
            formatdate(prescription_date, "dd MMM yyyy"),
            practitioner_name,
            prescription_link,
            clinic_phone
        ]
        
        return send_template_message(
            clinic=clinic,
            recipient_phone=phone,
            template_name=template_name,
            template_params=params,
            message_type="Prescription",
            reference_doctype="Patient Prescription",
            reference_name=prescription_id
        )
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "WhatsApp Prescription Error")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def send_invoice(invoice_id, patient_phone=None):
    """
    Share invoice/payment receipt via WhatsApp
    
    Args:
        invoice_id: Sales Invoice name
        patient_phone: Override phone number (optional)
    """
    try:
        invoice = frappe.get_doc("Sales Invoice", invoice_id)
        
        # Get patient from customer
        patient_id = frappe.db.get_value("Patient", {"customer": invoice.customer}, "name")
        
        if not patient_id:
            return {"success": False, "error": "No patient linked to invoice"}
        
        patient = frappe.get_doc("Patient", patient_id)
        phone = patient_phone or patient.mobile or patient.phone
        
        if not phone:
            return {"success": False, "error": "No phone number available"}
        
        clinic = invoice.company
        if not clinic:
            return {"success": False, "error": "No clinic linked to invoice"}
        
        credentials = _get_whatsapp_credentials(clinic)
        template_name = credentials["templates"].get("invoice")
        
        if not template_name:
            return {"success": False, "error": "Invoice template not configured"}
        
        clinic_name = frappe.db.get_value("Company", clinic, "company_name")
        clinic_phone = frappe.db.get_value("Company", clinic, "phone_no") or ""
        
        from frappe.utils import formatdate, fmt_money
        invoice_link = get_url(f"/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Invoice&name={invoice_id}")
        
        params = [
            patient.patient_name,
            fmt_money(invoice.grand_total, currency=invoice.currency),
            clinic_name,
            invoice.name,
            formatdate(invoice.posting_date, "dd MMM yyyy"),
            invoice_link,
            clinic_phone
        ]
        
        return send_template_message(
            clinic=clinic,
            recipient_phone=phone,
            template_name=template_name,
            template_params=params,
            message_type="Invoice",
            reference_doctype="Sales Invoice",
            reference_name=invoice_id
        )
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "WhatsApp Invoice Error")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def test_connection(clinic):
    """
    Test WhatsApp API connection
    
    Args:
        clinic: Company/Clinic name
    
    Returns:
        dict with success status
    """
    try:
        credentials = _get_whatsapp_credentials(clinic)
        
        # Test by getting business profile
        endpoint = f"{WHATSAPP_API_BASE}/{credentials['phone_number_id']}"
        headers = {
            "Authorization": f"Bearer {credentials['access_token']}"
        }
        
        response = requests.get(endpoint, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "message": "Connection successful",
                "phone_number_id": data.get("id"),
                "display_phone": data.get("display_phone_number")
            }
        else:
            error = response.json().get("error", {}).get("message", "Unknown error")
            return {"success": False, "error": error}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def get_message_logs(clinic, limit=50, offset=0, message_type=None, status=None):
    """
    Get WhatsApp message logs for a clinic
    
    Args:
        clinic: Company/Clinic name
        limit: Number of records
        offset: Pagination offset
        message_type: Filter by message type
        status: Filter by status
    
    Returns:
        List of message logs
    """
    try:
        filters = {"clinic": clinic}
        
        if message_type:
            filters["message_type"] = message_type
        if status:
            filters["status"] = status
        
        logs = frappe.get_all(
            "WhatsApp Message Log",
            filters=filters,
            fields=["name", "recipient_phone", "template_name", "message_type", 
                    "status", "sent_at", "reference_doctype", "reference_name", "error_message"],
            order_by="sent_at desc",
            limit_page_length=int(limit),
            limit_start=int(offset)
        )
        
        total = frappe.db.count("WhatsApp Message Log", filters)
        
        return {
            "success": True,
            "logs": logs,
            "total": total
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}
