import frappe
from frappe import _
from frappe.utils import cstr, get_datetime, nowdate, add_days, getdate, now_datetime
import json
from datetime import datetime, timedelta

@frappe.whitelist(methods=['GET'])
def get_appointments(filters=None, limit_start=0, limit_page_length=20, order_by="appointment_date desc"):
    """
    Get list of appointments with pagination and filtering
    
    Args:
        filters (str): JSON string of filters
        limit_start (int): Pagination start
        limit_page_length (int): Records per page
        order_by (str): Sort order
        
    Returns:
        dict: List of appointments with pagination info
    """
    try:
        # Parse filters
        if filters:
            if isinstance(filters, str):
                filters = json.loads(filters)
        else:
            filters = {}
        
        # Get current practitioner
        practitioner = get_current_practitioner()
        if practitioner:
            filters["practitioner"] = practitioner.name
        elif frappe.session.user != "Administrator":
            # Only return empty if not Administrator (who can see all)
            return {
                "message": "success",
                "data": [],
                "total_count": 0,
                "page_length": limit_page_length,
                "start": limit_start
            }
        
        # Handle date range filters
        query_filters = dict(filters)
        if "date_from" in query_filters:
            date_from = query_filters.pop("date_from")
            date_to = query_filters.pop("date_to", date_from)
            query_filters["appointment_date"] = ["between", [date_from, date_to]]
        
        # Get appointments
        appointments = frappe.get_all(
            "Patient Appointment",
            fields=[
                "name", "patient", "patient_name", "appointment_date", 
                "appointment_time", "duration", "status", "appointment_type",
                "chief_complaint", "notes", "invoiced", "paid_amount"
            ],
            filters=query_filters,
            limit_start=limit_start,
            limit_page_length=limit_page_length,
            order_by=order_by
        )
        
        # Enhance appointment data
        enhanced_appointments = []
        for appt in appointments:
            patient_data = get_patient_basic_info(appt.get("patient"))
            
            enhanced_appt = dict(appt)
            enhanced_appt.update({
                "patient_mobile": patient_data.get("mobile"),
                "patient_email": patient_data.get("email"),
                "patient_image": patient_data.get("image"),
                "appointment_datetime": f"{appt.get('appointment_date')} {appt.get('appointment_time')}" if appt.get('appointment_time') else appt.get('appointment_date'),
                "booked_via_app": frappe.db.get_value("Patient Appointment", appt.get("name"), "booked_via_app") or 0,
                "can_reschedule": can_reschedule_appointment(appt.get("name")),
                "can_cancel": can_cancel_appointment(appt.get("name"))
            })
            
            enhanced_appointments.append(enhanced_appt)
        
        # Get total count using the same query_filters
        total_count = frappe.db.count("Patient Appointment", query_filters)
        
        return {
            "message": "success",
            "data": enhanced_appointments,
            "total_count": total_count,
            "page_length": limit_page_length,
            "start": limit_start
        }
        
    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Appointments Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error retrieving appointments"
        }

@frappe.whitelist(methods=['GET'])
def get_appointment(appointment_id):
    """
    Get detailed appointment information
    
    Args:
        appointment_id (str): Appointment ID
        
    Returns:
        dict: Detailed appointment data
    """
    try:
        appointment = frappe.get_doc("Patient Appointment", appointment_id)
        
        # Get patient details
        patient_data = get_patient_basic_info(appointment.patient)
        
        # Get practitioner details
        practitioner = frappe.get_doc("Healthcare Practitioner", appointment.practitioner)
        
        appointment_data = {
            "appointment_id": appointment.name,
            "patient_id": appointment.patient,
            "patient_name": appointment.patient_name,
            "patient_mobile": patient_data.get("mobile"),
            "patient_email": patient_data.get("email"),
            "patient_age": patient_data.get("age"),
            "patient_sex": patient_data.get("sex"),
            "practitioner_id": appointment.practitioner,
            "practitioner_name": practitioner.practitioner_name,
            "appointment_date": cstr(appointment.appointment_date),
            "appointment_time": cstr(appointment.appointment_time),
            "duration": appointment.duration,
            "status": appointment.status,
            "appointment_type": appointment.appointment_type,
            "chief_complaint": getattr(appointment, 'chief_complaint', ''),
            "notes": appointment.notes,
            "invoiced": appointment.invoiced,
            "paid_amount": appointment.paid_amount,
            "booked_via_app": getattr(appointment, 'booked_via_app', 0),
            "reminder_sent": getattr(appointment, 'reminder_sent', 0),
            "patient_confirmed": getattr(appointment, 'patient_confirmed', 0),
            "can_reschedule": can_reschedule_appointment(appointment.name),
            "can_cancel": can_cancel_appointment(appointment.name)
        }
        
        return {
            "message": "success",
            "data": appointment_data
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": f"Appointment {appointment_id} not found"
        }
    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Appointment Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error retrieving appointment"
        }

