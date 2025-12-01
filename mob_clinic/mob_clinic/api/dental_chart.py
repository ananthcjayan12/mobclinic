"""
Dental Chart API - Redesigned from First Principles
Uses Frappe's built-in `name` field as unique identifier
No custom ID generation - relies on database auto-increment
"""

import frappe
import json
from frappe import _
from frappe.utils import nowdate, now_datetime, cstr
from mob_clinic.mob_clinic.api import clinic as clinic_helper


# ============================================================================
# CONDITION MANAGEMENT
# ============================================================================

@frappe.whitelist(methods=['POST'])
def add_condition(patient_id, tooth_numbers, condition):
    """
    Add dental condition to specified teeth
    
    Args:
        patient_id: Patient identifier
        tooth_numbers: List of tooth numbers (can include duplicates for multiple conditions)
        condition: Dict with type, severity, notes, date
    
    Returns:
        Dict with created condition names (Frappe's auto-generated IDs)
    """
    try:
        validate_patient_access(patient_id)
        
        # Parse parameters
        if isinstance(tooth_numbers, str):
            tooth_numbers = json.loads(tooth_numbers)
        if isinstance(condition, str):
            condition = json.loads(condition)
        
        # Validate
        if not tooth_numbers or not isinstance(tooth_numbers, list):
            frappe.throw(_("tooth_numbers must be a non-empty list"))
        
        if not condition.get("type"):
            frappe.throw(_("condition type is required"))
        
        # Get or create dental chart
        chart = get_or_create_chart(patient_id)
        
        # Track affected teeth for status update
        affected_teeth = set()
        
        # Add condition for each tooth
        for tooth_num in tooth_numbers:
            tooth_num = int(tooth_num)
            
            # Validate tooth number
            if not is_valid_tooth_number(tooth_num):
                continue
            
            # Create condition entry - Frappe will auto-generate unique name
            chart.append("conditions", {
                "tooth_number": tooth_num,
                "type": condition.get("type"),
                "severity": condition.get("severity", ""),
                "notes": condition.get("notes", ""),
                "date": condition.get("date", nowdate()),
                "created_by": frappe.session.user,
                "is_deleted": 0
            })
            
            affected_teeth.add(tooth_num)
        
        # Save chart once - this generates names for all new conditions
        chart.save(ignore_permissions=True)
        frappe.db.commit()
        
        # Collect the newly created condition names
        created_conditions = []
        new_condition_docs = []
        
        # Get the conditions we just added (they'll be the last ones without history)
        for cond in reversed(chart.conditions):
            if not cond.is_deleted and cond.tooth_number in affected_teeth:
                # Get as full document to add history
                cond_doc = frappe.get_doc("Dental Chart Condition", cond.name)
                
                # Check if it already has history (means it's not new)
                if len(cond_doc.history) == 0:
                    new_condition_docs.append(cond_doc)
                    created_conditions.append({
                        "name": cond.name,
                        "tooth_number": cond.tooth_number,
                        "type": cond.type
                    })
                    
                    # Stop when we've found all new conditions
                    if len(created_conditions) == len(tooth_numbers):
                        break
        
        # Add initial history for each new condition
        for cond_doc in new_condition_docs:
            cond_doc.append("history", {
                "type": cond_doc.type,
                "severity": cond_doc.severity,
                "notes": cond_doc.notes or "",
                "timestamp": now_datetime(),
                "updated_by": frappe.session.user
            })
            cond_doc.save(ignore_permissions=True)
        
        frappe.db.commit()
        
        # Update tooth status
        update_tooth_status(chart, list(affected_teeth))
        
        return {
            "message": "Condition added successfully",
            "data": {
                "conditions": created_conditions,
                "affected_teeth": list(affected_teeth)
            }
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Add Condition Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error adding condition: {str(e)}"
        }


