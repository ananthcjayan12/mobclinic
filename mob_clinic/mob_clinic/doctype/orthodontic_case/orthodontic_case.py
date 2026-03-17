# Copyright (c) 2026, Mob Clinic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, flt


ACTIVE_CASE_STATUSES = {"Planned", "Active", "On Hold"}


class OrthodonticCase(Document):
    def validate(self):
        self._set_party_details()
        self._set_consultant_snapshot()
        self._set_commission_defaults()
        self._set_financial_fields()
        self._validate_financial_inputs()
        self._validate_active_case_uniqueness()
        self._validate_advance_updates()

    def _set_party_details(self):
        if self.patient:
            self.patient_name = frappe.db.get_value("Patient", self.patient, "patient_name")

        if self.practitioner:
            self.practitioner_name = frappe.db.get_value(
                "Healthcare Practitioner",
                self.practitioner,
                "practitioner_name",
            )

    def _set_consultant_snapshot(self):
        if not self.consultant_id:
            self.consultant_name = ""
            self.consultant_type = ""
            self.consultant_practitioner = ""
            return

        consultant = frappe.db.get_value(
            "Clinic Consultant",
            self.consultant_id,
            [
                "parent",
                "consultant_name",
                "consultant_type",
                "practitioner",
                "is_active",
            ],
            as_dict=True,
        )
        if not consultant:
            frappe.throw(_("Consultant not found"))

        if self.company and consultant.parent != self.company:
            frappe.throw(_("Consultant does not belong to the selected clinic"))

        if not consultant.get("is_active"):
            frappe.throw(_("Selected consultant is inactive"))

        if self.is_new() or self.has_value_changed("consultant_id") or not self.consultant_name:
            self.consultant_name = consultant.consultant_name
            self.consultant_type = consultant.consultant_type
            self.consultant_practitioner = consultant.practitioner

    def _set_commission_defaults(self):
        self.commission_model = self.commission_model or "None"

        if self.commission_model == "None":
            self.commission_type = ""
            self.commission_value = 0
            self.commission_basis = ""
            return

        if not self.commission_type:
            self.commission_type = (
                "Percentage" if self.commission_model == "Percentage" else "Fixed"
            )

        if not self.commission_basis:
            self.commission_basis = "On collected amount"

    def _set_financial_fields(self):
        package_fee = flt(self.package_fee)
        discount_amount = flt(self.discount_amount)
        discount_percentage = flt(self.discount_percentage)

        if package_fee and discount_percentage and not discount_amount:
            discount_amount = (package_fee * discount_percentage) / 100.0
            self.discount_amount = discount_amount

        self.net_fee = round(max(package_fee - discount_amount, 0), 2)

        if self.start_date and self.estimated_duration_months:
            self.estimated_end_date = add_months(
                self.start_date, int(self.estimated_duration_months)
            )

        totals = frappe.db.sql(
            """
            SELECT
                COALESCE(SUM(payment_amount), 0) AS total_paid,
                COALESCE(SUM(consultant_commission_amount), 0) AS total_commission_accrued,
                COALESCE(SUM(commission_paid_amount), 0) AS total_commission_paid
            FROM `tabOrthodontic Ledger Entry`
            WHERE orthodontic_case = %s
            """,
            (self.name,),
            as_dict=True,
        )[0]

        self.total_paid = round(flt(totals.total_paid), 2)
        self.balance_amount = round(max(self.net_fee - self.total_paid, 0), 2)
        self.total_commission_accrued = round(
            flt(totals.total_commission_accrued), 2
        )
        self.total_commission_paid = round(flt(totals.total_commission_paid), 2)
        self.pending_commission_amount = round(
            max(self.total_commission_accrued - self.total_commission_paid, 0), 2
        )

        if self.status in {"Completed", "Cancelled"}:
            self.is_active = 0
        elif self.status:
            self.is_active = 1

    def _validate_financial_inputs(self):
        if flt(self.package_fee) < 0:
            frappe.throw(_("Package fee cannot be negative"))

        if flt(self.discount_amount) < 0 or flt(self.discount_percentage) < 0:
            frappe.throw(_("Discount cannot be negative"))

        if flt(self.discount_percentage) > 100:
            frappe.throw(_("Discount percentage cannot exceed 100"))

        if flt(self.advance_paid) < 0:
            frappe.throw(_("Advance paid cannot be negative"))

        if flt(self.discount_amount) > flt(self.package_fee):
            frappe.throw(_("Discount amount cannot exceed package fee"))

        if flt(self.commission_value) < 0:
            frappe.throw(_("Commission value cannot be negative"))

        if self.commission_type == "Percentage" and flt(self.commission_value) > 100:
            frappe.throw(_("Percentage commission cannot exceed 100"))

    def _validate_active_case_uniqueness(self):
        if not self.patient or not self.is_active or self.status not in ACTIVE_CASE_STATUSES:
            return

        existing_case = frappe.db.get_value(
            "Orthodontic Case",
            {
                "patient": self.patient,
                "is_active": 1,
                "status": ["in", list(ACTIVE_CASE_STATUSES)],
                "name": ["!=", self.name or ""],
            },
            "name",
        )
        if existing_case:
            frappe.throw(_("Only one active orthodontic case is allowed per patient"))

    def _validate_advance_updates(self):
        if self.is_new() or not self.has_value_changed("advance_paid"):
            return

        has_ledger = frappe.db.exists(
            "Orthodontic Ledger Entry", {"orthodontic_case": self.name}
        )
        if has_ledger:
            frappe.throw(
                _("Advance paid cannot be changed after ledger entries have been recorded")
            )

