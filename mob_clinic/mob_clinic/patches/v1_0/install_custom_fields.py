import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def execute():
    """Install custom fields for mobile clinic app"""
    
    print("="*50)
    print("STARTING MOBILE CLINIC CUSTOM FIELDS INSTALLATION")
    print("="*50)
    
    try:
        # Check if Healthcare app is installed
        if "healthcare" not in frappe.get_installed_apps():
            print("WARNING: Healthcare app not found. Please install healthcare app first.")
            print("Run: bench get-app healthcare && bench --site [site-name] install-app healthcare")
            return
            
        # Create all custom fields
        print("Creating Healthcare Practitioner custom fields...")
        create_healthcare_practitioner_fields()
        
        print("Creating Patient custom fields...")
        create_patient_fields() 
        
        print("Creating Patient Appointment custom fields...")
        create_patient_appointment_fields()
        
        print("Creating Patient Medical Record custom fields...")
        create_patient_medical_record_fields()
        
        print("Creating Sales Invoice custom fields...")
        create_sales_invoice_fields()
        
        # Commit the changes
        frappe.db.commit()
        
        print("="*50)
        print("MOBILE CLINIC CUSTOM FIELDS INSTALLATION COMPLETED SUCCESSFULLY!")
        print("="*50)
        
        # Log success
        frappe.log_error("Mobile clinic custom fields installation completed successfully", "Custom Fields Installation")
        
    except Exception as e:
        print(f"ERROR: Failed to install custom fields: {str(e)}")
        frappe.log_error(f"Error installing mobile clinic custom fields: {str(e)}", "Custom Fields Installation Error")
        raise

def create_healthcare_practitioner_fields():
    """Add mobile clinic specific fields to Healthcare Practitioner"""
    custom_fields = {
        "Healthcare Practitioner": [
            {
                "fieldname": "mobile_clinic_section",
                "label": "Mobile Clinic Settings",
                "fieldtype": "Section Break",
                "insert_after": "contact_html",
                "collapsible": 1
            },
            {
                "fieldname": "mobile_app_enabled",
                "label": "Enable Mobile App Access",
                "fieldtype": "Check",
                "default": 0,
                "insert_after": "mobile_clinic_section"
            },
            {
                "fieldname": "app_user_id", 
                "label": "App User ID",
                "fieldtype": "Data",
                "read_only": 1,
                "insert_after": "mobile_app_enabled"
            },
            {
                "fieldname": "column_break_mobile1",
                "fieldtype": "Column Break",
                "insert_after": "app_user_id"
            },
            {
                "fieldname": "clinic_logo",
                "label": "Clinic Logo",
                "fieldtype": "Attach Image", 
                "insert_after": "column_break_mobile1"
            },
            {
                "fieldname": "clinic_description",
                "label": "Clinic Description",
                "fieldtype": "Text",
                "insert_after": "clinic_logo"
            },
            {
                "fieldname": "consultation_section",
                "label": "Consultation Settings",
                "fieldtype": "Section Break",
                "insert_after": "clinic_description",
                "collapsible": 1
            },
            {
                "fieldname": "online_consultation",
                "label": "Enable Online Consultation",
                "fieldtype": "Check",
                "default": 0,
                "insert_after": "consultation_section"
            },
            {
                "fieldname": "consultation_fee",
                "label": "Consultation Fee",
                "fieldtype": "Currency",
                "insert_after": "online_consultation"
            },
            {
                "fieldname": "working_hours_section",
                "label": "Working Hours",
                "fieldtype": "Section Break",
                "insert_after": "consultation_fee",
                "collapsible": 1
            },
            {
                "fieldname": "clinic_working_hours",
                "label": "Clinic Working Hours",
                "fieldtype": "Table",
                "options": "Clinic Working Hours",
                "insert_after": "working_hours_section"
            }
        ]
    }
    
    try:
        create_custom_fields(custom_fields, update=True)
        frappe.log_error("Healthcare Practitioner custom fields created successfully")
    except Exception as e:
        frappe.log_error(f"Error creating Healthcare Practitioner custom fields: {str(e)}")
        raise

