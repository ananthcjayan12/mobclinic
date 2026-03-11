import frappe
from frappe import _
from frappe.utils import cstr, cint, get_datetime, nowdate, add_days, getdate, now_datetime
import json
from datetime import datetime, timedelta
from mob_clinic.mob_clinic.api import clinic as clinic_helper


def resolve_appointment_duration(practitioner_id=None, clinic=None, duration=None):
    """Return the practitioner-specific slot duration, falling back to clinic default and then 30."""
    requested_duration = cint(duration)
    if requested_duration > 0:
        return requested_duration

    resolved_clinic = clinic
    practitioner_doc = None
    if practitioner_id:
        try:
            practitioner_doc = frappe.get_doc("Healthcare Practitioner", practitioner_id)
            resolved_clinic = resolved_clinic or getattr(practitioner_doc, "primary_company", None)
            if frappe.get_meta("Healthcare Practitioner").has_field("appointment_slot_duration"):
                practitioner_duration = cint(getattr(practitioner_doc, "appointment_slot_duration", 0))
                if practitioner_duration > 0:
                    return practitioner_duration
        except Exception:
            practitioner_doc = None

    if resolved_clinic and frappe.db.exists("Clinic Settings", resolved_clinic):
        clinic_duration = cint(frappe.db.get_value("Clinic Settings", resolved_clinic, "appointment_slot_duration"))
        if clinic_duration > 0:
            return clinic_duration

    return 30