@frappe.whitelist(methods=['POST'])
def update_condition(patient_id, condition_name, updates):
    """
    Update a dental condition using Frappe's name field
    
    Args:
        patient_id: Patient identifier
        condition_name: Frappe's auto-generated name (e.g., "abc123xyz")
        updates: Dict with fields to update
    """
    try:
        validate_patient_access(patient_id)
        
        if isinstance(updates, str):
            updates = json.loads(updates)
        
        # Get condition document directly
        if not frappe.db.exists("Dental Chart Condition", condition_name):
            frappe.local.response["http_status_code"] = 404
            return {
                "exc_type": "NotFoundError",
                "message": f"Condition {condition_name} not found"
            }
        
        cond_doc = frappe.get_doc("Dental Chart Condition", condition_name)
        
        # Verify it belongs to the correct patient
        chart = frappe.get_doc("Dental Chart", cond_doc.parent)
        if chart.patient != patient_id:
            frappe.local.response["http_status_code"] = 403
            return {
                "exc_type": "PermissionError",
                "message": "Condition does not belong to specified patient"
            }
        
        # Track changes
        has_changes = False
        
        # Update fields if provided
        if "type" in updates and updates["type"] != cond_doc.type:
            cond_doc.type = updates["type"]
            has_changes = True
        
        if "severity" in updates and updates["severity"] != cond_doc.severity:
            cond_doc.severity = updates["severity"]
            has_changes = True
        
        if "notes" in updates and updates["notes"] != cond_doc.notes:
            cond_doc.notes = updates["notes"]
            has_changes = True
        
        if "date" in updates:
            cond_doc.date = updates["date"]
            has_changes = True
        
        # Only add history if something changed
        if has_changes:
            cond_doc.append("history", {
                "type": cond_doc.type,
                "severity": cond_doc.severity,
                "notes": cond_doc.notes or "",
                "timestamp": now_datetime(),
                "updated_by": frappe.session.user
            })
            cond_doc.save(ignore_permissions=True)
            
            # Update parent chart timestamp
            chart.save(ignore_permissions=True)
            frappe.db.commit()
            
            # Update tooth status
            update_tooth_status(chart, [cond_doc.tooth_number])
        
        return {
            "message": "Condition updated successfully",
            "data": {
                "condition_name": condition_name,
                "tooth_number": cond_doc.tooth_number,
                "updated_at": now_datetime(),
                "changes_made": has_changes
            }
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Update Condition Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error updating condition: {str(e)}"
        }


@frappe.whitelist(methods=['POST', 'DELETE'])
def remove_condition(patient_id, condition_name, reason=None):
    """
    Soft delete a condition using Frappe's name field
    """
    try:
        validate_patient_access(patient_id)
        
        if not frappe.db.exists("Dental Chart Condition", condition_name):
            frappe.local.response["http_status_code"] = 404
            return {
                "exc_type": "NotFoundError",
                "message": f"Condition {condition_name} not found"
            }
        
        cond_doc = frappe.get_doc("Dental Chart Condition", condition_name)
        chart = frappe.get_doc("Dental Chart", cond_doc.parent)
        
        if chart.patient != patient_id:
            frappe.local.response["http_status_code"] = 403
            return {
                "exc_type": "PermissionError",
                "message": "Condition does not belong to specified patient"
            }
        
        # Soft delete
        cond_doc.is_deleted = 1
        cond_doc.deleted_at = now_datetime()
        cond_doc.deleted_by = frappe.session.user
        cond_doc.deletion_reason = reason
        cond_doc.db_update()
        
        # Commit immediately
        frappe.db.commit()
        
        # Reload parent chart to reflect changes
        chart.reload()
        
        # Update tooth status
        update_tooth_status(chart, [cond_doc.tooth_number])
        
        return {
            "message": "Condition removed successfully",
            "data": {
                "condition_name": condition_name,
                "tooth_number": cond_doc.tooth_number
            }
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Remove Condition Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error removing condition: {str(e)}"
        }


# ============================================================================
# PROCEDURE MANAGEMENT
# ============================================================================

@frappe.whitelist(methods=['POST'])
def add_procedure(patient_id, tooth_numbers, procedure):
    """
    Add dental procedure to specified teeth
    """
    try:
        validate_patient_access(patient_id)
        
        # Parse parameters
        if isinstance(tooth_numbers, str):
            tooth_numbers = json.loads(tooth_numbers)
        if isinstance(procedure, str):
            procedure = json.loads(procedure)
        
        # Validate
        if not tooth_numbers or not isinstance(tooth_numbers, list):
            frappe.throw(_("tooth_numbers must be a non-empty list"))
        
        if not procedure.get("name"):
            frappe.throw(_("procedure name is required"))
        
        # Get or create chart
        chart = get_or_create_chart(patient_id)
        
        affected_teeth = set()
        
        # Add procedure for each tooth
        for tooth_num in tooth_numbers:
            tooth_num = int(tooth_num)
            
            if not is_valid_tooth_number(tooth_num):
                continue
            
            chart.append("procedures", {
                "tooth_number": tooth_num,
                "name_of_procedure": procedure.get("name"),
                "status": procedure.get("status", "planned"),
                "notes": procedure.get("notes", ""),
                "date": procedure.get("date", nowdate()),
                "cost": procedure.get("cost", 0),
                "duration_minutes": procedure.get("duration_minutes", 0),
                "created_by": frappe.session.user,
                "is_deleted": 0
            })
            
            affected_teeth.add(tooth_num)
        
        # Save chart
        chart.save(ignore_permissions=True)
        frappe.db.commit()
        
        # Collect newly created procedures
        created_procedures = []
        new_procedure_docs = []
        
        for proc in reversed(chart.procedures):
            if not proc.is_deleted and proc.tooth_number in affected_teeth:
                proc_doc = frappe.get_doc("Dental Chart Procedure", proc.name)
                
                if len(proc_doc.timeline) == 0:
                    new_procedure_docs.append(proc_doc)
                    created_procedures.append({
                        "name": proc.name,
                        "tooth_number": proc.tooth_number,
                        "procedure_name": proc.name_of_procedure
                    })
                    
                    if len(created_procedures) == len(tooth_numbers):
                        break
        
        # Add initial timeline for each new procedure
        for proc_doc in new_procedure_docs:
            proc_doc.append("timeline", {
                "status": proc_doc.status,
                "timestamp": now_datetime(),
                "notes": proc_doc.notes or "",
                "changed_by": frappe.session.user
            })
            proc_doc.save(ignore_permissions=True)
        
        frappe.db.commit()
        
        # Update tooth status
        update_tooth_status(chart, list(affected_teeth))
        
        return {
            "message": "Procedure added successfully",
            "data": {
                "procedures": created_procedures,
                "affected_teeth": list(affected_teeth)
            }
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Add Procedure Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error adding procedure: {str(e)}"
        }


