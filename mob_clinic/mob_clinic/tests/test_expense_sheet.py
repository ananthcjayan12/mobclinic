import unittest

import frappe
from erpnext.accounts.utils import get_fiscal_year
from frappe.utils import add_months, flt, getdate, nowdate

from mob_clinic.mob_clinic.api.expense_sheet import (
    FILTER_MODE_MONTH,
    create_expense,
    delete_expense,
    get_expense_breakdown,
    get_expense_sheet,
    save_expense_changes,
    search_expense_items,
    update_expense_rule,
)
from mob_clinic.mob_clinic.tests.test_payment import TestPaymentAPI


class TestExpenseSheetAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frappe.set_user("Administrator")
        for module_name in ["expense_rule", "expense_monthly_value"]:
            frappe.reload_doc("mob_clinic", "doctype", module_name)

        if not getattr(TestPaymentAPI, "company", None):
            TestPaymentAPI.setUpClass()

        cls.company = TestPaymentAPI.company
        cls.patient_id = TestPaymentAPI.patient_id
        cls.practitioner_id = TestPaymentAPI.practitioner_id
        cls.associate_practitioner_id = TestPaymentAPI.associate_practitioner_id
        cls.external_consultant_id = TestPaymentAPI.consultant_id
        cls.today_month = getdate(nowdate()).replace(day=1)
        cls.next_month = add_months(cls.today_month, 1)
        cls.following_month = add_months(cls.today_month, 2)
        cls._ensure_internal_consultant()
        cls._seed_commission_invoices()

    @classmethod
    def tearDownClass(cls):
        frappe.set_user("Administrator")
        expense_rule_ids = frappe.get_all("Expense Rule", filters={"clinic": cls.company}, pluck="name")
        for rule_id in expense_rule_ids:
            if frappe.db.exists("Expense Rule", rule_id):
                value_ids = frappe.get_all("Expense Monthly Value", filters={"expense_rule": rule_id}, pluck="name")
                for value_id in value_ids:
                    if frappe.db.exists("Expense Monthly Value", value_id):
                        frappe.delete_doc("Expense Monthly Value", value_id, ignore_permissions=True, force=True)
                frappe.delete_doc("Expense Rule", rule_id, ignore_permissions=True, force=True)

        invoice_names = frappe.get_all(
            "Sales Invoice",
            filters={"remarks": ["like", "Expense sheet test%"]},
            pluck="name",
        )
        for invoice_name in invoice_names:
            if not frappe.db.exists("Sales Invoice", invoice_name):
                continue
            invoice = frappe.get_doc("Sales Invoice", invoice_name)
            if invoice.docstatus == 1:
                invoice.cancel()
            frappe.delete_doc("Sales Invoice", invoice_name, ignore_permissions=True, force=True)

    @classmethod
    def _ensure_internal_consultant(cls):
        settings = frappe.get_doc("Clinic Settings", cls.company)
        consultant_row = None
        for row in settings.get("consultants") or []:
            if row.consultant_name == "Internal Expense Consultant":
                consultant_row = row
                break
        if not consultant_row:
            consultant_row = settings.append("consultants", {})

        consultant_row.consultant_type = "Internal"
        consultant_row.practitioner = cls.associate_practitioner_id
        consultant_row.consultant_name = "Internal Expense Consultant"
        consultant_row.mobile = "9991112220"
        consultant_row.commission_type = "Percentage"
        consultant_row.commission_value = 12
        consultant_row.is_active = 1
        settings.save(ignore_permissions=True)
        cls.internal_consultant_id = consultant_row.name

    @classmethod
    def _seed_commission_invoices(cls):
        from mob_clinic.mob_clinic.api.payment import create_invoice

        existing_ids = set(
            frappe.get_all(
                "Sales Invoice",
                filters={"remarks": ["like", "Expense sheet test%"]},
                pluck="name",
            )
        )
        if existing_ids:
            return

        frappe.set_user("test_payment_doctor@example.com")
        try:
            create_invoice(
                patient_id=cls.patient_id,
                items=[
                    {
                        "item_code": "CONS-001",
                        "qty": 1,
                        "rate": 800,
                        "description": "Expense sheet test external commission",
                        "consultant": {
                            "consultant_id": cls.external_consultant_id,
                            "commission_type": "Fixed",
                            "commission_value": 160,
                            "override": True,
                        },
                    }
                ],
                posting_date=str(cls.today_month),
                due_date=str(cls.today_month),
                remarks="Expense sheet test external",
            )
            create_invoice(
                patient_id=cls.patient_id,
                items=[
                    {
                        "item_code": "CONS-001",
                        "qty": 1,
                        "rate": 700,
                        "description": "Expense sheet test internal commission",
                        "consultant": {
                            "consultant_id": cls.internal_consultant_id,
                            "commission_type": "Fixed",
                            "commission_value": 210,
                            "override": True,
                        },
                    }
                ],
                posting_date=str(cls.today_month),
                due_date=str(cls.today_month),
                remarks="Expense sheet test internal",
            )
        finally:
            frappe.set_user("Administrator")

    def test_month_and_next_month_recurrence_rules(self):
        frappe.set_user("test_payment_doctor@example.com")

        fixed = create_expense(
            expense_name="Clinic Rent",
            expense_category="Recurring Fixed",
            amount=12000,
            clinic=self.company,
            filter_mode=FILTER_MODE_MONTH,
            month=self.today_month.month,
            year=self.today_month.year,
        )["data"]["expense_rule_id"]

        variable = create_expense(
            expense_name="Electricity",
            expense_category="Recurring Variable",
            amount=1800,
            clinic=self.company,
            filter_mode=FILTER_MODE_MONTH,
            month=self.today_month.month,
            year=self.today_month.year,
        )["data"]["expense_rule_id"]

        create_expense(
            expense_name="Festival Banner",
            expense_category="One-Time",
            amount=900,
            clinic=self.company,
            filter_mode=FILTER_MODE_MONTH,
            month=self.today_month.month,
            year=self.today_month.year,
        )

        current_sheet = get_expense_sheet(
            filter_mode=FILTER_MODE_MONTH,
            month=self.today_month.month,
            year=self.today_month.year,
            clinic=self.company,
        )["data"]
        current_rows = {row["expense_name"]: row for row in current_sheet["rows"]}
        self.assertEqual(current_rows["Clinic Rent"]["amount"], 12000.0)
        self.assertFalse(current_rows["Clinic Rent"]["can_edit_amount"])
        self.assertTrue(current_rows["Clinic Rent"]["can_edit_rule"])
        self.assertEqual(current_rows["Electricity"]["amount"], 1800.0)
        self.assertTrue(current_rows["Electricity"]["can_edit_amount"])
        self.assertIn("Festival Banner", current_rows)

        next_sheet = get_expense_sheet(
            filter_mode=FILTER_MODE_MONTH,
            month=self.next_month.month,
            year=self.next_month.year,
            clinic=self.company,
        )["data"]
        next_rows = {row["expense_name"]: row for row in next_sheet["rows"]}
        self.assertIsNone(next_rows["Clinic Rent"]["amount"])
        self.assertTrue(next_rows["Clinic Rent"]["is_read_only"] is False)
        self.assertIsNone(next_rows["Electricity"]["amount"])
        self.assertTrue(next_rows["Electricity"]["can_edit_amount"])
        self.assertNotIn("Festival Banner", next_rows)

        electricity_row = next_rows["Electricity"]
        save_expense_changes(
            changes=[
                {
                    "row_key": electricity_row["row_key"],
                    "amount": 1950,
                    "payment_date": str(self.next_month),
                }
            ],
            clinic=self.company,
        )

        updated_next_sheet = get_expense_sheet(
            filter_mode=FILTER_MODE_MONTH,
            month=self.next_month.month,
            year=self.next_month.year,
            clinic=self.company,
        )["data"]
        updated_next_rows = {row["expense_name"]: row for row in updated_next_sheet["rows"]}
        self.assertEqual(updated_next_rows["Electricity"]["amount"], 1950.0)

        update_expense_rule(
            rule_id=fixed,
            effective_month=str(self.next_month),
            expense_category="Recurring Variable",
            amount=13000,
            expense_name="Clinic Rent",
            clinic=self.company,
        )

        following_sheet = get_expense_sheet(
            filter_mode=FILTER_MODE_MONTH,
            month=self.following_month.month,
            year=self.following_month.year,
            clinic=self.company,
        )["data"]
        following_rows = {row["expense_name"]: row for row in following_sheet["rows"]}
        self.assertIsNone(following_rows["Clinic Rent"]["amount"])
        self.assertTrue(following_rows["Clinic Rent"]["can_edit_amount"])

        delete_expense(
            rule_id=variable,
            effective_month=str(self.next_month),
            clinic=self.company,
        )
        deleted_sheet = get_expense_sheet(
            filter_mode=FILTER_MODE_MONTH,
            month=self.following_month.month,
            year=self.following_month.year,
            clinic=self.company,
        )["data"]
        deleted_rows = {row["expense_name"]: row for row in deleted_sheet["rows"]}
        self.assertNotIn("Electricity", deleted_rows)

        fixed_remove_all = create_expense(
            expense_name="Annual Insurance",
            expense_category="Recurring Fixed",
            amount=2400,
            clinic=self.company,
            filter_mode=FILTER_MODE_MONTH,
            month=self.today_month.month,
            year=self.today_month.year,
        )["data"]["expense_rule_id"]

        delete_expense(
            rule_id=fixed_remove_all,
            clinic=self.company,
            delete_mode="all",
        )

        removed_all_sheet = get_expense_sheet(
            filter_mode=FILTER_MODE_MONTH,
            month=self.today_month.month,
            year=self.today_month.year,
            clinic=self.company,
        )["data"]
        removed_all_rows = {row["expense_name"]: row for row in removed_all_sheet["rows"]}
        self.assertNotIn("Annual Insurance", removed_all_rows)

    def test_system_rows_and_breakdown(self):
        frappe.set_user("test_payment_doctor@example.com")

        sheet = get_expense_sheet(
            filter_mode=FILTER_MODE_MONTH,
            month=self.today_month.month,
            year=self.today_month.year,
            clinic=self.company,
        )["data"]
        rows = {row["expense_name"]: row for row in sheet["rows"]}
        self.assertEqual(rows["Vendor Payment"]["amount"], 160.0)
        self.assertEqual(rows["Practitioner Salary"]["amount"], 210.0)
        self.assertTrue(rows["Vendor Payment"]["is_system_generated"])
        self.assertFalse(rows["Vendor Payment"]["can_delete"])

        breakdown = get_expense_breakdown(
            row_key=rows["Vendor Payment"]["row_key"],
            filter_mode=FILTER_MODE_MONTH,
            month=self.today_month.month,
            year=self.today_month.year,
            clinic=self.company,
        )["data"]
        self.assertEqual(breakdown["summary"]["total_amount"], 160.0)
        self.assertEqual(breakdown["groups"][0]["contributors"][0]["label"], "Payout Consultant")

    def test_fy_view_and_search(self):
        frappe.set_user("test_payment_doctor@example.com")
        create_expense(
            expense_name="Consumables",
            expense_category="Recurring Variable",
            amount=1100,
            clinic=self.company,
            filter_mode=FILTER_MODE_MONTH,
            month=self.today_month.month,
            year=self.today_month.year,
        )

        current_month_fy = get_expense_sheet(
            filter_mode="financial_year",
            fiscal_year=frappe.db.get_value(
                "Expense Monthly Value",
                {"expense_name_snapshot": "Consumables"},
                "fiscal_year",
            ),
            clinic=self.company,
        )["data"]

        row_names = {row["expense_name"] for row in current_month_fy["rows"]}
        self.assertIn("Consumables", row_names)
        self.assertIn("Vendor Payment", row_names)

        search_result = search_expense_items(q="Cons", clinic=self.company)["data"]["items"]
        self.assertTrue(any(item["name"] == "Consumables" for item in search_result))

    def test_fy_fixed_does_not_include_future_months(self):
        frappe.set_user("test_payment_doctor@example.com")
        fixed_amount = 2000
        fixed_name = "Rent FY Current"
        create_expense(
            expense_name=fixed_name,
            expense_category="Recurring Fixed",
            amount=fixed_amount,
            clinic=self.company,
            filter_mode=FILTER_MODE_MONTH,
            month=self.today_month.month,
            year=self.today_month.year,
        )

        fiscal_year = get_fiscal_year(date=self.today_month, company=self.company, as_dict=True)["name"]

        fy_sheet = get_expense_sheet(
            filter_mode="financial_year",
            fiscal_year=fiscal_year,
            clinic=self.company,
        )["data"]
        fy_rows = {row["expense_name"]: row for row in fy_sheet["rows"]}

        row = fy_rows[fixed_name]
        expected_month_count = 1
        self.assertEqual(row["amount"], float(fixed_amount * expected_month_count))

    def test_recurring_fixed_backfill_window(self):
        frappe.set_user("test_payment_doctor@example.com")
        previous_month = add_months(self.today_month, -1)
        create_expense(
            expense_name="Backfilled Rent",
            expense_category="Recurring Fixed",
            amount=3000,
            clinic=self.company,
            filter_mode=FILTER_MODE_MONTH,
            month=self.today_month.month,
            year=self.today_month.year,
            apply_backfill=1,
            backfill_start_month=str(previous_month),
            backfill_end_month=str(previous_month),
        )

        prev_sheet = get_expense_sheet(
            filter_mode=FILTER_MODE_MONTH,
            month=previous_month.month,
            year=previous_month.year,
            clinic=self.company,
        )["data"]
        prev_rows = {row["expense_name"]: row for row in prev_sheet["rows"]}
        self.assertEqual(prev_rows["Backfilled Rent"]["amount"], 3000.0)

    def test_month_view_uses_erpnext_fiscal_year_resolution_for_previous_year(self):
        frappe.set_user("test_payment_doctor@example.com")
        previous_year_month = getdate("2026-02-01")
        expected_fy = get_fiscal_year(date=previous_year_month, company=self.company, as_dict=True)

        sheet = get_expense_sheet(
            filter_mode=FILTER_MODE_MONTH,
            month=previous_year_month.month,
            year=previous_year_month.year,
            clinic=self.company,
        )["data"]

        self.assertEqual(sheet["filters"]["selected_fiscal_year"], expected_fy["name"])
        self.assertEqual(sheet["filters"]["selected_month"], str(previous_year_month))
        self.assertEqual(expected_fy["name"], "2025-2026")

    def test_non_admin_cannot_create(self):
        frappe.set_user("Administrator")
        original_flag = frappe.db.get_value("Healthcare Practitioner", self.practitioner_id, "is_clinic_admin")
        try:
            frappe.db.set_value("Healthcare Practitioner", self.practitioner_id, "is_clinic_admin", 0)
            frappe.set_user("test_payment_doctor@example.com")
            with self.assertRaises(frappe.PermissionError):
                create_expense(
                    expense_name="Blocked Expense",
                    expense_category="One-Time",
                    amount=100,
                    clinic=self.company,
                    filter_mode=FILTER_MODE_MONTH,
                    month=self.today_month.month,
                    year=self.today_month.year,
                )
        finally:
            frappe.set_user("Administrator")
            frappe.db.set_value("Healthcare Practitioner", self.practitioner_id, "is_clinic_admin", original_flag)
