import frappe
from frappe import _
from frappe.utils import cstr, get_datetime, nowdate
import json
from mob_clinic.mob_clinic.api import clinic as clinic_helper

@frappe.whitelist(methods=['GET'])
def get_patients(fields=None, filters=None, limit_start=0, limit_page_length=20, order_by="creation desc", clinic=None):
    """
    Get list of patients with pagination and filtering
    
    Args:
        fields (str): Comma-separated field names to return
        filters (str): JSON string of filters
        limit_start (int): Pagination start
        limit_page_length (int): Records per page  
        order_by (str): Sort order
        
    Returns:
        dict: List of patients with pagination info
    """
    try:
        # Parse fields
        if fields:
            if isinstance(fields, str):
                fields = [f.strip() for f in fields.split(',')]
        else:
            fields = ["name", "patient_name", "mobile", "email", "sex", "dob", "status", "image"]
            
        # Parse filters
        if filters:
            if isinstance(filters, str):
                filters = json.loads(filters)
        else:
            filters = {}
            
        # Get current practitioner for context but don't filter by it in search
        practitioner = get_current_practitioner()
        
        # Resolve clinic and apply filter
        resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name if practitioner else None, clinic)
        if resolved_clinic:
            filters["primary_clinic"] = resolved_clinic
        
        # Note: Search should include all patients, not filter by practitioner
        # This allows practitioners to find and add new patients to their practice
        
        # Get patients
        patients = frappe.get_all(
            "Patient",
            fields=fields,
            filters=filters,
            limit_start=limit_start,
            limit_page_length=limit_page_length,
            order_by=order_by
        )
        
        # Enhance patient data with custom fields
        enhanced_patients = []
        for patient in patients:
            # patient is a dict returned by frappe.get_list
            patient_name = patient.get("name")
            patient_doc = frappe.get_doc("Patient", patient_name)

            # Calculate numeric age from DOB
            age_years = None
            if patient_doc.dob:
                from dateutil.relativedelta import relativedelta
                from frappe.utils import getdate
                age_obj = relativedelta(getdate(), getdate(patient_doc.dob))
                age_years = age_obj.years

            enhanced_patient = dict(patient)
            enhanced_patient.update({
                "age": age_years,
                "avatar": getattr(patient_doc, 'profile_image', None) or patient_doc.get("image"),
                "last_visit": get_last_appointment_date(patient_name, practitioner.name if practitioner else None),
                "total_visits": get_total_appointments(patient_name, practitioner.name if practitioner else None),
                "pending_amount": get_pending_amount(patient_name),
                "preferred_language": getattr(patient_doc, 'preferred_language', 'English')
            })

            enhanced_patients.append(enhanced_patient)
        
        # Get total count for pagination
        total_count = frappe.db.count("Patient", filters)
        
        return {
            "message": "success",
            "data": enhanced_patients,
            "total_count": total_count,
            "page_length": limit_page_length,
            "start": limit_start
        }
        
    except Exception as e:
        frappe.log_error(f"Get patients error: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error retrieving patients"
        }