@frappe.whitelist(methods=['POST'])
def update_procedure(patient_id, procedure_name, updates):
    """
    Update a dental procedure using Frappe's name field
    """
    try:
        validate_patient_access(patient_id)
        
        if isinstance(updates, str):
            updates = json.loads(updates)
        
        if not frappe.db.exists("Dental Chart Procedure", procedure_name):
            frappe.local.response["http_status_code"] = 404
            return {
                "exc_type": "NotFoundError",
                "message": f"Procedure {procedure_name} not found"
            }
        
        proc_doc = frappe.get_doc("Dental Chart Procedure", procedure_name)
        chart = frappe.get_doc("Dental Chart", proc_doc.parent)
        
        if chart.patient != patient_id:
            frappe.local.response["http_status_code"] = 403
            return {
                "exc_type": "PermissionError",
                "message": "Procedure does not belong to specified patient"
            }
        
        # Track changes
        has_changes = False
        old_status = proc_doc.status
        
        # Update fields
        if "name" in updates and updates["name"] != proc_doc.name_of_procedure:
            proc_doc.name_of_procedure = updates["name"]
            has_changes = True
        
        if "status" in updates and updates["status"] != proc_doc.status:
            proc_doc.status = updates["status"]
            has_changes = True
        
        if "notes" in updates and updates["notes"] != proc_doc.notes:
            proc_doc.notes = updates["notes"]
            has_changes = True
        
        if "cost" in updates:
            proc_doc.cost = updates["cost"]
            has_changes = True
        
        if "duration_minutes" in updates:
            proc_doc.duration_minutes = updates["duration_minutes"]
            has_changes = True
        
        if "date" in updates:
            proc_doc.date = updates["date"]
            has_changes = True
        
        # Add timeline entry if something changed
        if has_changes:
            proc_doc.append("timeline", {
                "status": proc_doc.status,
                "timestamp": now_datetime(),
                "notes": proc_doc.notes or "",
                "changed_by": frappe.session.user
            })
            
            # Use db_update() for immediate persistence of procedure fields
            proc_doc.db_update()
            
            # Save the timeline entry separately (it's a child table)
            if proc_doc.timeline:
                timeline_entry = proc_doc.timeline[-1]
                frappe.get_doc({
                    "doctype": "Dental Chart Procedure Timeline",
                    "parent": proc_doc.name,
                    "parenttype": "Dental Chart Procedure",
                    "parentfield": "timeline",
                    "status": timeline_entry.status,
                    "timestamp": timeline_entry.timestamp,
                    "notes": timeline_entry.notes,
                    "changed_by": timeline_entry.changed_by
                }).db_insert()
            
            frappe.db.commit()
            chart.reload()
            
            # Update tooth status if status changed
            if old_status != proc_doc.status:
                update_tooth_status(chart, [proc_doc.tooth_number])
        
        return {
            "message": "Procedure updated successfully",
            "data": {
                "procedure_name": procedure_name,
                "tooth_number": proc_doc.tooth_number,
                "updated_at": now_datetime(),
                "changes_made": has_changes
            }
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Update Procedure Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error updating procedure: {str(e)}"
        }


@frappe.whitelist(methods=['POST', 'DELETE'])
def remove_procedure(patient_id, procedure_name, reason=None):
    """
    Soft delete a procedure
    """
    try:
        validate_patient_access(patient_id)
        
        if not frappe.db.exists("Dental Chart Procedure", procedure_name):
            frappe.local.response["http_status_code"] = 404
            return {
                "exc_type": "NotFoundError",
                "message": f"Procedure {procedure_name} not found"
            }
        
        proc_doc = frappe.get_doc("Dental Chart Procedure", procedure_name)
        chart = frappe.get_doc("Dental Chart", proc_doc.parent)
        
        if chart.patient != patient_id:
            frappe.local.response["http_status_code"] = 403
            return {
                "exc_type": "PermissionError",
                "message": "Procedure does not belong to specified patient"
            }
        
        # Soft delete
        proc_doc.is_deleted = 1
        proc_doc.deleted_at = now_datetime()
        proc_doc.deleted_by = frappe.session.user
        proc_doc.deletion_reason = reason
        proc_doc.db_update()
        
        # Commit immediately
        frappe.db.commit()
        
        # Reload parent chart to reflect changes
        chart.reload()
        
        # Update tooth status
        update_tooth_status(chart, [proc_doc.tooth_number])
        
        return {
            "message": "Procedure removed successfully",
            "data": {
                "procedure_name": procedure_name,
                "tooth_number": proc_doc.tooth_number
            }
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Remove Procedure Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error removing procedure: {str(e)}"
        }


