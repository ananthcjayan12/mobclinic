import frappe
from frappe.model.document import Document


class ConsentFormSession(Document):
    def validate(self):
        if self.token:
            self.token = self.token.strip()

        if self.language:
            self.language = self.language.strip().lower()

        if self.language and self.language not in {"en", "ml"}:
            frappe.throw("Language must be either 'en' or 'ml'")