def create_patient_fields():
    """Add mobile clinic specific fields to Patient"""
    custom_fields = {
        "Patient": [
            {
                "fieldname": "mobile_app_section",
                "label": "Mobile App Profile",
                "fieldtype": "Section Break", 
                "insert_after": "image",
                "collapsible": 1
            },
            {
                "fieldname": "app_user_id",
                "label": "App User ID", 
                "fieldtype": "Data",
                "read_only": 1,
                "insert_after": "mobile_app_section"
            },
            {
                "fieldname": "profile_image",
                "label": "Profile Image",
                "fieldtype": "Attach Image",
                "insert_after": "app_user_id"
            },
            {
                "fieldname": "column_break_app1", 
                "fieldtype": "Column Break",
                "insert_after": "profile_image"
            },
            {
                "fieldname": "preferred_language",
                "label": "Preferred Language",
                "fieldtype": "Data",
                "default": "English",
                "insert_after": "column_break_app1"
            },
            {
                "fieldname": "last_app_login",
                "label": "Last App Login",
                "fieldtype": "Datetime",
                "read_only": 1,
                "insert_after": "preferred_language"
            },
            {
                "fieldname": "notification_preferences_section",
                "label": "Notification Preferences", 
                "fieldtype": "Section Break",
                "insert_after": "last_app_login",
                "collapsible": 1
            },
            {
                "fieldname": "notification_preferences",
                "label": "Notification Settings",
                "fieldtype": "Text",
                "insert_after": "notification_preferences_section"
            },
            {
                "fieldname": "insurance_section",
                "label": "Insurance Details",
                "fieldtype": "Section Break",
                "insert_after": "notification_preferences",
                "collapsible": 1
            },
            {
                "fieldname": "insurance_details",
                "label": "Insurance Information", 
                "fieldtype": "Text",
                "insert_after": "insurance_section"
            }
        ]
    }
    
    try:
        create_custom_fields(custom_fields, update=True)
        frappe.log_error("Patient custom fields created successfully")
    except Exception as e:
        frappe.log_error(f"Error creating Patient custom fields: {str(e)}")
        raise

def create_patient_appointment_fields():
    """Add mobile clinic specific fields to Patient Appointment"""
    custom_fields = {
        "Patient Appointment": [
            {
                "fieldname": "mobile_app_section",
                "label": "Mobile App Details",
                "fieldtype": "Section Break",
                "insert_after": "notes",
                "collapsible": 1
            },
            {
                "fieldname": "booked_via_app",
                "label": "Booked via Mobile App",
                "fieldtype": "Check",
                "default": 0,
                "insert_after": "mobile_app_section"
            },
            {
                "fieldname": "app_booking_source",
                "label": "App Booking Source",
                "fieldtype": "Data",
                "insert_after": "booked_via_app"
            },
            {
                "fieldname": "column_break_app2",
                "fieldtype": "Column Break", 
                "insert_after": "app_booking_source"
            },
            {
                "fieldname": "reminder_sent",
                "label": "Reminder Sent",
                "fieldtype": "Check",
                "default": 0,
                "insert_after": "column_break_app2"
            },
            {
                "fieldname": "patient_confirmed",
                "label": "Patient Confirmed",
                "fieldtype": "Check",
                "default": 0,
                "insert_after": "reminder_sent"
            },
            {
                "fieldname": "treatment_details_section",
                "label": "Treatment Details",
                "fieldtype": "Section Break", 
                "insert_after": "patient_confirmed",
                "collapsible": 1
            },
            {
                "fieldname": "chief_complaint",
                "label": "Chief Complaint",
                "fieldtype": "Text",
                "insert_after": "treatment_details_section"
            },
            {
                "fieldname": "treatment_type",
                "label": "Treatment Type",
                "fieldtype": "Select",
                "options": "Consultation\nCheckup\nTreatment\nFollow-up\nEmergency",
                "insert_after": "chief_complaint"
            },
            {
                "fieldname": "column_break_treatment1",
                "fieldtype": "Column Break",
                "insert_after": "treatment_type"
            },
            {
                "fieldname": "estimated_duration",
                "label": "Estimated Duration (minutes)",
                "fieldtype": "Int",
                "insert_after": "column_break_treatment1"
            },
            {
                "fieldname": "follow_up_required", 
                "label": "Follow-up Required",
                "fieldtype": "Check",
                "default": 0,
                "insert_after": "estimated_duration"
            },
            {
                "fieldname": "follow_up_date",
                "label": "Follow-up Date",
                "fieldtype": "Date",
                "depends_on": "follow_up_required",
                "insert_after": "follow_up_required"
            },
            {
                "fieldname": "cancellation_section",
                "label": "Cancellation Details", 
                "fieldtype": "Section Break",
                "insert_after": "follow_up_date",
                "collapsible": 1,
                "depends_on": "eval:doc.status == 'Cancelled'"
            },
            {
                "fieldname": "cancellation_reason",
                "label": "Cancellation Reason",
                "fieldtype": "Text",
                "insert_after": "cancellation_section"
            },
            {
                "fieldname": "rescheduled_from",
                "label": "Rescheduled From",
                "fieldtype": "Link",
                "options": "Patient Appointment",
                "insert_after": "cancellation_reason"
            }
        ]
    }
    
    try:
        create_custom_fields(custom_fields, update=True)
        frappe.log_error("Patient Appointment custom fields created successfully")
    except Exception as e:
        frappe.log_error(f"Error creating Patient Appointment custom fields: {str(e)}")
        raise

