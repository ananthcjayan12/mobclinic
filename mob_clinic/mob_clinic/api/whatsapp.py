"""
WhatsApp Business API Integration
Send messages via Meta WhatsApp Cloud API
"""

import frappe
from frappe import _
import requests
import json
import hmac
import hashlib
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from frappe.utils import now_datetime, get_url
from frappe.utils.password import (
    get_decrypted_password,
    remove_encrypted_password,
    set_encrypted_password,
)
from frappe.installer import update_site_config

from mob_clinic.mob_clinic.api import clinic as clinic_helper
from mob_clinic.mob_clinic.api import role_access


# Meta WhatsApp Cloud API Base URL
WHATSAPP_API_BASE = "https://graph.facebook.com/v18.0"

ALLOWED_WHATSAPP_SETTINGS_FIELDS = {
    "whatsapp_enabled",
    "whatsapp_phone_number_id",
    "whatsapp_business_account_id",
    "whatsapp_access_token",
    "whatsapp_appointment_template",
    "whatsapp_review_template",
    "whatsapp_prescription_template",
    "whatsapp_invoice_template",
}

WHATSAPP_CARE_WINDOW_HOURS = 24


def _parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        try:
            return frappe.utils.get_datetime(value)
        except Exception:
            return None




def _epoch_to_datetime(epoch_value):
    if epoch_value is None:
        return now_datetime()
    try:
        value_int = int(str(epoch_value).strip())
        if value_int > 10**12:
            value_int = value_int // 1000
        return datetime.fromtimestamp(value_int)
    except Exception:
        return now_datetime()




def _safe_json_dumps(value):
    try:
        return json.dumps(value, default=str)
    except Exception:
        return "{}"


def _normalize_template_language(language):
    code = (language or "").strip()
    if not code:
        return "en_US"
    if code.lower() == "en":
        return "en_US"
    return code


def _resolve_practitioner_and_clinic(clinic=None, require_admin=False):
    requester_practitioner = role_access.get_current_practitioner_doc()
    clinic_name = clinic_helper.resolve_active_clinic(
        practitioner_name=requester_practitioner.name if requester_practitioner else None,
        clinic_param=clinic,
    )

    if not clinic_name:
        frappe.local.response["http_status_code"] = 400
        return None, None, {"exc_type": "ValidationError", "message": "Clinic is required"}

    if not requester_practitioner:
        frappe.local.response["http_status_code"] = 403
        return None, None, {"exc_type": "PermissionError", "message": "Practitioner profile is required"}

    if not clinic_helper.validate_practitioner_access(requester_practitioner.name, clinic_name):
        frappe.local.response["http_status_code"] = 403


        return None, None, {"exc_type": "PermissionError", "message": "Clinic access denied"}

    if require_admin:
        permissions = role_access.get_practitioner_permissions(requester_practitioner)
        if not permissions.get("is_clinic_admin"):
            frappe.local.response["http_status_code"] = 403
            return None, None, {"exc_type": "PermissionError", "message": "Clinic admin access required"}



    return requester_practitioner, clinic_name, None


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) == 1
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False




def _mask_token(token):
    if not token:
        return ""

    token = str(token)
    if len(token) <= 4:
        return "*" * len(token)

    return ("*" * (len(token) - 4)) + token[-4:]


def _is_invalid_encryption_key_error(error):
    return "encryption key is in invalid format" in str(error or "").strip().lower()


def _repair_site_encryption_key_if_needed(error):
    if not _is_invalid_encryption_key_error(error):
        return False

    new_key = Fernet.generate_key().decode()
    update_site_config("encryption_key", new_key)

    if hasattr(frappe.local, "conf") and frappe.local.conf is not None:
        frappe.local.conf.encryption_key = new_key

    if hasattr(frappe, "conf") and frappe.conf is not None:
        frappe.conf.encryption_key = new_key

    frappe.logger("mob_clinic.whatsapp").warning("Invalid encryption key detected; regenerated a valid site encryption key")
    return True


def _read_whatsapp_access_token(settings_name):
    try:
        return get_decrypted_password(
            "Clinic Settings",
            settings_name,
            fieldname="whatsapp_access_token",
            raise_exception=False,
        ) or ""
    except Exception as e:
        if _repair_site_encryption_key_if_needed(e):
            return get_decrypted_password(
                "Clinic Settings",
                settings_name,
                fieldname="whatsapp_access_token",
                raise_exception=False,
            ) or ""
        raise


def _write_whatsapp_access_token(settings_name, value):
    if value:
        try:
            set_encrypted_password(
                "Clinic Settings",
                settings_name,
                value,
                fieldname="whatsapp_access_token",
            )
            return
        except Exception as e:
            if _repair_site_encryption_key_if_needed(e):
                set_encrypted_password(
                    "Clinic Settings",
                    settings_name,
                    value,
                    fieldname="whatsapp_access_token",
                )
                return
            raise

    remove_encrypted_password("Clinic Settings", settings_name, fieldname="whatsapp_access_token")


