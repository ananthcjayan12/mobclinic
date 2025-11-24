import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, cstr, getdate
import json
from datetime import datetime


# ============================================================================
# CORE DENTAL CHART MANAGEMENT
# ============================================================================

@frappe.whitelist(methods=['GET'])
def get_dental_chart(patient_id, chart_type=None):
    """
    Retrieves complete dental chart for a patient
    
    Args:
        patient_id (str): Patient ID
        chart_type (str): Optional chart type filter
        
    Returns:
        dict: Complete dental chart with teeth, conditions, and procedures
    """
    try:
        # Validate patient
        if not frappe.db.exists("Patient", patient_id):
            frappe.local.response["http_status_code"] = 404
            return {
                "exc_type": "NotFound",
                "message": f"Patient {patient_id} not found"
            }
        
        # Get or create dental chart
        chart = frappe.db.get_value("Dental Chart", {"patient": patient_id}, "name")
        
        if not chart:
            # Return empty chart structure
            return {
                "message": "Dental chart retrieved successfully",
                "data": {
                    "patient_id": patient_id,
                    "chart_type": chart_type or "adult",
                    "last_updated": None,
                    "teeth": {},
                    "summary": {
                        "total_teeth_affected": 0,
                        "total_conditions": 0,
                        "total_procedures": 0,
                        "completed_procedures": 0,
                        "planned_procedures": 0,
                        "in_progress_procedures": 0
                    }
                }
            }
        
        # Get chart document
        chart_doc = frappe.get_doc("Dental Chart", chart)
        
        # Build teeth data structure
        teeth_data = {}
        summary_stats = {
            "total_teeth_affected": 0,
            "total_conditions": 0,
            "total_procedures": 0,
            "completed_procedures": 0,
            "planned_procedures": 0,
            "in_progress_procedures": 0
        }
        
        for tooth in chart_doc.teeth:
            tooth_number = str(tooth.tooth_number)
            
            # Get non-deleted conditions
            conditions = []
            for cond in tooth.conditions:
                if not cond.is_deleted:
                    conditions.append({
                        "id": cond.condition_id,
                        "type": cond.type,
                        "severity": cond.severity,
                        "notes": cond.notes,
                        "date": cstr(cond.date),
                        "created_at": cstr(cond.creation),
                        "updated_at": cstr(cond.modified),
                        "created_by": cond.created_by
                    })
                    summary_stats["total_conditions"] += 1
            
            # Get non-deleted procedures
            procedures = []
            for proc in tooth.procedures:
                if not proc.is_deleted:
                    # Get timeline
                    timeline = []
                    for tl in proc.timeline:
                        timeline.append({
                            "status": tl.status,
                            "timestamp": cstr(tl.timestamp),
                            "notes": tl.notes,
                            "changed_by": tl.changed_by
                        })
                    
                    procedures.append({
                        "id": proc.procedure_id,
                        "name": proc.name_of_procedure,
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
            
            # Only include teeth with conditions or procedures
            if conditions or procedures:
                teeth_data[tooth_number] = {
                    "tooth_number": tooth.tooth_number,
                    "status": tooth.status,
                    "conditions": sorted(conditions, key=lambda x: x["created_at"], reverse=True),
                    "procedures": sorted(procedures, key=lambda x: x["created_at"], reverse=True)
                }
                summary_stats["total_teeth_affected"] += 1
        
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


@frappe.whitelist(methods=['POST'])
def save_dental_chart(patient_id, chart_type="adult", teeth_data=None):
    """
    Saves complete dental chart data
    
    Args:
        patient_id (str): Patient ID
        chart_type (str): Chart type
        teeth_data (dict): Teeth data to save
        
    Returns:
        dict: Save status with statistics
    """
    try:
        # Validate patient
        if not frappe.db.exists("Patient", patient_id):
            frappe.local.response["http_status_code"] = 404
            return {
                "exc_type": "NotFound",
                "message": f"Patient {patient_id} not found"
            }
        
        # Parse teeth_data if string
        if isinstance(teeth_data, str):
            teeth_data = json.loads(teeth_data)
        
        if not teeth_data:
            teeth_data = {}
        
        # Get or create dental chart
        chart_name = frappe.db.get_value("Dental Chart", {"patient": patient_id}, "name")
        
        if chart_name:
            chart = frappe.get_doc("Dental Chart", chart_name)
        else:
            chart = frappe.new_doc("Dental Chart")
            chart.patient = patient_id
            chart.chart_type = chart_type
        
        # Track changes
        updated_teeth = []
        new_conditions = 0
        new_procedures = 0
        updated_procedures = 0
        
        # Process each tooth
        for tooth_number, tooth_data in teeth_data.items():
            tooth_number = int(tooth_number)
            
            # Find or create tooth record
            tooth_doc = None
            for t in chart.teeth:
                if t.tooth_number == tooth_number:
                    tooth_doc = t
                    break
            
            if not tooth_doc:
                tooth_doc = chart.append("teeth", {})
                tooth_doc.tooth_number = tooth_number
            
            # Update tooth status
            tooth_doc.status = tooth_data.get("status", "healthy")
            
            # Process conditions
            if "conditions" in tooth_data:
                for cond_data in tooth_data["conditions"]:
                    if cond_data.get("id"):
                        # Update existing condition
                        for cond in tooth_doc.conditions:
                            if cond.condition_id == cond_data["id"]:
                                cond.type = cond_data.get("type", cond.type)
                                cond.severity = cond_data.get("severity", cond.severity)
                                cond.notes = cond_data.get("notes", cond.notes)
                                cond.date = cond_data.get("date", cond.date)
                                break
                    else:
                        # Create new condition
                        condition_id = generate_condition_id(patient_id, tooth_number)
                        tooth_doc.append("conditions", {
                            "condition_id": condition_id,
                            "type": cond_data["type"],
                            "severity": cond_data.get("severity"),
                            "notes": cond_data.get("notes"),
                            "date": cond_data.get("date", nowdate()),
                            "created_by": frappe.session.user
                        })
                        new_conditions += 1
            
            # Process procedures
            if "procedures" in tooth_data:
                for proc_data in tooth_data["procedures"]:
                    if proc_data.get("id"):
                        # Update existing procedure
                        for proc in tooth_doc.procedures:
                            if proc.procedure_id == proc_data["id"]:
                                old_status = proc.status
                                proc.name_of_procedure = proc_data.get("name", proc.name_of_procedure)
                                proc.status = proc_data.get("status", proc.status)
                                proc.notes = proc_data.get("notes", proc.notes)
                                proc.date = proc_data.get("date", proc.date)
                                proc.cost = proc_data.get("cost", proc.cost)
                                proc.duration_minutes = proc_data.get("duration_minutes", proc.duration_minutes)
                                
                                # Add timeline entry if status changed
                                if old_status != proc.status:
                                    proc.append("timeline", {
                                        "status": proc.status,
                                        "timestamp": now_datetime(),
                                        "notes": proc_data.get("notes", ""),
                                        "changed_by": frappe.session.user
                                    })
                                
                                updated_procedures += 1
                                break
                    else:
                        # Create new procedure
                        procedure_id = generate_procedure_id(patient_id, tooth_number)
                        new_proc = tooth_doc.append("procedures", {
                            "procedure_id": procedure_id,
                            "name_of_procedure": proc_data["name"],
                            "status": proc_data.get("status", "planned"),
                            "notes": proc_data.get("notes"),
                            "date": proc_data.get("date", nowdate()),
                            "cost": proc_data.get("cost"),
                            "duration_minutes": proc_data.get("duration_minutes"),
                            "created_by": frappe.session.user
                        })
                        
                        # Add initial timeline entry
                        new_proc.append("timeline", {
                            "status": proc_data.get("status", "planned"),
                            "timestamp": now_datetime(),
                            "notes": proc_data.get("notes", ""),
                            "changed_by": frappe.session.user
                        })
                        
                        new_procedures += 1
            
            # Recalculate tooth status
            tooth_doc.status = calculate_tooth_status(tooth_doc)
            
            if tooth_number not in updated_teeth:
                updated_teeth.append(tooth_number)
        
        # Save chart
        if chart.is_new():
            chart.insert(ignore_permissions=True)
        else:
            chart.save(ignore_permissions=True)
        
        frappe.db.commit()
        
        return {
            "message": "Dental chart saved successfully",
            "data": {
                "patient_id": patient_id,
                "updated_teeth": updated_teeth,
                "new_conditions": new_conditions,
                "new_procedures": new_procedures,
                "updated_procedures": updated_procedures
            }
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Save Dental Chart Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error saving dental chart: {str(e)}"
        }


# ============================================================================
# CONDITION MANAGEMENT
# ============================================================================

@frappe.whitelist(methods=['POST'])
def add_condition(patient_id, tooth_numbers, condition):
    """
    Adds a condition to one or multiple teeth
    
    Args:
        patient_id (str): Patient ID
        tooth_numbers (list): List of tooth numbers
        condition (dict): Condition data
        
    Returns:
        dict: Created condition IDs
    """
    try:
        # Parse parameters
        if isinstance(tooth_numbers, str):
            tooth_numbers = json.loads(tooth_numbers)
        if isinstance(condition, str):
            condition = json.loads(condition)
        
        # Validate
        if not tooth_numbers:
            frappe.local.response["http_status_code"] = 400
            return {
                "exc_type": "ValidationError",
                "message": "Tooth numbers are required"
            }
        
        # Get or create chart
        chart = get_or_create_chart(patient_id)
        
        condition_ids = []
        
        for tooth_number in tooth_numbers:
            tooth_number = int(tooth_number)
            
            # Validate tooth number
            if not is_valid_tooth_number(tooth_number):
                continue
            
            # Find or create tooth
            tooth_doc = None
            for t in chart.teeth:
                if t.tooth_number == tooth_number:
                    tooth_doc = t
                    break
            
            if not tooth_doc:
                tooth_doc = chart.append("teeth", {})
                tooth_doc.tooth_number = tooth_number
                tooth_doc.status = "healthy"
            
            # Generate condition ID
            condition_id = generate_condition_id(patient_id, tooth_number)
            
            # Add condition
            tooth_doc.append("conditions", {
                "condition_id": condition_id,
                "type": condition["type"],
                "severity": condition.get("severity"),
                "notes": condition.get("notes"),
                "date": condition.get("date", nowdate()),
                "created_by": frappe.session.user
            })
            
            # Update tooth status
            tooth_doc.status = calculate_tooth_status(tooth_doc)
            
            condition_ids.append(condition_id)
        
        chart.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "message": "Condition added successfully",
            "data": {
                "condition_ids": condition_ids,
                "affected_teeth": tooth_numbers
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
def update_condition(patient_id, tooth_number, condition_id, updates):
    """
    Updates an existing tooth condition
    """
    try:
        # Parse parameters
        if isinstance(updates, str):
            updates = json.loads(updates)
        
        tooth_number = int(tooth_number)
        
        # Get chart
        chart = get_or_create_chart(patient_id)
        
        # Find tooth and condition
        for tooth in chart.teeth:
            if tooth.tooth_number == tooth_number:
                for cond in tooth.conditions:
                    if cond.condition_id == condition_id:
                        # Update fields
                        if "severity" in updates:
                            cond.severity = updates["severity"]
                        if "notes" in updates:
                            cond.notes = updates["notes"]
                        if "type" in updates:
                            cond.type = updates["type"]
                        if "date" in updates:
                            cond.date = updates["date"]
                        
                        chart.save(ignore_permissions=True)
                        frappe.db.commit()
                        
                        return {
                            "message": "Condition updated successfully",
                            "data": {
                                "condition_id": condition_id,
                                "tooth_number": tooth_number,
                                "updated_at": cstr(now_datetime())
                            }
                        }
        
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": "Condition not found"
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Update Condition Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error updating condition: {str(e)}"
        }


@frappe.whitelist(methods=['POST', 'DELETE'])
def remove_condition(patient_id, tooth_number, condition_id, reason=None):
    """
    Soft deletes a condition
    """
    try:
        tooth_number = int(tooth_number)
        
        # Get chart
        chart = get_or_create_chart(patient_id)
        
        # Find tooth and condition
        for tooth in chart.teeth:
            if tooth.tooth_number == tooth_number:
                for cond in tooth.conditions:
                    if cond.condition_id == condition_id:
                        # Soft delete
                        cond.is_deleted = 1
                        cond.deleted_at = now_datetime()
                        cond.deleted_by = frappe.session.user
                        cond.deletion_reason = reason
                        
                        # Recalculate tooth status
                        tooth.status = calculate_tooth_status(tooth)
                        
                        chart.save(ignore_permissions=True)
                        frappe.db.commit()
                        
                        return {
                            "message": "Condition removed successfully",
                            "data": {
                                "condition_id": condition_id,
                                "tooth_number": tooth_number,
                                "removed_at": cstr(now_datetime()),
                                "audit_log_created": True
                            }
                        }
        
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": "Condition not found"
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Remove Condition Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error removing condition: {str(e)}"
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


# ============================================================================
# PROCEDURE MANAGEMENT
# ============================================================================

@frappe.whitelist(methods=['POST'])
def add_procedure(patient_id, tooth_numbers, procedure):
    """
    Adds a procedure to one or multiple teeth
    """
    try:
        # Parse parameters
        if isinstance(tooth_numbers, str):
            tooth_numbers = json.loads(tooth_numbers)
        if isinstance(procedure, str):
            procedure = json.loads(procedure)
        
        # Get or create chart
        chart = get_or_create_chart(patient_id)
        
        procedure_ids = []
        
        for tooth_number in tooth_numbers:
            tooth_number = int(tooth_number)
            
            # Find or create tooth
            tooth_doc = None
            for t in chart.teeth:
                if t.tooth_number == tooth_number:
                    tooth_doc = t
                    break
            
            if not tooth_doc:
                tooth_doc = chart.append("teeth", {})
                tooth_doc.tooth_number = tooth_number
                tooth_doc.status = "healthy"
            
            # Generate procedure ID
            procedure_id = generate_procedure_id(patient_id, tooth_number)
            
            # Add procedure
            new_proc = tooth_doc.append("procedures", {
                "procedure_id": procedure_id,
                "name_of_procedure": procedure["name"],
                "status": procedure.get("status", "planned"),
                "notes": procedure.get("notes"),
                "date": procedure.get("date", nowdate()),
                "cost": procedure.get("cost"),
                "duration_minutes": procedure.get("duration_minutes"),
                "created_by": frappe.session.user
            })
            
            # Add initial timeline entry
            new_proc.append("timeline", {
                "status": procedure.get("status", "planned"),
                "timestamp": now_datetime(),
                "notes": procedure.get("notes", ""),
                "changed_by": frappe.session.user
            })
            
            # Update tooth status
            tooth_doc.status = calculate_tooth_status(tooth_doc)
            
            procedure_ids.append(procedure_id)
        
        chart.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "message": "Procedure added successfully",
            "data": {
                "procedure_ids": procedure_ids,
                "affected_teeth": tooth_numbers,
                "timeline_created": True
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
def update_procedure_status(patient_id, tooth_number, procedure_id, status, notes=None, cost=None):
    """
    Updates procedure status and adds timeline entry
    """
    try:
        tooth_number = int(tooth_number)
        
        # Get chart
        chart = get_or_create_chart(patient_id)
        
        # Find tooth and procedure
        for tooth in chart.teeth:
            if tooth.tooth_number == tooth_number:
                for proc in tooth.procedures:
                    if proc.procedure_id == procedure_id:
                        old_status = proc.status
                        timeline_entry_added = False
                        
                        # Update status
                        proc.status = status
                        if notes:
                            proc.notes = notes
                        if cost:
                            proc.cost = cost
                        
                        # Add timeline entry if status changed
                        if old_status != status:
                            proc.append("timeline", {
                                "status": status,
                                "timestamp": now_datetime(),
                                "notes": notes or "",
                                "changed_by": frappe.session.user
                            })
                            timeline_entry_added = True
                        
                        # Recalculate tooth status
                        tooth.status = calculate_tooth_status(tooth)
                        
                        chart.save(ignore_permissions=True)
                        frappe.db.commit()
                        
                        return {
                            "message": "Procedure status updated successfully",
                            "data": {
                                "procedure_id": procedure_id,
                                "tooth_number": tooth_number,
                                "old_status": old_status,
                                "new_status": status,
                                "timeline_entry_added": timeline_entry_added,
                                "updated_at": cstr(now_datetime()),
                                "tooth_status_updated": tooth.status
                            }
                        }
        
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": "Procedure not found"
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Update Procedure Status Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error updating procedure status: {str(e)}"
        }


@frappe.whitelist(methods=['POST'])
def update_procedure(patient_id, tooth_number, procedure_id, updates):
    """
    Updates procedure details without changing status
    """
    try:
        # Parse parameters
        if isinstance(updates, str):
            updates = json.loads(updates)
        
        tooth_number = int(tooth_number)
        
        # Get chart
        chart = get_or_create_chart(patient_id)
        
        # Find tooth and procedure
        for tooth in chart.teeth:
            if tooth.tooth_number == tooth_number:
                for proc in tooth.procedures:
                    if proc.procedure_id == procedure_id:
                        # Update fields
                        if "name" in updates:
                            proc.name_of_procedure = updates["name"]
                        if "notes" in updates:
                            proc.notes = updates["notes"]
                        if "cost" in updates:
                            proc.cost = updates["cost"]
                        if "duration_minutes" in updates:
                            proc.duration_minutes = updates["duration_minutes"]
                        if "date" in updates:
                            proc.date = updates["date"]
                        
                        chart.save(ignore_permissions=True)
                        frappe.db.commit()
                        
                        return {
                            "message": "Procedure updated successfully",
                            "data": {
                                "procedure_id": procedure_id,
                                "tooth_number": tooth_number,
                                "updated_at": cstr(now_datetime())
                            }
                        }
        
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": "Procedure not found"
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Update Procedure Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error updating procedure: {str(e)}"
        }


@frappe.whitelist(methods=['POST', 'DELETE'])
def remove_procedure(patient_id, tooth_number, procedure_id, reason=None):
    """
    Soft deletes a procedure
    """
    try:
        tooth_number = int(tooth_number)
        
        # Get chart
        chart = get_or_create_chart(patient_id)
        
        # Find tooth and procedure
        for tooth in chart.teeth:
            if tooth.tooth_number == tooth_number:
                for proc in tooth.procedures:
                    if proc.procedure_id == procedure_id:
                        # Soft delete
                        proc.is_deleted = 1
                        proc.deleted_at = now_datetime()
                        proc.deleted_by = frappe.session.user
                        proc.deletion_reason = reason
                        
                        # Recalculate tooth status
                        tooth.status = calculate_tooth_status(tooth)
                        
                        chart.save(ignore_permissions=True)
                        frappe.db.commit()
                        
                        return {
                            "message": "Procedure removed successfully",
                            "data": {
                                "procedure_id": procedure_id,
                                "tooth_number": tooth_number,
                                "removed_at": cstr(now_datetime()),
                                "audit_log_created": True
                            }
                        }
        
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": "Procedure not found"
        }
        
    except Exception as e:
        frappe.log_error(str(e), "Remove Procedure Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error removing procedure: {str(e)}"
        }