def create_patient_medical_record_fields():
    """Add mobile clinic specific fields to Patient Medical Record"""
    custom_fields = {
        "Patient Medical Record": [
            {
                "fieldname": "mobile_app_section",
                "label": "Mobile App Sharing",
                "fieldtype": "Section Break",
                "insert_after": "reference_docname", 
                "collapsible": 1
            },
            {
                "fieldname": "shared_with_patient",
                "label": "Shared with Patient",
                "fieldtype": "Check",
                "default": 0,
                "insert_after": "mobile_app_section"
            },
            {
                "fieldname": "patient_viewed",
                "label": "Patient Viewed",
                "fieldtype": "Check",
                "default": 0,
                "insert_after": "shared_with_patient"
            },
            {
                "fieldname": "column_break_sharing1",
                "fieldtype": "Column Break",
                "insert_after": "patient_viewed"
            },
            {
                "fieldname": "prescription_image",
                "label": "Prescription Image",
                "fieldtype": "Attach Image",
                "insert_after": "column_break_sharing1"
            },
            {
                "fieldname": "voice_notes",
                "label": "Voice Notes",
                "fieldtype": "Attach",
                "insert_after": "prescription_image"
            },
            {
                "fieldname": "treatment_plan_section",
                "label": "Treatment Plan",
                "fieldtype": "Section Break",
                "insert_after": "voice_notes",
                "collapsible": 1
            },
            {
                "fieldname": "treatment_plan",
                "label": "Treatment Plan",
                "fieldtype": "Text",
                "insert_after": "treatment_plan_section"
            },
            {
                "fieldname": "next_visit_instructions",
                "label": "Next Visit Instructions",
                "fieldtype": "Text", 
                "insert_after": "treatment_plan"
            },
            {
                "fieldname": "recommendations_section",
                "label": "Recommendations",
                "fieldtype": "Section Break",
                "insert_after": "next_visit_instructions",
                "collapsible": 1
            },
            {
                "fieldname": "lifestyle_recommendations",
                "label": "Lifestyle Recommendations",
                "fieldtype": "Text",
                "insert_after": "recommendations_section"
            },
            {
                "fieldname": "column_break_recommendations1",
                "fieldtype": "Column Break", 
                "insert_after": "lifestyle_recommendations"
            },
            {
                "fieldname": "diet_recommendations",
                "label": "Diet Recommendations", 
                "fieldtype": "Text",
                "insert_after": "column_break_recommendations1"
            },
            {
                "fieldname": "follow_up_section",
                "label": "Follow-up Details",
                "fieldtype": "Section Break",
                "insert_after": "diet_recommendations",
                "collapsible": 1
            },
            {
                "fieldname": "follow_up_required_medical",
                "label": "Follow-up Required",
                "fieldtype": "Check",
                "default": 0,
                "insert_after": "follow_up_section"
            },
            {
                "fieldname": "follow_up_date_medical",
                "label": "Follow-up Date",
                "fieldtype": "Date",
                "depends_on": "follow_up_required_medical",
                "insert_after": "follow_up_required_medical"
            },
            {
                "fieldname": "follow_up_notes_medical",
                "label": "Follow-up Notes",
                "fieldtype": "Text",
                "depends_on": "follow_up_required_medical",
                "insert_after": "follow_up_date_medical"
            }
        ]
    }
    
    try:
        create_custom_fields(custom_fields, update=True)
        frappe.log_error("Patient Medical Record custom fields created successfully")
    except Exception as e:
        frappe.log_error(f"Error creating Patient Medical Record custom fields: {str(e)}")
        raise

