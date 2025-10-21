import frappe
from frappe import _
from frappe.utils import cstr, get_datetime, nowdate
import json

@frappe.whitelist()
def get_patients(fields=None, filters=None, limit_start=0, limit_page_length=20, order_by="creation desc"):
    """
    Get list of patients with pagination and filtering
    
    Args:
        fields (str): Comma-separated field names to return
        filters (str): JSON string of filters
        limit_start (int): Pagination start
        limit_page_length (int): Records per page  
        order_by (str): Sort order
        
    Returns:
        dict: List of patients with pagination info
    """
    try:
        # Parse fields
        if fields:
            if isinstance(fields, str):
                fields = [f.strip() for f in fields.split(',')]
        else:
            fields = ["name", "patient_name", "mobile", "email", "sex", "dob", "status", "image"]
            
        # Parse filters
        if filters:
            if isinstance(filters, str):
                filters = json.loads(filters)
        else:
            filters = {}
            
        # Add practitioner filter to show only patients of current doctor
        practitioner = get_current_practitioner()
        if practitioner:
            # Filter patients who have appointments with this practitioner
            patient_names = frappe.get_list(
                "Patient Appointment",
                filters={"practitioner": practitioner.name},
                fields=["patient"],
                distinct=True,
                pluck="patient"
            )
            if patient_names:
                filters.setdefault("name", ["in", patient_names])
        
        # Get patients
        patients = frappe.get_list(
            "Patient",
            fields=fields,
            filters=filters,
            limit_start=limit_start,
            limit_page_length=limit_page_length,
            order_by=order_by
        )
        
        # Enhance patient data with custom fields
        enhanced_patients = []
        for patient in patients:
            patient_doc = frappe.get_doc("Patient", patient.name)
            
            enhanced_patient = patient.copy()
            enhanced_patient.update({
                "age": patient_doc.get("age_html", ""),
                "avatar": getattr(patient_doc, 'profile_image', None) or patient_doc.get("image"),
                "last_visit": get_last_appointment_date(patient.name, practitioner.name if practitioner else None),
                "total_visits": get_total_appointments(patient.name, practitioner.name if practitioner else None),
                "pending_amount": get_pending_amount(patient.name),
                "preferred_language": getattr(patient_doc, 'preferred_language', 'English')
            })
            
            enhanced_patients.append(enhanced_patient)
        
        # Get total count for pagination
        total_count = frappe.db.count("Patient", filters)
        
        return {
            "message": "success",
            "data": enhanced_patients,
            "total_count": total_count,
            "page_length": limit_page_length,
            "start": limit_start
        }
        
    except Exception as e:
        frappe.log_error(f"Get patients error: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error retrieving patients"
        }

@frappe.whitelist()
def get_patient(patient_id):
    """
    Get detailed patient information
    
    Args:
        patient_id (str): Patient ID
        
    Returns:
        dict: Detailed patient information
    """
    try:
        patient = frappe.get_doc("Patient", patient_id)
        practitioner = get_current_practitioner()
        
        patient_data = {
            "patient_id": patient.name,
            "name": patient.patient_name,
            "first_name": patient.first_name or "",
            "middle_name": patient.middle_name or "",
            "last_name": patient.last_name or "",
            "sex": patient.sex,
            "blood_group": patient.blood_group,
            "dob": cstr(patient.dob),
            "age": patient.get("age_html", ""),
            "mobile": patient.mobile,
            "phone": patient.phone,
            "email": patient.email,
            "status": patient.status,
            "image": patient.image,
            "avatar": getattr(patient, 'profile_image', None) or patient.image,
            "preferred_language": getattr(patient, 'preferred_language', 'English'),
            "last_app_login": getattr(patient, 'last_app_login', None),
            "occupation": patient.occupation,
            "marital_status": patient.marital_status,
            "insurance_details": getattr(patient, 'insurance_details', ''),
            "uid": patient.uid
        }
        
        # Get medical history
        if hasattr(patient, 'allergies') and patient.allergies:
            allergies = []
            for allergy in patient.allergies:
                allergies.append({
                    "allergy": allergy.allergy,
                    "allergen": allergy.allergen
                })
            patient_data["allergies"] = allergies
            
        # Get medication history
        if hasattr(patient, 'medication') and patient.medication:
            medications = []
            for med in patient.medication:
                medications.append({
                    "medication": med.medication,
                    "medical_code": med.medical_code
                })
            patient_data["medications"] = medications
            
        # Get medical conditions
        if hasattr(patient, 'medical_history') and patient.medical_history:
            conditions = []
            for condition in patient.medical_history:
                conditions.append({
                    "condition": condition.medical_history,
                    "medical_code": condition.medical_code
                })
            patient_data["medical_history"] = conditions
            
        # Get emergency contact
        if hasattr(patient, 'patient_relation') and patient.patient_relation:
            emergency_contacts = []
            for relation in patient.patient_relation:
                emergency_contacts.append({
                    "name": relation.patient_relation,
                    "relation": relation.relation,
                    "phone": relation.phone,
                    "email": relation.email
                })
            patient_data["emergency_contacts"] = emergency_contacts
            
        # Get appointment statistics
        if practitioner:
            patient_data.update({
                "last_visit": get_last_appointment_date(patient.name, practitioner.name),
                "next_appointment": get_next_appointment_date(patient.name, practitioner.name),
                "total_visits": get_total_appointments(patient.name, practitioner.name),
                "pending_amount": get_pending_amount(patient.name),
                "last_treatment": get_last_treatment(patient.name, practitioner.name)
            })
        
        return {
            "message": "success",
            "data": patient_data
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": f"Patient {patient_id} not found"
        }
    except Exception as e:
        frappe.log_error(f"Get patient error: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error retrieving patient details"
        }

