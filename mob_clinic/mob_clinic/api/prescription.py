import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, getdate
import json


@frappe.whitelist()
def get_prescriptions(patient_id=None, filters=None, limit_start=0, limit_page_length=20, order_by="creation desc"):
    """
    Get list of prescriptions/medical records with filtering
    
    Args:
        patient_id (str): Filter by patient ID
        filters (str): JSON string of additional filters
        limit_start (int): Pagination start
        limit_page_length (int): Records per page
        order_by (str): Sort order
        
    Returns:
        dict: List of medical records with pagination info
    """
    try:
        # Parse filters
        if filters:
            if isinstance(filters, str):
                filters = json.loads(filters)
        else:
            filters = {}
        
        # Add patient filter if provided
        if patient_id:
            filters["patient"] = patient_id
        
        # Get current practitioner
        practitioner = get_current_practitioner()
        if practitioner and not patient_id:
            # If no specific patient, show practitioner's records
            filters["practitioner"] = practitioner.get("name")
        
        # Get patient encounters (prescriptions)
        records = frappe.get_all(
            "Patient Encounter",
            fields=[
                "name", "patient", "patient_name", "practitioner",
                "medical_department", "encounter_date", "encounter_time",
                "invoiced", "company", "docstatus", "creation"
            ],
            filters=filters,
            limit_start=limit_start,
            limit_page_length=limit_page_length,
            order_by=order_by
        )
        
        # Enhance record data
        enhanced_records = []
        for record in records:
            # Get patient info
            patient_data = get_patient_basic_info(record.get("patient"))
            
            # Get medications count
            medications = frappe.get_all(
                "Drug Prescription",
                filters={"parent": record.get("name")},
                fields=["drug_code", "drug_name", "dosage", "period"]
            )
            
            # Get investigations count
            investigations = frappe.get_all(
                "Lab Prescription",
                filters={"parent": record.get("name")},
                fields=["lab_test_code", "lab_test_name"]
            )
            
            enhanced_record = dict(record)
            enhanced_record.update({
                "patient_mobile": patient_data.get("mobile"),
                "patient_email": patient_data.get("email"),
                "medications_count": len(medications),
                "investigations_count": len(investigations),
                "has_attachments": has_attachments(record.get("name")),
                "can_edit": can_edit_record(record.get("name")),
                "can_share": can_share_record(record.get("name"))
            })
            
            enhanced_records.append(enhanced_record)
        
        # Get total count
        total_count = frappe.db.count("Patient Encounter", filters)
        
        return {
            "message": "success",
            "data": enhanced_records,
            "total_count": total_count,
            "page_length": limit_page_length,
            "start": limit_start
        }
        
    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Prescriptions Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error retrieving prescriptions: {str(e)}"
        }


@frappe.whitelist()
def get_prescription(record_id):
    """
    Get detailed prescription/medical record information
    
    Args:
        record_id (str): Medical Record ID
        
    Returns:
        dict: Detailed medical record data
    """
    try:
        record = frappe.get_doc("Patient Encounter", record_id)
        
        # Get patient details
        patient_data = get_patient_basic_info(record.patient)
        
        # Get practitioner details
        practitioner_data = {}
        if record.practitioner:
            prac = frappe.get_doc("Healthcare Practitioner", record.practitioner)
            practitioner_data = {
                "practitioner_id": prac.name,
                "practitioner_name": prac.practitioner_name,
                "mobile": prac.mobile_phone,
                "department": prac.get("department")
            }
        
        # Get medications
        medications = []
        for med in record.drug_prescription:
            medications.append({
                "drug_code": med.drug_code,
                "drug_name": med.drug_name,
                "dosage": med.dosage,
                "period": med.period,
                "dosage_form": med.dosage_form,
                "interval": med.interval,
                "interval_uom": med.interval_uom,
                "medical_code": med.medical_code,
                "comment": med.comment
            })
        
        # Get investigations/lab tests
        investigations = []
        for lab in record.lab_test_prescription:
            investigations.append({
                "lab_test_code": lab.lab_test_code,
                "lab_test_name": lab.lab_test_name,
                "lab_test_comment": lab.lab_test_comment,
                "invoiced": lab.invoiced
            })
        
        # Get attachments
        attachments = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": "Patient Encounter",
                "attached_to_name": record_id
            },
            fields=["name", "file_name", "file_url", "file_size", "creation"]
        )
        
        # Build response
        response_data = {
            "record_id": record.name,
            "patient_id": record.patient,
            "patient_name": record.patient_name,
            "patient_mobile": patient_data.get("mobile"),
            "patient_email": patient_data.get("email"),
            "patient_age": patient_data.get("age"),
            "patient_sex": patient_data.get("sex"),
            "practitioner": practitioner_data,
            "encounter_date": record.encounter_date,
            "encounter_time": record.encounter_time,
            "department": record.medical_department,
            "medications": medications,
            "investigations": investigations,
            "attachments": attachments,
            "invoiced": record.invoiced,
            "docstatus": record.docstatus,
            "creation": record.creation,
            "modified": record.modified
        }
        
        return {
            "message": "success",
            "data": response_data
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": f"Medical record {record_id} not found"
        }
    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Prescription Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error retrieving prescription details"
        }


