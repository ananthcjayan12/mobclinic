"""
Practitioner API Module
Handles practitioner-related API endpoints for mobile app
"""

import frappe
from frappe import _
from frappe.utils import cint
from mob_clinic.mob_clinic.api import clinic as clinic_helper

@frappe.whitelist(allow_guest=False)
def get_practitioners():
    """
    Get list of all active practitioners
    
    Returns:
        dict: {
            "message": "Success",
            "data": [
                {
                    "name": "PRAC-001",
                    "practitioner_name": "Dr. Name",
                    ...
                }
            ]
        }
    """
    try:
        # Determine active clinic for this session/user. Prefer resolving
        # with practitioner's primary company when available so that
        # session-scoped active clinic and practitioner fallback are handled.
        user = frappe.session.user
        try:
            session_practitioner = frappe.get_doc("Healthcare Practitioner", {"user_id": user})
            session_practitioner_name = session_practitioner.name
        except Exception:
            session_practitioner_name = None

        active_clinic = clinic_helper.resolve_active_clinic(practitioner_name=session_practitioner_name, clinic_param=None)

        # Fetch all active practitioners, then filter by active clinic (if set).
        practitioners = frappe.get_all(
            "Healthcare Practitioner",
            filters={"status": "Active"},
            fields=[
                "name", "practitioner_name", "mobile_phone as mobile",
                "department", "designation", "status"
            ],
            order_by="practitioner_name asc"
        )

        filtered = []
        for practitioner in practitioners:
            if not active_clinic:
                include = True
            else:
                # Check whether this practitioner has access to the active clinic
                try:
                    companies = clinic_helper.get_accessible_companies_for_practitioner(practitioner.get("name"))
                except Exception:
                    companies = []
                include = active_clinic in (companies or [])

            if include:
                practitioner["available"] = True
                filtered.append(practitioner)

        return {
            "message": "Success",
            "data": filtered
        }
        
    except Exception as e:
        frappe.log_error(f"Error fetching practitioners: {str(e)}")
        frappe.throw(_("Failed to fetch practitioners: {0}").format(str(e)))


@frappe.whitelist(allow_guest=False)
def get_practitioner(practitioner_id):
    """
    Get details of a specific practitioner
    
    Args:
        practitioner_id (str): Practitioner ID
        
    Returns:
        dict: Practitioner details
    """
    try:
        if not practitioner_id:
            frappe.throw(_("Practitioner ID is required"))
        
        practitioner = frappe.get_doc("Healthcare Practitioner", practitioner_id)

        # Ensure practitioner belongs to the active clinic (if session has one)
        user = frappe.session.user
        try:
            session_practitioner = frappe.get_doc("Healthcare Practitioner", {"user_id": user})
            session_practitioner_name = session_practitioner.name
        except Exception:
            session_practitioner_name = None

        active_clinic = clinic_helper.resolve_active_clinic(practitioner_name=session_practitioner_name, clinic_param=None)
        if active_clinic:
            if not clinic_helper.validate_practitioner_access(practitioner.name, active_clinic):
                frappe.local.response["http_status_code"] = 403
                return {
                    "exc_type": "PermissionError",
                    "message": "Practitioner does not belong to the active clinic"
                }

        return {
            "message": "Success",
            "data": {
                "name": practitioner.name,
                "practitioner_name": practitioner.practitioner_name,
                "email": practitioner.email,
                "mobile": practitioner.mobile_phone,
                "department": practitioner.department,
                "designation": practitioner.designation,
                "status": practitioner.status,
                "image": practitioner.image
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error fetching practitioner: {str(e)}")
        frappe.throw(_("Failed to fetch practitioner: {0}").format(str(e)))