@frappe.whitelist(methods=['POST'])
def create_appointment(patient_id, appointment_date, appointment_time, **kwargs):
    """
    Create a new appointment with conflict detection
    
    Args:
        patient_id (str): Patient ID
        appointment_date (str): Appointment date (YYYY-MM-DD)
        appointment_time (str): Appointment time (HH:MM:SS)
        **kwargs: Additional appointment fields
        
    Returns:
        dict: Created appointment information
    """
    try:
        # Validate required fields
        if not all([patient_id, appointment_date, appointment_time]):
            frappe.local.response["http_status_code"] = 400
            return {
                "exc_type": "ValidationError",
                "message": "Missing required fields: patient_id, appointment_date, appointment_time"
            }
        
        # Get current practitioner
        practitioner = get_current_practitioner()
        if not practitioner:
            frappe.local.response["http_status_code"] = 403
            return {
                "exc_type": "PermissionError",
                "message": "Healthcare Practitioner profile not found"
            }
        
        # Check for appointment conflicts
        conflict = check_appointment_conflict(
            practitioner.name,
            appointment_date,
            appointment_time,
            kwargs.get("duration", 30)
        )
        
        if conflict:
            frappe.local.response["http_status_code"] = 409
            return {
                "exc_type": "ValidationError",
                "message": f"Appointment slot conflict: {conflict}"
            }
        
        # Create appointment
        appointment = frappe.get_doc({
            "doctype": "Patient Appointment",
            "patient": patient_id,
            "practitioner": practitioner.name,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "duration": kwargs.get("duration", 30),
            "status": "Open",
            "appointment_type": kwargs.get("appointment_type", ""),
            "notes": kwargs.get("notes", ""),
            "chief_complaint": kwargs.get("chief_complaint", ""),
            "booked_via_app": 1,
            "app_booking_source": "Mobile App"
        })
        
        appointment.flags.ignore_permissions = True
        appointment.flags.ignore_mandatory = True
        appointment.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Get the created appointment with enhanced data
        created_appointment = get_appointment(appointment.name)
        
        return {
            "message": "Appointment created successfully",
            "data": created_appointment.get("data")
        }
        
    except Exception as e:
        error_msg = str(e)
        if not frappe.conf.get('developer_mode'):
            try:
                frappe.log_error(error_msg[:500], "Appointment Creation")
            except:
                pass
        
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error creating appointment: {error_msg[:100]}"
        }

@frappe.whitelist(methods=['POST', 'PUT'])
def update_appointment(appointment_id, **kwargs):
    """
    Update appointment (reschedule or update details)
    
    Args:
        appointment_id (str): Appointment ID
        **kwargs: Fields to update
        
    Returns:
        dict: Updated appointment information
    """
    try:
        appointment = frappe.get_doc("Patient Appointment", appointment_id)
        
        # Check if appointment can be updated
        if appointment.status in ["Cancelled", "Closed"]:
            frappe.local.response["http_status_code"] = 400
            return {
                "exc_type": "ValidationError",
                "message": f"Cannot update {appointment.status} appointment"
            }
        
        # If rescheduling, check for conflicts
        if kwargs.get("appointment_date") or kwargs.get("appointment_time"):
            new_date = kwargs.get("appointment_date", appointment.appointment_date)
            new_time = kwargs.get("appointment_time", appointment.appointment_time)
            duration = kwargs.get("duration", appointment.duration)
            
            conflict = check_appointment_conflict(
                appointment.practitioner,
                new_date,
                new_time,
                duration,
                exclude_appointment=appointment_id
            )
            
            if conflict:
                frappe.local.response["http_status_code"] = 409
                return {
                    "exc_type": "ValidationError",
                    "message": f"Appointment slot conflict: {conflict}"
                }
            
            # Track rescheduling
            appointment.rescheduled_from = appointment_id
        
        # Update allowed fields
        allowed_fields = [
            'appointment_date', 'appointment_time', 'duration', 'status',
            'appointment_type', 'notes', 'chief_complaint'
        ]
        
        updated_fields = []
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(appointment, field):
                setattr(appointment, field, value)
                updated_fields.append(field)
        
        if updated_fields:
            appointment.flags.ignore_permissions = True
            appointment.save(ignore_permissions=True)
            frappe.db.commit()
        
        # Return updated appointment
        updated_appointment = get_appointment(appointment_id)
        
        return {
            "message": "Appointment updated successfully",
            "updated_fields": updated_fields,
            "data": updated_appointment.get("data")
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": f"Appointment {appointment_id} not found"
        }
    except Exception as e:
        frappe.log_error(str(e)[:500], "Appointment Update")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error updating appointment"
        }

