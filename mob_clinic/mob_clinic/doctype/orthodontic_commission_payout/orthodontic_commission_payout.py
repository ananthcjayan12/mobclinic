# Copyright (c) 2026, Mob Clinic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today


class OrthodonticCommissionPayout(Document):
    def validate(self):
        self.posting_date = self.posting_date or today()
        self.paid_by = self.paid_by or frappe.session.user

        if flt(self.paid_amount) <= 0:
            frappe.throw(_("Paid amount must be greater than zero"))

        allocated_amount = round(
            sum(flt(row.commission_paid_amount) for row in self.get("allocations") or []),
            2,
        )
        if allocated_amount != round(flt(self.paid_amount), 2):
            frappe.throw(_("Allocated amount must match paid amount"))

        if self.status not in {"Submitted", "Reversed"}:
            self.status = "Submitted"