@frappe.whitelist(methods=['GET'])
def get_patient(patient_id):
    """
    Get detailed patient information
    
    Args:
        patient_id (str): Patient ID
        
    Returns:
        dict: Detailed patient information
    """
    try:
        patient = frappe.get_doc("Patient", patient_id)
        practitioner = get_current_practitioner()
        
        # Calculate numeric age from DOB
        age_years = None
        if patient.dob:
            try:
                from dateutil.relativedelta import relativedelta
                from frappe.utils import getdate
                age_obj = relativedelta(getdate(), getdate(patient.dob))
                age_years = age_obj.years
            except Exception as age_error:
                frappe.log_error(f"Error calculating age: {str(age_error)}", "Get Patient Age")
        
        patient_data = {
            "patient_id": patient.name,
            "name": patient.patient_name,
            "first_name": patient.first_name or "",
            "middle_name": patient.middle_name or "",
            "last_name": patient.last_name or "",
            "sex": patient.sex,
            "blood_group": patient.blood_group,
            "dob": cstr(patient.dob),
            "age": age_years,
            "mobile": patient.mobile,
            "phone": patient.phone,
            "email": patient.email,
            "status": patient.status,
            "image": patient.image,
            "avatar": getattr(patient, 'profile_image', None) or patient.image,
            "preferred_language": getattr(patient, 'preferred_language', 'English'),
            "last_app_login": getattr(patient, 'last_app_login', None),
            "occupation": patient.occupation,
            "marital_status": patient.marital_status,
            "insurance_details": getattr(patient, 'insurance_details', ''),
            "medical_history": patient.medical_history if hasattr(patient, 'medical_history') else None,
            "address": getattr(patient, 'address', None),
            "uid": patient.uid
        }
        
        # Get address - try custom field first, then linked address
        address = None
        if hasattr(patient, 'address') and patient.address:
            address = patient.address
        else:
            # Try to get linked address
            try:
                addresses = frappe.get_all(
                    "Dynamic Link",
                    filters={
                        "link_doctype": "Patient",
                        "link_name": patient.name,
                        "parenttype": "Address"
                    },
                    fields=["parent"],
                    limit=1
                )
                if addresses:
                    addr_doc = frappe.get_doc("Address", addresses[0].parent)
                    # Combine address fields
                    address_parts = [
                        addr_doc.address_line1,
                        addr_doc.address_line2,
                        addr_doc.city,
                        addr_doc.state,
                        addr_doc.pincode
                    ]
                    address = ", ".join([part for part in address_parts if part])
            except Exception:
                pass
        
        patient_data["address"] = address
        
        # Get medical history
        if hasattr(patient, 'allergies') and patient.allergies:
            allergies = []
            for allergy in patient.allergies:
                allergies.append({
                    "allergy": allergy.allergy,
                    "allergen": allergy.allergen
                })
            patient_data["allergies"] = allergies
            
        # Get medication history
        if hasattr(patient, 'medication') and patient.medication:
            print(f"DEBUG get_patient: Processing medications")
            medications = []
            for med in patient.medication:
                medications.append({
                    "medication": med.medication,
                    "medical_code": med.medical_code
                })
            patient_data["medications"] = medications
            
        # Note: medical_history is already handled in patient_data dict above as a text field
        # Skip the child table processing as we're using the Small Text field instead
            
        # Get emergency contact
        if hasattr(patient, 'patient_relation') and patient.patient_relation:
            emergency_contacts = []
            for relation in patient.patient_relation:
                emergency_contacts.append({
                    "name": relation.patient_relation,
                    "relation": relation.relation,
                    "phone": relation.phone,
                    "email": relation.email
                })
            patient_data["emergency_contacts"] = emergency_contacts
            
        # Get appointment statistics
        if practitioner:
            try:
                patient_data.update({
                    "last_visit": get_last_appointment_date(patient.name, practitioner.name),
                    "next_appointment": get_next_appointment_date(patient.name, practitioner.name),
                    "total_visits": get_total_appointments(patient.name, practitioner.name),
                    "pending_amount": get_pending_amount(patient.name),
                    "last_treatment": get_last_treatment(patient.name, practitioner.name)
                })
            except Exception as stats_error:
                frappe.log_error(f"Error getting patient statistics: {str(stats_error)}", "Get Patient Stats")
                # Continue without statistics
        
        return {
            "message": "success",
            "data": patient_data
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": f"Patient {patient_id} not found"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        frappe.log_error(f"Get patient error: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error retrieving patient details"
        }

