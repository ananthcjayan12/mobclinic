import frappe
from frappe import _
from frappe.utils import cstr, get_datetime, nowdate, add_days, getdate, now_datetime
import json
from datetime import datetime, timedelta

@frappe.whitelist()
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
        
        # Get appointments
        appointments = frappe.get_all(
            "Patient Appointment",
            fields=[
                "name", "patient", "patient_name", "appointment_date", 
                "appointment_time", "duration", "status", "appointment_type",
                "chief_complaint", "notes", "invoiced", "paid_amount"
            ],
            filters=filters,
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
        
        # Get total count
        total_count = frappe.db.count("Patient Appointment", filters)
        
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

@frappe.whitelist()
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

@frappe.whitelist()
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

@frappe.whitelist()
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

@frappe.whitelist()
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

@frappe.whitelist()
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
    except frappe.DoesNotExistError:
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
    except:
        return {}

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
