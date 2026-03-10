"""
Clinic Profile Management API
Manage clinic information, branding, settings, and customization
"""

import frappe
from frappe import _
import json
from frappe.utils import get_url, cstr
from datetime import datetime
from mob_clinic.mob_clinic.api.role_access import assert_page_access


def _full_url(path):
	"""Return a full URL for `path`. If `path` is already absolute, return it unchanged."""
	if not path:
		return None
	if path.startswith("http://") or path.startswith("https://"):
		return path
	try:
		return get_url(path)
	except Exception:
		return path

def _normalize_time(value):
	"""Normalize input time to HH:MM:SS."""
	if not value:
		return None
	if isinstance(value, str):
		for fmt in ("%H:%M:%S", "%H:%M"):
			try:
				return datetime.strptime(value, fmt).strftime("%H:%M:%S")
			except Exception:
				continue
	return cstr(value)


def _get_practitioner_for_clinic(clinic):
	"""Resolve the practitioner whose schedule should be read/updated for this request."""
	practitioner = None

	try:
		practitioner = frappe.get_doc("Healthcare Practitioner", {"user_id": frappe.session.user})
	except Exception:
		practitioner = None

	if practitioner:
		if not clinic or practitioner.get("primary_company") == clinic:
			return practitioner

	if clinic:
		try:
			practitioner_name = frappe.db.get_value(
				"Healthcare Practitioner",
				{"primary_company": clinic, "status": "Active"},
				"name"
			)
			if practitioner_name:
				return frappe.get_doc("Healthcare Practitioner", practitioner_name)
		except Exception:
			return None

	return practitioner


def _extract_practitioner_schedule(practitioner):
	"""Return the first configured working-hours block for a practitioner."""
	start_time = None
	end_time = None

	if practitioner and hasattr(practitioner, "clinic_working_hours"):
		for row in practitioner.clinic_working_hours:
			if row.is_working_day:
				start_time = cstr(row.start_time)
				end_time = cstr(row.end_time)
				break

	return {
		"start_time": start_time,
		"end_time": end_time,
	}


def _upsert_practitioner_schedule(practitioner, start_time=None, end_time=None):
	"""Apply the same working hours across all weekdays for the practitioner."""
	normalized_start = _normalize_time(start_time)
	normalized_end = _normalize_time(end_time)

	days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
	existing = {}
	if hasattr(practitioner, "clinic_working_hours"):
		for row in practitioner.clinic_working_hours:
			existing[row.day] = row

	for day in days:
		row = existing.get(day)
		if not row:
			row = practitioner.append("clinic_working_hours", {})
			row.day = day
			row.is_working_day = 1
		if normalized_start is not None:
			row.start_time = normalized_start
		if normalized_end is not None:
			row.end_time = normalized_end

	practitioner.flags.ignore_permissions = True
	practitioner.save(ignore_permissions=True)

	return {
		"start_time": normalized_start,
		"end_time": normalized_end,
	}


def _get_or_create_clinic_settings(clinic):
	if frappe.db.exists("Clinic Settings", clinic):
		return frappe.get_doc("Clinic Settings", clinic)

	settings = frappe.new_doc("Clinic Settings")
	settings.clinic = clinic
	return settings


def _serialize_consultant_row(row):
	return {
		"consultant_id": row.name,
		"consultant_type": row.consultant_type,
		"practitioner": row.practitioner,
		"consultant_name": row.consultant_name,
		"mobile": row.mobile,
		"commission_type": row.commission_type,
		"commission_value": row.commission_value,
		"is_active": int(row.is_active or 0),
		"notes": row.notes,
	}


def _validate_consultant_payload(clinic, consultant_type, practitioner, consultant_name, commission_type, commission_value):
	if consultant_type not in {"Internal", "External"}:
		frappe.throw(_("Invalid consultant type"))

	if commission_type not in {"Percentage", "Fixed"}:
		frappe.throw(_("Invalid commission type"))

	commission_value = frappe.utils.flt(commission_value)
	if commission_value < 0:
		frappe.throw(_("Commission value cannot be negative"))
	if commission_type == "Percentage" and commission_value > 100:
		frappe.throw(_("Percentage commission cannot exceed 100"))

	if consultant_type == "Internal":
		if not practitioner:
			frappe.throw(_("Internal consultants must be linked to a practitioner"))
		practitioner_doc = frappe.get_doc("Healthcare Practitioner", practitioner)
		if practitioner_doc.get("primary_company") != clinic:
			frappe.throw(_("Selected practitioner does not belong to this clinic"))
		consultant_name = practitioner_doc.get("practitioner_name")
	elif not consultant_name:
		frappe.throw(_("Consultant name is required"))

	return consultant_name, commission_value

