"""
Dental Procedure Clinic Override DocType
Allows clinics to:
1. Override pricing/availability of global templates
2. Create custom procedures specific to their clinic
"""

import frappe
from frappe.model.document import Document

class DentalProcedureClinicOverride(Document):
	def validate(self):
		"""Validate the override before saving"""
		
		# Either procedure_template OR is_custom_procedure must be set, not both
		if self.is_custom_procedure and self.procedure_template:
			frappe.throw("Cannot set both procedure_template and is_custom_procedure. Choose one.")
		
		if not self.is_custom_procedure and not self.procedure_template:
			frappe.throw("Either select a procedure template or mark as custom procedure")
		
		# For custom procedures, ensure required fields are filled
		if self.is_custom_procedure:
			if not self.procedure_name:
				frappe.throw("Procedure Name is required for custom procedures")
			
			# Check for duplicate custom procedure names within the same clinic
			existing = frappe.db.exists({
				"doctype": "Dental Procedure Clinic Override",
				"clinic": self.clinic,
				"procedure_name": self.procedure_name,
				"is_custom_procedure": 1,
				"name": ["!=", self.name]
			})
			if existing:
				frappe.throw(f"Custom procedure '{self.procedure_name}' already exists for this clinic")
		
		# Ensure cost is positive
		if self.cost and self.cost < 0:
			frappe.throw("Cost cannot be negative")
		
		# Ensure duration is positive for custom procedures
		if self.is_custom_procedure and self.duration_minutes and self.duration_minutes <= 0:
			frappe.throw("Duration must be greater than 0")
	
	def before_save(self):
		"""Hook before saving"""
		# Convert code to uppercase for consistency
		if self.code:
			self.code = self.code.upper()
