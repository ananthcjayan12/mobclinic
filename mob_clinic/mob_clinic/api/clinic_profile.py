"""
Clinic Profile Management API
Manage clinic information, branding, settings, and customization
"""

import frappe
from frappe import _
import json

@frappe.whitelist()
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
				"logo_url": company.company_logo if company.company_logo else None,
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
				"signature_url": settings.invoice_signature if settings.invoice_signature else None,
				"seal_url": settings.clinic_seal if settings.clinic_seal else None,
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
				"currency": settings.currency
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
			"logo_url": ret.file_url
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
			"file_url": ret.file_url
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
								timezone=None, currency=None):
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
				"currency": settings.currency
			}
		}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Update Additional Settings Error")
		return {"message": str(e)}, 500