@frappe.whitelist(allow_guest=True)
def get_clinic_profile(clinic):
	"""
	Get complete clinic profile including basic info, address, branding, and settings
	
	Args:
		clinic: Company/Clinic name
	"""
	try:
		# Verify clinic exists
		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404
		
		# Get company/clinic basic info
		company = frappe.get_doc("Company", clinic)
		
		# Get clinic settings
		settings = None
		if frappe.db.exists("Clinic Settings", clinic):
			settings = frappe.get_doc("Clinic Settings", clinic)
		
		# Get primary address
		address_link = frappe.db.get_value(
			"Dynamic Link",
			{
				"link_doctype": "Company",
				"link_name": clinic,
				"parenttype": "Address"
			},
			"parent"
		)
		
		address_data = None
		if address_link:
			address = frappe.get_doc("Address", address_link)
			address_data = {
				"address_line1": address.address_line1,
				"address_line2": address.address_line2,
				"city": address.city,
				"state": address.state,
				"country": address.country,
				"pincode": address.pincode,
				"phone": address.phone,
				"email": address.email_id
			}
		
		# Build response
		profile = {
			"basic_info": {
				"clinic_name": company.company_name,
				"abbr": company.abbr,
				"logo_url": _full_url(company.company_logo) if company.company_logo else None,
				"phone": company.phone_no if hasattr(company, 'phone_no') else None,
				"email": company.email if hasattr(company, 'email') else None,
				"website": company.website if hasattr(company, 'website') else None,
				"registration_number": company.registration_number if hasattr(company, 'registration_number') else None,
				"tax_id": company.tax_id if hasattr(company, 'tax_id') else None
			},
			"address": address_data,
			"branding": None,
			"invoice_settings": None,
			"notifications": None,
			"social_media": None,
			"additional": None
		}
		
		# Determine practitioner working hours (fallback to None when not available)
		start_time = None
		end_time = None
		try:
			practitioner = _get_practitioner_for_clinic(clinic)
			schedule = _extract_practitioner_schedule(practitioner)
			start_time = schedule["start_time"]
			end_time = schedule["end_time"]
		except Exception:
			start_time = None
			end_time = None

		# Add settings data if available
		if settings:
			profile["branding"] = {
				"primary_color": settings.primary_color,
				"secondary_color": settings.secondary_color,
				"text_color": settings.text_color,
				"background_color": settings.background_color,
				"font_family": settings.font_family
			}
			
			profile["invoice_settings"] = {
				"header_text": settings.invoice_header_text,
				"footer_text": settings.invoice_footer_text,
				"terms_conditions": settings.invoice_terms_conditions,
				"signature_url": _full_url(settings.invoice_signature) if settings.invoice_signature else None,
				"seal_url": _full_url(settings.clinic_seal) if settings.clinic_seal else None,
				"show_logo": settings.show_logo_on_invoice,
				"show_seal": settings.show_seal_on_prescription
			}

		# include invoice template id if present
		try:
			profile["invoice_settings"]["template_id"] = getattr(settings, 'invoice_template_id', None)
		except Exception:
			profile["invoice_settings"]["template_id"] = None
		
		profile["notifications"] = {
			"appointment_reminder": settings.appointment_reminder_message,
			"payment_receipt": settings.payment_receipt_message,
			"prescription_message": settings.prescription_message,
			"sms_sender": settings.sms_sender_name
		}
		
		profile["social_media"] = {
			"facebook": settings.facebook_url,
			"instagram": settings.instagram_url,
			"twitter": settings.twitter_url,
			"google_maps": settings.google_maps_url
		}
		
		profile["additional"] = {
			"appointment_slot_duration": settings.appointment_slot_duration,
			"allow_online_booking": settings.allow_online_booking,
			"timezone": settings.timezone,
			"currency": settings.currency,
			"start_time": start_time,
			"end_time": end_time
		}
		
		return {"message": "success", "profile": profile}
	
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Clinic Profile Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def update_basic_info(clinic, phone=None, email=None, website=None, registration_number=None, tax_id=None):
	"""
	Update clinic basic information
	
	Args:
		clinic: Company/Clinic name
		phone: Phone number
		email: Email address
		website: Website URL
		registration_number: Registration/License number
		tax_id: Tax ID or GST number
	"""
	try:
		assert_page_access("settings")

		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404
		
		company = frappe.get_doc("Company", clinic)
		
		if phone:
			company.phone_no = phone
		if email:
			company.email = email
		if website:
			company.website = website
		if registration_number:
			company.registration_number = registration_number
		if tax_id:
			company.tax_id = tax_id
		
		company.flags.ignore_permissions = True
		company.save(ignore_permissions=True)
		frappe.db.commit()
		
		return {
			"message": "Basic information updated successfully",
			"basic_info": {
				"clinic_name": company.company_name,
				"phone": company.phone_no if hasattr(company, 'phone_no') else None,
				"email": company.email if hasattr(company, 'email') else None,
				"website": company.website if hasattr(company, 'website') else None,
				"registration_number": company.registration_number if hasattr(company, 'registration_number') else None,
				"tax_id": company.tax_id if hasattr(company, 'tax_id') else None
			}
		}
	
	except frappe.PermissionError:
		return {"message": "Not permitted"}, 403
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Update Basic Info Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def update_address(clinic, address_line1, city, state, country, pincode, 
				   address_line2=None, phone=None, email=None):
	"""
	Update or create clinic address
	
	Args:
		clinic: Company/Clinic name
		address_line1: Address line 1
		city: City
		state: State
		country: Country
		pincode: Postal/ZIP code
		address_line2: Address line 2 (optional)
		phone: Phone number (optional)
		email: Email address (optional)
	"""
	try:
		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404
		
		# Check if address already exists
		address_link = frappe.db.get_value(
			"Dynamic Link",
			{
				"link_doctype": "Company",
				"link_name": clinic,
				"parenttype": "Address"
			},
			"parent"
		)
		
		if address_link:
			# Update existing address
			address = frappe.get_doc("Address", address_link)
		else:
			# Create new address
			address = frappe.new_doc("Address")
			address.append("links", {
				"link_doctype": "Company",
				"link_name": clinic
			})
		
		address.address_line1 = address_line1
		address.address_line2 = address_line2
		address.city = city
		address.state = state
		address.country = country
		address.pincode = pincode
		address.phone = phone
		address.email_id = email
		address.address_type = "Billing"
		
		address.flags.ignore_permissions = True
		if address_link:
			address.save(ignore_permissions=True)
		else:
			address.insert(ignore_permissions=True)
		
		frappe.db.commit()
		
		return {
			"message": "Address updated successfully",
			"address": {
				"address_line1": address.address_line1,
				"address_line2": address.address_line2,
				"city": address.city,
				"state": address.state,
				"country": address.country,
				"pincode": address.pincode,
				"phone": address.phone,
				"email": address.email_id
			}
		}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Update Address Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def update_branding(clinic, primary_color=None, secondary_color=None, text_color=None, 
					background_color=None, font_family=None):
	"""
	Update clinic branding/theme settings
	
	Args:
		clinic: Company/Clinic name
		primary_color: Primary brand color
		secondary_color: Secondary brand color
		text_color: Text color
		background_color: Background color
		font_family: Font family name
	"""
	try:
		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404
		
		# Get or create clinic settings
		if frappe.db.exists("Clinic Settings", clinic):
			settings = frappe.get_doc("Clinic Settings", clinic)
		else:
			settings = frappe.new_doc("Clinic Settings")
			settings.clinic = clinic
		
		if primary_color:
			settings.primary_color = primary_color
		if secondary_color:
			settings.secondary_color = secondary_color
		if text_color:
			settings.text_color = text_color
		if background_color:
			settings.background_color = background_color
		if font_family:
			settings.font_family = font_family
		
		settings.flags.ignore_permissions = True
		if settings.is_new():
			settings.insert(ignore_permissions=True)
		else:
			settings.save(ignore_permissions=True)
		
		frappe.db.commit()
		
		return {
			"message": "Branding updated successfully",
			"branding": {
				"primary_color": settings.primary_color,
				"secondary_color": settings.secondary_color,
				"text_color": settings.text_color,
				"background_color": settings.background_color,
				"font_family": settings.font_family
			}
		}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Update Branding Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def update_invoice_settings(clinic, header_text=None, footer_text=None, terms_conditions=None,
							show_logo=None, show_seal=None, template_id=None):
	"""
	Update invoice/document settings
	
	Args:
		clinic: Company/Clinic name
		header_text: Invoice header text
		footer_text: Invoice footer text
		terms_conditions: Terms and conditions
		show_logo: Show logo on invoice (0 or 1)
		show_seal: Show seal on prescription (0 or 1)
	"""
	try:
		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404
		
		# Get or create clinic settings
		if frappe.db.exists("Clinic Settings", clinic):
			settings = frappe.get_doc("Clinic Settings", clinic)
		else:
			settings = frappe.new_doc("Clinic Settings")
			settings.clinic = clinic
		
		if header_text is not None:
			settings.invoice_header_text = header_text
		if footer_text is not None:
			settings.invoice_footer_text = footer_text
		if terms_conditions is not None:
			settings.invoice_terms_conditions = terms_conditions
		if show_logo is not None:
			settings.show_logo_on_invoice = int(show_logo)
		if show_seal is not None:
			settings.show_seal_on_prescription = int(show_seal)
		if template_id is not None:
			settings.invoice_template_id = template_id
		
		settings.flags.ignore_permissions = True
		if settings.is_new():
			settings.insert(ignore_permissions=True)
		else:
			settings.save(ignore_permissions=True)
		
		frappe.db.commit()
		
		return {
			"message": "Invoice settings updated successfully",
			"invoice_settings": {
				"header_text": settings.invoice_header_text,
				"footer_text": settings.invoice_footer_text,
				"terms_conditions": settings.invoice_terms_conditions,
				"show_logo": settings.show_logo_on_invoice,
				"show_seal": settings.show_seal_on_prescription,
				"template_id": getattr(settings, 'invoice_template_id', None)
			}
		}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Update Invoice Settings Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def upload_logo(clinic):
	"""
	Upload clinic logo
	
	Args:
		clinic: Company/Clinic name
	
	Request must include file in multipart/form-data
	"""
	try:
		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404
		
		# Get uploaded file
		files = frappe.request.files
		if 'file' not in files:
			return {"message": "No file uploaded"}, 400
		
		file = files['file']
		
		# Save file
		ret = frappe.get_doc({
			"doctype": "File",
			"attached_to_doctype": "Company",
			"attached_to_name": clinic,
			"folder": "Home/Attachments",
			"file_name": file.filename,
			"is_private": 0,
			"content": file.read()
		})
		ret.flags.ignore_permissions = True
		ret.save(ignore_permissions=True)
		
		# Update company logo
		company = frappe.get_doc("Company", clinic)
		company.company_logo = ret.file_url
		company.flags.ignore_permissions = True
		company.save(ignore_permissions=True)
		
		frappe.db.commit()
		
		return {
			"message": "Logo uploaded successfully",
			"logo_url": _full_url(ret.file_url)
		}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Upload Logo Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def upload_document(clinic, document_type):
	"""
	Upload clinic documents (signature, seal)
	
	Args:
		clinic: Company/Clinic name
		document_type: 'signature' or 'seal'
	
	Request must include file in multipart/form-data
	"""
	try:
		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404
		
		if document_type not in ['signature', 'seal']:
			return {"message": "Invalid document type. Use 'signature' or 'seal'"}, 400
		
		# Get uploaded file
		files = frappe.request.files
		if 'file' not in files:
			return {"message": "No file uploaded"}, 400
		
		file = files['file']
		
		# Save file
		ret = frappe.get_doc({
			"doctype": "File",
			"attached_to_doctype": "Clinic Settings",
			"attached_to_name": clinic,
			"folder": "Home/Attachments",
			"file_name": file.filename,
			"is_private": 0,
			"content": file.read()
		})
		ret.flags.ignore_permissions = True
		ret.save(ignore_permissions=True)
		
		# Get or create clinic settings
		if frappe.db.exists("Clinic Settings", clinic):
			settings = frappe.get_doc("Clinic Settings", clinic)
		else:
			settings = frappe.new_doc("Clinic Settings")
			settings.clinic = clinic
		
		# Update appropriate field
		if document_type == 'signature':
			settings.invoice_signature = ret.file_url
		else:
			settings.clinic_seal = ret.file_url
		
		settings.flags.ignore_permissions = True
		if settings.is_new():
			settings.insert(ignore_permissions=True)
		else:
			settings.save(ignore_permissions=True)
		
		frappe.db.commit()
		
		return {
			"message": f"{document_type.capitalize()} uploaded successfully",
			"file_url": _full_url(ret.file_url)
		}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Upload Document Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def update_notification_templates(clinic, appointment_reminder=None, payment_receipt=None,
								   prescription_message=None, sms_sender=None):
	"""
	Update notification message templates
	
	Args:
		clinic: Company/Clinic name
		appointment_reminder: Appointment reminder template
		payment_receipt: Payment receipt template
		prescription_message: Prescription message template
		sms_sender: SMS sender name (max 6 chars)
	"""
	try:
		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404
		
		# Get or create clinic settings
		if frappe.db.exists("Clinic Settings", clinic):
			settings = frappe.get_doc("Clinic Settings", clinic)
		else:
			settings = frappe.new_doc("Clinic Settings")
			settings.clinic = clinic
		
		if appointment_reminder is not None:
			settings.appointment_reminder_message = appointment_reminder
		if payment_receipt is not None:
			settings.payment_receipt_message = payment_receipt
		if prescription_message is not None:
			settings.prescription_message = prescription_message
		if sms_sender is not None:
			if len(sms_sender) > 6:
				return {"message": "SMS sender name cannot exceed 6 characters"}, 400
			settings.sms_sender_name = sms_sender
		
		settings.flags.ignore_permissions = True
		if settings.is_new():
			settings.insert(ignore_permissions=True)
		else:
			settings.save(ignore_permissions=True)
		
		frappe.db.commit()
		
		return {
			"message": "Notification templates updated successfully",
			"notifications": {
				"appointment_reminder": settings.appointment_reminder_message,
				"payment_receipt": settings.payment_receipt_message,
				"prescription_message": settings.prescription_message,
				"sms_sender": settings.sms_sender_name
			}
		}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Update Notification Templates Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def update_social_media(clinic, facebook=None, instagram=None, twitter=None, google_maps=None):
	"""
	Update social media links
	
	Args:
		clinic: Company/Clinic name
		facebook: Facebook URL
		instagram: Instagram URL
		twitter: Twitter URL
		google_maps: Google Maps URL
	"""
	try:
		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404
		
		# Get or create clinic settings
		if frappe.db.exists("Clinic Settings", clinic):
			settings = frappe.get_doc("Clinic Settings", clinic)
		else:
			settings = frappe.new_doc("Clinic Settings")
			settings.clinic = clinic
		
		if facebook is not None:
			settings.facebook_url = facebook
		if instagram is not None:
			settings.instagram_url = instagram
		if twitter is not None:
			settings.twitter_url = twitter
		if google_maps is not None:
			settings.google_maps_url = google_maps
		
		settings.flags.ignore_permissions = True
		if settings.is_new():
			settings.insert(ignore_permissions=True)
		else:
			settings.save(ignore_permissions=True)
		
		frappe.db.commit()
		
		return {
			"message": "Social media links updated successfully",
			"social_media": {
				"facebook": settings.facebook_url,
				"instagram": settings.instagram_url,
				"twitter": settings.twitter_url,
				"google_maps": settings.google_maps_url
			}
		}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Update Social Media Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def update_additional_settings(clinic, appointment_slot_duration=None, allow_online_booking=None,
								timezone=None, currency=None, start_time=None, end_time=None):
	"""
	Update additional clinic settings
	
	Args:
		clinic: Company/Clinic name
		appointment_slot_duration: Default appointment duration in minutes
		allow_online_booking: Allow online booking (0 or 1)
		timezone: Timezone
		currency: Currency code
	"""
	try:
		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404
		
		# Get or create clinic settings
		if frappe.db.exists("Clinic Settings", clinic):
			settings = frappe.get_doc("Clinic Settings", clinic)
		else:
			settings = frappe.new_doc("Clinic Settings")
			settings.clinic = clinic
		
		if appointment_slot_duration is not None:
			settings.appointment_slot_duration = int(appointment_slot_duration)
		if allow_online_booking is not None:
			settings.allow_online_booking = int(allow_online_booking)
		if timezone is not None:
			settings.timezone = timezone
		if currency is not None:
			settings.currency = currency

		# Update practitioner working hours if provided
		if start_time is not None or end_time is not None:
			try:
				practitioner = _get_practitioner_for_clinic(clinic)
			except Exception:
				practitioner = None

			if not practitioner:
				return {"message": "Healthcare Practitioner profile not found"}, 403

			schedule = _upsert_practitioner_schedule(practitioner, start_time=start_time, end_time=end_time)
		
		settings.flags.ignore_permissions = True
		if settings.is_new():
			settings.insert(ignore_permissions=True)
		else:
			settings.save(ignore_permissions=True)
		
		frappe.db.commit()
		
		return {
			"message": "Additional settings updated successfully",
			"additional": {
				"appointment_slot_duration": settings.appointment_slot_duration,
				"allow_online_booking": settings.allow_online_booking,
				"timezone": settings.timezone,
				"currency": settings.currency,
				"start_time": schedule["start_time"] if (start_time is not None or end_time is not None) else _normalize_time(start_time),
				"end_time": schedule["end_time"] if (start_time is not None or end_time is not None) else _normalize_time(end_time)
			}
		}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Update Additional Settings Error")
		return {"message": str(e)}, 500


