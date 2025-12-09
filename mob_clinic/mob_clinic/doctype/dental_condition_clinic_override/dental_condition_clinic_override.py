"""
Dental Condition Clinic Override DocType
Allows clinics to:
1. Enable/disable global condition templates
2. Create custom conditions specific to their clinic
"""

import frappe
from frappe.model.document import Document

class DentalConditionClinicOverride(Document):
	def validate(self):
		"""Validate the override before saving"""
		
		# Either condition_template OR is_custom_condition must be set, not both
		if self.is_custom_condition and self.condition_template:
			frappe.throw("Cannot set both condition_template and is_custom_condition. Choose one.")
		
		if not self.is_custom_condition and not self.condition_template:
			frappe.throw("Either select a condition template or mark as custom condition")
		
		# For custom conditions, ensure required fields are filled
		if self.is_custom_condition:
			if not self.condition_name:
				frappe.throw("Condition Name is required for custom conditions")
			
			# Check for duplicate custom condition names within the same clinic
			existing = frappe.db.exists({
				"doctype": "Dental Condition Clinic Override",
				"clinic": self.clinic,
				"condition_name": self.condition_name,
				"is_custom_condition": 1,
				"name": ["!=", self.name]
			})
			if existing:
				frappe.throw(f"Custom condition '{self.condition_name}' already exists for this clinic")
		
		# Validate severity levels if provided for custom conditions
		if self.is_custom_condition and self.severity_levels:
			severity_names = [sl.severity_level for sl in self.severity_levels]
			if len(severity_names) != len(set(severity_names)):
				frappe.throw("Duplicate severity levels are not allowed")
	
	def before_save(self):
		"""Hook before saving"""
		# Convert code to uppercase for consistency
		if self.code:
			self.code = self.code.upper()
