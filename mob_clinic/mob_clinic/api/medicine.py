"""
Medicine Template API for mob_clinic
Provides endpoints for medicine template CRUD and search
"""

import frappe
from frappe import _
from frappe.utils import flt, cint
import json

from mob_clinic.mob_clinic.api import clinic as clinic_helper


def get_current_practitioner():
    """Get current logged-in practitioner"""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Please login to continue"))
    
    practitioner = frappe.db.get_value(
        "Healthcare Practitioner",
        {"user_id": user},
        ["name", "practitioner_name"],
        as_dict=True
    )
    
    if not practitioner:
        frappe.throw(_("Healthcare practitioner profile not found"))
    
    return practitioner


@frappe.whitelist(methods=['GET'])
def get_medicine_templates(search=None, category=None, limit_start=0, limit_page_length=50):
    """
    Get list of medicine templates with optional search
    
    Args:
        search: Search term for medicine name or generic name
        category: Filter by category
        limit_start: Pagination start
        limit_page_length: Number of records per page
    
    Returns:
        List of medicine templates
    """
    try:
        filters = {"is_active": 1}
        
        if category and category != 'all':
            filters["category"] = category
        
        or_filters = None
        if search:
            or_filters = [
                ["medicine_name", "like", f"%{search}%"],
                ["generic_name", "like", f"%{search}%"]
            ]
        
        medicines = frappe.get_all(
            "Medicine Template",
            filters=filters,
            or_filters=or_filters,
            fields=[
                "name",
                "medicine_name",
                "generic_name",
                "dosage_form",
                "strength",
                "category",
                "default_morning",
                "default_lunch",
                "default_evening",
                "default_night",
                "default_days",
                "default_condition",
                "instructions"
            ],
            order_by="medicine_name asc",
            limit_start=cint(limit_start),
            limit_page_length=cint(limit_page_length)
        )
        
        # Get total count for pagination
        total_count = frappe.db.count("Medicine Template", filters=filters)
        
        return {
            "medicines": medicines,
            "total_count": total_count
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Medicine Templates Error")
        frappe.throw(_("Error fetching medicine templates: {0}").format(str(e)))


@frappe.whitelist(methods=['GET'])
def search_medicines(query, limit=20):
    """
    Quick search for autocomplete
    
    Args:
        query: Search term
        limit: Max results
    
    Returns:
        List of matching medicines
    """
    try:
        if not query or len(query) < 2:
            return []
        
        medicines = frappe.get_all(
            "Medicine Template",
            filters={"is_active": 1},
            or_filters=[
                ["medicine_name", "like", f"%{query}%"],
                ["generic_name", "like", f"%{query}%"]
            ],
            fields=[
                "name",
                "medicine_name",
                "generic_name",
                "dosage_form",
                "strength",
                "default_morning",
                "default_lunch",
                "default_evening",
                "default_night",
                "default_days",
                "default_condition"
            ],
            order_by="medicine_name asc",
            limit=cint(limit)
        )
        
        return medicines
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Search Medicines Error")
        return []


@frappe.whitelist(methods=['POST'])
def create_medicine_template(**kwargs):
    """
    Create a new medicine template
    
    Args:
        medicine_name: Medicine name (required)
        generic_name: Generic name
        dosage_form: Tablet, Capsule, Syrup, etc.
        strength: e.g., 500mg
        category: Antibiotic, Analgesic, etc.
        default_morning, default_lunch, default_evening, default_night: Default dosages
        default_days: Default duration
        default_condition: After Food, Before Food, etc.
        instructions: Special instructions
    
    Returns:
        Created medicine template
    """
    try:
        practitioner = get_current_practitioner()
        
        medicine_name = kwargs.get("medicine_name")
        if not medicine_name:
            frappe.throw(_("Medicine name is required"))
        
        # Check for duplicate
        existing = frappe.db.exists("Medicine Template", {"medicine_name": medicine_name})
        if existing:
            frappe.throw(_("Medicine template with this name already exists"))
        
        doc = frappe.get_doc({
            "doctype": "Medicine Template",
            "medicine_name": medicine_name,
            "generic_name": kwargs.get("generic_name"),
            "dosage_form": kwargs.get("dosage_form", "Tablet"),
            "strength": kwargs.get("strength"),
            "category": kwargs.get("category", "Other"),
            "default_morning": cint(kwargs.get("default_morning", 0)),
            "default_lunch": cint(kwargs.get("default_lunch", 0)),
            "default_evening": cint(kwargs.get("default_evening", 0)),
            "default_night": cint(kwargs.get("default_night", 0)),
            "default_days": cint(kwargs.get("default_days", 5)),
            "default_condition": kwargs.get("default_condition", "After Food"),
            "instructions": kwargs.get("instructions"),
            "is_active": 1
        })
        
        doc.insert(ignore_permissions=True)
        
        return {
            "message": "Medicine template created successfully",
            "medicine_id": doc.name,
            "medicine_name": doc.medicine_name
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Medicine Template Error")
        frappe.throw(_("Error creating medicine template: {0}").format(str(e)))


@frappe.whitelist(methods=['POST', 'PUT'])
def update_medicine_template(medicine_id, **kwargs):
    """
    Update an existing medicine template
    
    Args:
        medicine_id: Medicine Template ID
        **kwargs: Fields to update
    
    Returns:
        Updated medicine template
    """
    try:
        practitioner = get_current_practitioner()
        
        if not frappe.db.exists("Medicine Template", medicine_id):
            frappe.throw(_("Medicine template not found"))
        
        doc = frappe.get_doc("Medicine Template", medicine_id)
        
        # Update fields
        updatable_fields = [
            "medicine_name", "generic_name", "dosage_form", "strength",
            "category", "default_morning", "default_lunch", "default_evening",
            "default_night", "default_days", "default_condition", "instructions",
            "is_active"
        ]
        
        for field in updatable_fields:
            if field in kwargs:
                setattr(doc, field, kwargs[field])
        
        doc.save(ignore_permissions=True)
        
        return {
            "message": "Medicine template updated successfully",
            "medicine_id": doc.name
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Medicine Template Error")
        frappe.throw(_("Error updating medicine template: {0}").format(str(e)))


@frappe.whitelist(methods=['DELETE'])
def delete_medicine_template(medicine_id):
    """
    Delete a medicine template
    
    Args:
        medicine_id: Medicine Template ID
    
    Returns:
        Deletion status
    """
    try:
        practitioner = get_current_practitioner()
        
        if not frappe.db.exists("Medicine Template", medicine_id):
            frappe.throw(_("Medicine template not found"))
        
        frappe.delete_doc("Medicine Template", medicine_id, ignore_permissions=True)
        
        return {
            "message": "Medicine template deleted successfully"
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Medicine Template Error")
        frappe.throw(_("Error deleting medicine template: {0}").format(str(e)))


@frappe.whitelist(methods=['GET'])
def get_medicine_categories():
    """
    Get list of medicine categories
    
    Returns:
        List of categories
    """
    return [
        "Antibiotic",
        "Analgesic",
        "Anti-inflammatory",
        "Antifungal",
        "Antiviral",
        "Antiseptic",
        "Anesthetic",
        "Vitamin",
        "Mineral",
        "Antacid",
        "Antihistamine",
        "Steroid",
        "Muscle Relaxant",
        "Other"
    ]


@frappe.whitelist(methods=['GET'])
def get_dosage_conditions():
    """
    Get list of special conditions for dosage
    
    Returns:
        List of conditions
    """
    return [
        "After Food",
        "Before Food",
        "With Food",
        "Empty Stomach",
        "As Needed",
        "Bedtime"
    ]