def _resolve_admin_scoped_clinic(clinic=None):


    return _resolve_practitioner_and_clinic(clinic=clinic, require_admin=True)


def _get_webhook_verify_token(clinic=None):
    clinic_value = clinic
    if clinic_value and frappe.db.exists("Clinic Settings", clinic_value):
        token = frappe.db.get_value("Clinic Settings", clinic_value, "whatsapp_business_account_id")
        if token:
            return str(token)
    return frappe.conf.get("whatsapp_webhook_verify_token") or frappe.conf.get("webhook_verify_token") or ""


def _get_webhook_app_secret():
    return frappe.conf.get("whatsapp_app_secret") or ""


def _verify_webhook_signature(raw_body, signature_header):


    app_secret = _get_webhook_app_secret()
    if not app_secret:
        return True
    if not signature_header:
        return False

    try:
        expected = "sha256=" + hmac.new(
            app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)
    except Exception:
        return False


def _get_or_create_conversation(clinic, wa_id, customer_phone=None, customer_name=None):
    filters = {"clinic": clinic, "wa_id": wa_id}
    existing_name = frappe.db.get_value("WhatsApp Conversation", filters, "name")
    if existing_name:
        return frappe.get_doc("WhatsApp Conversation", existing_name)

    conversation = frappe.get_doc({
        "doctype": "WhatsApp Conversation",


        "clinic": clinic,
        "wa_id": wa_id,
        "customer_phone": customer_phone or "",
        "customer_name": customer_name or "",
        "unread_count": 0,
    })
    conversation.flags.ignore_permissions = True
    conversation.insert(ignore_permissions=True)
    return conversation


def _update_conversation_summary(
    conversation,
    content,
    message_direction,
    message_status,
    message_time,
    customer_phone=None,


    customer_name=None,
):
    conversation.last_message_preview = (content or "")[:500]
    conversation.last_message_direction = message_direction or ""
    conversation.last_message_status = message_status or ""
    conversation.last_message_at = message_time
    if customer_phone:
        conversation.customer_phone = customer_phone
    if customer_name:
        conversation.customer_name = customer_name

    if message_direction == "Inbound":
        conversation.last_inbound_at = message_time
        conversation.unread_count = int(conversation.unread_count or 0) + 1
        conversation.session_expires_at = message_time + timedelta(hours=WHATSAPP_CARE_WINDOW_HOURS)
    elif message_direction == "Outbound":
        conversation.last_outbound_at = message_time

    session_expiry = _parse_datetime(conversation.session_expires_at)
    conversation.is_session_active = 1 if session_expiry and session_expiry >= now_datetime() else 0

    conversation.flags.ignore_permissions = True
    conversation.save(ignore_permissions=True)


def _upsert_conversation_message(
    conversation,
    clinic,
    wa_message_id,
    direction,
    message_type,
    content,
    status,
    message_time,
    sender_phone=None,
    recipient_phone=None,
    raw_payload=None,
    template_name=None,
    error_message=None,
):
    if wa_message_id:
        existing_name = frappe.db.get_value("WhatsApp Conversation Message", {"wa_message_id": wa_message_id}, "name")
        if existing_name:
            existing_doc = frappe.get_doc("WhatsApp Conversation Message", existing_name)
            existing_doc.status = status or existing_doc.status
            if error_message:
                existing_doc.error_message = error_message


            existing_doc.flags.ignore_permissions = True
            existing_doc.save(ignore_permissions=True)
            return existing_doc, False

    message_doc = frappe.get_doc({
        "doctype": "WhatsApp Conversation Message",
        "conversation": conversation.name,
        "clinic": clinic,
        "wa_message_id": wa_message_id or "",
        "direction": direction or "",
        "message_type": message_type or "unknown",
        "content": content or "",
        "status": status or "Pending",
        "message_timestamp": message_time,
        "sender_phone": sender_phone or "",
        "recipient_phone": recipient_phone or "",
        "raw_payload": _safe_json_dumps(raw_payload) if raw_payload else "",
        "template_name": template_name or "",
        "error_message": error_message or "",
    })
    message_doc.flags.ignore_permissions = True
    message_doc.insert(ignore_permissions=True)
    return message_doc, True


def _extract_message_content(message_obj):
    if not isinstance(message_obj, dict):
        return ""
    message_type = message_obj.get("type")
    if message_type == "text":
        return (message_obj.get("text") or {}).get("body") or ""
    if message_type == "button":
        return (message_obj.get("button") or {}).get("text") or ""
    if message_type == "interactive":
        interactive = message_obj.get("interactive") or {}
        return (interactive.get("button_reply") or {}).get("title") or (interactive.get("list_reply") or {}).get("title") or ""
    if message_type == "image":
        return "[image]"
    if message_type == "document":
        return "[document]"
    if message_type == "audio":
        return "[audio]"
    if message_type == "video":
        return "[video]"
    return ""