@frappe.whitelist(methods=["GET"])
def get_clinic_practitioner_schedules(clinic):
	"""Return all practitioner schedules for a clinic."""
	try:
		assert_page_access("settings")

		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404

		settings = frappe.get_doc("Clinic Settings", clinic) if frappe.db.exists("Clinic Settings", clinic) else None
		rows = []
		practitioners = frappe.get_all(
			"Healthcare Practitioner",
			filters={"primary_company": clinic},
			fields=["name", "practitioner_name", "user_id", "primary_company"],
			order_by="practitioner_name asc",
		)

		for row in practitioners:
			practitioner_doc = frappe.get_doc("Healthcare Practitioner", row["name"])
			schedule = _extract_practitioner_schedule(practitioner_doc)
			rows.append(
				{
					"practitioner_id": row["name"],
					"practitioner_name": row.get("practitioner_name"),
					"user_id": row.get("user_id"),
					"primary_company": row.get("primary_company"),
					"start_time": schedule["start_time"],
					"end_time": schedule["end_time"],
				}
			)

		return {
			"message": "success",
			"data": {
				"clinic": clinic,
				"default_slot_duration": getattr(settings, "appointment_slot_duration", None),
				"practitioners": rows,
			},
		}
	except frappe.PermissionError:
		return {"message": "Not permitted"}, 403
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Clinic Practitioner Schedules Error")
		return {"message": str(e)}, 500