@frappe.whitelist(methods=['POST', 'DELETE'])
def cancel_appointment(appointment_id, cancellation_reason=None):
    """
    Cancel an appointment
    
    Args:
        appointment_id (str): Appointment ID
        cancellation_reason (str): Reason for cancellation
        
    Returns:
        dict: Cancellation confirmation
    """
    try:
        appointment = frappe.get_doc("Patient Appointment", appointment_id)
        
        # Check if appointment can be cancelled
        if appointment.status in ["Cancelled", "Closed"]:
            frappe.local.response["http_status_code"] = 400
            return {
                "exc_type": "ValidationError",
                "message": f"Appointment is already {appointment.status}"
            }
        
        # Update status
        appointment.status = "Cancelled"
        if cancellation_reason:
            appointment.cancellation_reason = cancellation_reason
        
        appointment.flags.ignore_permissions = True
        appointment.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "message": "Appointment cancelled successfully",
            "appointment_id": appointment_id,
            "status": "Cancelled"
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": f"Appointment {appointment_id} not found"
        }
    except Exception as e:
        frappe.log_error(str(e)[:500], "Appointment Cancellation")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error cancelling appointment"
        }


@frappe.whitelist(methods=['DELETE', 'POST'])
def delete_appointment(appointment_id):
    """
    Delete an appointment permanently
    
    Args:
        appointment_id (str): Appointment ID
        
    Returns:
        dict: Deletion status
    """
    try:
        # Check if appointment exists
        if not frappe.db.exists("Patient Appointment", appointment_id):
            frappe.local.response["http_status_code"] = 404
            return {
                "exc_type": "NotFound",
                "message": f"Appointment {appointment_id} not found"
            }
        
        # Get the appointment
        appointment = frappe.get_doc("Patient Appointment", appointment_id)
        
        # Check if appointment can be deleted
        if appointment.docstatus == 1:
            frappe.local.response["http_status_code"] = 400
            return {
                "exc_type": "ValidationError",
                "message": "Cannot delete submitted appointment. Please cancel it first."
            }
        
        if appointment.invoiced:
            frappe.local.response["http_status_code"] = 400
            return {
                "exc_type": "ValidationError",
                "message": "Cannot delete invoiced appointment."
            }
        
        # Store info before deletion
        patient_name = appointment.patient_name
        appointment_date = appointment.appointment_date
        appointment_time = appointment.appointment_time
        
        # Delete the appointment
        frappe.delete_doc("Patient Appointment", appointment_id, ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "message": "Appointment deleted successfully",
            "data": {
                "appointment_id": appointment_id,
                "patient_name": patient_name,
                "appointment_date": str(appointment_date),
                "appointment_time": str(appointment_time)
            }
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": f"Appointment {appointment_id} not found"
        }
    except Exception as e:
        frappe.log_error(str(e)[:500], "Delete Appointment Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error deleting appointment: {str(e)}"
        }