@frappe.whitelist(methods=['POST'])
def create_patient(**kwargs):
    """
    Create a new patient record
    
    Args:
        **kwargs: Patient data fields
        
    Returns:
        dict: Created patient information
    """
    try:
        # Validate required fields
        required_fields = ["first_name", "sex"]
        for field in required_fields:
            if not kwargs.get(field):
                frappe.local.response["http_status_code"] = 400
                return {
                    "exc_type": "ValidationError",
                    "message": f"Missing required field: {field}"
                }
        
        # Allow duplicate mobile numbers: real-world scenarios may have
        # multiple patients sharing the same contact number. Do not block
        # creation for duplicate mobile entries. Log a warning for audit.
        if kwargs.get("mobile"):
            try:
                existing_patient = frappe.db.exists("Patient", {"mobile": kwargs["mobile"]})
                if existing_patient:
                    # Lightweight audit log — not a blocking validation
                    frappe.log_error(
                        f"Creating patient with duplicate mobile: {kwargs['mobile']}",
                        "Duplicate Mobile Warning"
                    )
            except Exception:
                # If logging fails for any reason, continue with creation
                pass
        
        # Handle age to dob conversion if age is provided but dob is not
        if kwargs.get("age") and not kwargs.get("dob"):
            from frappe.utils import add_years, today, getdate
            try:
                age = int(kwargs.get("age"))
                # Calculate approximate DOB (first day of birth year)
                dob = add_years(getdate(today()), -age)
                kwargs["dob"] = dob
                # Remove age from kwargs as it's a calculated field
                kwargs.pop("age", None)
            except (ValueError, TypeError):
                # If age conversion fails, just skip it
                kwargs.pop("age", None)
        else:
            # Remove age if provided, as it's read-only and calculated from dob
            kwargs.pop("age", None)
        
        # Handle medical_history - if it's a JSON string, keep it as is
        # The Patient DocType has medical_history as Small Text field which can store JSON
        if kwargs.get("medical_history"):
            # If it's already a string (JSON), keep it
            if isinstance(kwargs["medical_history"], str):
                pass  # Keep as is
            else:
                # If it's a dict/object, convert to JSON string
                kwargs["medical_history"] = json.dumps(kwargs["medical_history"])
        
        # Handle address field - Patient DocType doesn't have a direct address field
        # Remove it to prevent field not found error
        address_data = kwargs.pop("address", None)
        
        # Resolve clinic
        practitioner = get_current_practitioner()
        clinic = kwargs.get("clinic")
        resolved_clinic = clinic_helper.resolve_active_clinic(practitioner.name if practitioner else None, clinic)
        
        if clinic and practitioner and not clinic_helper.validate_practitioner_access(practitioner.name, resolved_clinic):
             frappe.throw(_("Practitioner does not have access to the requested clinic"), frappe.PermissionError)
             
        if resolved_clinic:
            kwargs["primary_clinic"] = resolved_clinic
            
        # Remove clinic from kwargs if it was passed
        if "clinic" in kwargs:
            del kwargs["clinic"]
        
        # Create patient document
        patient = frappe.get_doc({
            "doctype": "Patient",
            **kwargs
        })
        
        # Set naming series if not provided
        if not kwargs.get("naming_series"):
            patient.naming_series = "HLC-PAT-.YYYY.-"
        
        # Disable invite_user to prevent website user creation on insert
        patient.invite_user = 0
        
        patient.flags.ignore_permissions = True
        patient.flags.ignore_mandatory = True
        
        # Use a different approach: set the name manually to avoid naming series issues
        try:
            # Try normal insert first
            patient.insert(ignore_permissions=True)
        except frappe.exceptions.NameError:
            # If naming fails, generate name manually
            from frappe.model.naming import make_autoname
            patient.name = make_autoname("HLC-PAT-.YYYY.-.#####")
            patient.flags.name_set = True
            patient.insert(ignore_permissions=True, set_name=patient.name)
        
        frappe.db.commit()
        
        # If address was provided, store it as a custom field or create address document
        if address_data:
            try:
                # Try to set it as a custom field if it exists
                frappe.db.set_value("Patient", patient.name, "address", address_data, update_modified=False)
                frappe.db.commit()
            except Exception:
                # If custom field doesn't exist, just log and continue
                pass
        
        # Get the created patient with enhanced data
        created_patient = get_patient(patient.name)
        patient_data = created_patient.get("data")
        
        return {
            "message": "Patient created successfully",
            "data": patient_data
        }
        
    except frappe.DuplicateEntryError:
        frappe.local.response["http_status_code"] = 409
        return {
            "exc_type": "ValidationError",
            "message": "Patient with similar details already exists"
        }
    except Exception as e:
        error_msg = str(e)
        # Don't log errors during tests to avoid nested error log issues
        import os
        if not os.environ.get('CI'):
            try:
                frappe.log_error(error_msg[:500], "Patient Creation")
            except:
                pass  # Ignore if error logging fails
        
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error creating patient: {error_msg[:100]}"
        }