@frappe.whitelist(methods=["POST"])
def update_practitioner_schedule(clinic, practitioner_id, start_time=None, end_time=None):
	"""Update one practitioner's working hours for a clinic."""
	try:
		assert_page_access("settings")

		if not clinic or not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404

		if not practitioner_id or not frappe.db.exists("Healthcare Practitioner", practitioner_id):
			return {"message": "Invalid practitioner"}, 404

		practitioner = frappe.get_doc("Healthcare Practitioner", practitioner_id)
		if practitioner.get("primary_company") != clinic:
			return {"message": "Practitioner does not belong to the selected clinic"}, 400

		schedule = _upsert_practitioner_schedule(practitioner, start_time=start_time, end_time=end_time)
		frappe.db.commit()

		return {
			"message": "Practitioner schedule updated successfully",
			"data": {
				"practitioner_id": practitioner.name,
				"practitioner_name": practitioner.practitioner_name,
				"start_time": schedule["start_time"],
				"end_time": schedule["end_time"],
			},
		}
	except frappe.PermissionError:
		return {"message": "Not permitted"}, 403
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Update Practitioner Schedule Error")
		return {"message": str(e)}, 500


@frappe.whitelist(methods=["GET"])
def get_clinic_consultants(clinic):
	try:
		assert_page_access("settings")

		if not clinic or not frappe.db.exists("Company", clinic):
			frappe.local.response["http_status_code"] = 404
			return {"message": "Invalid clinic"}

		settings = _get_or_create_clinic_settings(clinic)
		rows = [_serialize_consultant_row(row) for row in (settings.get("consultants") or [])]

		return {
			"message": "success",
			"data": {
				"clinic": clinic,
				"consultants": rows,
			},
		}
	except frappe.PermissionError:
		frappe.local.response["http_status_code"] = 403
		return {"message": "Not permitted"}
	except Exception as e:
		frappe.local.response["http_status_code"] = 500
		frappe.log_error(frappe.get_traceback(), "Get Clinic Consultants Error")
		return {"message": str(e)}


