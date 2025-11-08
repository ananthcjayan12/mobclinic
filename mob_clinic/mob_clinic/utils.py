"""
Utility functions for Mobile Clinic Management System
"""
import frappe
from frappe import _


def before_request():
    """Handle CORS and CSRF exemption for API requests from frontend applications"""
    
    # Exempt mobile API endpoints from CSRF validation
    if frappe.request and frappe.request.path:
        # List of API paths that should be exempt from CSRF
        csrf_exempt_paths = [
            "/api/method/mob_clinic.mob_clinic.api.auth.",
            "/api/method/mob_clinic.mob_clinic.api.patient.",
            "/api/method/mob_clinic.mob_clinic.api.appointment.",
            "/api/method/mob_clinic.mob_clinic.api.prescription.",
            "/api/method/mob_clinic.mob_clinic.api.payment.",
            "/api/method/mob_clinic.mob_clinic.api.file_upload.",
        ]
        
        # Check if current request path matches any exempt path
        for exempt_path in csrf_exempt_paths:
            if exempt_path in frappe.request.path:
                # Set flag to ignore CSRF validation
                frappe.flags.ignore_csrf = True
                break
    
    # Get the request origin
    origin = frappe.get_request_header("Origin")
    
    # Define allowed origins for CORS
    allowed_origins = [
        "http://localhost:3000",  # React development server
        "http://localhost:3001",  # Alternative React port
        "http://127.0.0.1:3000",  # Local IP variant
        "http://192.168.1.100:3000",  # Local network access (adjust IP as needed)
        "https://yourdomain.com",  # Production domain (replace with actual domain)
    ]
    
    # Check if origin is in allowed list
    if origin and any(origin.startswith(allowed) for allowed in allowed_origins):
        # Set CORS headers
        frappe.response.headers.update({
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Frappe-CSRF-Token, X-Requested-With",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "86400"  # 24 hours
        })
        
        # Handle preflight OPTIONS requests
        if frappe.request.method == "OPTIONS":
            frappe.response.status_code = 200
            frappe.response.data = ""
            return
    
    # For development, be more permissive
    if frappe.conf.get("developer_mode"):
        # Allow localhost variants for development
        if origin and ("localhost" in origin or "127.0.0.1" in origin):
            frappe.response.headers.update({
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Frappe-CSRF-Token, X-Requested-With",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Max-Age": "86400"
            })
            
            if frappe.request.method == "OPTIONS":
                frappe.response.status_code = 200
                frappe.response.data = ""
                return


def get_patient_by_mobile(mobile):
    """Get patient by mobile number"""
    try:
        patient = frappe.get_value("Patient", {"mobile": mobile}, ["name", "patient_name", "mobile", "email"])
        if patient:
            return {
                "patient_id": patient[0],
                "name": patient[1],
                "mobile": patient[2],
                "email": patient[3]
            }
        return None
    except Exception as e:
        frappe.log_error(f"Error getting patient by mobile: {str(e)}")
        return None


def validate_mobile_number(mobile):
    """Validate mobile number format"""
    import re
    
    if not mobile:
        return False
    
    # Remove spaces and special characters
    mobile = re.sub(r'[^\d+]', '', mobile)
    
    # Check if it's a valid format (10-15 digits, optionally starting with +)
    pattern = r'^\+?[1-9]\d{9,14}$'
    return bool(re.match(pattern, mobile))


def format_mobile_number(mobile):
    """Format mobile number to standard format"""
    import re
    
    if not mobile:
        return mobile
    
    # Remove all non-digit characters except +
    mobile = re.sub(r'[^\d+]', '', mobile)
    
    # If doesn't start with +, assume it's an Indian number
    if not mobile.startswith('+'):
        if mobile.startswith('0'):
            mobile = mobile[1:]  # Remove leading 0
        if len(mobile) == 10:
            mobile = '+91' + mobile  # Add India country code
    
    return mobile


def send_sms_notification(mobile, message):
    """Send SMS notification (placeholder for SMS integration)"""
    try:
        # This is a placeholder - integrate with your SMS provider
        # Examples: Twilio, AWS SNS, local SMS gateway
        frappe.logger().info(f"SMS to {mobile}: {message}")
        
        # For now, just log the SMS
        return True
    except Exception as e:
        frappe.log_error(f"SMS sending failed: {str(e)}")
        return False


def send_email_notification(email, subject, message):
    """Send email notification"""
    try:
        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
            now=True
        )
        return True
    except Exception as e:
        frappe.log_error(f"Email sending failed: {str(e)}")
        return False


def get_clinic_settings():
    """Get clinic-specific settings"""
    try:
        # This could be extended to get clinic-specific configurations
        settings = {
            "default_appointment_duration": 30,
            "working_hours_start": "09:00:00",
            "working_hours_end": "17:00:00",
            "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "appointment_buffer": 15,  # minutes between appointments
            "max_appointments_per_day": 20
        }
        return settings
    except Exception as e:
        frappe.log_error(f"Error getting clinic settings: {str(e)}")
        return {}


def validate_file_upload(file_content, file_name, max_size_mb=10):
    """Validate file upload parameters"""
    import base64
    
    errors = []
    
    # Check file name
    if not file_name or not file_name.strip():
        errors.append("File name is required")
    
    # Check file content
    if not file_content:
        errors.append("File content is required")
    else:
        try:
            # Check if it's base64 encoded
            decoded = base64.b64decode(file_content)
            file_size_mb = len(decoded) / (1024 * 1024)
            
            if file_size_mb > max_size_mb:
                errors.append(f"File size exceeds {max_size_mb}MB limit")
                
        except Exception:
            errors.append("Invalid file content encoding")
    
    return errors


def get_file_category_config():
    """Get file category configuration"""
    return {
        "prescription": {
            "description": "Prescription documents and images",
            "allowed_extensions": [".pdf", ".jpg", ".jpeg", ".png"],
            "optimize_images": True,
            "max_size_mb": 5
        },
        "xray": {
            "description": "X-ray and diagnostic images", 
            "allowed_extensions": [".jpg", ".jpeg", ".png", ".dcm"],
            "optimize_images": True,
            "max_size_mb": 10
        },
        "report": {
            "description": "Medical reports and lab results",
            "allowed_extensions": [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"],
            "optimize_images": True,
            "max_size_mb": 8
        },
        "profile": {
            "description": "Patient profile pictures",
            "allowed_extensions": [".jpg", ".jpeg", ".png"],
            "optimize_images": True,
            "max_size_mb": 2
        },
        "treatment": {
            "description": "Treatment progress photos and videos",
            "allowed_extensions": [".jpg", ".jpeg", ".png", ".mp4", ".mov"],
            "optimize_images": True,
            "max_size_mb": 20
        },
        "document": {
            "description": "General medical documents",
            "allowed_extensions": [".pdf", ".doc", ".docx", ".txt"],
            "optimize_images": False,
            "max_size_mb": 5
        }
    }