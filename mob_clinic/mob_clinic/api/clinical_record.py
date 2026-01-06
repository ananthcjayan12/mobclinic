import frappe
from frappe import _
from frappe.utils import nowdate
import json
from mob_clinic.mob_clinic.api import clinic as clinic_helper


def get_current_practitioner():
    """Get current logged-in practitioner"""
    user = frappe.session.user
    if user == "Guest":
        return None
    
    try:
        return frappe.get_doc("Healthcare Practitioner", {"user_id": user})
    except frappe.DoesNotExistError:
        return None


def validate_clinic_access(patient_id=None, company=None):
    """
    Validate that the current practitioner has access to the clinic/company.
    Returns the resolved clinic if access is valid, raises error otherwise.
    """
    practitioner = get_current_practitioner()
    if not practitioner:
        frappe.throw(_("Healthcare practitioner profile not found"))
    
    # Resolve the active clinic
    resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name, company)
    
    # If patient_id provided, verify patient belongs to the resolved clinic
    if patient_id and resolved_clinic:
        patient_clinic = frappe.db.get_value("Patient", patient_id, "primary_clinic")
        if patient_clinic and patient_clinic != resolved_clinic:
            frappe.throw(_("You don't have access to this patient's records"), frappe.PermissionError)
    
    return resolved_clinic, practitioner


@frappe.whitelist(methods=['POST'])
def create_clinical_record(patient_id, **kwargs):
    """
    Create a new clinical record (Case Diary)

    Args:
        patient_id (str): Patient ID (required)
        notes (str): Case notes - surgical history, procedures, dates etc.
        
    Returns:
        dict: Created clinical record info
    """
    try:
        if not patient_id:
            frappe.local.response["http_status_code"] = 400
            return {"exc_type": "ValidationError", "message": "Patient ID is required"}

        # Validate clinic access and get resolved clinic
        resolved_clinic, practitioner = validate_clinic_access(patient_id, kwargs.get("company"))

        # Get patient name
        patient_name = frappe.db.get_value("Patient", patient_id, "patient_name")
        if not patient_name:
            frappe.local.response["http_status_code"] = 404
            return {"exc_type": "NotFound", "message": f"Patient {patient_id} not found"}

        # Create record
        record = frappe.get_doc({
            "doctype": "Clinical Record",
            "patient": patient_id,
            "patient_name": patient_name,
            "practitioner": practitioner.name if practitioner else None,
            "practitioner_name": practitioner.practitioner_name if practitioner else None,
            "record_date": kwargs.get("date") or nowdate(),
            "notes": kwargs.get("notes"),
            "company": resolved_clinic or kwargs.get("company") or frappe.defaults.get_user_default("Company"),
            "status": "Draft"
        })

        record.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "message": "Clinical record created successfully",
            "data": {
                "record_id": record.name,
                "patient_id": record.patient,
                "patient_name": record.patient_name,
                "practitioner_name": record.practitioner_name,
                "record_date": str(record.record_date),
                "notes": record.notes,
                "status": record.status,
                "company": record.company
            }
        }

    except frappe.PermissionError as e:
        frappe.local.response["http_status_code"] = 403
        return {"exc_type": "PermissionError", "message": str(e)}
    except frappe.ValidationError as e:
        frappe.local.response["http_status_code"] = 400
        return {"exc_type": "ValidationError", "message": str(e)}
    except Exception as e:
        frappe.log_error(str(e)[:500], "Create Clinical Record Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": f"Error creating clinical record: {str(e)}"}


@frappe.whitelist(methods=['GET'])
def get_clinical_records(patient_id, limit=20, clinic=None):
    """
    Get clinical records for a patient
    
    Args:
        patient_id (str): Patient ID (required)
        limit (int): Number of records to return
        clinic (str): Optional clinic filter
        
    Returns:
        dict: List of clinical records
    """
    try:
        # Validate clinic access
        resolved_clinic, practitioner = validate_clinic_access(patient_id, clinic)
        
        # Build filters with clinic isolation
        filters = {"patient": patient_id}
        if resolved_clinic:
            filters["company"] = resolved_clinic
        
        records = frappe.get_all(
            "Clinical Record",
            filters=filters,
            fields=[
                "name", "patient", "patient_name", "practitioner", "practitioner_name",
                "record_date", "notes", "status", "company"
            ],
            order_by="record_date desc",
            limit=limit
        )

        return {
            "message": "success",
            "data": records
        }

    except frappe.PermissionError as e:
        frappe.local.response["http_status_code"] = 403
        return {"exc_type": "PermissionError", "message": str(e)}
    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Clinical Records Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": str(e)}