@frappe.whitelist(methods=['GET'])
def get_appointments(filters=None, limit_start=0, limit_page_length=20, order_by="appointment_date desc", clinic=None):
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
        
        # Get current practitioner context
        practitioner = get_current_practitioner()

        # Respect incoming practitioner filter from UI:
        # - if practitioner is provided => filter to that practitioner
        # - if practitioner is "all"/empty/not provided => show clinic-wide appointments
        requested_practitioner = filters.get("practitioner")
        if requested_practitioner in ["all", "All", "ALL", "", None]:
            filters.pop("practitioner", None)
        
        # Resolve clinic and apply company filter if present
        resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name if practitioner else None, clinic)
        if resolved_clinic:
            filters["company"] = resolved_clinic
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

        # Support a free-text search_term in filters (search across patient_name, patient id)
        search_term = None
        if "search_term" in query_filters:
            try:
                search_term = query_filters.pop("search_term")
            except Exception:
                search_term = None

        or_filters = None
        if search_term:
            or_filters = [
                ["patient_name", "like", f"%{search_term}%"],
                ["patient", "like", f"%{search_term}%"],
                ["name", "like", f"%{search_term}%"]
            ]
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
                "chief_complaint", "notes", "invoiced", "paid_amount",
                "check_in_time", "start_time", "end_time", "payment_time",
                "review_requested", "review_requested_time", "invoice_id", "invoice_status",
                "practitioner", "practitioner_name"
            ],
            filters=query_filters,
            or_filters=or_filters,
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
        
        # Get total count using same filters (including or_filters if present)
        try:
            if or_filters:
                total_count = len(frappe.get_all(
                    "Patient Appointment",
                    filters=query_filters,
                    or_filters=or_filters,
                    fields=["name"]
                ))
            else:
                total_count = frappe.db.count("Patient Appointment", query_filters)
        except Exception:
            # Fallback to 0 on any counting issues
            total_count = 0
        
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
        
        # Get practitioner (either from kwargs or current user)
        practitioner_id = kwargs.get("practitioner")
        if practitioner_id:
            practitioner_name = practitioner_id
        else:
            practitioner = get_current_practitioner()
            if not practitioner:
                frappe.local.response["http_status_code"] = 403
                return {
                    "exc_type": "PermissionError",
                    "message": "Healthcare Practitioner profile not found"
                }
            practitioner_name = practitioner.name
        
        # CHECK FOR DUPLICATE APPOINTMENT
        existing_appointments = frappe.get_all(
            "Patient Appointment",
            filters={
                "patient": patient_id,
                "appointment_date": appointment_date,
                "status": ["not in", ["Cancelled", "Closed"]]
            },
            fields=["name", "appointment_time", "status", "practitioner"]
        )
        
        if existing_appointments:
            # Patient already has an appointment on this date
            existing = existing_appointments[0]
            frappe.local.response["http_status_code"] = 400
            return {
                "message": "Patient already has an appointment scheduled for this date",
                "error": "DuplicateAppointment",
                "status_code": 400,
                "existing_appointment": {
                    "name": existing.name,
                    "appointment_time": str(existing.appointment_time),
                    "status": existing.status
                }
            }
        
        # Resolve clinic and validate practitioner access
        resolved_clinic = clinic_helper.resolve_active_clinic(practitioner_name, kwargs.get("clinic"))
        if kwargs.get("clinic") and not clinic_helper.validate_practitioner_access(practitioner_name, resolved_clinic):
            frappe.local.response["http_status_code"] = 403
            return {
                "exc_type": "PermissionError",
                "message": "Practitioner does not have access to the requested clinic"
            }

        resolved_duration = resolve_appointment_duration(practitioner_name, resolved_clinic, kwargs.get("duration"))

        # Count overlapping appointments for this slot (allow overbooking but inform caller)
        overlap_count = count_overlapping_appointments(
            practitioner_name,
            appointment_date,
            appointment_time,
            resolved_duration
        )
        if overlap_count:
            warning_msg = f"{overlap_count} existing appointment(s) in this time slot for the practitioner"
        else:
            warning_msg = None
        
        # Create appointment
        appointment = frappe.get_doc({
            "doctype": "Patient Appointment",
            "patient": patient_id,
            "practitioner": practitioner_name,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "duration": resolved_duration,
            "status": "Open",
            "appointment_type": kwargs.get("appointment_type", ""),
            "appointment_for": "Practitioner",
            "notes": kwargs.get("notes", ""),
            "chief_complaint": kwargs.get("chief_complaint", ""),
            "booked_via_app": 1,
            "app_booking_source": "Mobile App"
        })

        # Assign company if clinic resolved
        if resolved_clinic:
            appointment.company = resolved_clinic
        
        appointment.flags.ignore_permissions = True
        appointment.flags.ignore_mandatory = True
        # Bypass upstream overlap validation in the healthcare app for app-driven bookings
        # (healthcare.PatientAppointment.validate_overlaps checks this flag).
        appointment.flags.ignore_overlap_validation = True
        appointment.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Get the created appointment with enhanced data
        created_appointment = get_appointment(appointment.name)
        data = created_appointment.get("data") if created_appointment else {}

        # Add slot occupancy/warning info for frontend heads-up
        try:
            data = data or {}
            data["slot_existing_appointments"] = overlap_count
            data["slot_occupancy"] = (overlap_count or 0) + 1
            if warning_msg:
                data["warning"] = warning_msg
        except Exception:
            # Defensive: if anything fails here, ignore and return main data
            pass

        return {
            "message": "Appointment created successfully",
            "data": data
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

@frappe.whitelist(allow_guest=True, methods=['POST'])
def create_public_appointment(clinic, patient_name, mobile, appointment_date, appointment_time, practitioner=None, appointment_type=None, **kwargs):
    """
    Create a public appointment for a guest user
    """
    try:
        # 1. Resolve Practitioner - use provided or fallback to first available
        if not practitioner:
            practitioners = frappe.get_all(
                "Healthcare Practitioner",
                filters={"primary_company": clinic, "status": "Active"},
                fields=["name"],
                limit=1
            )
            if practitioners:
                practitioner = practitioners[0].name
        
        if not practitioner:
             return {"message": "No doctors available at this clinic"}, 400

        # 2. Find or Create Patient
        patient_name = patient_name.strip()
        
        # Check if patient exists by mobile
        existing_patient = frappe.db.get_value("Patient", {"mobile": mobile}, "name")
        
        if existing_patient:
            patient_id = existing_patient
        else:
            # Create new patient - first_name is required
            patient = frappe.new_doc("Patient")
            # Split patient_name into first_name and last_name
            name_parts = patient_name.split(' ', 1)
            patient.first_name = name_parts[0]
            if len(name_parts) > 1:
                patient.last_name = name_parts[1]
            patient.patient_name = patient_name
            patient.mobile = mobile
            patient.email = kwargs.get("email")
            patient.sex = kwargs.get("sex", "Unknown")
            patient.flags.ignore_permissions = True
            patient.insert(ignore_permissions=True)
            patient_id = patient.name
        
        # 3. Create Appointment using internal function (reusing logic but passing practitioner explicitly)
        # We need to call create_appointment but it expects logged in user for practitioner check
        # So we will replicate the essential creation logic here to bypass current_practitioner check
        
        # Overlap check
        overlap_count = count_overlapping_appointments(
            practitioner,
            appointment_date,
            appointment_time,
            kwargs.get("duration", 30)
        )
        
        if overlap_count > 0:
             # Strict for public booking? Or allow overbooking? 
             # Let's be strict for public to avoid chaos
             return {"message": "Selected slot is no longer available"}, 409

        # Create appointment
        appointment = frappe.get_doc({
            "doctype": "Patient Appointment",
            "patient": patient_id,
            "practitioner": practitioner,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "duration": kwargs.get("duration", 30),
            "status": "Open",
            "appointment_type": appointment_type or "Online Booking",
            "appointment_for": "Practitioner",
            "notes": f"Web Booking. {kwargs.get('notes', '')}",
            "booked_via_app": 1,
            "app_booking_source": "Public Website"
        })

        # Link Company
        # We assume clinic name passed IS the company name or linked to it
        # The clinic_helper.resolve_active_clinic expects a practitioner, but here we know the clinic directly
        # If 'clinic' arg is the Company name
        if frappe.db.exists("Company", clinic):
            appointment.company = clinic

        appointment.flags.ignore_permissions = True
        appointment.flags.ignore_mandatory = True
        appointment.flags.ignore_overlap_validation = True
        appointment.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "message": "Appointment booked successfully",
            "data": {
                "appointment_id": appointment.name,
                "patient_name": patient_name,
                "date": appointment_date,
                "time": appointment_time,
                "status": "Confirmed"
            }
        }

    except Exception as e:
        frappe.log_error(str(e), "Public Appointment Error")
        return {"message": str(e)}, 500


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
        
        updates = {}
        for field, value in kwargs.items():
            if field in allowed_fields:
                updates[field] = value
        
        # If rescheduling, check for conflicts
        if kwargs.get("appointment_date") or kwargs.get("appointment_time"):
            updates['rescheduled_from'] = appointment_id

        if updates:
            # Use db_set to bypass framework restrictions like set_only_once
            appointment.db_set(updates)
            frappe.db.commit()
        
        # Return updated appointment
        updated_appointment = get_appointment(appointment_id)
        
        return {
            "message": "Appointment updated successfully",
            "updated_fields": list(updates.keys()),
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
        
        # Update status using db_set to bypass mandatory validation
        updates = {
            "status": "Cancelled"
        }
        if cancellation_reason:
            updates["cancellation_reason"] = cancellation_reason
            
        appointment.db_set(updates)
        
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
        
        # Resolve clinic and set company on quick-queue appointment
        resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name, kwargs.get("clinic"))
        if kwargs.get("clinic") and not clinic_helper.validate_practitioner_access(practitioner.name, resolved_clinic):
            frappe.local.response["http_status_code"] = 403
            return {
                "exc_type": "PermissionError",
                "message": "Practitioner does not have access to the requested clinic"
            }

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

        if resolved_clinic:
            appointment.company = resolved_clinic
        
        appointment.flags.ignore_permissions = True
        appointment.flags.ignore_mandatory = True
        # Bypass upstream overlap validation when adding quick-queue bookings
        appointment.flags.ignore_overlap_validation = True
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