# ============================================================================
# GET DENTAL CHART
# ============================================================================

@frappe.whitelist(methods=['GET'])
def get_dental_chart(patient_id):
    """
    Get complete dental chart with conditions, procedures, history, and timeline
    """
    try:
        validate_patient_access(patient_id)
        
        # Get chart
        chart_name = frappe.db.get_value("Dental Chart", {"patient": patient_id}, "name")
        if not chart_name:
            return {
                "message": "No dental chart found",
                "data": None
            }
        
        chart_doc = frappe.get_doc("Dental Chart", chart_name)
        
        # Build response grouped by tooth
        teeth_data = {}
        summary_stats = {
            "total_teeth_affected": 0,
            "total_conditions": 0,
            "total_procedures": 0,
            "completed_procedures": 0,
            "planned_procedures": 0,
            "in_progress_procedures": 0
        }
        
        # Process conditions
        for cond in chart_doc.conditions:
            # Skip deleted conditions (check both truthy and explicit 1)
            if cond.is_deleted or cond.get('is_deleted') == 1:
                continue
            
            tooth_num = str(cond.tooth_number)
            if tooth_num not in teeth_data:
                teeth_data[tooth_num] = {
                    "tooth_number": cond.tooth_number,
                    "status": "healthy",  # Default, will be recalculated later
                    "conditions": [],
                    "procedures": []
                }
            
            # Get history from database
            history_records = frappe.get_all(
                "Dental Chart Condition History",
                filters={"parent": cond.name},
                fields=["type", "severity", "notes", "timestamp", "updated_by"],
                order_by="timestamp asc"
            )
            
            history = [
                {
                    "type": h.type,
                    "severity": h.severity,
                    "notes": h.notes,
                    "timestamp": cstr(h.timestamp),
                    "updated_by": h.updated_by
                }
                for h in history_records
            ]
            
            teeth_data[tooth_num]["conditions"].append({
                "name": cond.name,  # Frappe's unique ID
                "type": cond.type,
                "severity": cond.severity,
                "notes": cond.notes,
                "date": cstr(cond.date),
                "created_at": cstr(cond.creation),
                "updated_at": cstr(cond.modified),
                "created_by": cond.created_by,
                "history": history
            })
            
            summary_stats["total_conditions"] += 1
        
        # Process procedures
        for proc in chart_doc.procedures:
            # Skip deleted procedures (check both truthy and explicit 1)
            if proc.is_deleted or proc.get('is_deleted') == 1:
                continue
            
            tooth_num = str(proc.tooth_number)
            if tooth_num not in teeth_data:
                teeth_data[tooth_num] = {
                    "tooth_number": proc.tooth_number,
                    "status": "healthy",  # Default, will be recalculated later
                    "conditions": [],
                    "procedures": []
                }
            
            # Get timeline from database
            timeline_records = frappe.get_all(
                "Dental Chart Procedure Timeline",
                filters={"parent": proc.name},
                fields=["status", "timestamp", "notes", "changed_by"],
                order_by="timestamp asc"
            )
            
            timeline = [
                {
                    "status": t.status,
                    "timestamp": cstr(t.timestamp),
                    "notes": t.notes,
                    "changed_by": t.changed_by
                }
                for t in timeline_records
            ]
            
            teeth_data[tooth_num]["procedures"].append({
                "name": proc.name,  # Frappe's unique ID
                "procedure_name": proc.name_of_procedure,
                "status": proc.status,
                "notes": proc.notes,
                "date": cstr(proc.date),
                "cost": proc.cost,
                "duration_minutes": proc.duration_minutes,
                "created_at": cstr(proc.creation),
                "updated_at": cstr(proc.modified),
                "created_by": proc.created_by,
                "timeline": timeline
            })
            
            summary_stats["total_procedures"] += 1
            if proc.status == "completed":
                summary_stats["completed_procedures"] += 1
            elif proc.status == "planned":
                summary_stats["planned_procedures"] += 1
            elif proc.status == "in-progress":
                summary_stats["in_progress_procedures"] += 1
        
        # Calculate tooth status based on procedures and conditions
        for tooth_num, tooth_data in teeth_data.items():
            status = "healthy"
            
            # Check procedures first (higher priority)
            if tooth_data["procedures"]:
                for proc in tooth_data["procedures"]:
                    if proc["status"] == "in-progress":
                        status = "in-treatment"
                        break
                    elif proc["status"] == "planned":
                        status = "in-treatment"
                        break
                    elif proc["status"] == "completed":
                        # If procedure completed but still has conditions, mark as has-condition
                        if tooth_data["conditions"]:
                            status = "has-condition"
                        else:
                            status = "treated"
            
            # If no active procedures but has conditions
            if status == "healthy" and tooth_data["conditions"]:
                status = "has-condition"
            
            tooth_data["status"] = status
        
        summary_stats["total_teeth_affected"] = len(teeth_data)
        
        return {
            "message": "Dental chart retrieved successfully",
            "data": {
                "patient_id": patient_id,
                "chart_type": chart_doc.chart_type,
                "last_updated": cstr(chart_doc.modified),
                "teeth": teeth_data,
                "summary": summary_stats
            }
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Get Dental Chart Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error retrieving dental chart: {str(e)}"
        }