def _process_inbound_message(clinic, contact_by_waid, message_obj, raw_payload):
    wa_id = message_obj.get("from")
    if not wa_id:
        return False

    message_time = _epoch_to_datetime(message_obj.get("timestamp"))
    wa_message_id = message_obj.get("id")
    contact_info = contact_by_waid.get(wa_id, {})
    customer_name = contact_info.get("profile_name") or ""

    conversation = _get_or_create_conversation(
        clinic=clinic,
        wa_id=wa_id,
        customer_phone=wa_id,
        customer_name=customer_name,
    )

    message_content = _extract_message_content(message_obj)
    message_type = message_obj.get("type") or "unknown"

    _, is_new = _upsert_conversation_message(
        conversation=conversation,
        clinic=clinic,
        wa_message_id=wa_message_id,
        direction="Inbound",
        message_type=message_type,
        content=message_content,
        status="Read",
        message_time=message_time,
        sender_phone=wa_id,
        recipient_phone="",
        raw_payload=raw_payload,
    )

    if is_new:
        _update_conversation_summary(
            conversation=conversation,
            content=message_content,
            message_direction="Inbound",
            message_status="Read",
            message_time=message_time,
            customer_phone=wa_id,
            customer_name=customer_name,
        )
    return is_new


def _process_status_update(clinic, status_obj, raw_payload):
    wa_message_id = status_obj.get("id")
    if not wa_message_id:
        return False

    delivery_status = (status_obj.get("status") or "").capitalize()
    if delivery_status not in {"Sent", "Delivered", "Read", "Failed", "Pending"}:
        delivery_status = "Pending"

    message_time = _epoch_to_datetime(status_obj.get("timestamp"))
    message_name = frappe.db.get_value("WhatsApp Conversation Message", {"wa_message_id": wa_message_id}, "name")
    if not message_name:
        return False

    message_doc = frappe.get_doc("WhatsApp Conversation Message", message_name)
    message_doc.status = delivery_status
    if delivery_status == "Failed":
        errors = status_obj.get("errors") or []
        if errors and isinstance(errors, list):
            first_error = errors[0] or {}
            message_doc.error_message = first_error.get("title") or first_error.get("message") or "Failed"
    message_doc.raw_payload = _safe_json_dumps(raw_payload)
    message_doc.flags.ignore_permissions = True
    message_doc.save(ignore_permissions=True)

    frappe.db.set_value(
        "WhatsApp Message Log",
        {"message_id": wa_message_id},
        {"status": delivery_status, "error_message": message_doc.error_message or ""},
        update_modified=True,
    )

    conversation = frappe.get_doc("WhatsApp Conversation", message_doc.conversation)
    _update_conversation_summary(
        conversation=conversation,
        content=message_doc.content,
        message_direction=message_doc.direction,
        message_status=delivery_status,
        message_time=message_time,
    )
    return True


def _process_webhook_payload(payload):
    if not isinstance(payload, dict):
        return {"processed": 0, "duplicates": 0}

    processed = 0
    duplicates = 0

    entries = payload.get("entry") or []
    for entry in entries:
        changes = (entry or {}).get("changes") or []
        for change in changes:
            value = (change or {}).get("value") or {}
            metadata = value.get("metadata") or {}
            phone_number_id = metadata.get("phone_number_id")
            if not phone_number_id:
                continue

            clinic = frappe.db.get_value("Clinic Settings", {"whatsapp_phone_number_id": phone_number_id}, "name")
            if not clinic:
                frappe.logger("mob_clinic.whatsapp").warning("Webhook payload ignored: clinic not found for phone_number_id %s", phone_number_id)
                continue

            contacts = value.get("contacts") or []
            contact_by_waid = {}
            for contact in contacts:
                wa_id = contact.get("wa_id")
                if wa_id:
                    contact_by_waid[wa_id] = {
                        "profile_name": ((contact.get("profile") or {}).get("name") or "").strip()
                    }

            messages = value.get("messages") or []
            for message_obj in messages:
                created = _process_inbound_message(clinic, contact_by_waid, message_obj, payload)
                if created:
                    processed += 1
                else:
                    duplicates += 1

            statuses = value.get("statuses") or []
            for status_obj in statuses:
                updated = _process_status_update(clinic, status_obj, payload)
                if updated:
                    processed += 1

    return {"processed": processed, "duplicates": duplicates}