@frappe.whitelist()
def create_prescription(patient_id, **kwargs):
    """
    Create a new prescription/medical record
    
    Args:
        patient_id (str): Patient ID
        **kwargs: Medical record fields
        
    Returns:
        dict: Created medical record information
    """
    try:
        # Validate required fields
        if not patient_id:
            frappe.local.response["http_status_code"] = 400
            return {
                "exc_type": "ValidationError",
                "message": "Patient ID is required"
            }
        
        # Get current practitioner
        practitioner = get_current_practitioner()
        if not practitioner:
            frappe.local.response["http_status_code"] = 403
            return {
                "exc_type": "PermissionError",
                "message": "Healthcare Practitioner profile not found"
            }
        
        # Get patient details
        patient = frappe.get_doc("Patient", patient_id)
        
        # Create patient encounter (prescription/medical record)
        record = frappe.get_doc({
            "doctype": "Patient Encounter",
            "patient": patient_id,
            "patient_name": patient.patient_name,
            "practitioner": practitioner.name,
            "medical_department": kwargs.get("department") or practitioner.get("department"),
            "encounter_date": kwargs.get("date") or nowdate(),
            "encounter_time": kwargs.get("time") or now_datetime().time(),
            "company": kwargs.get("company") or frappe.defaults.get_user_default("Company")
        })
        
        # Add medications if provided
        medications = kwargs.get("medications")
        if medications:
            if isinstance(medications, str):
                medications = json.loads(medications)
            
            for med in medications:
                # Only include absolutely required and safe fields
                drug_data = {}
                
                # Required: drug_code (Link to Item)
                if med.get("drug_code"):
                    drug_data["drug_code"] = med.get("drug_code")
                    
                # Optional: drug_name (fetched from drug_code usually)
                if med.get("drug_name"):
                    drug_data["drug_name"] = med.get("drug_name")
                
                # Optional: interval fields
                if med.get("interval"):
                    drug_data["interval"] = int(med.get("interval"))
                if med.get("interval_uom"):
                    drug_data["interval_uom"] = med.get("interval_uom")
                
                # Optional: comment (stores dosage/period as text)
                if med.get("comment"):
                    drug_data["comment"] = med.get("comment")
                
                # Do NOT add: dosage_form, dosage, period - they need master data
                    
                record.append("drug_prescription", drug_data)
        
        # Add investigations if provided
        investigations = kwargs.get("investigations")
        if investigations:
            if isinstance(investigations, str):
                investigations = json.loads(investigations)
            
            for inv in investigations:
                # lab_test_code is mandatory - skip if not provided or doesn't exist
                lab_test_code = inv.get("lab_test_code")
                if lab_test_code and frappe.db.exists("Lab Test Template", lab_test_code):
                    record.append("lab_test_prescription", {
                        "lab_test_code": lab_test_code,
                        "lab_test_name": inv.get("lab_test_name") or lab_test_code,
                        "lab_test_comment": inv.get("lab_test_comment")
                    })
        
        record.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "message": "Prescription created successfully",
            "data": {
                "record_id": record.name,
                "patient_id": record.patient,
                "patient_name": record.patient_name,
                "practitioner_id": record.practitioner,
                "encounter_date": record.encounter_date,
                "encounter_time": str(record.encounter_time),
                "docstatus": record.docstatus,
                "medications_count": len(record.drug_prescription),
                "investigations_count": len(record.lab_test_prescription),
                "invoiced": record.invoiced
            }
        }
        
    except frappe.ValidationError as e:
        frappe.local.response["http_status_code"] = 400
        return {
            "exc_type": "ValidationError",
            "message": str(e)
        }
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        frappe.log_error(error_trace, "Create Prescription Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error creating prescription: {str(e)}"
        }


