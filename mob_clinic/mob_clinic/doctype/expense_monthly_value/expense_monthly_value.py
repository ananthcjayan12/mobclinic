# Copyright (c) 2026, Mob Clinic and contributors
# For license information, please see license.txt

from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_first_day, getdate


def _has_two_decimals(value) -> bool:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return False
    return decimal_value == decimal_value.quantize(Decimal("0.01"))


class ExpenseMonthlyValue(Document):
    def validate(self):
        if not self.clinic:
            frappe.throw(_("Clinic is required"))

        if not self.expense_rule:
            frappe.throw(_("Expense rule is required"))

        if not self.expense_name_snapshot:
            frappe.throw(_("Expense item is required"))

        self.period_month = get_first_day(getdate(self.period_month))
        if self.payment_date:
            self.payment_date = getdate(self.payment_date)

        if self.amount is None:
            frappe.throw(_("Amount is required"))
        if flt(self.amount) < 0:
            frappe.throw(_("Amount cannot be negative"))
        if not _has_two_decimals(self.amount):
            frappe.throw(_("Amount can have at most 2 decimal places"))
        self.amount = flt(self.amount, 2)
        self.source_type = self.source_type or "Manual"

        existing_name = frappe.db.exists(
            "Expense Monthly Value",
            {
                "expense_rule": self.expense_rule,
                "period_month": self.period_month,
                "name": ["!=", self.name],
            },
        )
        if existing_name:
            frappe.throw(_("An amount already exists for this month"))

