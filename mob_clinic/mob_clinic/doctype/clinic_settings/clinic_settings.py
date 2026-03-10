"""
Clinic Settings DocType
Store clinic-specific branding, invoice settings, and customizations
"""

import frappe
from frappe.model.document import Document

class ClinicSettings(Document):
	def validate(self):
		"""Validate settings before saving"""
		# Validate SMS sender name length
		if self.sms_sender_name and len(self.sms_sender_name) > 6:
			frappe.throw("SMS Sender Name cannot exceed 6 characters")
		
		# Validate appointment slot duration
		if self.appointment_slot_duration and self.appointment_slot_duration <= 0:
			frappe.throw("Appointment slot duration must be greater than 0")

		for row in self.get("consultants") or []:
			if row.commission_value is None or row.commission_value < 0:
				frappe.throw("Consultant commission value cannot be negative")
			if row.commission_type == "Percentage" and row.commission_value > 100:
				frappe.throw("Consultant percentage commission cannot exceed 100")
			if row.consultant_type == "Internal" and not row.practitioner:
				frappe.throw("Internal consultants must be linked to a practitioner")
			if not row.consultant_name:
				frappe.throw("Consultant name is required")
		
		# Ensure clinic exists
		if not frappe.db.exists("Company", self.clinic):
			frappe.throw(f"Clinic '{self.clinic}' does not exist")
	
	def before_save(self):
		"""Hook before saving"""
		# Set default currency from company if not set
		if not self.currency and self.clinic:
			company = frappe.get_doc("Company", self.clinic)
			self.currency = company.default_currency
