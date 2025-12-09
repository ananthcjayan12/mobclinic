"""
Add custom fields to Company DocType for clinic-specific information
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def execute():
	"""Create custom fields for Company (Clinic)"""
	
	custom_fields = {
		"Company": [
			{
				"fieldname": "clinic_details_section",
				"fieldtype": "Section Break",
				"label": "Clinic Details",
				"insert_after": "default_currency"
			},
			{
				"fieldname": "phone_no",
				"fieldtype": "Data",
				"label": "Phone Number",
				"insert_after": "clinic_details_section"
			},
			{
				"fieldname": "email",
				"fieldtype": "Data",
				"label": "Email",
				"options": "Email",
				"insert_after": "phone_no"
			},
			{
				"fieldname": "website",
				"fieldtype": "Data",
				"label": "Website",
				"insert_after": "email"
			},
			{
				"fieldname": "column_break_clinic",
				"fieldtype": "Column Break",
				"insert_after": "website"
			},
			{
				"fieldname": "registration_number",
				"fieldtype": "Data",
				"label": "Registration Number",
				"insert_after": "column_break_clinic"
			},
			{
				"fieldname": "tax_id",
				"fieldtype": "Data",
				"label": "Tax ID / GST Number",
				"insert_after": "registration_number"
			}
		]
	}
	
	# Create custom fields one by one, catching ValidationError if field already exists
	for doctype, fields in custom_fields.items():
		for df in fields:
			try:
				# Check if custom field already exists
				if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": df.get("fieldname")}):
					print(f"Custom field {df.get('fieldname')} already exists in {doctype}, skipping")
					continue
				
				# Create single field
				create_custom_fields({doctype: [df]}, update=True)
				print(f"Created custom field {df.get('fieldname')} in {doctype}")
			except frappe.exceptions.ValidationError as e:
				if "already exists" in str(e):
					print(f"Custom field {df.get('fieldname')} already exists in {doctype}, skipping")
				else:
					raise
	
	frappe.db.commit()
	print("Custom fields processing completed for Company DocType")