@frappe.whitelist(methods=['POST', 'PUT'])
def update_patient(patient_id, **kwargs):
    """
    Update patient information
    
    Args:
        patient_id (str): Patient ID
        **kwargs: Fields to update
        
    Returns:
        dict: Updated patient information
    """
    try:
        patient = frappe.get_doc("Patient", patient_id)
        
        # Disable invite_user to prevent website user creation
        if hasattr(patient, 'invite_user'):
            patient.invite_user = 0
        
        # Handle age -> dob conversion if age provided but dob not
        if kwargs.get("age") and not kwargs.get("dob"):
            try:
                from frappe.utils import add_years, today, getdate
                age = int(kwargs.get("age"))
                dob = add_years(getdate(today()), -age)
                kwargs["dob"] = dob
            except Exception:
                # ignore conversion errors
                pass

        # Update allowed fields (include name parts and dob)
        allowed_fields = [
            'first_name', 'middle_name', 'last_name', 'patient_name',
            'mobile', 'phone', 'email', 'occupation', 'marital_status',
            'profile_image', 'preferred_language', 'insurance_details', 'dob', 'address'
        ]

        updated_fields = []
        # Apply simple field updates
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(patient, field):
                setattr(patient, field, value)
                updated_fields.append(field)

        # medical_history may be a dict/object or JSON string; persist appropriately
        if 'medical_history' in kwargs:
            mh = kwargs.get('medical_history')
            try:
                import json as _json
                if isinstance(mh, dict):
                    mh_val = _json.dumps(mh)
                else:
                    # if it's a string, keep as-is
                    mh_val = mh
                if hasattr(patient, 'medical_history'):
                    patient.medical_history = mh_val
                else:
                    # fallback to DB set if field not present on Doc
                    frappe.db.set_value('Patient', patient_id, 'medical_history', mh_val, update_modified=False)
                if 'medical_history' not in updated_fields:
                    updated_fields.append('medical_history')
            except Exception:
                # ignore errors and continue
                pass

        # address handling: try to set field if exists, else fallback to db.set_value
        if 'address' in kwargs:
            addr_val = kwargs.get('address')
            try:
                if hasattr(patient, 'address'):
                    patient.address = addr_val
                else:
                    frappe.db.set_value('Patient', patient_id, 'address', addr_val, update_modified=False)
                if 'address' not in updated_fields:
                    updated_fields.append('address')
            except Exception:
                pass

        # If first_name/last_name provided but patient_name not, compose it
        if (('first_name' in kwargs or 'last_name' in kwargs) and 'patient_name' not in kwargs):
            first = kwargs.get('first_name', getattr(patient, 'first_name', '') or '')
            last = kwargs.get('last_name', getattr(patient, 'last_name', '') or '')
            composed = (first + ' ' + last).strip()
            if composed:
                patient.patient_name = composed
                if 'patient_name' not in updated_fields:
                    updated_fields.append('patient_name')

        # If patient_name provided explicitly, ensure it's set
        if 'patient_name' in kwargs and hasattr(patient, 'patient_name'):
            patient.patient_name = kwargs.get('patient_name')
            if 'patient_name' not in updated_fields:
                updated_fields.append('patient_name')
        
        if updated_fields:
            patient.flags.ignore_permissions = True
            patient.flags.ignore_links = True
            # Prevent on_update hooks that try to create website user
            patient.flags.ignore_validate_update_after_submit = True
            patient.save(ignore_permissions=True)
            frappe.db.commit()
            
        # Persist changes if any fields were updated
        if updated_fields:
            patient.flags.ignore_permissions = True
            patient.flags.ignore_links = True
            # Prevent on_update hooks that try to create website user
            patient.flags.ignore_validate_update_after_submit = True
            patient.save(ignore_permissions=True)
            frappe.db.commit()

        # Return updated patient data
        updated_patient = get_patient(patient_id)
        
        return {
            "message": "Patient updated successfully",
            "updated_fields": updated_fields,
            "data": updated_patient.get("data")
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": f"Patient {patient_id} not found"
        }
    except Exception as e:
        error_msg = str(e)
        # Log with shorter title
        frappe.log_error(error_msg, "Patient Update")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error updating patient"
        }


