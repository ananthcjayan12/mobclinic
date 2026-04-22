import json

import frappe
from frappe.model.document import Document


class ConsentFormTemplate(Document):
    def validate(self):
        if self.consent_type_id:
            self.consent_type_id = self.consent_type_id.strip().lower().replace(" ", "_")

        if self.language:
            self.language = self.language.strip().lower()

        if self.language not in {"en", "ml"}:
            frappe.throw("Language must be either 'en' or 'ml'")

        if self.sections_json:
            try:
                sections = json.loads(self.sections_json)
            except Exception:
                frappe.throw("Sections JSON must be valid JSON")

            if not isinstance(sections, list):
                frappe.throw("Sections JSON must be an array")

        self._validate_unique_scope()

    def _validate_unique_scope(self):
        matches = frappe.get_all(
            "Consent Form Template",
            filters={
                "clinic": self.clinic,
                "consent_type_id": self.consent_type_id,
                "language": self.language,
            },
            fields=["name", "doctor"],
        )
        for row in matches:
            same_doctor_scope = (row.get("doctor") or None) == (self.doctor or None)
            if same_doctor_scope and row.get("name") != self.name:
                scope = self.doctor or "clinic-default"
                frappe.throw(
                    f"A template already exists for type '{self.consent_type_id}' ({self.language}) in scope '{scope}'"
                )
