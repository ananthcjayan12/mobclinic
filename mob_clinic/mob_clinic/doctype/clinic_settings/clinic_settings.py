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
		
		# Ensure clinic exists
		if not frappe.db.exists("Company", self.clinic):
			frappe.throw(f"Clinic '{self.clinic}' does not exist")
	
	def before_save(self):
		"""Hook before saving"""
		# Set default currency from company if not set
		if not self.currency and self.clinic:
			company = frappe.get_doc("Company", self.clinic)
			self.currency = company.default_currency
