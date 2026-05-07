# Copyright (c) 2026, Mob Clinic and contributors
# For license information, please see license.txt

from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_first_day, getdate


ALLOWED_EXPENSE_CATEGORIES = {
    "Recurring Fixed",
    "Recurring Variable",
    "One-Time",
}


def _has_two_decimals(value) -> bool:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return False
    return decimal_value == decimal_value.quantize(Decimal("0.01"))


class ExpenseRule(Document):
    def validate(self):
        if self.expense_category not in ALLOWED_EXPENSE_CATEGORIES:
            frappe.throw(_("Expense category is invalid"))

        if not self.expense_name:
            frappe.throw(_("Expense item is required"))

        if not self.clinic:
            frappe.throw(_("Clinic is required"))

        self.expense_name = self.expense_name.strip()
        self.effective_from_month = get_first_day(getdate(self.effective_from_month))
        if self.effective_to_month:
            self.effective_to_month = get_first_day(getdate(self.effective_to_month))
            if self.effective_to_month < self.effective_from_month:
                frappe.throw(_("Effective to month cannot be before effective from month"))

        if self.expense_category == "Recurring Fixed":
            if self.fixed_amount is None:
                frappe.throw(_("Recurring fixed expenses require a fixed amount"))
            if flt(self.fixed_amount) < 0:
                frappe.throw(_("Amount cannot be negative"))
            if not _has_two_decimals(self.fixed_amount):
                frappe.throw(_("Amount can have at most 2 decimal places"))
            self.fixed_amount = flt(self.fixed_amount, 2)
        else:
            self.fixed_amount = 0

        self.is_active = 1 if self.is_active is None else int(self.is_active)
        self.created_by_user = self.created_by_user or frappe.session.user

