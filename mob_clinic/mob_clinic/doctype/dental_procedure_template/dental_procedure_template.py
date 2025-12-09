"""
Dental Procedure Template DocType
Global master template for procedures - shared across all clinics
"""

import frappe
from frappe.model.document import Document

class DentalProcedureTemplate(Document):
	def validate(self):
		"""Validate the procedure template before saving"""
		# Ensure default_cost is positive
		if self.default_cost and self.default_cost < 0:
			frappe.throw("Default cost cannot be negative")
		
		# Ensure duration is positive
		if self.duration_minutes and self.duration_minutes <= 0:
			frappe.throw("Duration must be greater than 0")
		
		# Set created_by if not set
		if not self.created_by:
			self.created_by = frappe.session.user
	
	def before_save(self):
		"""Hook before saving"""
		# Convert code to uppercase for consistency
		if self.code:
			self.code = self.code.upper()