@frappe.whitelist(methods=['GET'])
def get_procedure_timeline(patient_id, tooth_number, procedure_id):
    """
    Retrieves complete timeline history for a specific procedure
    """
    try:
        tooth_number = int(tooth_number)
        
        # Get chart
        chart_name = frappe.db.get_value("Dental Chart", {"patient": patient_id}, "name")
        if not chart_name:
            frappe.local.response["http_status_code"] = 404
            return {
                "exc_type": "NotFound",
                "message": "Dental chart not found"
            }
        
        chart = frappe.get_doc("Dental Chart", chart_name)
        
        # Find tooth and procedure
        for tooth in chart.teeth:
            if tooth.tooth_number == tooth_number:
                for proc in tooth.procedures:
                    if proc.procedure_id == procedure_id:
                        # Build timeline
                        timeline = []
                        for tl in proc.timeline:
                            timeline.append({
                                "status": tl.status,
                                "timestamp": cstr(tl.timestamp),
                                "notes": tl.notes,
                                "changed_by": tl.changed_by
                            })
                        
                        # Sort by timestamp
                        timeline.sort(key=lambda x: x["timestamp"])
                        
                        return {
                            "message": "Procedure timeline retrieved successfully",
                            "data": {
                                "procedure_id": procedure_id,
                                "procedure_name": proc.name_of_procedure,
                                "tooth_number": tooth_number,
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
                procedures_by_status[proc["status"]].append({
                    "tooth_number": int(tooth_num),
                    "procedure": proc["name"],
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
                    "details": f"{proc['name']} - {proc['status'].replace('-', ' ').title()}",
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
                        "procedure": proc["name"],
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


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_or_create_chart(patient_id, chart_type="adult"):
    """Get existing or create new dental chart"""
    chart_name = frappe.db.get_value("Dental Chart", {"patient": patient_id}, "name")
    
    if chart_name:
        return frappe.get_doc("Dental Chart", chart_name)
    else:
        chart = frappe.new_doc("Dental Chart")
        chart.patient = patient_id
        chart.chart_type = chart_type
        chart.insert(ignore_permissions=True)
        return chart


def generate_condition_id(patient_id, tooth_number):
    """Generate unique condition ID"""
    # Count existing conditions for this tooth
    chart_name = frappe.db.get_value("Dental Chart", {"patient": patient_id}, "name")
    if not chart_name:
        return f"COND-{tooth_number}-001"
    
    chart = frappe.get_doc("Dental Chart", chart_name)
    count = 0
    
    for tooth in chart.teeth:
        if tooth.tooth_number == tooth_number:
            count = len([c for c in tooth.conditions if not c.is_deleted])
            break
    
    sequence = count + 1
    return f"COND-{tooth_number}-{sequence:03d}"


def generate_procedure_id(patient_id, tooth_number):
    """Generate unique procedure ID"""
    # Count existing procedures for this tooth
    chart_name = frappe.db.get_value("Dental Chart", {"patient": patient_id}, "name")
    if not chart_name:
        return f"PROC-{tooth_number}-001"
    
    chart = frappe.get_doc("Dental Chart", chart_name)
    count = 0
    
    for tooth in chart.teeth:
        if tooth.tooth_number == tooth_number:
            count = len([p for p in tooth.procedures if not p.is_deleted])
            break
    
    sequence = count + 1
    return f"PROC-{tooth_number}-{sequence:03d}"


def calculate_tooth_status(tooth_doc):
    """
    Calculate tooth status based on conditions and procedures
    
    Priority order:
    1. Any completed procedure → "treated"
    2. Any in-progress or planned procedure → "in-treatment"
    3. Any condition exists → "has-condition"
    4. Otherwise → "healthy"
    """
    # Get non-deleted procedures
    procedures = [p for p in tooth_doc.procedures if not p.is_deleted]
    
    # Check procedures first
    if any(p.status == "completed" for p in procedures):
        return "treated"
    
    if any(p.status in ["in-progress", "planned"] for p in procedures):
        return "in-treatment"
    
    # Check conditions
    conditions = [c for c in tooth_doc.conditions if not c.is_deleted]
    if len(conditions) > 0:
        return "has-condition"
    
    return "healthy"


def is_valid_tooth_number(tooth_number):
    """Validate tooth number"""
    # Adult teeth: 11-48
    adult_teeth = list(range(11, 49))
    
    # Pediatric teeth
    pediatric_teeth = [51, 52, 53, 54, 55, 61, 62, 63, 64, 65,
                      71, 72, 73, 74, 75, 81, 82, 83, 84, 85]
    
    valid_teeth = adult_teeth + pediatric_teeth
    
    return tooth_number in valid_teeth