@frappe.whitelist(methods=['GET'])
def get_clinical_record(record_id):
    """
    Get single clinical record details
    
    Args:
        record_id (str): Clinical Record ID
        
    Returns:
        dict: Clinical record details
    """
    try:
        rec = frappe.get_doc("Clinical Record", record_id)
        
        # Validate clinic access - check if practitioner has access to record's company
        practitioner = get_current_practitioner()
        if practitioner:
            resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name, None)
            if resolved_clinic and rec.company and rec.company != resolved_clinic:
                frappe.local.response["http_status_code"] = 403
                return {"exc_type": "PermissionError", "message": "You don't have access to this record"}

        return {
            "message": "success",
            "data": {
                "record_id": rec.name,
                "patient_id": rec.patient,
                "patient_name": rec.patient_name,
                "practitioner": rec.practitioner,
                "practitioner_name": rec.practitioner_name,
                "record_date": str(rec.record_date),
                "notes": rec.notes,
                "status": rec.status,
                "company": rec.company,
                "creation": rec.creation,
                "modified": rec.modified
            }
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"exc_type": "NotFound", "message": f"Clinical record {record_id} not found"}
    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Clinical Record Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": str(e)}


@frappe.whitelist(methods=['POST'])
def update_clinical_record(record_id, **kwargs):
    """
    Update a clinical record
    
    Args:
        record_id (str): Clinical Record ID
        **kwargs: Fields to update (notes, status)
        
    Returns:
        dict: Updated clinical record
    """
    try:
        if not record_id:
            frappe.local.response["http_status_code"] = 400
            return {"exc_type": "ValidationError", "message": "Record ID is required"}

        rec = frappe.get_doc("Clinical Record", record_id)
        
        # Validate clinic access - check if practitioner has access to record's company
        practitioner = get_current_practitioner()
        if practitioner:
            resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name, None)
            if resolved_clinic and rec.company and rec.company != resolved_clinic:
                frappe.local.response["http_status_code"] = 403
                return {"exc_type": "PermissionError", "message": "You don't have permission to update this record"}
        
        # Update fields
        if kwargs.get("notes") is not None:
            rec.notes = kwargs.get("notes")
        if kwargs.get("status") is not None:
            rec.status = kwargs.get("status")
        
        rec.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "message": "Clinical record updated successfully",
            "data": {
                "record_id": rec.name,
                "notes": rec.notes,
                "status": rec.status
            }
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"exc_type": "NotFound", "message": f"Clinical record {record_id} not found"}
    except Exception as e:
        frappe.log_error(str(e)[:500], "Update Clinical Record Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": str(e)}


@frappe.whitelist(methods=['POST'])
def delete_clinical_record(record_id):
    """
    Delete a clinical record
    
    Args:
        record_id (str): Clinical Record ID
        
    Returns:
        dict: Deletion status
    """
    try:
        if not record_id:
            frappe.local.response["http_status_code"] = 400
            return {"exc_type": "ValidationError", "message": "Record ID is required"}

        rec = frappe.get_doc("Clinical Record", record_id)
        
        # Validate clinic access - check if practitioner has access to record's company
        practitioner = get_current_practitioner()
        if practitioner:
            resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name, None)
            if resolved_clinic and rec.company and rec.company != resolved_clinic:
                frappe.local.response["http_status_code"] = 403
                return {"exc_type": "PermissionError", "message": "You don't have permission to delete this record"}

        frappe.delete_doc("Clinical Record", record_id, ignore_permissions=True)
        frappe.db.commit()

        return {
            "message": "Clinical record deleted successfully",
            "data": {"record_id": record_id}
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"exc_type": "NotFound", "message": f"Clinical record {record_id} not found"}
    except Exception as e:
        frappe.log_error(str(e)[:500], "Delete Clinical Record Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": str(e)}