def _extract_update_fields(settings_payload=None, **kwargs):
    update_fields = {}

    if settings_payload:
        if isinstance(settings_payload, str):
            try:
                settings_payload = json.loads(settings_payload)
            except Exception:
                settings_payload = None

        if isinstance(settings_payload, dict):
            for key, value in settings_payload.items():
                if key in ALLOWED_WHATSAPP_SETTINGS_FIELDS:
                    update_fields[key] = value

    for key in ALLOWED_WHATSAPP_SETTINGS_FIELDS:
        if key in kwargs and kwargs.get(key) is not None:
            update_fields[key] = kwargs.get(key)

    return update_fields


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

    access_token = _read_whatsapp_access_token(settings.name)
    if not access_token:
        frappe.throw(_("WhatsApp Access Token is not configured"))
    
    return {
        "phone_number_id": settings.whatsapp_phone_number_id,
        "business_account_id": settings.whatsapp_business_account_id,
        "access_token": access_token,
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
                          language="en_US", message_type="Custom",
                          reference_doctype=None, reference_name=None,
                          header_document_link=None, header_document_filename=None):
    """
    Send a WhatsApp template message
    
    Args:
        clinic: Company/Clinic name
        recipient_phone: Recipient's phone number
        template_name: Approved template name
        template_params: List of parameter values (optional)
        language: Language code (default: "en_US")
        message_type: Type for logging (Appointment Reminder, Review Request, etc.)
        reference_doctype: Linked document type
        reference_name: Linked document name
    
    Returns:
        dict with success status and message details
    """
    try:
        # Get credentials
        credentials = _get_whatsapp_credentials(clinic)

        template_name = (template_name or "").strip()
        if not template_name:
            return {"success": False, "error": "Template name is required"}

        language_code = _normalize_template_language(language)
        
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
                    "code": language_code
                }
            }
        }
        
        components = []

        if header_document_link:
            components.append({
                "type": "header",
                "parameters": [{
                    "type": "document",
                    "document": {
                        "link": str(header_document_link),
                        "filename": str(header_document_filename or "document.pdf"),
                    }
                }]
            })

        # Add parameters if provided
        if template_params:
            if isinstance(template_params, str):
                template_params = json.loads(template_params)

            components.append({
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(param)} for param in template_params
                ]
            })

        if components:
            payload["template"]["components"] = components
        
        # Send message (retry with common language fallback for Meta template translations)
        response = None
        last_error = None
        candidate_languages = []
        fallback_languages = [language_code]
        if (language_code or "").lower().startswith("en"):
            fallback_languages.extend(["en_US", "en_IN", "en_GB", "en"])
        else:
            fallback_languages.extend(["en_US", "en_IN", "en"])

        for candidate in fallback_languages:
            if candidate and candidate not in candidate_languages:
                candidate_languages.append(candidate)

        for candidate_language in candidate_languages:
            payload["template"]["language"]["code"] = candidate_language
            try:
                response = _call_whatsapp_api(endpoint, payload, credentials["access_token"])
                break
            except Exception as api_error:
                last_error = api_error
                error_text = str(api_error).lower()
                if (
                    "132001" in error_text
                    or "translation" in error_text
                    or "template name does not exist" in error_text
                ):
                    continue
                raise

        if response is None and last_error:
            raise last_error
        
        # Extract message ID
        message_id = None
        if response.get("messages"):
            message_id = response["messages"][0].get("id")
        
        # Log the message as Pending; final delivery state comes from webhook statuses
        log_id = _log_message(
            clinic=clinic,
            recipient_phone=formatted_phone,
            template_name=template_name,
            message_type=message_type,
            reference_doctype=reference_doctype,
            reference_name=reference_name,
            message_id=message_id,
            status="Pending"
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
        
        # Format date and time
        from frappe.utils import formatdate, format_time
        appt_date = formatdate(appointment.appointment_date, "dd MMM yyyy")
        appt_time = format_time(appointment.appointment_time) if appointment.appointment_time else ""
        
        # Prepare template parameters
        params = [
            patient.patient_name,
            appt_date,
            appt_time,
            appointment.name
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
        
        params = [
            patient.patient_name,
            clinic_name
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
        
        params = [
            patient.patient_name,
            prescription.name
        ]
        prescription_pdf_link = get_url(
            f"/api/method/frappe.utils.print_format.download_pdf?doctype=Patient%20Prescription&name={prescription_id}"
        )
        
        return send_template_message(
            clinic=clinic,
            recipient_phone=phone,
            template_name=template_name,
            template_params=params,
            message_type="Prescription",
            reference_doctype="Patient Prescription",
            reference_name=prescription_id,
            header_document_link=prescription_pdf_link,
            header_document_filename=f"{prescription.name}.pdf",
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
        
        appointment_reference = invoice.name
        linked_appointment = frappe.db.get_value(
            "Sales Invoice Item",
            {
                "parent": invoice.name,
                "reference_dt": "Patient Appointment",
            },
            "reference_dn",
        )
        if linked_appointment:
            appointment_reference = linked_appointment
        
        params = [
            patient.patient_name,
            appointment_reference
        ]
        invoice_pdf_link = get_url(
            f"/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Invoice&name={invoice_id}"
        )
        
        return send_template_message(
            clinic=clinic,
            recipient_phone=phone,
            template_name=template_name,
            template_params=params,
            message_type="Invoice",
            reference_doctype="Sales Invoice",
            reference_name=invoice_id,
            header_document_link=invoice_pdf_link,
            header_document_filename=f"{invoice.name}.pdf",
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


@frappe.whitelist(methods=["GET"])
def get_whatsapp_settings(clinic=None):
    try:
        _, clinic_name, access_error = _resolve_admin_scoped_clinic(clinic=clinic)
        if access_error:
            return access_error

        if not frappe.db.exists("Clinic Settings", clinic_name):
            frappe.local.response["http_status_code"] = 404
            return {"exc_type": "NotFound", "message": "Clinic Settings not found"}

        settings_doc = frappe.get_doc("Clinic Settings", clinic_name)
        token_value = _read_whatsapp_access_token(settings_doc.name)

        return {
            "message": "success",
            "data": {
                "clinic": clinic_name,
                "whatsapp_enabled": 1 if _parse_bool(settings_doc.whatsapp_enabled) else 0,
                "whatsapp_phone_number_id": settings_doc.whatsapp_phone_number_id or "",
                "whatsapp_business_account_id": settings_doc.whatsapp_business_account_id or "",
                "whatsapp_access_token_masked": _mask_token(token_value),
                "has_whatsapp_access_token": 1 if token_value else 0,
                "whatsapp_appointment_template": settings_doc.whatsapp_appointment_template or "",
                "whatsapp_review_template": settings_doc.whatsapp_review_template or "",
                "whatsapp_prescription_template": settings_doc.whatsapp_prescription_template or "",
                "whatsapp_invoice_template": settings_doc.whatsapp_invoice_template or "",
            },
        }
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Get WhatsApp Settings Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": "Error retrieving WhatsApp settings"}


@frappe.whitelist(methods=["POST"])
def update_whatsapp_settings(
    clinic=None,
    settings=None,
    whatsapp_enabled=None,
    whatsapp_phone_number_id=None,
    whatsapp_business_account_id=None,
    whatsapp_access_token=None,
    whatsapp_appointment_template=None,
    whatsapp_review_template=None,
    whatsapp_prescription_template=None,
    whatsapp_invoice_template=None,
):
    try:
        requester_practitioner, clinic_name, access_error = _resolve_admin_scoped_clinic(clinic=clinic)
        if access_error:
            return access_error

        if not frappe.db.exists("Clinic Settings", clinic_name):
            frappe.local.response["http_status_code"] = 404
            return {"exc_type": "NotFound", "message": "Clinic Settings not found"}

        update_fields = _extract_update_fields(
            settings_payload=settings,
            whatsapp_enabled=whatsapp_enabled,
            whatsapp_phone_number_id=whatsapp_phone_number_id,
            whatsapp_business_account_id=whatsapp_business_account_id,
            whatsapp_access_token=whatsapp_access_token,
            whatsapp_appointment_template=whatsapp_appointment_template,
            whatsapp_review_template=whatsapp_review_template,
            whatsapp_prescription_template=whatsapp_prescription_template,
            whatsapp_invoice_template=whatsapp_invoice_template,
        )

        if not update_fields:
            frappe.local.response["http_status_code"] = 400
            return {"exc_type": "ValidationError", "message": "No valid WhatsApp settings fields provided"}

        settings_doc = frappe.get_doc("Clinic Settings", clinic_name)
        token_update_requested = "whatsapp_access_token" in update_fields
        token_update_value = ""

        if not settings_doc.get("clinic"):
            settings_doc.set("clinic", clinic_name)

        for field_name, field_value in update_fields.items():
            if field_name == "whatsapp_enabled":
                settings_doc.set(field_name, 1 if _parse_bool(field_value) else 0)
                continue

            if field_name == "whatsapp_access_token":
                token_update_value = "" if field_value is None else str(field_value).strip()
                continue

            settings_doc.set(field_name, "" if field_value is None else str(field_value).strip())

        settings_doc.save(ignore_permissions=True)

        if token_update_requested:
            _write_whatsapp_access_token(settings_doc.name, token_update_value)

        frappe.db.commit()

        token_value = _read_whatsapp_access_token(settings_doc.name)
        requester_name = getattr(requester_practitioner, "name", None) or frappe.session.user or "unknown"
        frappe.logger("mob_clinic.whatsapp").info(
            "WhatsApp settings updated for clinic %s by practitioner %s",
            clinic_name,
            requester_name,
        )

        return {
            "message": "WhatsApp settings updated successfully",
            "data": {
                "clinic": clinic_name,
                "whatsapp_enabled": 1 if _parse_bool(settings_doc.whatsapp_enabled) else 0,
                "whatsapp_phone_number_id": settings_doc.whatsapp_phone_number_id or "",
                "whatsapp_business_account_id": settings_doc.whatsapp_business_account_id or "",
                "whatsapp_access_token_masked": _mask_token(token_value),
                "has_whatsapp_access_token": 1 if token_value else 0,
                "whatsapp_appointment_template": settings_doc.whatsapp_appointment_template or "",
                "whatsapp_review_template": settings_doc.whatsapp_review_template or "",
                "whatsapp_prescription_template": settings_doc.whatsapp_prescription_template or "",
                "whatsapp_invoice_template": settings_doc.whatsapp_invoice_template or "",
            },
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update WhatsApp Settings Error")
        frappe.local.response["http_status_code"] = 500
        response = {"exc_type": "ServerError", "message": "Error updating WhatsApp settings"}
        if frappe.conf.get("developer_mode"):
            response["details"] = str(e)
        return response


@frappe.whitelist(allow_guest=True, methods=["GET"])
def verify_webhook(clinic=None):
    mode = frappe.form_dict.get("hub.mode") or frappe.form_dict.get("mode")
    verify_token = frappe.form_dict.get("hub.verify_token") or frappe.form_dict.get("verify_token")
    challenge = frappe.form_dict.get("hub.challenge") or frappe.form_dict.get("challenge")

    if mode != "subscribe":
        frappe.local.response["http_status_code"] = 400
        return "Invalid mode"

    expected_token = _get_webhook_verify_token(clinic)
    if not expected_token or verify_token != expected_token:
        frappe.local.response["http_status_code"] = 403
        return "Verification token mismatch"

    frappe.local.response["http_status_code"] = 200
    return challenge or "ok"


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive_webhook():
    try:
        raw_body = frappe.request.get_data() or b""
        signature_header = frappe.get_request_header("X-Hub-Signature-256")
        if not _verify_webhook_signature(raw_body, signature_header):
            frappe.local.response["http_status_code"] = 403
            return {"success": False, "error": "Invalid signature"}

        payload = frappe.request.get_json(silent=True) or {}
        result = _process_webhook_payload(payload)
        frappe.db.commit()
        return {"success": True, "processed": result.get("processed", 0), "duplicates": result.get("duplicates", 0)}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "WhatsApp Webhook Receive Error")
        frappe.local.response["http_status_code"] = 500
        return {"success": False, "error": "Webhook processing failed"}


@frappe.whitelist(methods=["POST"])
def reprocess_webhook_payload(payload):
    try:
        _, _, access_error = _resolve_practitioner_and_clinic(require_admin=True)
        if access_error:
            return access_error

        parsed_payload = payload
        if isinstance(parsed_payload, str):
            parsed_payload = json.loads(parsed_payload)

        result = _process_webhook_payload(parsed_payload or {})
        frappe.db.commit()
        return {"message": "success", "data": result}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Reprocess WhatsApp Webhook Payload Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": "Failed to reprocess webhook payload"}


@frappe.whitelist(methods=["GET"])
def get_conversations(clinic=None, search=None, unread_only=0, limit=20, offset=0):
    try:
        _, clinic_name, access_error = _resolve_practitioner_and_clinic(clinic=clinic)
        if access_error:
            return access_error

        filters = {"clinic": clinic_name}
        if _parse_bool(unread_only):
            filters["unread_count"] = [">", 0]

        fields = [
            "name",
            "clinic",
            "wa_id",
            "customer_name",
            "customer_phone",
            "last_message_preview",
            "last_message_at",
            "last_message_direction",
            "last_message_status",
            "unread_count",
            "session_expires_at",
            "is_session_active",
            "last_inbound_at",
            "last_outbound_at",
        ]

        conversations = frappe.get_all(
            "WhatsApp Conversation",
            filters=filters,
            fields=fields,
            or_filters={
                "customer_name": ["like", f"%{search}%"],
                "customer_phone": ["like", f"%{search}%"],
                "wa_id": ["like", f"%{search}%"],
            } if search else None,
            order_by="last_message_at desc",
            limit_page_length=int(limit),
            limit_start=int(offset),
        )

        total = frappe.db.count("WhatsApp Conversation", filters=filters)
        return {
            "message": "success",
            "data": {
                "conversations": conversations,
                "total": total,
                "clinic": clinic_name,
            },
        }
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Get WhatsApp Conversations Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": "Error retrieving conversations"}


@frappe.whitelist(methods=["GET"])
def get_conversation_messages(conversation_id, clinic=None, limit=50, offset=0):
    try:
        _, clinic_name, access_error = _resolve_practitioner_and_clinic(clinic=clinic)
        if access_error:
            return access_error

        conversation = frappe.get_doc("WhatsApp Conversation", conversation_id)
        if conversation.clinic != clinic_name:
            frappe.local.response["http_status_code"] = 403
            return {"exc_type": "PermissionError", "message": "Conversation outside selected clinic"}

        messages = frappe.get_all(
            "WhatsApp Conversation Message",
            filters={"conversation": conversation_id, "clinic": clinic_name},
            fields=[
                "name",
                "wa_message_id",
                "direction",
                "message_type",
                "content",
                "status",
                "message_timestamp",
                "sender_phone",
                "recipient_phone",
                "template_name",
                "error_message",
            ],
            order_by="message_timestamp asc",
            limit_page_length=int(limit),
            limit_start=int(offset),
        )

        total = frappe.db.count(
            "WhatsApp Conversation Message",
            filters={"conversation": conversation_id, "clinic": clinic_name},
        )
        return {
            "message": "success",
            "data": {
                "conversation": {
                    "name": conversation.name,
                    "customer_name": conversation.customer_name,
                    "customer_phone": conversation.customer_phone,
                    "wa_id": conversation.wa_id,
                    "session_expires_at": conversation.session_expires_at,
                    "is_session_active": conversation.is_session_active,
                },
                "messages": messages,
                "total": total,
            },
        }
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"exc_type": "NotFound", "message": "Conversation not found"}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Get Conversation Messages Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": "Error retrieving conversation messages"}


@frappe.whitelist(methods=["POST"])
def mark_conversation_read(conversation_id, clinic=None):
    try:
        _, clinic_name, access_error = _resolve_practitioner_and_clinic(clinic=clinic)
        if access_error:
            return access_error

        conversation = frappe.get_doc("WhatsApp Conversation", conversation_id)
        if conversation.clinic != clinic_name:
            frappe.local.response["http_status_code"] = 403
            return {"exc_type": "PermissionError", "message": "Conversation outside selected clinic"}

        conversation.unread_count = 0
        conversation.flags.ignore_permissions = True
        conversation.save(ignore_permissions=True)

        frappe.db.set_value(
            "WhatsApp Conversation Message",
            {"conversation": conversation_id, "clinic": clinic_name, "direction": "Inbound"},
            "conversation_read",
            1,
            update_modified=False,
        )
        frappe.db.commit()
        return {"message": "success", "data": {"conversation_id": conversation_id, "unread_count": 0}}
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"exc_type": "NotFound", "message": "Conversation not found"}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Mark Conversation Read Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": "Error marking conversation read"}


@frappe.whitelist(methods=["POST"])
def send_conversation_reply(conversation_id, message_text=None, template_name=None, template_params=None, clinic=None):
    try:
        _, clinic_name, access_error = _resolve_practitioner_and_clinic(clinic=clinic)
        if access_error:
            return access_error

        conversation = frappe.get_doc("WhatsApp Conversation", conversation_id)
        if conversation.clinic != clinic_name:
            frappe.local.response["http_status_code"] = 403
            return {"exc_type": "PermissionError", "message": "Conversation outside selected clinic"}

        session_expiry = _parse_datetime(conversation.session_expires_at)
        session_active = bool(session_expiry and session_expiry >= now_datetime())
        conversation.is_session_active = 1 if session_active else 0

        recipient_phone = conversation.customer_phone or conversation.wa_id
        if not recipient_phone:
            frappe.local.response["http_status_code"] = 400
            return {"exc_type": "ValidationError", "message": "Recipient phone is required"}

        if session_active:
            if not message_text:
                frappe.local.response["http_status_code"] = 400
                return {"exc_type": "ValidationError", "message": "message_text is required for active session"}

            credentials = _get_whatsapp_credentials(clinic_name)
            endpoint = f"{WHATSAPP_API_BASE}/{credentials['phone_number_id']}/messages"
            formatted_phone = _format_phone_number(recipient_phone)
            payload = {
                "messaging_product": "whatsapp",
                "to": formatted_phone,
                "type": "text",
                "text": {"preview_url": False, "body": str(message_text)},
            }
            response = _call_whatsapp_api(endpoint, payload, credentials["access_token"])
            message_id = ((response.get("messages") or [{}])[0]).get("id")
            sent_content = str(message_text)
        else:
            if not template_name:
                frappe.local.response["http_status_code"] = 409
                return {
                    "exc_type": "PolicyViolation",
                    "message": "Customer care window expired. Use template-based message.",
                    "requires_template": True,
                }

            template_response = send_template_message(
                clinic=clinic_name,
                recipient_phone=recipient_phone,
                template_name=template_name,
                template_params=template_params,
                message_type="Custom",
            )
            if not template_response.get("success"):
                return {"success": False, "error": template_response.get("error") or "Failed to send template"}
            message_id = template_response.get("message_id")
            sent_content = f"[template:{template_name}]"

        message_time = now_datetime()
        _, is_new = _upsert_conversation_message(
            conversation=conversation,
            clinic=clinic_name,
            wa_message_id=message_id,
            direction="Outbound",
            message_type="template" if template_name and not session_active else "text",
            content=sent_content,
            status="Pending",
            message_time=message_time,
            sender_phone="",
            recipient_phone=recipient_phone,
            raw_payload={"conversation_id": conversation_id, "session_active": session_active},
            template_name=template_name,
        )

        if is_new:
            _update_conversation_summary(
                conversation=conversation,
                content=sent_content,
                message_direction="Outbound",
                message_status="Pending",
                message_time=message_time,
            )

        _log_message(
            clinic=clinic_name,
            recipient_phone=recipient_phone,
            template_name=template_name or "",
            message_type="Custom",
            reference_doctype="WhatsApp Conversation",
            reference_name=conversation_id,
            message_id=message_id,
            status="Pending",
        )

        frappe.db.commit()
        return {
            "message": "success",
            "data": {
                "conversation_id": conversation_id,
                "message_id": message_id,
                "session_active": session_active,
                "requires_template": False,
            },
        }
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"exc_type": "NotFound", "message": "Conversation not found"}
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Send Conversation Reply Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": "Error sending conversation reply"}


@frappe.whitelist(methods=["GET"])
def get_whatsapp_stats(clinic=None, date_from=None, date_to=None, granularity="day"):
    try:
        _, clinic_name, access_error = _resolve_practitioner_and_clinic(clinic=clinic, require_admin=True)
        if access_error:
            return access_error

        from_dt = _parse_datetime(date_from) if date_from else (now_datetime() - timedelta(days=30))
        to_dt = _parse_datetime(date_to) if date_to else now_datetime()
        if from_dt > to_dt:
            from_dt, to_dt = to_dt, from_dt

        base_filters = {
            "clinic": clinic_name,
            "sent_at": ["between", [from_dt, to_dt]],
        }

        total = frappe.db.count("WhatsApp Message Log", base_filters)
        sent = frappe.db.count("WhatsApp Message Log", {**base_filters, "status": "Sent"})
        delivered = frappe.db.count("WhatsApp Message Log", {**base_filters, "status": "Delivered"})
        read = frappe.db.count("WhatsApp Message Log", {**base_filters, "status": "Read"})
        failed = frappe.db.count("WhatsApp Message Log", {**base_filters, "status": "Failed"})

        template_breakdown = frappe.get_all(
            "WhatsApp Message Log",
            filters=base_filters,
            fields=["template_name", "count(name) as total"],
            group_by="template_name",
            order_by="total desc",
            limit_page_length=20,
        )

        failure_reasons = frappe.get_all(
            "WhatsApp Message Log",
            filters={**base_filters, "status": "Failed"},
            fields=["error_message", "count(name) as total"],
            group_by="error_message",
            order_by="total desc",
            limit_page_length=10,
        )

        date_format = "%Y-%m-%d"
        if granularity == "week":
            date_format = "%Y-W%W"
        elif granularity == "month":
            date_format = "%Y-%m"

        trend_buckets = {}
        rows = frappe.get_all(
            "WhatsApp Message Log",
            filters=base_filters,
            fields=["sent_at", "status"],
            order_by="sent_at asc",
            limit_page_length=10000,
        )
        for row in rows:
            sent_at = _parse_datetime(row.get("sent_at"))
            if not sent_at:
                continue
            bucket = sent_at.strftime(date_format)
            if bucket not in trend_buckets:
                trend_buckets[bucket] = {"bucket": bucket, "sent": 0, "delivered": 0, "read": 0, "failed": 0, "total": 0}
            trend_buckets[bucket]["total"] += 1
            status_value = (row.get("status") or "").lower()
            if status_value in trend_buckets[bucket]:
                trend_buckets[bucket][status_value] += 1

        trends = [trend_buckets[key] for key in sorted(trend_buckets.keys())]
        return {
            "message": "success",
            "data": {
                "clinic": clinic_name,
                "date_from": str(from_dt),
                "date_to": str(to_dt),
                "granularity": granularity,
                "kpis": {
                    "total": total,
                    "sent": sent,
                    "delivered": delivered,
                    "read": read,
                    "failed": failed,
                },
                "template_breakdown": template_breakdown,
                "failure_reasons": failure_reasons,
                "trends": trends,
            },
        }
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Get WhatsApp Stats Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": "Error retrieving WhatsApp analytics"}


@frappe.whitelist(methods=["GET"])
def get_message_logs(clinic=None, limit=50, offset=0, message_type=None, status=None, date_from=None, date_to=None, recipient_search=None):
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
        _, clinic_name, access_error = _resolve_practitioner_and_clinic(clinic=clinic, require_admin=True)
        if access_error:
            return access_error

        filters = {"clinic": clinic_name}
        
        if message_type:
            filters["message_type"] = message_type
        if status:
            filters["status"] = status

        if date_from and date_to:
            filters["sent_at"] = ["between", [date_from, date_to]]
        elif date_from:
            filters["sent_at"] = [">=", date_from]
        elif date_to:
            filters["sent_at"] = ["<=", date_to]
        
        logs = frappe.get_all(
            "WhatsApp Message Log",
            filters=filters,
            or_filters={"recipient_phone": ["like", f"%{recipient_search}%"]} if recipient_search else None,
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
            "total": total,
            "clinic": clinic_name,
        }
    
    except Exception as e:
        return {"success": False, "error": str(e)}