# ============================================================================
# REPORTING & ANALYTICS
# ============================================================================

@frappe.whitelist(methods=['GET'])
def get_chart_summary(patient_id):
    """
    Generates comprehensive summary report for dental chart
    """
    try:
        # Get dental chart
        chart_response = get_dental_chart(patient_id)
        if chart_response.get("exc_type"):
            return chart_response
        
        chart_data = chart_response["data"]
        if not chart_data:
             return {
                "message": "No dental chart found",
                "data": None
            }

        teeth_data = chart_data["teeth"]
        
        # Get patient info
        patient = frappe.get_doc("Patient", patient_id)
        
        # Build statistics
        statistics = chart_data["summary"].copy()
        
        # Calculate financial info
        total_treatment_cost = 0
        for tooth_num, tooth_data in teeth_data.items():
            for proc in tooth_data["procedures"]:
                if proc.get("cost"):
                    total_treatment_cost += proc["cost"]
        
        statistics["total_treatment_cost"] = total_treatment_cost
        statistics["paid_amount"] = 0  # TODO: Link to invoices
        statistics["pending_amount"] = total_treatment_cost
        
        # Group conditions by type
        conditions_by_type = {}
        for tooth_num, tooth_data in teeth_data.items():
            for cond in tooth_data["conditions"]:
                cond_type = cond["type"]
                if cond_type not in conditions_by_type:
                    conditions_by_type[cond_type] = {
                        "count": 0,
                        "teeth": []
                    }
                conditions_by_type[cond_type]["count"] += 1
                conditions_by_type[cond_type]["teeth"].append(int(tooth_num))
        
        # Group procedures by status
        procedures_by_status = {
            "planned": [],
            "in-progress": [],
            "completed": [],
            "cancelled": []
        }
        
        for tooth_num, tooth_data in teeth_data.items():
            for proc in tooth_data["procedures"]:
                status = proc.get("status", "planned")
                if status not in procedures_by_status:
                    procedures_by_status[status] = []
                    
                procedures_by_status[status].append({
                    "tooth_number": int(tooth_num),
                    "procedure": proc["procedure_name"],
                    "cost": proc.get("cost", 0),
                    "date": proc["date"]
                })
        
        # Build timeline by date
        timeline_items = []
        for tooth_num, tooth_data in teeth_data.items():
            for cond in tooth_data["conditions"]:
                timeline_items.append({
                    "date": cond["date"],
                    "tooth_number": int(tooth_num),
                    "type": "condition",
                    "details": f"{cond['type'].replace('-', ' ').title()} detected",
                    "timestamp": cond["created_at"]
                })
            
            for proc in tooth_data["procedures"]:
                timeline_items.append({
                    "date": proc["date"],
                    "tooth_number": int(tooth_num),
                    "type": "procedure",
                    "details": f"{proc['procedure_name']} - {proc['status'].replace('-', ' ').title()}",
                    "timestamp": proc["created_at"]
                })
        
        # Sort timeline by date (newest first)
        timeline_items.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Group by date
        timeline_by_date = []
        current_date = None
        current_items = []
        
        for item in timeline_items:
            if item["date"] != current_date:
                if current_items:
                    timeline_by_date.append({
                        "date": current_date,
                        "items": current_items
                    })
                current_date = item["date"]
                current_items = []
            
            current_items.append({
                "tooth_number": item["tooth_number"],
                "type": item["type"],
                "details": item["details"]
            })
        
        if current_items:
            timeline_by_date.append({
                "date": current_date,
                "items": current_items
            })
        
        return {
            "message": "Chart summary generated successfully",
            "data": {
                "patient_id": patient_id,
                "patient_name": patient.patient_name,
                "generated_at": cstr(now_datetime()),
                "statistics": statistics,
                "conditions_by_type": conditions_by_type,
                "procedures_by_status": procedures_by_status,
                "timeline_by_date": timeline_by_date
            }
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Get Chart Summary Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error generating chart summary: {str(e)}"
        }