@frappe.whitelist(methods=["POST"])
def save_clinic_consultant(
	clinic,
	consultant_id=None,
	consultant_type="Internal",
	practitioner=None,
	consultant_name=None,
	mobile=None,
	commission_type="Percentage",
	commission_value=0,
	is_active=1,
	notes=None,
):
	try:
		assert_page_access("settings")

		if not clinic or not frappe.db.exists("Company", clinic):
			frappe.local.response["http_status_code"] = 404
			return {"message": "Invalid clinic"}

		settings = _get_or_create_clinic_settings(clinic)
		consultant_name, commission_value = _validate_consultant_payload(
			clinic,
			consultant_type,
			practitioner,
			consultant_name,
			commission_type,
			commission_value,
		)

		row = None
		for existing in settings.get("consultants") or []:
			if consultant_id and existing.name == consultant_id:
				row = existing
				break

		if not row and consultant_type == "Internal" and practitioner:
			for existing in settings.get("consultants") or []:
				if existing.practitioner == practitioner:
					row = existing
					break

		if not row:
			row = settings.append("consultants", {})

		row.consultant_type = consultant_type
		row.practitioner = practitioner if consultant_type == "Internal" else None
		row.consultant_name = consultant_name
		row.mobile = mobile
		row.commission_type = commission_type
		row.commission_value = commission_value
		row.is_active = int(is_active or 0)
		row.notes = notes

		settings.flags.ignore_permissions = True
		if settings.is_new():
			settings.insert(ignore_permissions=True)
		else:
			settings.save(ignore_permissions=True)
		frappe.db.commit()

		return {
			"message": "Consultant saved successfully",
			"data": _serialize_consultant_row(row),
		}
	except frappe.PermissionError:
		frappe.local.response["http_status_code"] = 403
		return {"message": "Not permitted"}
	except Exception as e:
		frappe.db.rollback()
		frappe.local.response["http_status_code"] = 500
		frappe.log_error(frappe.get_traceback(), "Save Clinic Consultant Error")
		return {"message": str(e)}


@frappe.whitelist(methods=["POST"])
def delete_clinic_consultant(clinic, consultant_id):
	try:
		assert_page_access("settings")

		if not clinic or not frappe.db.exists("Company", clinic):
			frappe.local.response["http_status_code"] = 404
			return {"message": "Invalid clinic"}

		settings = _get_or_create_clinic_settings(clinic)
		rows = settings.get("consultants") or []
		target = None
		for row in rows:
			if row.name == consultant_id:
				target = row
				break

		if not target:
			frappe.local.response["http_status_code"] = 404
			return {"message": "Consultant not found"}

		settings.remove(target)
		settings.flags.ignore_permissions = True
		settings.save(ignore_permissions=True)
		frappe.db.commit()

		return {"message": "Consultant deleted successfully", "data": {"consultant_id": consultant_id}}
	except frappe.PermissionError:
		frappe.local.response["http_status_code"] = 403
		return {"message": "Not permitted"}
	except Exception as e:
		frappe.db.rollback()
		frappe.local.response["http_status_code"] = 500
		frappe.log_error(frappe.get_traceback(), "Delete Clinic Consultant Error")
		return {"message": str(e)}