def create_sales_invoice_fields():
    """Add medical/clinic specific fields to Sales Invoice"""
    custom_fields = {
        "Sales Invoice": [
            {
                "fieldname": "medical_details_section",
                "label": "Medical Details",
                "fieldtype": "Section Break",
                "insert_after": "customer_address",
                "collapsible": 1
            },
            {
                "fieldname": "patient",
                "label": "Patient",
                "fieldtype": "Link",
                "options": "Patient",
                "insert_after": "medical_details_section"
            },
            {
                "fieldname": "healthcare_practitioner",
                "label": "Healthcare Practitioner",
                "fieldtype": "Link", 
                "options": "Healthcare Practitioner",
                "insert_after": "patient"
            },
            {
                "fieldname": "column_break_medical1",
                "fieldtype": "Column Break",
                "insert_after": "healthcare_practitioner"
            },
            {
                "fieldname": "appointment_reference",
                "label": "Appointment Reference",
                "fieldtype": "Link",
                "options": "Patient Appointment", 
                "insert_after": "column_break_medical1"
            },
            {
                "fieldname": "treatment_type_invoice",
                "label": "Treatment Type",
                "fieldtype": "Data",
                "insert_after": "appointment_reference"
            },
            {
                "fieldname": "treatment_description_section",
                "label": "Treatment Description",
                "fieldtype": "Section Break",
                "insert_after": "treatment_type_invoice",
                "collapsible": 1
            },
            {
                "fieldname": "treatment_description",
                "label": "Treatment Description",
                "fieldtype": "Text",
                "insert_after": "treatment_description_section"
            },
            {
                "fieldname": "payment_tracking_section", 
                "label": "Payment Tracking",
                "fieldtype": "Section Break",
                "insert_after": "treatment_description",
                "collapsible": 1
            },
            {
                "fieldname": "payment_due_date_custom",
                "label": "Payment Due Date",
                "fieldtype": "Date",
                "insert_after": "payment_tracking_section"
            },
            {
                "fieldname": "payment_reminder_sent",
                "label": "Payment Reminder Sent",
                "fieldtype": "Check",
                "default": 0,
                "insert_after": "payment_due_date_custom"
            },
            {
                "fieldname": "column_break_payment1",
                "fieldtype": "Column Break",
                "insert_after": "payment_reminder_sent"
            },
            {
                "fieldname": "paid_via_app",
                "label": "Paid via Mobile App",
                "fieldtype": "Check",
                "default": 0,
                "insert_after": "column_break_payment1"
            },
            {
                "fieldname": "payment_gateway_response",
                "label": "Payment Gateway Response", 
                "fieldtype": "Text",
                "insert_after": "paid_via_app"
            }
        ]
    }
    
    try:
        create_custom_fields(custom_fields, update=True)
        frappe.log_error("Sales Invoice custom fields created successfully")
    except Exception as e:
        frappe.log_error(f"Error creating Sales Invoice custom fields: {str(e)}")
        raise