@frappe.whitelist(methods=['GET'])
def export_chart(patient_id, format="json"):
    """
    Exports dental chart in specified format
    """
    try:
        # Get chart data
        chart_response = get_dental_chart(patient_id)
        if chart_response.get("exc_type"):
            return chart_response
        
        if format == "json":
            return {
                "message": "Chart exported successfully",
                "data": {
                    "export_format": "json",
                    "chart_data": chart_response["data"]
                }
            }
        elif format == "pdf":
            # TODO: Implement PDF generation
            frappe.local.response["http_status_code"] = 501
            return {
                "exc_type": "NotImplementedError",
                "message": "PDF export not yet implemented"
            }
        elif format == "excel":
            # TODO: Implement Excel generation
            frappe.local.response["http_status_code"] = 501
            return {
                "exc_type": "NotImplementedError",
                "message": "Excel export not yet implemented"
            }
        else:
            frappe.local.response["http_status_code"] = 400
            return {
                "exc_type": "ValidationError",
                "message": "Invalid format. Supported formats: json, pdf, excel"
            }
        
    except Exception as e:
        frappe.log_error(str(e), "Export Chart Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error exporting chart: {str(e)}"
        }


@frappe.whitelist(methods=['GET'])
def get_treatment_progress(patient_id, from_date=None, to_date=None):
    """
    Tracks treatment progress over time
    """
    try:
        # Get chart data
        chart_response = get_dental_chart(patient_id)
        if chart_response.get("exc_type"):
            return chart_response
        
        chart_data = chart_response["data"]
        if not chart_data:
             return {
                "message": "No dental chart found",
                "data": None
            }
            
        teeth_data = chart_data["teeth"]
        
        # Calculate completion percentage
        total_procedures = chart_data["summary"]["total_procedures"]
        completed_procedures = chart_data["summary"]["completed_procedures"]
        
        completion_percentage = 0
        if total_procedures > 0:
            completion_percentage = int((completed_procedures / total_procedures) * 100)
        
        # Get upcoming procedures
        upcoming_procedures = []
        for tooth_num, tooth_data in teeth_data.items():
            for proc in tooth_data["procedures"]:
                if proc["status"] in ["planned", "in-progress"]:
                    upcoming_procedures.append({
                        "tooth_number": int(tooth_num),
                        "procedure": proc["procedure_name"],
                        "scheduled_date": proc["date"],
                        "estimated_cost": proc.get("cost", 0),
                        "status": proc["status"]
                    })
        
        # Sort by date
        upcoming_procedures.sort(key=lambda x: x["scheduled_date"])
        
        return {
            "message": "Treatment progress retrieved successfully",
            "data": {
                "patient_id": patient_id,
                "period": {
                    "from": from_date or "N/A",
                    "to": to_date or "N/A"
                },
                "completion_percentage": completion_percentage,
                "upcoming_procedures": upcoming_procedures
            }
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Get Treatment Progress Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error retrieving treatment progress: {str(e)}"
        }


@frappe.whitelist(methods=['GET'])
def get_condition_history(patient_id, condition_name):
    """
    Retrieves complete history for a specific condition
    """
    try:
        # Get chart
        chart_name = frappe.db.get_value("Dental Chart", {"patient": patient_id}, "name")
        if not chart_name:
            frappe.local.response["http_status_code"] = 404
            return {
                "exc_type": "NotFound",
                "message": "Dental chart not found"
            }
        
        chart = frappe.get_doc("Dental Chart", chart_name)
        
        # Find condition in chart.conditions
        for cond in chart.conditions:
            if cond.name == condition_name:
                # Build history
                history = []
                # Fetch history from DB
                history_records = frappe.get_all(
                    "Dental Chart Condition History",
                    filters={"parent": cond.name},
                    fields=["type", "severity", "notes", "timestamp", "updated_by"],
                    order_by="timestamp asc"
                )
                
                for hist in history_records:
                    history.append({
                        "type": hist.type,
                        "severity": hist.severity,
                        "notes": hist.notes,
                        "timestamp": cstr(hist.timestamp),
                        "updated_by": hist.updated_by
                    })
                
                return {
                    "message": "Condition history retrieved successfully",
                    "data": {
                        "condition_name": condition_name,
                        "tooth_number": cond.tooth_number,
                        "current_type": cond.type,
                        "current_severity": cond.severity,
                        "history": history,
                        "total_updates": len(history)
                    }
                }
        
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": "Condition not found"
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Get Condition History Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error retrieving condition history: {str(e)}"
        }


