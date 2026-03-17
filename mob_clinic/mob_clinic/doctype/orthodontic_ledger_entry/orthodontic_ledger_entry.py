# Copyright (c) 2026, Mob Clinic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class OrthodonticLedgerEntry(Document):
    def validate(self):
        self._set_case_context()
        self._set_created_by()
        self._validate_payment()

    def _set_case_context(self):
        if not self.orthodontic_case:
            return

        case = frappe.db.get_value(
            "Orthodontic Case",
            self.orthodontic_case,
            ["patient", "company"],
            as_dict=True,
        )
        if not case:
            frappe.throw(_("Orthodontic case not found"))

        self.patient = case.patient
        self.company = case.company

    def _set_created_by(self):
        if not self.created_by:
            self.created_by = frappe.session.user

    def _validate_payment(self):
        if flt(self.payment_amount) < 0:
            frappe.throw(_("Payment amount cannot be negative"))

        if flt(self.commission_paid_amount) < 0:
            frappe.throw(_("Commission paid amount cannot be negative"))