@frappe.whitelist()
def update_prescription(record_id, **kwargs):
    """
    Update an existing prescription/medical record
    
    Args:
        record_id (str): Medical Record ID
        **kwargs: Fields to update
        
    Returns:
        dict: Updated medical record information
    """
    try:
        record = frappe.get_doc("Patient Encounter", record_id)
        
        # Update allowed fields
        updatable_fields = [
            "chief_complaint", "symptoms", "signs", "diagnosis",
            "medical_code", "medical_code_description", "treatment_plan",
            "medication", "lab_test_prescription", "status",
            "shared_with_patient", "follow_up_required", "follow_up_date",
            "follow_up_notes", "lifestyle_recommendations", "diet_recommendations"
        ]
        
        updated_fields = []
        for field in updatable_fields:
            if field in kwargs and kwargs[field] is not None:
                setattr(record, field, kwargs[field])
                updated_fields.append(field)
        
        # Update medications if provided
        if "medications" in kwargs:
            medications = kwargs["medications"]
            if isinstance(medications, str):
                medications = json.loads(medications)
            
            # Clear existing and add new
            record.drug_prescription = []
            for med in medications:
                # Only include absolutely required and safe fields
                drug_data = {}
                
                # Required: drug_code (Link to Item)
                if med.get("drug_code"):
                    drug_data["drug_code"] = med.get("drug_code")
                    
                # Optional: drug_name
                if med.get("drug_name"):
                    drug_data["drug_name"] = med.get("drug_name")
                
                # Optional: interval fields
                if med.get("interval"):
                    drug_data["interval"] = int(med.get("interval"))
                if med.get("interval_uom"):
                    drug_data["interval_uom"] = med.get("interval_uom")
                
                # Optional: comment
                if med.get("comment"):
                    drug_data["comment"] = med.get("comment")
                
                # Do NOT add: dosage_form, dosage, period
                    
                record.append("drug_prescription", drug_data)
            updated_fields.append("medications")
        
        # Update investigations if provided
        if "investigations" in kwargs:
            investigations = kwargs["investigations"]
            if isinstance(investigations, str):
                investigations = json.loads(investigations)
            
            # Clear existing and add new
            record.lab_test_prescription = []
            for inv in investigations:
                # lab_test_code is mandatory - skip if not provided or doesn't exist
                lab_test_code = inv.get("lab_test_code")
                if lab_test_code and frappe.db.exists("Lab Test Template", lab_test_code):
                    record.append("lab_test_prescription", {
                        "lab_test_code": lab_test_code,
                        "lab_test_name": inv.get("lab_test_name") or lab_test_code,
                        "lab_test_comment": inv.get("lab_test_comment")
                    })
            updated_fields.append("investigations")
        
        record.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "message": "Prescription updated successfully",
            "data": {
                "record_id": record.name,
                "updated_fields": updated_fields,
                "status": record.status,
                "medications_count": len(record.drug_prescription),
                "investigations_count": len(record.lab_test_prescription)
            }
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": f"Medical record {record_id} not found"
        }
    except Exception as e:
        frappe.log_error(str(e)[:500], "Update Prescription Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error updating prescription"
        }


