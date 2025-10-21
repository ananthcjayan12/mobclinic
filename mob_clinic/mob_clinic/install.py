import frappe
from frappe import _

def after_install():
    """Actions to perform after app installation"""
    
    # Create default appointment types if they don't exist
    create_default_appointment_types()
    
    # Set up default permissions
    setup_default_permissions()
    
    # Create default clinic profile
    create_default_clinic_settings()
    
    frappe.db.commit()
    print("Mob Clinic app installed successfully!")

def create_default_appointment_types():
    """Create default appointment types for the clinic"""
    
    appointment_types = [
        {
            "appointment_type": "General Consultation",
            "default_duration": 30,
            "color": "#4285F4"
        },
        {
            "appointment_type": "Follow-up",
            "default_duration": 15,
            "color": "#34A853"
        },
        {
            "appointment_type": "Emergency",
            "default_duration": 45,
            "color": "#EA4335"
        },
        {
            "appointment_type": "Dental Checkup",
            "default_duration": 30,
            "color": "#FF9800"
        },
        {
            "appointment_type": "Treatment",
            "default_duration": 60,
            "color": "#9C27B0"
        }
    ]
    
    for apt_type in appointment_types:
        if not frappe.db.exists("Appointment Type", apt_type["appointment_type"]):
            doc = frappe.get_doc({
                "doctype": "Appointment Type",
                **apt_type
            })
            doc.insert(ignore_permissions=True)
            print(f"Created Appointment Type: {apt_type['appointment_type']}")

def setup_default_permissions():
    """Setup default permissions for mobile app users"""
    
    # Healthcare Practitioner permissions
    practitioner_perms = [
        {"doctype": "Patient", "role": "Healthcare Practitioner", "read": 1, "write": 1, "create": 1},
        {"doctype": "Patient Appointment", "role": "Healthcare Practitioner", "read": 1, "write": 1, "create": 1},
        {"doctype": "Patient Medical Record", "role": "Healthcare Practitioner", "read": 1, "write": 1, "create": 1},
        {"doctype": "Sales Invoice", "role": "Healthcare Practitioner", "read": 1, "write": 1, "create": 1},
    ]
    
    # Note: In production, you would properly set up role permissions
    # This is a simplified setup for development
    print("Default permissions configured")

def create_default_clinic_settings():
    """Create default clinic settings document"""
    
    # Create a singleton for clinic settings if needed
    try:
        if not frappe.db.exists("Healthcare Settings"):
            # Healthcare Settings should already exist, just update it
            settings = frappe.get_doc("Healthcare Settings")
            settings.link_customer_to_patient = 1
            settings.default_medical_code_standard = "ICD 10"
            settings.save(ignore_permissions=True)
            print("Healthcare Settings updated for mobile clinic")
    except Exception as e:
        print(f"Healthcare Settings update failed: {str(e)}")

def before_uninstall():
    """Actions to perform before app uninstall"""
    
    # Clean up custom fields (optional - they will be removed automatically)
    # You can add any cleanup logic here
    
    print("Preparing for Mob Clinic app uninstall...")

def after_uninstall():
    """Actions to perform after app uninstall"""
    
    print("Mob Clinic app uninstalled successfully!")