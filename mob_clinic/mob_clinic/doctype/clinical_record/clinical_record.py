# Copyright (c) 2025, DCube Systems Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ClinicalRecord(Document):
    def before_save(self):
        if self.patient and not self.patient_name:
            self.patient_name = frappe.db.get_value("Patient", self.patient, "patient_name")
        
        if self.practitioner and not self.practitioner_name:
            self.practitioner_name = frappe.db.get_value("Healthcare Practitioner", self.practitioner, "practitioner_name")
