import frappe
from frappe import _
from frappe.utils import nowdate
import json


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

        # Get practitioner
        user = frappe.session.user
        practitioner = None
        if user != "Guest":
            practitioner = frappe.db.get_value(
                "Healthcare Practitioner",
                {"user_id": user},
                ["name", "practitioner_name"],
                as_dict=True
            )

        # Get patient name
        patient_name = frappe.db.get_value("Patient", patient_id, "patient_name")

        # Create record
        record = frappe.get_doc({
            "doctype": "Clinical Record",
            "patient": patient_id,
            "patient_name": patient_name,
            "practitioner": practitioner.name if practitioner else None,
            "practitioner_name": practitioner.practitioner_name if practitioner else None,
            "record_date": kwargs.get("date") or nowdate(),
            "notes": kwargs.get("notes"),
            "company": kwargs.get("company") or frappe.defaults.get_user_default("Company"),
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
                "status": record.status
            }
        }

    except frappe.ValidationError as e:
        frappe.local.response["http_status_code"] = 400
        return {"exc_type": "ValidationError", "message": str(e)}
    except Exception as e:
        frappe.log_error(str(e)[:500], "Create Clinical Record Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": f"Error creating clinical record: {str(e)}"}


@frappe.whitelist(methods=['GET'])
def get_clinical_records(patient_id, limit=20):
    """
    Get clinical records for a patient
    """
    try:
        records = frappe.get_all(
            "Clinical Record",
            filters={"patient": patient_id},
            fields=[
                "name", "patient", "patient_name", "practitioner", "practitioner_name",
                "record_date", "notes", "status"
            ],
            order_by="record_date desc",
            limit=limit
        )

        return {
            "message": "success",
            "data": records
        }

    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Clinical Records Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": str(e)}


@frappe.whitelist(methods=['GET'])
def get_clinical_record(record_id):
    """
    Get single clinical record details
    """
    try:
        rec = frappe.get_doc("Clinical Record", record_id)

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
    """
    try:
        if not record_id:
            frappe.local.response["http_status_code"] = 400
            return {"exc_type": "ValidationError", "message": "Record ID is required"}

        rec = frappe.get_doc("Clinical Record", record_id)
        
        # Update notes field
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
    """
    try:
        if not record_id:
            frappe.local.response["http_status_code"] = 400
            return {"exc_type": "ValidationError", "message": "Record ID is required"}

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