@frappe.whitelist()
def create_patient(**kwargs):
    """
    Create a new patient record
    
    Args:
        **kwargs: Patient data fields
        
    Returns:
        dict: Created patient information
    """
    try:
        # Validate required fields
        required_fields = ["first_name", "sex"]
        for field in required_fields:
            if not kwargs.get(field):
                frappe.local.response["http_status_code"] = 400
                return {
                    "exc_type": "ValidationError",
                    "message": f"Missing required field: {field}"
                }
        
        # Check for duplicate mobile number
        if kwargs.get("mobile"):
            existing_patient = frappe.db.exists("Patient", {"mobile": kwargs["mobile"]})
            if existing_patient:
                frappe.local.response["http_status_code"] = 409
                return {
                    "exc_type": "ValidationError", 
                    "message": "Patient with this mobile number already exists"
                }
        
        # Create patient document
        patient = frappe.get_doc({
            "doctype": "Patient",
            **kwargs
        })
        
        patient.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Get the created patient with enhanced data
        created_patient = get_patient(patient.name)
        
        return {
            "message": "Patient created successfully",
            "data": created_patient.get("data")
        }
        
    except frappe.DuplicateEntryError:
        frappe.local.response["http_status_code"] = 409
        return {
            "exc_type": "ValidationError",
            "message": "Patient with similar details already exists"
        }
    except Exception as e:
        frappe.log_error(f"Create patient error: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error creating patient"
        }

@frappe.whitelist()
def update_patient(patient_id, **kwargs):
    """
    Update patient information
    
    Args:
        patient_id (str): Patient ID
        **kwargs: Fields to update
        
    Returns:
        dict: Updated patient information
    """
    try:
        patient = frappe.get_doc("Patient", patient_id)
        
        # Update allowed fields
        allowed_fields = [
            'mobile', 'phone', 'email', 'occupation', 'marital_status',
            'profile_image', 'preferred_language', 'insurance_details'
        ]
        
        updated_fields = []
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(patient, field):
                setattr(patient, field, value)
                updated_fields.append(field)
        
        if updated_fields:
            patient.save()
            frappe.db.commit()
            
        # Return updated patient data
        updated_patient = get_patient(patient_id)
        
        return {
            "message": "Patient updated successfully",
            "updated_fields": updated_fields,
            "data": updated_patient.get("data")
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": f"Patient {patient_id} not found"
        }
    except Exception as e:
        frappe.log_error(f"Update patient error: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error updating patient"
        }