@frappe.whitelist(methods=['GET'])
def get_procedure_timeline(patient_id, procedure_name):
    """
    Retrieves complete timeline history for a specific procedure
    """
    try:
        # Get chart
        chart_name = frappe.db.get_value("Dental Chart", {"patient": patient_id}, "name")
        if not chart_name:
            frappe.local.response["http_status_code"] = 404
            return {
                "exc_type": "NotFound",
                "message": "Dental chart not found"
            }
        
        chart = frappe.get_doc("Dental Chart", chart_name)
        
        # Find procedure in chart.procedures
        for proc in chart.procedures:
            if proc.name == procedure_name:
                # Build timeline
                timeline = []
                # Fetch timeline from DB
                timeline_records = frappe.get_all(
                    "Dental Chart Procedure Timeline",
                    filters={"parent": proc.name},
                    fields=["status", "timestamp", "notes", "changed_by"],
                    order_by="timestamp asc"
                )
                
                for tl in timeline_records:
                    timeline.append({
                        "status": tl.status,
                        "timestamp": cstr(tl.timestamp),
                        "notes": tl.notes,
                        "changed_by": tl.changed_by
                    })
                
                return {
                    "message": "Procedure timeline retrieved successfully",
                    "data": {
                        "procedure_name": procedure_name,
                        "procedure_label": proc.name_of_procedure,
                        "tooth_number": proc.tooth_number,
                        "current_status": proc.status,
                        "timeline": timeline,
                        "total_sessions": len(timeline)
                    }
                }
        
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": "Procedure not found"
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Get Procedure Timeline Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error retrieving procedure timeline: {str(e)}"
        }


# ============================================================================
# CONFIGURATION
# ============================================================================

@frappe.whitelist(methods=['GET'])
def get_chart_types():
    """
    Returns available chart types with tooth numbering information
    """
    try:
        chart_types = [
            {
                "type": "adult",
                "label": "Adult Dentition",
                "tooth_numbers": {
                    "upper": [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28],
                    "lower": [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38]
                },
                "total_teeth": 32,
                "numbering_system": "FDI World Dental Federation notation"
            },
            {
                "type": "pediatric",
                "label": "Primary Dentition",
                "tooth_numbers": {
                    "upper": [55, 54, 53, 52, 51, 61, 62, 63, 64, 65],
                    "lower": [85, 84, 83, 82, 81, 71, 72, 73, 74, 75]
                },
                "total_teeth": 20,
                "numbering_system": "FDI World Dental Federation notation"
            },
            {
                "type": "mixed",
                "label": "Mixed Dentition",
                "description": "Combination of primary and permanent teeth"
            }
        ]
        
        return {
            "message": "Chart types retrieved successfully",
            "data": chart_types
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Get Chart Types Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error retrieving chart types: {str(e)}"
        }


@frappe.whitelist(methods=['GET'])
def get_tooth_status_options():
    """
    Returns available tooth status values
    """
    try:
        status_options = [
            {
                "value": "healthy",
                "label": "Healthy",
                "description": "No conditions or procedures",
                "color": "#FFFFFF"
            },
            {
                "value": "has-condition",
                "label": "Has Condition",
                "description": "Condition identified, treatment not started",
                "color": "#FEF3C7"
            },
            {
                "value": "in-treatment",
                "label": "In Treatment",
                "description": "Active treatment in progress",
                "color": "#CFFAFE"
            },
            {
                "value": "treated",
                "label": "Treated",
                "description": "Treatment completed successfully",
                "color": "#D1FAE5"
            }
        ]
        
        return {
            "message": "Tooth status options retrieved successfully",
            "data": status_options
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Get Tooth Status Options Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error retrieving tooth status options: {str(e)}"
        }


@frappe.whitelist(methods=['GET'])
def get_condition_types():
    """
    Returns list of available condition types
    """
    try:
        condition_types = [
            {
                "value": "cavity",
                "label": "Cavity",
                "description": "Tooth decay or dental caries",
                "severity_options": ["mild", "moderate", "severe"]
            },
            {
                "value": "crown",
                "label": "Crown",
                "description": "Dental crown placement",
                "severity_options": None
            },
            {
                "value": "bridge",
                "label": "Bridge",
                "description": "Dental bridge",
                "severity_options": None
            },
            {
                "value": "implant",
                "label": "Implant",
                "description": "Dental implant",
                "severity_options": None
            },
            {
                "value": "root-canal",
                "label": "Root Canal",
                "description": "Root canal treatment needed",
                "severity_options": ["mild", "moderate", "severe"]
            },
            {
                "value": "extraction",
                "label": "Extraction",
                "description": "Tooth extraction needed",
                "severity_options": None
            },
            {
                "value": "filling",
                "label": "Filling",
                "description": "Dental filling",
                "severity_options": None
            },
            {
                "value": "fracture",
                "label": "Fracture",
                "description": "Tooth fracture",
                "severity_options": ["mild", "moderate", "severe"]
            },
            {
                "value": "abscess",
                "label": "Abscess",
                "description": "Dental abscess",
                "severity_options": ["mild", "moderate", "severe"]
            },
            {
                "value": "other",
                "label": "Other",
                "description": "Other condition",
                "severity_options": None
            }
        ]
        
        return {
            "message": "Condition types retrieved successfully",
            "data": condition_types
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Get Condition Types Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error retrieving condition types: {str(e)}"
        }


