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
	
	create_custom_fields(custom_fields, update=True)
	
	frappe.db.commit()
	print("Custom fields added to Company DocType successfully")