@frappe.whitelist(methods=['POST'])
def add_to_todays_queue(patient_id, duration=30, **kwargs):
    """
    Add patient to today's queue by finding the nearest available slot
    
    Args:
        patient_id (str): Patient ID
        duration (int): Appointment duration in minutes
        **kwargs: Additional appointment fields
        
    Returns:
        dict: Created appointment information
    """
    try:
        # Validate patient exists
        if not frappe.db.exists("Patient", patient_id):
            frappe.local.response["http_status_code"] = 404
            return {
                "exc_type": "NotFound",
                "message": f"Patient {patient_id} not found"
            }
        
        # Get current practitioner
        practitioner = get_current_practitioner()
        if not practitioner:
            frappe.local.response["http_status_code"] = 403
            return {
                "exc_type": "PermissionError",
                "message": "Healthcare Practitioner profile not found"
            }
        
        # Get today's date
        today = nowdate()
        
        # Get available slots for today
        slots_response = get_available_slots(today, duration)
        
        if slots_response.get("exc_type"):
            return slots_response
        
        slots_data = slots_response.get("data", {})
        available_slots = slots_data.get("available_slots", [])
        
        if not available_slots:
            # No available slots - add to end of day
            # Get last appointment time
            last_appointment = frappe.get_all(
                "Patient Appointment",
                filters={
                    "practitioner": practitioner.name,
                    "appointment_date": today,
                    "status": ["not in", ["Cancelled"]]
                },
                fields=["appointment_time", "duration"],
                order_by="appointment_time desc",
                limit=1
            )
            
            if last_appointment and last_appointment[0].appointment_time:
                # Calculate next slot after last appointment
                last_time = datetime.strptime(str(last_appointment[0].appointment_time), "%H:%M:%S")
                last_duration = int(last_appointment[0].duration or 30)
                next_time = last_time + timedelta(minutes=last_duration)
                appointment_time = next_time.strftime("%H:%M:%S")
            else:
                # No appointments today - use current time or start of working hours
                working_hours = get_working_hours(practitioner.name, getdate(today).strftime("%A"))
                if working_hours and working_hours.get("is_working_day"):
                    # Use start time if before current time, otherwise use current time
                    current_time = now_datetime().time()
                    start_time = datetime.strptime(str(working_hours.get("start_time")), "%H:%M:%S").time()
                    
                    if current_time < start_time:
                        appointment_time = str(working_hours.get("start_time"))
                    else:
                        appointment_time = current_time.strftime("%H:%M:%S")
                else:
                    # Default to current time
                    appointment_time = now_datetime().strftime("%H:%M:%S")
        else:
            # Use the first available slot
            appointment_time = available_slots[0]
        
        # Create the appointment
        appointment = frappe.get_doc({
            "doctype": "Patient Appointment",
            "patient": patient_id,
            "practitioner": practitioner.name,
            "appointment_date": today,
            "appointment_time": appointment_time,
            "duration": duration,
            "status": "Open",
            "appointment_type": kwargs.get("appointment_type", "Walk In"),
            "notes": kwargs.get("notes", "Added to today's queue"),
            "chief_complaint": kwargs.get("chief_complaint", ""),
            "booked_via_app": 1,
            "app_booking_source": "Mobile App - Quick Queue"
        })
        
        appointment.flags.ignore_permissions = True
        appointment.flags.ignore_mandatory = True
        appointment.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Get the created appointment with enhanced data
        created_appointment = get_appointment(appointment.name)
        
        return {
            "message": "Patient added to today's queue successfully",
            "queue_position": get_queue_position(appointment.name, today, practitioner.name),
            "data": created_appointment.get("data")
        }
        
    except Exception as e:
        error_msg = str(e)
        frappe.log_error(error_msg[:500], "Add to Queue Error")
        
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error adding to queue: {error_msg[:100]}"
        }


@frappe.whitelist(methods=['GET'])
def get_todays_queue():
    """
    Get today's appointment queue for current practitioner
    
    Returns:
        dict: List of today's appointments ordered by time
    """
    try:
        practitioner = get_current_practitioner()
        if not practitioner:
            frappe.local.response["http_status_code"] = 403
            return {
                "exc_type": "PermissionError",
                "message": "Healthcare Practitioner profile not found"
            }
        
        today = nowdate()
        
        # Get today's appointments
        appointments = frappe.get_all(
            "Patient Appointment",
            filters={
                "practitioner": practitioner.name,
                "appointment_date": today,
                "status": ["not in", ["Cancelled"]]
            },
            fields=[
                "name", "patient", "patient_name", "appointment_time",
                "duration", "status", "appointment_type", "chief_complaint"
            ],
            order_by="appointment_time asc"
        )
        
        # Enhance with queue position and patient info
        queue = []
        for idx, appt in enumerate(appointments, 1):
            patient_data = get_patient_basic_info(appt.get("patient"))
            
            queue_item = dict(appt)
            queue_item.update({
                "queue_position": idx,
                "patient_mobile": patient_data.get("mobile"),
                "patient_image": patient_data.get("image"),
                "estimated_time": calculate_estimated_time(appointments[:idx], appt.get("appointment_time"))
            })
            
            queue.append(queue_item)
        
        return {
            "message": "success",
            "data": {
                "date": today,
                "total_queue": len(queue),
                "queue": queue
            }
        }
        
    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Queue Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error retrieving today's queue"
        }