@frappe.whitelist()
def share_prescription(record_id, patient_email=None):
    """
    Share prescription with patient
    
    Args:
        record_id (str): Medical Record ID
        patient_email (str): Patient email for notification
        
    Returns:
        dict: Share status
    """
    try:
        record = frappe.get_doc("Patient Encounter", record_id)
        
        # Mark as shared
        record.shared_with_patient = 1
        record.save(ignore_permissions=True)
        frappe.db.commit()
        
        # TODO: Send email notification to patient
        # Can implement email sending here
        
        return {
            "message": "Prescription shared successfully",
            "data": {
                "record_id": record.name,
                "shared_with_patient": record.shared_with_patient,
                "patient_name": record.patient_name
            }
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": f"Medical record {record_id} not found"
        }
    except Exception as e:
        frappe.log_error(str(e)[:500], "Share Prescription Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error sharing prescription"
        }


@frappe.whitelist()
def get_patient_history(patient_id, record_type=None, limit=10):
    """
    Get patient's medical history
    
    Args:
        patient_id (str): Patient ID
        record_type (str): Filter by type (appointments, prescriptions, etc.)
        limit (int): Number of records to fetch
        
    Returns:
        dict: Patient medical history
    """
    try:
        history = {
            "patient_id": patient_id,
            "patient_name": frappe.db.get_value("Patient", patient_id, "patient_name")
        }
        
        # Get recent appointments
        if not record_type or record_type == "appointments":
            appointments = frappe.get_all(
                "Patient Appointment",
                filters={"patient": patient_id},
                fields=["name", "appointment_date", "appointment_time", "status", 
                       "practitioner", "appointment_type"],
                order_by="appointment_date desc",
                limit=limit
            )
            history["appointments"] = appointments
        
        # Get recent prescriptions
        if not record_type or record_type == "prescriptions":
            prescriptions = frappe.get_all(
                "Patient Encounter",
                filters={"patient": patient_id},
                fields=["name", "encounter_date", "encounter_time", "practitioner", 
                       "medical_department", "docstatus", "invoiced"],
                order_by="encounter_date desc",
                limit=limit
            )
            history["prescriptions"] = prescriptions
        
        # Get recent invoices
        if not record_type or record_type == "invoices":
            invoices = frappe.get_all(
                "Sales Invoice",
                filters={"patient": patient_id, "docstatus": ["!=", 2]},
                fields=["name", "posting_date", "grand_total", "outstanding_amount", 
                       "status"],
                order_by="posting_date desc",
                limit=limit
            )
            history["invoices"] = invoices
        
        return {
            "message": "success",
            "data": history
        }
        
    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Patient History Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error retrieving patient history: {str(e)}"
        }


# Helper Functions

def get_current_practitioner():
    """Get current logged-in practitioner"""
    user = frappe.session.user
    if user == "Guest":
        return None
    
    try:
        practitioner = frappe.db.get_value(
            "Healthcare Practitioner",
            {"user_id": user},
            ["name", "practitioner_name", "department", "mobile_phone"],
            as_dict=True
        )
        return practitioner
    except Exception as e:
        frappe.log_error(f"Error getting practitioner for user {user}: {str(e)}", "Get Current Practitioner")
        return None


def get_patient_basic_info(patient_id):
    """Get basic patient information"""
    try:
        patient = frappe.get_doc("Patient", patient_id)
        return {
            "patient_id": patient.name,
            "name": patient.patient_name,
            "mobile": patient.mobile,
            "email": patient.email,
            "sex": patient.sex,
            "age": patient.get_age() if hasattr(patient, 'get_age') else None,
            "blood_group": patient.blood_group
        }
    except:
        return {}


def has_attachments(record_id):
    """Check if medical record has attachments"""
    return frappe.db.exists(
        "File",
        {
            "attached_to_doctype": "Patient Encounter",
            "attached_to_name": record_id
        }
    )


def can_edit_record(record_id):
    """Check if current user can edit the record"""
    try:
        practitioner = get_current_practitioner()
        if not practitioner:
            return False
        
        record_practitioner = frappe.db.get_value(
            "Patient Encounter",
            record_id,
            "healthcare_practitioner"
        )
        
        return record_practitioner == practitioner.name
    except:
        return False


def can_share_record(record_id):
    """Check if record can be shared with patient"""
    return can_edit_record(record_id)
