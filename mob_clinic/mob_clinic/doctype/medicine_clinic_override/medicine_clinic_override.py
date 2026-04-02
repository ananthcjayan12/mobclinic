"""
Medicine Clinic Override DocType
Allows clinics to:
1. Override global medicine template values per clinic
2. Create custom medicines specific to their clinic
"""

import frappe
from frappe.model.document import Document


class MedicineClinicOverride(Document):
	def validate(self):
		"""Validate override mode and required fields."""
		if self.is_custom_medicine and self.medicine_template:
			frappe.throw("Cannot set both medicine_template and is_custom_medicine. Choose one.")

		if not self.is_custom_medicine and not self.medicine_template:
			frappe.throw("Either select a medicine template or mark as custom medicine")

		if self.is_custom_medicine and not self.medicine_name:
			frappe.throw("Medicine Name is required for custom medicines")

		if self.is_custom_medicine:
			existing = frappe.db.exists({
				"doctype": "Medicine Clinic Override",
				"clinic": self.clinic,
				"medicine_name": self.medicine_name,
				"is_custom_medicine": 1,
				"name": ["!=", self.name],
			})
			if existing:
				frappe.throw(f"Custom medicine '{self.medicine_name}' already exists for this clinic")

		if self.default_days is not None and int(self.default_days) < 0:
			frappe.throw("Days cannot be negative")

		for fieldname in ("default_morning", "default_lunch", "default_evening", "default_night"):
			value = getattr(self, fieldname, 0) or 0
			if int(value) < 0:
				frappe.throw(f"{fieldname.replace('_', ' ').title()} cannot be negative")