@frappe.whitelist(methods=['GET'])
def get_procedure_types():
    """
    Returns list of common dental procedures
    """
    try:
        procedure_types = [
            {
                "name": "Cleaning",
                "default_cost": 500,
                "default_duration": 30,
                "description": "Regular dental cleaning"
            },
            {
                "name": "Filling",
                "default_cost": 1500,
                "default_duration": 45,
                "description": "Dental filling"
            },
            {
                "name": "Root Canal Treatment",
                "default_cost": 3000,
                "default_duration": 90,
                "description": "Endodontic treatment"
            },
            {
                "name": "Crown",
                "default_cost": 5000,
                "default_duration": 60,
                "description": "Dental crown placement"
            },
            {
                "name": "Extraction",
                "default_cost": 2000,
                "default_duration": 30,
                "description": "Tooth extraction"
            },
            {
                "name": "Bridge",
                "default_cost": 8000,
                "default_duration": 90,
                "description": "Dental bridge"
            },
            {
                "name": "Implant",
                "default_cost": 15000,
                "default_duration": 120,
                "description": "Dental implant"
            },
            {
                "name": "Whitening",
                "default_cost": 3000,
                "default_duration": 60,
                "description": "Teeth whitening"
            }
        ]
        
        return {
            "message": "Procedure types retrieved successfully",
            "data": procedure_types
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Get Procedure Types Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error retrieving procedure types: {str(e)}"
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def validate_patient_access(patient_id):
    """Validate if current practitioner has access to patient's clinic"""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Please login to access dental chart"), frappe.PermissionError)
        
    practitioner = frappe.db.get_value("Healthcare Practitioner", {"user_id": user}, "name")
    if practitioner:
        resolved_clinic = clinic_helper.resolve_active_clinic(practitioner, None)
        if resolved_clinic:
            # Check if patient belongs to a different clinic
            # Only enforce if patient has a primary clinic assigned
            patient_clinic = frappe.db.get_value("Patient", patient_id, "primary_clinic")
            if patient_clinic and patient_clinic != resolved_clinic:
                 frappe.throw(_("Access denied: Patient belongs to a different clinic"), frappe.PermissionError)


def get_or_create_chart(patient_id):
    """Get existing chart or create new one"""
    chart_name = frappe.db.get_value("Dental Chart", {"patient": patient_id}, "name")
    
    if chart_name:
        return frappe.get_doc("Dental Chart", chart_name)
    
    # Create new chart
    chart = frappe.get_doc({
        "doctype": "Dental Chart",
        "patient": patient_id,
        "chart_type": "adult"
    })
    chart.insert(ignore_permissions=True)
    frappe.db.commit()
    
    return chart


def is_valid_tooth_number(tooth_number):
    """Validate tooth number (1-32 for adult, 51-85 for child)"""
    return (1 <= tooth_number <= 32) or (51 <= tooth_number <= 85)


def update_tooth_status(chart, tooth_numbers):
    """Update status for specified teeth based on conditions and procedures"""
    for tooth_num in tooth_numbers:
        # Check if tooth has active conditions
        has_condition = any(
            c.tooth_number == tooth_num and not c.is_deleted
            for c in chart.conditions
        )
        
        # Check if tooth has active procedures
        has_procedure = any(
            p.tooth_number == tooth_num and not p.is_deleted
            for p in chart.procedures
        )
        
        # Determine status
        if has_condition and has_procedure:
            status = "in-treatment"
        elif has_condition:
            status = "has-condition"
        elif has_procedure:
            status = "in-treatment"
        else:
            status = "healthy"
        
        # Update or create tooth record
        tooth_found = False
        for tooth in chart.teeth:
            if tooth.tooth_number == tooth_num:
                tooth.status = status
                tooth_found = True
                break
        
        if not tooth_found:
            chart.append("teeth", {
                "tooth_number": tooth_num,
                "status": status
            })
    
    chart.save(ignore_permissions=True)
    frappe.db.commit()


def calculate_tooth_status(chart, tooth_number):
    """Calculate tooth status (kept for backwards compatibility)"""
    has_condition = any(
        c.tooth_number == tooth_number and not c.is_deleted
        for c in chart.conditions
    )
    
    has_procedure = any(
        p.tooth_number == tooth_number and not p.is_deleted
        for p in chart.procedures
    )
    
    if has_condition and has_procedure:
        return "in-treatment"
    elif has_condition:
        return "has-condition"
    elif has_procedure:
        return "in-treatment"
    else:
        return "healthy"
