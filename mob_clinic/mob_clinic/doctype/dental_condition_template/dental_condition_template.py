"""
Dental Condition Template DocType
Global master template for conditions - shared across all clinics
"""

import frappe
from frappe.model.document import Document

class DentalConditionTemplate(Document):
	def validate(self):
		"""Validate the condition before saving"""
		# Set created_by if not set
		if not self.created_by:
			self.created_by = frappe.session.user
		
		# Validate severity levels if provided
		if self.severity_levels:
			severity_names = [sl.severity_level for sl in self.severity_levels]
			if len(severity_names) != len(set(severity_names)):
				frappe.throw("Duplicate severity levels are not allowed")
	
	def before_save(self):
		"""Hook before saving"""
		# Convert code to uppercase for consistency
		if self.code:
			self.code = self.code.upper()