@frappe.whitelist(methods=['DELETE', 'POST'])
def delete_patient(patient_id):
    """
    Delete a patient record
    
    Args:
        patient_id (str): Patient ID
        
    Returns:
        dict: Deletion status
    """
    try:
        # Check if patient exists
        if not frappe.db.exists("Patient", patient_id):
            frappe.local.response["http_status_code"] = 404
            return {
                "exc_type": "NotFound",
                "message": f"Patient {patient_id} not found"
            }
        
        # Get the patient
        patient = frappe.get_doc("Patient", patient_id)
        # --- Best-effort: unlink Dynamic Link entries that reference this Patient
        # Some setups add a Contact/Address linked to Patient via Dynamic Link which
        # prevents deletion. Remove those links (do not delete the Contact/Address).
        try:
            # Unlink Contacts that have a Dynamic Link to this patient
            contacts = frappe.get_all(
                "Dynamic Link",
                filters={
                    "link_doctype": "Patient",
                    "link_name": patient_id,
                    "parenttype": "Contact",
                },
                fields=["parent"],
            )
            for c in contacts:
                contact_name = c.get("parent")
                try:
                    contact = frappe.get_doc("Contact", contact_name)
                    if hasattr(contact, "links") and contact.links:
                        new_links = [ln for ln in contact.links if not (ln.link_doctype == "Patient" and ln.link_name == patient_id)]
                        if len(new_links) != len(contact.links):
                            contact.links = new_links
                            contact.flags.ignore_permissions = True
                            contact.save()
                except Exception:
                    # Continue even if unlinking a contact fails
                    continue

            # Unlink Addresses that have a Dynamic Link to this patient
            addresses = frappe.get_all(
                "Dynamic Link",
                filters={
                    "link_doctype": "Patient",
                    "link_name": patient_id,
                    "parenttype": "Address",
                },
                fields=["parent"],
            )
            for a in addresses:
                addr_name = a.get("parent")
                try:
                    addr = frappe.get_doc("Address", addr_name)
                    if hasattr(addr, "links") and addr.links:
                        new_links = [ln for ln in addr.links if not (ln.link_doctype == "Patient" and ln.link_name == patient_id)]
                        if len(new_links) != len(addr.links):
                            addr.links = new_links
                            addr.flags.ignore_permissions = True
                            addr.save()
                except Exception:
                    continue
        except Exception:
            # If anything goes wrong, don't block deletion flow — we'll surface the error later
            pass
        
        # Validate patient belongs to user's clinic (if not Administrator)
        current_user = frappe.session.user
        if current_user != "Administrator":
            from mob_clinic.mob_clinic.api.clinic import resolve_active_clinic
            
            practitioner_name = frappe.db.get_value(
                "Healthcare Practitioner",
                {"user_id": current_user},
                "name"
            )
            
            if practitioner_name:
                active_clinic = resolve_active_clinic(practitioner_name)
                if patient.primary_clinic and patient.primary_clinic != active_clinic:
                    frappe.throw(_("You don't have permission to delete patients from other clinics"))
        
        deleted_docs = {
            "invoices": 0,
            "payments": 0,
            "appointments": 0,
            "medical_records": 0,
            "encounters": 0,
            "events": 0
        }
        
        # Store current user and switch to Administrator for deletion operations
        original_user = frappe.session.user
        frappe.set_user("Administrator")
        
        try:
            # Step 1: Delete all Sales Invoices and their payments
            invoices = frappe.get_all(
                "Sales Invoice",
                filters={"patient": patient_id},
                fields=["name", "docstatus"]
            )
            
            for inv in invoices:
                try:
                    invoice = frappe.get_doc("Sales Invoice", inv.name)
                    
                    # Cancel invoice first
                    if invoice.docstatus == 1:
                        invoice.cancel()
                    
                    # Delete payment entries
                    payment_refs = frappe.db.sql("""
                        SELECT DISTINCT parent 
                        FROM `tabPayment Entry Reference` 
                        WHERE reference_name = %s AND reference_doctype = 'Sales Invoice'
                    """, inv.name, as_dict=True)
                    
                    for pr in payment_refs:
                        try:
                            pe = frappe.get_doc("Payment Entry", pr.parent)
                            if pe.docstatus == 1:
                                pe.cancel()
                            frappe.delete_doc("Payment Entry", pr.parent, force=True, ignore_permissions=True)
                            deleted_docs["payments"] += 1
                        except Exception:
                            # Force delete if standard delete fails
                            frappe.db.sql("DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no = %s", pr.parent)
                            frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no = %s", pr.parent)
                            frappe.db.sql("DELETE FROM `tabPayment Entry Reference` WHERE parent = %s", pr.parent)
                            frappe.db.sql("DELETE FROM `tabPayment Entry` WHERE name = %s", pr.parent)
                            deleted_docs["payments"] += 1
                    
                    # Delete invoice ledger entries
                    frappe.db.sql("DELETE FROM `tabPayment Ledger Entry` WHERE voucher_no = %s", inv.name)
                    frappe.db.sql("DELETE FROM `tabGL Entry` WHERE voucher_no = %s", inv.name)
                    
                    frappe.delete_doc("Sales Invoice", inv.name, force=True, ignore_permissions=True)
                    deleted_docs["invoices"] += 1
                    
                except Exception as inv_error:
                    frappe.logger().error(f"Error deleting invoice {inv.name}: {str(inv_error)}")
            
            # Step 2: Delete Patient Appointments
            appointments = frappe.get_all(
                "Patient Appointment",
                filters={"patient": patient_id},
                fields=["name", "docstatus"]
            )
            
            for appt in appointments:
                try:
                    appt_doc = frappe.get_doc("Patient Appointment", appt.name)
                    if appt_doc.docstatus == 1:
                        appt_doc.cancel()
                    frappe.delete_doc("Patient Appointment", appt.name, force=True, ignore_permissions=True)
                    deleted_docs["appointments"] += 1
                except Exception as appt_error:
                    frappe.logger().error(f"Error deleting appointment {appt.name}: {str(appt_error)}")
            
            # Step 3: Delete Patient Encounters
            encounters = frappe.get_all(
                "Patient Encounter",
                filters={"patient": patient_id},
                fields=["name", "docstatus"]
            )
            
            for enc in encounters:
                try:
                    enc_doc = frappe.get_doc("Patient Encounter", enc.name)
                    if enc_doc.docstatus == 1:
                        enc_doc.cancel()
                    frappe.delete_doc("Patient Encounter", enc.name, force=True, ignore_permissions=True)
                    deleted_docs["encounters"] += 1
                except Exception as enc_error:
                    frappe.logger().error(f"Error deleting encounter {enc.name}: {str(enc_error)}")
            
            # Step 4: Delete Patient Medical Records
            medical_records = frappe.get_all(
                "Patient Medical Record",
                filters={"patient": patient_id},
                fields=["name"]
            )
            
            for record in medical_records:
                try:
                    frappe.delete_doc("Patient Medical Record", record.name, force=True, ignore_permissions=True)
                    deleted_docs["medical_records"] += 1
                except Exception as rec_error:
                    frappe.logger().error(f"Error deleting medical record {record.name}: {str(rec_error)}")
            
            # Step 5: Delete Events (Calendar events) linked to patient
            events = frappe.db.sql("""
                SELECT DISTINCT parent
                FROM `tabDynamic Link`
                WHERE link_doctype = 'Patient' 
                AND link_name = %s
                AND parenttype = 'Event'
            """, patient_id, as_dict=True)
            
            for evt in events:
                try:
                    frappe.delete_doc("Event", evt.parent, force=True, ignore_permissions=True)
                    deleted_docs["events"] += 1
                except Exception:
                    # Force delete from DB if needed
                    frappe.db.sql("DELETE FROM `tabDynamic Link` WHERE parent = %s AND parenttype = 'Event'", evt.parent)
                    frappe.db.sql("DELETE FROM `tabEvent` WHERE name = %s", evt.parent)
                    deleted_docs["events"] += 1
            
            # Step 6: Delete any remaining dynamic links to this patient
            frappe.db.sql("""
                DELETE FROM `tabDynamic Link` 
                WHERE link_doctype = 'Patient' AND link_name = %s
            """, patient_id)
            
            # Store info before deletion
            patient_name = patient.patient_name
            mobile = patient.mobile
            
            # Step 7: Finally, delete the patient
            frappe.delete_doc("Patient", patient_id, force=True, ignore_permissions=True)
            frappe.db.commit()
            
            return {
                "message": "Patient deleted successfully",
                "data": {
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "mobile": mobile,
                    "deleted_items": deleted_docs
                }
            }
            
        finally:
            # Always restore original user
            frappe.set_user(original_user)
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": f"Patient {patient_id} not found"
        }
    except Exception as e:
        frappe.log_error(str(e)[:500], "Delete Patient Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Error deleting patient: {str(e)}"
        }