@frappe.whitelist(methods=['GET'])
def get_available_slots(date, duration=30):
    """
    Get available time slots for a specific date
    
    Args:
        date (str): Date to check (YYYY-MM-DD)
        duration (int): Appointment duration in minutes
        
    Returns:
        dict: Available time slots
    """
    try:
        practitioner = get_current_practitioner()
        if not practitioner:
            frappe.local.response["http_status_code"] = 403
            return {
                "exc_type": "PermissionError",
                "message": "Healthcare Practitioner profile not found"
            }
        
        # Get working hours for the day
        day_of_week = getdate(date).strftime("%A")
        working_hours = get_working_hours(practitioner.name, day_of_week)
        
        if not working_hours or not working_hours.get("is_working_day"):
            return {
                "message": "success",
                "data": {
                    "date": date,
                    "is_working_day": False,
                    "available_slots": []
                }
            }
        
        # Generate time slots
        start_time = working_hours.get("start_time")
        end_time = working_hours.get("end_time")
        all_slots = generate_time_slots(start_time, end_time, duration)
        
        # Get booked appointments for the date
        booked_appointments = frappe.get_all(
            "Patient Appointment",
            filters={
                "practitioner": practitioner.name,
                "appointment_date": date,
                "status": ["not in", ["Cancelled"]]
            },
            fields=["appointment_time", "duration"]
        )
        
        # Filter out booked slots
        available_slots = []
        for slot in all_slots:
            if not is_slot_booked(slot, booked_appointments, duration):
                available_slots.append(slot)
        
        return {
            "message": "success",
            "data": {
                "date": date,
                "is_working_day": True,
                "working_hours": {
                    "start": cstr(start_time),
                    "end": cstr(end_time)
                },
                "slot_duration": duration,
                "total_slots": len(all_slots),
                "available_slots": available_slots,
                "booked_count": len(all_slots) - len(available_slots)
            }
        }
        
    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Available Slots")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error retrieving available slots"
        }

# Helper Functions

def get_current_practitioner():
    """Get current user's healthcare practitioner record"""
    try:
        return frappe.get_doc("Healthcare Practitioner", {"user_id": frappe.session.user})
    except (frappe.DoesNotExistError, Exception):
        # Silently return None if no practitioner found (e.g., Administrator user)
        return None

def get_patient_basic_info(patient_id):
    """Get basic patient information"""
    try:
        patient = frappe.get_doc("Patient", patient_id)
        return {
            "mobile": patient.mobile,
            "email": patient.email,
            "image": patient.image,
            "age": patient.get("age_html", ""),
            "sex": patient.sex
        }
    except (frappe.DoesNotExistError, Exception):
        # Return empty dict if patient not found
        return {
            "mobile": None,
            "email": None,
            "image": None,
            "age": "",
            "sex": None
        }

def check_appointment_conflict(practitioner, date, time, duration, exclude_appointment=None):
    """
    Check if appointment slot conflicts with existing appointments
    
    Returns:
        str: Conflict message or None if no conflict
    """
    try:
        # Convert to datetime
        appointment_datetime = datetime.combine(getdate(date), datetime.strptime(str(time), "%H:%M:%S").time())
        end_datetime = appointment_datetime + timedelta(minutes=int(duration))
        
        # Get existing appointments
        filters = {
            "practitioner": practitioner,
            "appointment_date": date,
            "status": ["not in", ["Cancelled"]]
        }
        
        if exclude_appointment:
            filters["name"] = ["!=", exclude_appointment]
        
        existing_appointments = frappe.get_all(
            "Patient Appointment",
            filters=filters,
            fields=["name", "appointment_time", "duration", "patient_name"]
        )
        
        # Check for overlaps
        for appt in existing_appointments:
            if not appt.get("appointment_time"):
                continue
                
            existing_start = datetime.combine(getdate(date), datetime.strptime(str(appt.appointment_time), "%H:%M:%S").time())
            existing_end = existing_start + timedelta(minutes=int(appt.duration or 30))
            
            # Check if times overlap
            if (appointment_datetime < existing_end and end_datetime > existing_start):
                return f"Conflicts with appointment for {appt.patient_name} at {appt.appointment_time}"
        
        return None
        
    except Exception as e:
        frappe.log_error(f"Conflict check error: {str(e)}", "Appointment Conflict")
        return None

