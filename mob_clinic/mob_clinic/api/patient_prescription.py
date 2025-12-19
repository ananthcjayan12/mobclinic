import frappe
from frappe import _
from frappe.utils import nowdate
import json


@frappe.whitelist(methods=['POST'])
def create_patient_prescription(patient_id, **kwargs):
    """
    Create a new patient prescription with simple medication entries

    Args:
        patient_id (str): Patient ID (required)
        medications (list): List of medications
        chief_complaint (str): Chief complaint (optional)
        symptoms (str): Symptoms (optional)
        diagnosis (str): Diagnosis (optional)
        treatment_plan (str): Treatment plan (optional)
        
    Returns:
        dict: Created prescription info
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

        # Create prescription doc
        prescription = frappe.get_doc({
            "doctype": "Patient Prescription",
            "patient": patient_id,
            "patient_name": patient_name,
            "practitioner": practitioner.name if practitioner else None,
            "practitioner_name": practitioner.practitioner_name if practitioner else None,
            "prescription_date": kwargs.get("date") or nowdate(),
            "chief_complaint": kwargs.get("chief_complaint"),
            "symptoms": kwargs.get("symptoms"),
            "diagnosis": kwargs.get("diagnosis"),
            "treatment_plan": kwargs.get("treatment_plan"),
            "company": kwargs.get("company") or frappe.defaults.get_user_default("Company"),
            "status": "Draft"
        })

        # Add medications
        medications = kwargs.get("medications")
        if medications:
            if isinstance(medications, str):
                medications = json.loads(medications)
            
            for med in medications:
                if not med.get("drug_name"):
                    continue
                prescription.append("medications", {
                    "drug_name": med.get("drug_name"),
                    "dosage": med.get("dosage"),
                    "duration": med.get("period") or med.get("duration"),
                    "frequency": med.get("interval") or med.get("frequency"),
                    "form": med.get("dosage_form") or med.get("form"),
                    "instructions": med.get("comment") or med.get("instructions")
                })

        prescription.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "message": "Prescription created successfully",
            "data": {
                "prescription_id": prescription.name,
                "patient_id": prescription.patient,
                "patient_name": prescription.patient_name,
                "practitioner_name": prescription.practitioner_name,
                "prescription_date": str(prescription.prescription_date),
                "medications_count": len(prescription.medications),
                "status": prescription.status
            }
        }

    except frappe.ValidationError as e:
        frappe.local.response["http_status_code"] = 400
        return {"exc_type": "ValidationError", "message": str(e)}
    except Exception as e:
        frappe.log_error(str(e)[:500], "Create Patient Prescription Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": f"Error creating prescription: {str(e)}"}


@frappe.whitelist(methods=['GET'])
def get_patient_prescriptions(patient_id, limit=20):
    """
    Get prescriptions for a patient
    
    Args:
        patient_id (str): Patient ID
        limit (int): Number of records
        
    Returns:
        dict: List of prescriptions
    """
    try:
        prescriptions = frappe.get_all(
            "Patient Prescription",
            filters={"patient": patient_id},
            fields=[
                "name", "patient", "patient_name", "practitioner", "practitioner_name",
                "prescription_date", "chief_complaint", "diagnosis", "status"
            ],
            order_by="prescription_date desc",
            limit=limit
        )

        # Get medications count for each
        for rx in prescriptions:
            rx["medications_count"] = frappe.db.count(
                "Prescription Medication",
                {"parent": rx["name"]}
            )

        return {
            "message": "success",
            "data": prescriptions
        }

    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Patient Prescriptions Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": str(e)}


@frappe.whitelist(methods=['GET'])
def get_patient_prescription(prescription_id):
    """
    Get single prescription details
    
    Args:
        prescription_id (str): Prescription ID
        
    Returns:
        dict: Prescription details with medications
    """
    try:
        rx = frappe.get_doc("Patient Prescription", prescription_id)
        
        medications = []
        for med in rx.medications:
            medications.append({
                "drug_name": med.drug_name,
                "dosage": med.dosage,
                "duration": med.duration,
                "frequency": med.frequency,
                "form": med.form,
                "instructions": med.instructions
            })

        return {
            "message": "success",
            "data": {
                "prescription_id": rx.name,
                "patient_id": rx.patient,
                "patient_name": rx.patient_name,
                "practitioner": rx.practitioner,
                "practitioner_name": rx.practitioner_name,
                "prescription_date": str(rx.prescription_date),
                "chief_complaint": rx.chief_complaint,
                "symptoms": rx.symptoms,
                "diagnosis": rx.diagnosis,
                "treatment_plan": rx.treatment_plan,
                "medications": medications,
                "status": rx.status,
                "creation": rx.creation,
                "modified": rx.modified
            }
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"exc_type": "NotFound", "message": f"Prescription {prescription_id} not found"}
    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Patient Prescription Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": str(e)}


@frappe.whitelist(methods=['POST'])
def delete_patient_prescription(prescription_id):
    """
    Delete a patient prescription
    """
    try:
        if not prescription_id:
            frappe.local.response["http_status_code"] = 400
            return {"exc_type": "ValidationError", "message": "Prescription ID is required"}

        frappe.delete_doc("Patient Prescription", prescription_id, ignore_permissions=True)
        frappe.db.commit()

        return {
            "message": "Prescription deleted successfully",
            "data": {"prescription_id": prescription_id}
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"exc_type": "NotFound", "message": f"Prescription {prescription_id} not found"}
    except Exception as e:
        frappe.log_error(str(e)[:500], "Delete Patient Prescription Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": str(e)}


@frappe.whitelist(methods=['POST'])
def update_patient_prescription(prescription_id, **kwargs):
    """
    Update a patient prescription
    """
    try:
        if not prescription_id:
            frappe.local.response["http_status_code"] = 400
            return {"exc_type": "ValidationError", "message": "Prescription ID is required"}

        rx = frappe.get_doc("Patient Prescription", prescription_id)
        
        # Update medications if provided
        medications = kwargs.get("medications")
        if medications:
            if isinstance(medications, str):
                medications = json.loads(medications)
            
            # Clear existing medications
            rx.medications = []
            
            # Add new medications
            for med in medications:
                if not med.get("drug_name"):
                    continue
                rx.append("medications", {
                    "drug_name": med.get("drug_name"),
                    "dosage": med.get("dosage"),
                    "duration": med.get("duration") or med.get("period"),
                    "frequency": med.get("frequency") or med.get("interval"),
                    "form": med.get("form") or med.get("dosage_form"),
                    "instructions": med.get("instructions") or med.get("comment")
                })
        
        # Update other fields if provided
        if kwargs.get("chief_complaint") is not None:
            rx.chief_complaint = kwargs.get("chief_complaint")
        if kwargs.get("symptoms") is not None:
            rx.symptoms = kwargs.get("symptoms")
        if kwargs.get("diagnosis") is not None:
            rx.diagnosis = kwargs.get("diagnosis")
        if kwargs.get("treatment_plan") is not None:
            rx.treatment_plan = kwargs.get("treatment_plan")
        if kwargs.get("status") is not None:
            rx.status = kwargs.get("status")
        
        rx.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "message": "Prescription updated successfully",
            "data": {
                "prescription_id": rx.name,
                "medications_count": len(rx.medications),
                "status": rx.status
            }
        }

    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {"exc_type": "NotFound", "message": f"Prescription {prescription_id} not found"}
    except Exception as e:
        frappe.log_error(str(e)[:500], "Update Patient Prescription Error")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": str(e)}