@frappe.whitelist(methods=['GET'])
def search_patients(search_term, limit=10):
    """
    Search patients by name, mobile, or patient ID
    
    Args:
        search_term (str): Search query
        limit (int): Maximum results to return
        
    Returns:
        dict: Search results
    """
    try:
        practitioner = get_current_practitioner()
        
        # Base filters (empty for search - we want to search ALL patients)
        base_filters = {}
        
        # Build OR conditions for searching across multiple fields
        or_filters = [
            ["patient_name", "like", f"%{search_term}%"],
            ["mobile", "like", f"%{search_term}%"],
            ["name", "like", f"%{search_term}%"]
        ]
        
        # Get patients matching search criteria
        patients = frappe.get_all(
            "Patient",
            fields=["name", "patient_name", "mobile", "sex", "dob", "image"],
            filters=base_filters,
            or_filters=or_filters,
            limit=limit,
            order_by="patient_name"
        )
        
        # Enhance search results
        search_results = []
        for patient in patients:
            patient_name = patient.get("name")
            patient_doc = frappe.get_doc("Patient", patient_name)
            search_results.append({
                "patient_id": patient_name,
                "name": patient.get("patient_name"),
                "mobile": patient.get("mobile"),
                "sex": patient.get("sex"),
                "dob": cstr(patient.get("dob")),
                "avatar": getattr(patient_doc, 'profile_image', None) or patient.get("image"),
                "last_visit": get_last_appointment_date(patient_name, practitioner.name if practitioner else None)
            })
        
        return {
            "message": "success",
            "data": search_results
        }
        
    except Exception as e:
        frappe.log_error(f"Search patients error: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error searching patients"
        }