def can_reschedule_appointment(appointment_id):
    """Check if appointment can be rescheduled"""
    try:
        appt = frappe.db.get_value("Patient Appointment", appointment_id, ["status", "appointment_date"], as_dict=True)
        if not appt:
            return False
        
        # Can't reschedule cancelled or closed appointments
        if appt.status in ["Cancelled", "Closed"]:
            return False
        
        # Can't reschedule past appointments
        if getdate(appt.appointment_date) < getdate(nowdate()):
            return False
        
        return True
    except:
        return False

def can_cancel_appointment(appointment_id):
    """Check if appointment can be cancelled"""
    try:
        status = frappe.db.get_value("Patient Appointment", appointment_id, "status")
        return status not in ["Cancelled", "Closed"]
    except:
        return False

def get_working_hours(practitioner_id, day_of_week):
    """Get working hours for a specific day"""
    try:
        practitioner = frappe.get_doc("Healthcare Practitioner", practitioner_id)
        
        # Check if clinic_working_hours child table exists
        if hasattr(practitioner, 'clinic_working_hours'):
            for row in practitioner.clinic_working_hours:
                if row.day == day_of_week:
                    return {
                        "is_working_day": row.is_working_day,
                        "start_time": row.start_time,
                        "end_time": row.end_time
                    }
        
        # Default working hours if not configured
        return {
            "is_working_day": True,
            "start_time": "09:00:00",
            "end_time": "17:00:00"
        }
    except:
        return None

def generate_time_slots(start_time, end_time, duration):
    """Generate time slots between start and end time"""
    slots = []
    
    try:
        current = datetime.strptime(str(start_time), "%H:%M:%S")
        end = datetime.strptime(str(end_time), "%H:%M:%S")
        
        while current < end:
            slots.append(current.strftime("%H:%M:%S"))
            current += timedelta(minutes=int(duration))
        
        return slots
    except:
        return []

def is_slot_booked(slot, booked_appointments, duration):
    """Check if a time slot is already booked"""
    try:
        slot_time = datetime.strptime(slot, "%H:%M:%S")
        slot_end = slot_time + timedelta(minutes=int(duration))
        
        for appt in booked_appointments:
            if not appt.get("appointment_time"):
                continue
                
            appt_start = datetime.strptime(str(appt.appointment_time), "%H:%M:%S")
            appt_end = appt_start + timedelta(minutes=int(appt.duration or 30))
            
            # Check if times overlap
            if (slot_time < appt_end and slot_end > appt_start):
                return True
        
        return False
    except:
        return False


def get_queue_position(appointment_id, date, practitioner_id):
    """
    Get the position of an appointment in today's queue
    
    Args:
        appointment_id (str): Appointment ID
        date (str): Appointment date
        practitioner_id (str): Practitioner ID
        
    Returns:
        int: Queue position (1-based)
    """
    try:
        # Get all appointments for the day ordered by time
        appointments = frappe.get_all(
            "Patient Appointment",
            filters={
                "practitioner": practitioner_id,
                "appointment_date": date,
                "status": ["not in", ["Cancelled", "Closed"]]
            },
            fields=["name", "appointment_time"],
            order_by="appointment_time asc"
        )
        
        # Find position
        for idx, appt in enumerate(appointments, 1):
            if appt.name == appointment_id:
                return idx
        
        return len(appointments)
    except:
        return None


def calculate_estimated_time(previous_appointments, current_time):
    """
    Calculate estimated time for appointment based on queue
    
    Args:
        previous_appointments (list): List of appointments before current
        current_time (str): Scheduled appointment time
        
    Returns:
        str: Estimated time
    """
    try:
        if not previous_appointments:
            return current_time
        
        # Start with first appointment time
        estimated = datetime.strptime(str(previous_appointments[0].get("appointment_time")), "%H:%M:%S")
        
        # Add duration of all previous appointments
        for appt in previous_appointments:
            duration = int(appt.get("duration") or 30)
            estimated += timedelta(minutes=duration)
        
        return estimated.strftime("%H:%M:%S")
    except:
        return current_time
