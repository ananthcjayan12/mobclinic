"""
Initialize Clinic Settings for existing clinics
Creates default Clinic Settings for all existing Company records
"""

import frappe

def execute():
	"""Create default Clinic Settings for all existing clinics"""
	
	# Get all companies (clinics)
	companies = frappe.get_all("Company", fields=["name", "default_currency"])
	
	for company in companies:
		# Check if settings already exist
		if not frappe.db.exists("Clinic Settings", company.name):
			try:
				# Create default settings
				settings = frappe.new_doc("Clinic Settings")
				settings.clinic = company.name
				
				# Set defaults
				settings.primary_color = "#2563EB"
				settings.secondary_color = "#10B981"
				settings.text_color = "#1F2937"
				settings.background_color = "#F9FAFB"
				settings.font_family = "Inter"
				settings.show_logo_on_invoice = 1
				settings.show_seal_on_prescription = 1
				settings.appointment_slot_duration = 30
				settings.allow_online_booking = 1
				settings.timezone = "Asia/Kolkata"
				settings.currency = company.default_currency if company.default_currency else "INR"
				
				# Set default notification templates
				settings.appointment_reminder_message = "Dear {patient_name}, your appointment is scheduled for {date} at {time}. Please arrive 10 minutes early."
				settings.payment_receipt_message = "Dear {patient_name}, thank you for your payment of {amount}. Invoice number: {invoice_number}."
				settings.prescription_message = "Please follow the prescription as advised. Contact us if you have any questions."
				
				settings.insert(ignore_permissions=True)
				
				print(f"Created Clinic Settings for: {company.name}")
			
			except Exception as e:
				print(f"Error creating settings for {company.name}: {str(e)}")
				frappe.log_error(frappe.get_traceback(), f"Clinic Settings Init Error - {company.name}")
	
	frappe.db.commit()
	print("Clinic Settings initialization completed")