# Helper Functions
def get_current_practitioner():
    """Get current user's healthcare practitioner record"""
    try:
        return frappe.get_doc("Healthcare Practitioner", {"user_id": frappe.session.user})
    except frappe.DoesNotExistError:
        return None

def get_last_appointment_date(patient_id, practitioner_id=None):
    """Get patient's last appointment date"""
    try:
        filters = {"patient": patient_id, "status": ["!=", "Cancelled"]}
        if practitioner_id:
            filters["practitioner"] = practitioner_id
            
        last_appointment = frappe.get_all(
            "Patient Appointment",
            filters=filters,
            fields=["appointment_datetime"],
            order_by="appointment_datetime desc",
            limit=1
        )
        
        if last_appointment:
            return cstr(last_appointment[0].appointment_datetime)
        return None
    except:
        return None

def get_next_appointment_date(patient_id, practitioner_id=None):
    """Get patient's next appointment date"""
    try:
        filters = {
            "patient": patient_id,
            "status": ["in", ["Open", "Scheduled", "Confirmed"]],
            "appointment_date": [">=", nowdate()]
        }
        if practitioner_id:
            filters["practitioner"] = practitioner_id
            
        next_appointment = frappe.get_all(
            "Patient Appointment",
            filters=filters,
            fields=["appointment_datetime"],
            order_by="appointment_datetime asc",
            limit=1
        )
        
        if next_appointment:
            return cstr(next_appointment[0].appointment_datetime)
        return None
    except:
        return None

def get_total_appointments(patient_id, practitioner_id=None):
    """Get total appointment count for patient"""
    try:
        filters = {"patient": patient_id, "status": ["!=", "Cancelled"]}
        if practitioner_id:
            filters["practitioner"] = practitioner_id
            
        return frappe.db.count("Patient Appointment", filters)
    except:
        return 0

def get_pending_amount(patient_id):
    """Get pending payment amount for patient"""
    try:
        # Get outstanding amount from Sales Invoice
        pending = frappe.db.sql("""
            SELECT SUM(outstanding_amount)
            FROM `tabSales Invoice`
            WHERE patient = %s AND docstatus = 1 AND outstanding_amount > 0
        """, patient_id)
        
        return pending[0][0] if pending and pending[0][0] else 0
    except:
        return 0

def get_last_treatment(patient_id, practitioner_id=None):
    """Get last treatment details for patient"""
    try:
        filters = {"patient": patient_id}
        if practitioner_id:
            filters["practitioner"] = practitioner_id
            
        last_record = frappe.get_all(
            "Patient Medical Record",
            filters=filters,
            fields=["subject", "communication_date"],
            order_by="communication_date desc",
            limit=1
        )
        
        if last_record:
            return {
                "treatment": last_record[0].subject,
                "date": cstr(last_record[0].communication_date)
            }
        return None
    except:
        return None