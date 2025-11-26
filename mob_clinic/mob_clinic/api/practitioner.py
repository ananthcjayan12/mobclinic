"""
Practitioner API Module
Handles practitioner-related API endpoints for mobile app
"""

import frappe
from frappe import _
from frappe.utils import cint

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
        # Fetch all active practitioners
        practitioners = frappe.get_all(
            "Healthcare Practitioner",
            filters={"status": "Active"},
            fields=[
                "name", "practitioner_name", "mobile_phone as mobile",
                "department", "designation", "status"
            ],
            order_by="practitioner_name asc"
        )
        
        # Add availability flag (you can add custom logic here)
        for practitioner in practitioners:
            practitioner["available"] = True
        
        return {
            "message": "Success",
            "data": practitioners
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