@frappe.whitelist()
def search_patients(search_term, limit=10):
    """
    Search patients by name, mobile, or patient ID
    
    Args:
        search_term (str): Search query
        limit (int): Maximum results to return
        
    Returns:
        dict: Search results
    """
    try:
        practitioner = get_current_practitioner()
        
        # Build search filters
        filters = [
            ["patient_name", "like", f"%{search_term}%"],
            ["mobile", "like", f"%{search_term}%"],
            ["name", "like", f"%{search_term}%"]
        ]
        
        or_filters = {"or": filters}
        
        # If practitioner exists, filter by their patients
        if practitioner:
            patient_names = frappe.get_list(
                "Patient Appointment",
                filters={"practitioner": practitioner.name},
                fields=["patient"],
                distinct=True,
                pluck="patient"
            )
            if patient_names:
                or_filters["name"] = ["in", patient_names]
        
        patients = frappe.get_list(
            "Patient",
            fields=["name", "patient_name", "mobile", "sex", "dob", "image"],
            filters=or_filters,
            limit=limit,
            order_by="patient_name"
        )
        
        # Enhance search results
        search_results = []
        for patient in patients:
            patient_doc = frappe.get_doc("Patient", patient.name)
            search_results.append({
                "patient_id": patient.name,
                "name": patient.patient_name,
                "mobile": patient.mobile,
                "sex": patient.sex,
                "dob": cstr(patient.dob),
                "avatar": getattr(patient_doc, 'profile_image', None) or patient.image,
                "last_visit": get_last_appointment_date(patient.name, practitioner.name if practitioner else None)
            })
        
        return {
            "message": "success",
            "data": search_results
        }
        
    except Exception as e:
        frappe.log_error(f"Search patients error: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error searching patients"
        }

# Helper Functions
def get_current_practitioner():
    """Get current user's healthcare practitioner record"""
    try:
        return frappe.get_doc("Healthcare Practitioner", {"user_id": frappe.session.user})
    except frappe.DoesNotExistError:
        return None

def get_last_appointment_date(patient_id, practitioner_id=None):
    """Get patient's last appointment date"""
    try:
        filters = {"patient": patient_id, "status": ["!=", "Cancelled"]}
        if practitioner_id:
            filters["practitioner"] = practitioner_id
            
        last_appointment = frappe.get_list(
            "Patient Appointment",
            filters=filters,
            fields=["appointment_datetime"],
            order_by="appointment_datetime desc",
            limit=1
        )
        
        if last_appointment:
            return cstr(last_appointment[0].appointment_datetime)
        return None
    except:
        return None

def get_next_appointment_date(patient_id, practitioner_id=None):
    """Get patient's next appointment date"""
    try:
        filters = {
            "patient": patient_id,
            "status": ["in", ["Open", "Scheduled", "Confirmed"]],
            "appointment_date": [">=", nowdate()]
        }
        if practitioner_id:
            filters["practitioner"] = practitioner_id
            
        next_appointment = frappe.get_list(
            "Patient Appointment",
            filters=filters,
            fields=["appointment_datetime"],
            order_by="appointment_datetime asc",
            limit=1
        )
        
        if next_appointment:
            return cstr(next_appointment[0].appointment_datetime)
        return None
    except:
        return None

def get_total_appointments(patient_id, practitioner_id=None):
    """Get total appointment count for patient"""
    try:
        filters = {"patient": patient_id, "status": ["!=", "Cancelled"]}
        if practitioner_id:
            filters["practitioner"] = practitioner_id
            
        return frappe.db.count("Patient Appointment", filters)
    except:
        return 0

def get_pending_amount(patient_id):
    """Get pending payment amount for patient"""
    try:
        # Get outstanding amount from Sales Invoice
        pending = frappe.db.sql("""
            SELECT SUM(outstanding_amount)
            FROM `tabSales Invoice`
            WHERE patient = %s AND docstatus = 1 AND outstanding_amount > 0
        """, patient_id)
        
        return pending[0][0] if pending and pending[0][0] else 0
    except:
        return 0

def get_last_treatment(patient_id, practitioner_id=None):
    """Get last treatment details for patient"""
    try:
        filters = {"patient": patient_id}
        if practitioner_id:
            filters["practitioner"] = practitioner_id
            
        last_record = frappe.get_list(
            "Patient Medical Record",
            filters=filters,
            fields=["subject", "communication_date"],
            order_by="communication_date desc",
            limit=1
        )
        
        if last_record:
            return {
                "treatment": last_record[0].subject,
                "date": cstr(last_record[0].communication_date)
            }
        return None
    except:
        return None