@frappe.whitelist(allow_guest=True)
def get_available_slots(date, duration=30, practitioner=None, clinic=None):
    """
    Get available time slots for a specific date and optionally filter by practitioner
    
    Args:
        date (str): Date to check (YYYY-MM-DD)
        duration (int): Appointment duration in minutes
        practitioner (str): Optional practitioner ID to filter slots
        
    Returns:
        dict: Available time slots
    """
    try:
        if not practitioner:
            # Try to get practitioner from clinic if provided (for guest access)
            if clinic:
                # Query Healthcare Practitioner directly by primary_company
                practitioners = frappe.get_all(
                    "Healthcare Practitioner",
                    filters={"primary_company": clinic, "status": "Active"},
                    fields=["name"],
                    limit=1
                )
                if practitioners:
                    practitioner = practitioners[0].name
            
            if not practitioner:
                practitioner_doc = get_current_practitioner()
                if not practitioner_doc:
                    frappe.local.response["http_status_code"] = 403
                    return {
                        "exc_type": "PermissionError",
                        "message": "Healthcare Practitioner profile not found or clinic not specified"
                    }
                practitioner = practitioner_doc.name
        
        resolved_clinic = clinic
        if practitioner and not resolved_clinic:
            try:
                resolved_clinic = frappe.db.get_value("Healthcare Practitioner", practitioner, "primary_company")
            except Exception:
                resolved_clinic = None

        resolved_duration = resolve_appointment_duration(practitioner, resolved_clinic, duration)

        # Get working hours for the day
        day_of_week = getdate(date).strftime("%A")
        working_hours = get_working_hours(practitioner, day_of_week)
        
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
        all_slots = generate_time_slots(start_time, end_time, resolved_duration)
        
        # Get booked appointments for the date
        booked_appointments = frappe.get_all(
            "Patient Appointment",
            filters={
                "practitioner": practitioner,
                "appointment_date": date,
                "status": ["not in", ["Cancelled"]]
            },
            fields=["name", "appointment_time", "duration", "patient_name", "status"]
        )
        
        # Filter out booked slots and format response
        slots_data = []
        for slot in all_slots:
            is_booked = is_slot_booked(slot, booked_appointments, resolved_duration)
            slot_info = {
                "time": slot,
                "available": not is_booked
            }

            # Count existing overlapping appointments for this slot (for frontend occupancy display)
            try:
                existing_count = count_overlapping_appointments(practitioner, date, slot, resolved_duration)
            except Exception:
                existing_count = 0

            slot_info["existing_appointments"] = existing_count
            slot_info["occupancy"] = existing_count
            
            if is_booked:
                # Find the appointment booking this slot
                booking = get_booking_for_slot(slot, booked_appointments, resolved_duration)
                if booking:
                    slot_info["appointment"] = {
                        "name": booking.name,
                        "patient_name": booking.patient_name,
                        "status": booking.status
                    }
            
            slots_data.append(slot_info)
            
        # For backward compatibility, also return simple list of available slots
        available_slots_simple = [s["time"] for s in slots_data if s["available"]]
        
        return {
            "message": "success",
            "data": {
                "date": date,
                "is_working_day": True,
                "working_hours": {
                    "start": cstr(start_time),
                    "end": cstr(end_time)
                },
                "slot_duration": resolved_duration,
                "total_slots": len(all_slots),
                "available_slots": available_slots_simple, # Backward compatibility
                "slots": slots_data, # New detailed format
                "booked_count": len(all_slots) - len(available_slots_simple)
            }
        }
        
    except Exception as e:
        frappe.log_error(str(e)[:500], "Get Available Slots")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error retrieving available slots"
        }

def get_booking_for_slot(slot, booked_appointments, duration):
    """Find the appointment that books a specific slot"""
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
                return appt
        return None
    except:
        return None

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

def count_overlapping_appointments(practitioner, date, time, duration, exclude_appointment=None):
    """Return count of appointments that overlap the given slot for a practitioner"""
    try:
        appointment_datetime = datetime.combine(getdate(date), datetime.strptime(str(time), "%H:%M:%S").time())
        end_datetime = appointment_datetime + timedelta(minutes=int(duration))

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
            fields=["name", "appointment_time", "duration"]
        )

        count = 0
        for appt in existing_appointments:
            if not appt.get("appointment_time"):
                continue
            existing_start = datetime.combine(getdate(date), datetime.strptime(str(appt.appointment_time), "%H:%M:%S").time())
            existing_end = existing_start + timedelta(minutes=int(appt.duration or 30))

            if (appointment_datetime < existing_end and end_datetime > existing_start):
                count += 1

        return count
    except Exception as e:
        frappe.log_error(f"Count overlap error: {str(e)}", "Appointment Overlap Count")
        return 0

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

@frappe.whitelist(allow_guest=False)
def check_in_appointment(appointment_id):
    """
    Check-in patient for appointment (Status: Scheduled/Confirmed → Waiting)
    
    Args:
        appointment_id (str): Appointment ID
        
    Returns:
        dict: Updated appointment details
    """
    try:
        if not appointment_id:
            frappe.throw(_("Appointment ID is required"))
            
        appointment = frappe.get_doc("Patient Appointment", appointment_id)
        
        # Update status and check-in time using db_set to bypass controller logic
        check_in_time = now_datetime()
        appointment.db_set({
            "status": "Waiting",
            "check_in_time": check_in_time
        })
        
        return {
            "message": "Patient checked in successfully",
            "data": {
                "name": appointment.name,
                "status": appointment.status,
                "check_in_time": appointment.check_in_time
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error checking in appointment: {str(e)}")
        frappe.throw(_("Failed to check in appointment: {0}").format(str(e)))


@frappe.whitelist(allow_guest=False)
def start_visit(appointment_id):
    """
    Start patient visit (Status: Waiting → In Progress)
    
    Args:
        appointment_id (str): Appointment ID
        
    Returns:
        dict: Updated appointment details
    """
    try:
        if not appointment_id:
            frappe.throw(_("Appointment ID is required"))
            
        appointment = frappe.get_doc("Patient Appointment", appointment_id)
        
        # Update status and start time
        start_time = now_datetime()
        appointment.db_set({
            "status": "In Progress",
            "start_time": start_time
        })
        
        return {
            "message": "Visit started successfully",
            "data": {
                "name": appointment.name,
                "status": appointment.status,
                "start_time": appointment.start_time
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error starting visit: {str(e)}")
        frappe.throw(_("Failed to start visit: {0}").format(str(e)))


@frappe.whitelist(allow_guest=False)
def complete_visit(appointment_id):
    """
    Complete patient visit (Status: In Progress → Pending Payment)
    
    Args:
        appointment_id (str): Appointment ID
        
    Returns:
        dict: Updated appointment details
    """
    try:
        if not appointment_id:
            frappe.throw(_("Appointment ID is required"))
            
        appointment = frappe.get_doc("Patient Appointment", appointment_id)
        
        # Update status and end time
        end_time = now_datetime()
        appointment.db_set({
            "status": "Pending Payment",
            "end_time": end_time
        })
        
        return {
            "message": "Visit completed successfully",
            "data": {
                "name": appointment.name,
                "status": appointment.status,
                "end_time": appointment.end_time
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error completing visit: {str(e)}")
        frappe.throw(_("Failed to complete visit: {0}").format(str(e)))


@frappe.whitelist(allow_guest=False)
def mark_payment_complete(appointment_id, invoice_id=None):
    """
    Mark appointment payment as complete (Status: Pending Payment → Completed)
    
    Args:
        appointment_id (str): Appointment ID
        invoice_id (str): Optional invoice ID
        
    Returns:
        dict: Updated appointment details
    """
    try:
        if not appointment_id:
            frappe.throw(_("Appointment ID is required"))
            
        appointment = frappe.get_doc("Patient Appointment", appointment_id)
        
        # Update status and payment time
        updates = {
            "status": "Completed",
            "payment_time": now_datetime()
        }
        
        if invoice_id:
            updates["invoice_id"] = invoice_id
            updates["invoice_status"] = "Paid"
            
        appointment.db_set(updates)
        
        return {
            "message": "Payment marked as complete",
            "data": {
                "name": appointment.name,
                "status": appointment.status,
                "invoice_id": invoice_id,
                "payment_time": appointment.payment_time
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error marking payment complete: {str(e)}")
        frappe.throw(_("Failed to mark payment complete: {0}").format(str(e)))


@frappe.whitelist(allow_guest=False)
def update_review_status(appointment_id, review_requested):
    """
    Update Google review request status
    
    Args:
        appointment_id (str): Appointment ID
        review_requested (int/bool): Review requested flag (1 or 0)
        
    Returns:
        dict: Success message
    """
    try:
        if not appointment_id:
            frappe.throw(_("Appointment ID is required"))
            
        appointment = frappe.get_doc("Patient Appointment", appointment_id)
        
        updates = {
            "review_requested": 1 if review_requested else 0
        }
        
        if review_requested:
            updates["review_requested_time"] = now_datetime()
            
        appointment.db_set(updates)
        
        return {
            "message": "Review status updated successfully",
            "data": {
                "name": appointment.name,
                "review_requested": appointment.review_requested,
                "review_requested_time": appointment.review_requested_time
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error updating review status: {str(e)}")
        frappe.throw(_("Failed to update review status: {0}").format(str(e)))


@frappe.whitelist(allow_guest=False)
def get_invoice_status(appointment_id):
    """
    Check if invoice exists for an appointment
    
    Args:
        appointment_id (str): Appointment ID
        
    Returns:
        dict: Invoice status details
    """
    try:
        if not appointment_id:
            frappe.throw(_("Appointment ID is required"))
            
        appointment = frappe.get_doc("Patient Appointment", appointment_id)
        
        has_invoice = False
        invoice_data = {}
        
        # Check linked invoice field
        if appointment.invoice_id:
            has_invoice = True
            invoice = frappe.get_doc("Sales Invoice", appointment.invoice_id)
            invoice_data = {
                "invoice_id": invoice.name,
                "invoice_status": invoice.status,
                "total_amount": invoice.grand_total,
                "paid_amount": invoice.paid_amount
            }
        else:
            # Check if any invoice references this appointment
            invoices = frappe.get_all(
                "Sales Invoice Item",
                filters={"reference_dt": "Patient Appointment", "reference_dn": appointment_id},
                fields=["parent"]
            )
            
            if invoices:
                has_invoice = True
                invoice_id = invoices[0].parent
                invoice = frappe.get_doc("Sales Invoice", invoice_id)
                
                # Update appointment with invoice link if missing
                if not appointment.invoice_id:
                    appointment.invoice_id = invoice_id
                    appointment.invoice_status = invoice.status
                    appointment.flags.ignore_permissions = True
                    appointment.save(ignore_permissions=True)
                    frappe.db.commit()
                
                invoice_data = {
                    "invoice_id": invoice.name,
                    "invoice_status": invoice.status,
                    "total_amount": invoice.grand_total,
                    "paid_amount": invoice.paid_amount
                }
        
        return {
            "message": "Success",
            "data": {
                "has_invoice": has_invoice,
                **invoice_data
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Error getting invoice status: {str(e)}")
        frappe.throw(_("Failed to get invoice status: {0}").format(str(e)))


# --- Invoice / Payment / File synchronization helpers ---
def _appointment_has_files(appointment_id):
    """Return True if any File is attached to the Patient Appointment."""
    try:
        files = frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": "Patient Appointment",
                "attached_to_name": appointment_id,
            },
            limit=1,
        )
        return bool(files)
    except Exception:
        return False


def update_appointments_for_invoice(invoice_name):
    """Sync Patient Appointment(s) with a Sales Invoice.

    Behavior:
    - For each Sales Invoice Item that references a `Patient Appointment` (reference_dt/reference_dn):
      - set `invoice_id`, `invoice_status`, `invoiced`, `paid_amount` on that appointment
      - if invoice is submitted and fully paid:
          - if files attached -> status = "Completed"
          - else -> status = "Files To Be Uploaded"
        elif partially paid -> status = "Pending Payment"
        else -> status = "To Be Invoiced"
    - When invoice fully paid, optionally mark other `Pending Payment` appointments for the same patient as `Completed`.
    """
    try:
        invoice = frappe.get_doc("Sales Invoice", invoice_name)
        print(f"Updating appointments for invoice {invoice.name}")

        items = [
            i for i in (invoice.items or []) if i.get("reference_dt") == "Patient Appointment" and i.get("reference_dn")
        ]
        if not items:
            return

        paid = float(invoice.paid_amount or 0)
        grand = float(invoice.grand_total or 0)

        linked_patients = set()

        for item in items:
            appt_id = item.get("reference_dn")
            if not appt_id or not frappe.db.exists("Patient Appointment", appt_id):
                continue

            patient = frappe.db.get_value("Patient Appointment", appt_id, "patient")
            if patient:
                linked_patients.add(patient)

            files_exist = _appointment_has_files(appt_id)

            # Only mark appointment as invoiced when the Sales Invoice is submitted (docstatus == 1).
            # Avoid setting `invoiced` during draft/insert/update which can trigger
            # validation that the appointment is already invoiced during submit.

            updates = {
                "invoice_id": invoice.name,
                "invoice_status": invoice.get("status") or "",
                "paid_amount": paid,
            }
            print(f" invoice.docstatus={invoice.docstatus}, paid={paid}, grand={grand}, files_exist={files_exist}")
            if invoice.docstatus == 1:  # submitted
                # Determine if any Payment Entry references this invoice
                try:
                    payment_ref = frappe.db.sql(
                        "SELECT parent FROM `tabPayment Entry Reference` WHERE reference_doctype=%s AND reference_name=%s LIMIT 1",
                        ("Sales Invoice", invoice.name),
                        as_dict=True,
                    )
                    payment_exists = bool(payment_ref)
                except Exception:
                    payment_exists = False

                if not payment_exists:
                    # Invoice submitted but no payment entry recorded yet
                    updates.update({"status": "Pending Payment"})
                else:
                    # There is at least one payment entry for this invoice
                    # If files attached -> Completed, else require files upload
                    if files_exist:
                        updates.update({"status": "Completed", "payment_time": now_datetime()})
                    else:
                        updates.update({"status": "Files To Be Uploaded", "payment_time": now_datetime()})
            else:
                updates.update({"status": "To Be Invoiced"})

            frappe.db.set_value("Patient Appointment", appt_id, updates, update_modified=False)

        # If invoice fully paid, mark other pending appointments for same patient(s) as Completed
        if grand > 0 and paid >= grand and linked_patients:
            for patient in linked_patients:
                pending_appts = frappe.get_all(
                    "Patient Appointment", filters={"patient": patient, "status": "Pending Payment"}, fields=["name"]
                )
                for pa in pending_appts:
                    try:
                        frappe.db.set_value("Patient Appointment", pa.name, {"status": "Completed", "payment_time": now_datetime()}, update_modified=False)
                    except Exception:
                        frappe.log_error(f"Failed to mark appointment {pa.name} Completed after invoice payment", "InvoiceSync")

        frappe.db.commit()
    except Exception as e:
        frappe.log_error(str(e), "update_appointments_for_invoice")


def on_sales_invoice_event(doc, method=None):
    """Hook target for Sales Invoice doc_events"""
    try:
        update_appointments_for_invoice(doc.name)
    except Exception as e:
        frappe.log_error(str(e), "on_sales_invoice_event")


def on_payment_entry_submit(doc, method=None):
    """Hook target for Payment Entry - update invoices referenced by the payment"""
    try:
        # Payment Entry may reference invoices via `references` child table
        for ref in getattr(doc, "references", []) or []:
            if ref.get("reference_doctype") == "Sales Invoice" and ref.get("reference_name"):
                update_appointments_for_invoice(ref.get("reference_name"))
    except Exception as e:
        frappe.log_error(str(e), "on_payment_entry_submit")


def on_file_insert(doc, method=None):
    """When a File is attached/removed, re-evaluate appointment status.

    Triggered on File `after_insert` and `on_trash` via hooks.
    If a File is attached to a `Patient Appointment` which currently has status
    `Files To Be Uploaded`, and the linked invoice is fully paid, mark as Completed.
    """
    try:
        attached_to_doctype = getattr(doc, "attached_to_doctype", None)
        attached_to_name = getattr(doc, "attached_to_name", None)
        if attached_to_doctype != "Patient Appointment" or not attached_to_name:
            return

        appt_id = attached_to_name
        try:
            appt = frappe.get_doc("Patient Appointment", appt_id)
        except Exception:
            return

        # Only act when appointment is in 'Files To Be Uploaded'
        if appt.status not in ("Files To Be Uploaded",):
            return

        # If linked invoice exists and is fully paid -> mark Completed
        if appt.invoice_id:
            try:
                inv = frappe.get_doc("Sales Invoice", appt.invoice_id)
                paid = float(inv.paid_amount or 0)
                grand = float(inv.grand_total or 0)
                if grand > 0 and paid >= grand:
                    # files now present -> Completed
                    if _appointment_has_files(appt_id):
                        frappe.db.set_value("Patient Appointment", appt_id, {"status": "Completed", "payment_time": now_datetime()}, update_modified=False)
                        frappe.db.commit()
            except Exception:
                pass

    except Exception as e:
        frappe.log_error(str(e), "on_file_insert")
