"""
Unit tests for Payment and Invoice Management APIs
Tests Sales Invoice creation, payment tracking, and reminders
"""

import frappe
import unittest
from unittest.mock import patch
from frappe.utils import today, add_days, getdate, flt
from mob_clinic.mob_clinic.patches.v1_0.create_consultant_invoice_fields import execute as ensure_consultant_invoice_fields


class TestPaymentAPI(unittest.TestCase):
    """Test cases for Payment & Invoice Management APIs"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests"""
        frappe.set_user("Administrator")
        for module_name in [
            "orthodontic_commission_payout_reference",
            "orthodontic_commission_payout",
            "orthodontic_ledger_entry",
            "orthodontic_case",
        ]:
            frappe.reload_doc("mob_clinic", "doctype", module_name)
        if not frappe.db.exists("DocType", "Clinic Consultant"):
            frappe.reload_doc("mob_clinic", "doctype", "clinic_consultant")
        if not frappe.db.exists("DocField", {"parent": "Clinic Settings", "fieldname": "consultants"}):
            frappe.reload_doc("mob_clinic", "doctype", "clinic_settings")
        frappe.clear_cache(doctype="Clinic Settings")
        frappe.clear_cache(doctype="Clinic Consultant")
        ensure_consultant_invoice_fields()
        
        # Create test medical department if not exists
        if not frappe.db.exists("Medical Department", "Dentistry"):
            dept = frappe.get_doc({
                "doctype": "Medical Department",
                "department": "Dentistry"
            })
            dept.insert(ignore_permissions=True)
        
        # Create test practitioner
        if not frappe.db.exists("Healthcare Practitioner", {"first_name": "Test", "last_name": "Payment Doctor"}):
            practitioner = frappe.get_doc({
                "doctype": "Healthcare Practitioner",
                "first_name": "Test",
                "last_name": "Payment Doctor",
                "gender": "Male",
                "department": "Dentistry"
            })
            practitioner.insert(ignore_permissions=True)
            cls.practitioner_id = practitioner.name
        else:
            cls.practitioner_id = frappe.db.get_value("Healthcare Practitioner", 
                {"first_name": "Test", "last_name": "Payment Doctor"})

        if not frappe.db.exists("Healthcare Practitioner", {"first_name": "Associate", "last_name": "Payment Doctor"}):
            associate_practitioner = frappe.get_doc({
                "doctype": "Healthcare Practitioner",
                "first_name": "Associate",
                "last_name": "Payment Doctor",
                "gender": "Male",
                "department": "Dentistry"
            })
            associate_practitioner.insert(ignore_permissions=True)
            cls.associate_practitioner_id = associate_practitioner.name
        else:
            cls.associate_practitioner_id = frappe.db.get_value(
                "Healthcare Practitioner",
                {"first_name": "Associate", "last_name": "Payment Doctor"},
            )
        
        # Create Healthcare Practitioner role if not exists
        if not frappe.db.exists("Role", "Healthcare Practitioner"):
            role = frappe.get_doc({
                "doctype": "Role",
                "role_name": "Healthcare Practitioner"
            })
            role.insert(ignore_permissions=True)
        
        # Create test user for practitioner
        if not frappe.db.exists("User", "test_payment_doctor@example.com"):
            user = frappe.get_doc({
                "doctype": "User",
                "email": "test_payment_doctor@example.com",
                "first_name": "Test Payment",
                "last_name": "Doctor",
                "send_welcome_email": 0,
                "user_type": "System User"
            })
            user.insert(ignore_permissions=True)
            user.add_roles("Healthcare Practitioner")
        
        # Link user to practitioner
        practitioner_doc = frappe.get_doc("Healthcare Practitioner", cls.practitioner_id)
        practitioner_doc.user_id = "test_payment_doctor@example.com"
        practitioner_doc.save(ignore_permissions=True)
        
        # Create test patient (check by email to avoid duplicates)
        patient_email = "payment_test_patient@mobclinic.test"
        patient_mobile = "+919876543299"
        
        existing_patient = frappe.db.get_value("Patient", 
            {"email": patient_email}, "name")
        
        if existing_patient:
            cls.patient_id = existing_patient
        else:
            patient = frappe.get_doc({
                "doctype": "Patient",
                "first_name": "Payment",
                "last_name": "Test Patient",
                "sex": "Male",
                "mobile": patient_mobile,
                "email": patient_email,
                "invite_user": 0  # Don't create website user
            })
            patient.insert(ignore_permissions=True)
            cls.patient_id = patient.name
        
        # Create test items for invoicing
        items_data = [
            {"item_code": "CONS-001", "item_name": "Consultation", "item_group": "Services", "rate": 500},
            {"item_code": "ROOT-001", "item_name": "Root Canal", "item_group": "Services", "rate": 5000},
            {"item_code": "CLEAN-001", "item_name": "Teeth Cleaning", "item_group": "Services", "rate": 1500}
        ]
        
        for item_data in items_data:
            if not frappe.db.exists("Item", item_data["item_code"]):
                item = frappe.get_doc({
                    "doctype": "Item",
                    "item_code": item_data["item_code"],
                    "item_name": item_data["item_name"],
                    "item_group": item_data["item_group"],
                    "stock_uom": "Nos",
                    "is_stock_item": 0,
                    "gst_hsn_code": "999312",
                    "standard_rate": item_data["rate"]
                })
                item.insert(ignore_permissions=True)
        
        # Create Mode of Payment options if they don't exist
        payment_modes = ["Cash", "UPI", "Card"]
        for mode in payment_modes:
            if not frappe.db.exists("Mode of Payment", mode):
                mop = frappe.get_doc({
                    "doctype": "Mode of Payment",
                    "mode_of_payment": mode,
                    "type": "Cash" if mode == "Cash" else "Bank"
                })
                mop.insert(ignore_permissions=True)
        
        # ========== ACCOUNTING SETUP ==========
        # Setup proper accounting infrastructure for Payment Entry
        
        # Get or create default company
        company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
        if not company:
            # Create a test company if none exists
            if not frappe.db.exists("Company", "Test Mobile Clinic"):
                company_doc = frappe.get_doc({
                    "doctype": "Company",
                    "company_name": "Test Mobile Clinic",
                    "abbr": "TMC",
                    "default_currency": "INR",
                    "country": "India"
                })
                company_doc.insert(ignore_permissions=True)
                company = company_doc.name
                frappe.db.set_value("Global Defaults", None, "default_company", company)
            else:
                company = "Test Mobile Clinic"
        
        cls.company = company
        frappe.db.set_value("Healthcare Practitioner", cls.practitioner_id, "primary_company", company)
        frappe.db.set_value("Healthcare Practitioner", cls.practitioner_id, "is_clinic_admin", 1)
        frappe.db.set_value(
            "Healthcare Practitioner",
            cls.practitioner_id,
            "allowed_pages_json",
            '["home","appointments","patients","prescriptions","invoice","financial_dashboard","whatsapp-manager","settings"]',
        )
        frappe.db.set_value("Healthcare Practitioner", cls.associate_practitioner_id, "primary_company", company)
        
        # Ensure company has required accounts setup
        # Check if Chart of Accounts exists for this company
        if not frappe.db.exists("Account", {"company": company, "account_name": "Application of Funds (Assets)"}):
            # Chart of Accounts doesn't exist, create it
            from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import create_charts
            create_charts(company, "Standard")
        
        # Get or create default receivable account (Debtors)
        receivable_account = frappe.db.get_value("Company", company, "default_receivable_account")
        if not receivable_account:
            # Find or create Debtors account
            receivable_account = frappe.db.get_value("Account", {
                "company": company,
                "account_type": "Receivable",
                "is_group": 0
            }, "name")
            
            if receivable_account:
                frappe.db.set_value("Company", company, "default_receivable_account", receivable_account)
        
        # Get or create default cash account
        cash_account = frappe.db.get_value("Company", company, "default_cash_account")
        if not cash_account:
            # Find or create Cash account
            cash_account = frappe.db.get_value("Account", {
                "company": company,
                "account_type": "Cash",
                "is_group": 0
            }, "name")
            
            if cash_account:
                frappe.db.set_value("Company", company, "default_cash_account", cash_account)
        
        # Get or create income account for services
        income_account = frappe.db.get_value("Company", company, "default_income_account")
        if not income_account:
            # Find or create Income account
            income_account = frappe.db.get_value("Account", {
                "company": company,
                "root_type": "Income",
                "is_group": 0
            }, "name")
            
            if income_account:
                frappe.db.set_value("Company", company, "default_income_account", income_account)
        
        # Link Mode of Payment to accounts
        for mode in payment_modes:
            # Check if Mode of Payment Account already exists
            if not frappe.db.exists("Mode of Payment Account", {"parent": mode, "company": company}):
                mop_doc = frappe.get_doc("Mode of Payment", mode)
                mop_doc.append("accounts", {
                    "company": company,
                    "default_account": cash_account
                })
                mop_doc.save(ignore_permissions=True)
        
        # ========== END ACCOUNTING SETUP ==========
        
        # Create customer for patient (required for Sales Invoice)
        customer_name = f"CUST-{cls.patient_id}"
        if not frappe.db.exists("Customer", customer_name):
            patient_doc = frappe.get_doc("Patient", cls.patient_id)
            customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": patient_doc.patient_name,
                "customer_type": "Individual",
                "customer_group": "Individual",
                "territory": "All Territories"
            })
            customer.insert(ignore_permissions=True)
            cls.customer_id = customer.name
        else:
            cls.customer_id = customer_name
        
        # Store test invoice ID for later tests
        cls.test_invoice_id = None
        cls._extra_item_codes = set()
        cls._extra_procedure_templates = set()

        settings = frappe.get_doc("Clinic Settings", company) if frappe.db.exists("Clinic Settings", company) else frappe.new_doc("Clinic Settings")
        settings.clinic = company
        existing_consultant = None
        for row in settings.get("consultants") or []:
            if row.consultant_name == "Payout Consultant":
                existing_consultant = row
                break
        if not existing_consultant:
            existing_consultant = settings.append("consultants", {})
        existing_consultant.consultant_type = "External"
        existing_consultant.consultant_name = "Payout Consultant"
        existing_consultant.mobile = "9998881110"
        existing_consultant.commission_type = "Percentage"
        existing_consultant.commission_value = 10
        existing_consultant.is_active = 1
        settings.flags.ignore_permissions = True
        if settings.is_new():
            settings.insert(ignore_permissions=True)
        else:
            settings.save(ignore_permissions=True)
        cls.consultant_id = existing_consultant.name
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test data after all tests"""
        frappe.set_user("Administrator")

        case_ids = frappe.get_all(
            "Orthodontic Case",
            filters={"patient": cls.patient_id},
            pluck="name",
        )

        payout_ids = frappe.get_all(
            "Orthodontic Commission Payout",
            filters={"orthodontic_case": ["in", case_ids]} if case_ids else {"name": "__missing__"},
            pluck="name",
        )
        for payout_id in payout_ids:
            if frappe.db.exists("Orthodontic Commission Payout", payout_id):
                frappe.delete_doc(
                    "Orthodontic Commission Payout",
                    payout_id,
                    force=True,
                    ignore_permissions=True,
                )

        ledger_ids = frappe.get_all(
            "Orthodontic Ledger Entry",
            filters={"patient": cls.patient_id},
            pluck="name",
        )
        for ledger_id in ledger_ids:
            if frappe.db.exists("Orthodontic Ledger Entry", ledger_id):
                frappe.delete_doc(
                    "Orthodontic Ledger Entry",
                    ledger_id,
                    force=True,
                    ignore_permissions=True,
                )

        for case_id in case_ids:
            if frappe.db.exists("Orthodontic Case", case_id):
                frappe.delete_doc(
                    "Orthodontic Case",
                    case_id,
                    force=True,
                    ignore_permissions=True,
                )
        
        # Delete test invoices and payments
        invoices = frappe.get_all("Sales Invoice", 
            filters={"patient": cls.patient_id}, 
            pluck="name")
        for invoice_id in invoices:
            # Delete related payment entries first
            payment_refs = frappe.get_all("Payment Entry Reference",
                filters={"reference_name": invoice_id},
                pluck="parent")
            for payment_id in payment_refs:
                if frappe.db.exists("Payment Entry", payment_id):
                    pe = frappe.get_doc("Payment Entry", payment_id)
                    if pe.docstatus == 1:
                        pe.cancel()
                    frappe.delete_doc("Payment Entry", payment_id, force=True)
            
            # Delete invoice
            if frappe.db.exists("Sales Invoice", invoice_id):
                invoice = frappe.get_doc("Sales Invoice", invoice_id)
                if invoice.docstatus == 1:
                    invoice.cancel()
                frappe.delete_doc("Sales Invoice", invoice_id, force=True)
        
        # Delete test customer
        if frappe.db.exists("Customer", cls.customer_id):
            frappe.delete_doc("Customer", cls.customer_id, force=True)
        
        # Delete test items
        for item_code in ["CONS-001", "ROOT-001", "CLEAN-001"]:
            if frappe.db.exists("Item", item_code):
                frappe.delete_doc("Item", item_code, force=True)

        for item_code in getattr(cls, "_extra_item_codes", set()):
            if frappe.db.exists("Item", item_code):
                frappe.delete_doc("Item", item_code, force=True)

        for procedure_name in getattr(cls, "_extra_procedure_templates", set()):
            template_name = frappe.db.get_value(
                "Dental Procedure Template",
                {"procedure_name": procedure_name},
                "name",
            )
            if template_name:
                frappe.delete_doc("Dental Procedure Template", template_name, force=True)
        
        # Delete test patient
        if frappe.db.exists("Patient", cls.patient_id):
            frappe.delete_doc("Patient", cls.patient_id, force=True)

        if frappe.db.exists("Clinic Settings", cls.company):
            settings = frappe.get_doc("Clinic Settings", cls.company)
            for row in list(settings.get("consultants") or []):
                if row.name == getattr(cls, "consultant_id", None) or row.consultant_name == "Payout Consultant":
                    settings.remove(row)
            settings.flags.ignore_permissions = True
            settings.save(ignore_permissions=True)
        
        # Delete test practitioner
        if frappe.db.exists("Healthcare Practitioner", cls.practitioner_id):
            frappe.delete_doc("Healthcare Practitioner", cls.practitioner_id, force=True)

        if frappe.db.exists("Healthcare Practitioner", getattr(cls, "associate_practitioner_id", None)):
            frappe.delete_doc("Healthcare Practitioner", cls.associate_practitioner_id, force=True)
        
        # Delete test user
        if frappe.db.exists("User", "test_payment_doctor@example.com"):
            frappe.delete_doc("User", "test_payment_doctor@example.com", force=True)
        
        # Delete test medical department
        if frappe.db.exists("Medical Department", "Dentistry"):
            frappe.delete_doc("Medical Department", "Dentistry", force=True)
        
        # Delete test role (only if we created it)
        # Note: We don't delete the role as it might be used by other tests
        
        frappe.db.commit()
    
    def setUp(self):
        """Set up before each test"""
        frappe.set_user("test_payment_doctor@example.com")
        frappe.local.session["active_clinic"] = self.company

    def _create_procedure_template(self, code, procedure_name, cost=1000, description="Test procedure"):
        frappe.set_user("Administrator")
        template_name = frappe.db.get_value(
            "Dental Procedure Template",
            {"procedure_name": procedure_name},
            "name",
        )
        if template_name:
            frappe.delete_doc("Dental Procedure Template", template_name, force=True, ignore_permissions=True)

        if frappe.db.exists("Item", code):
            frappe.delete_doc("Item", code, force=True, ignore_permissions=True)

        template = frappe.get_doc(
            {
                "doctype": "Dental Procedure Template",
                "procedure_name": procedure_name,
                "code": code,
                "category": "Other",
                "default_cost": cost,
                "duration_minutes": 30,
                "description": description,
                "is_active": 1,
            }
        )
        template.insert(ignore_permissions=True)
        self.__class__._extra_procedure_templates.add(procedure_name)
        self.__class__._extra_item_codes.add(code)
        frappe.set_user("test_payment_doctor@example.com")
        return template

    def _cleanup_patient_records(self, patient_id):
        frappe.set_user("Administrator")

        case_ids = frappe.get_all(
            "Orthodontic Case",
            filters={"patient": patient_id},
            pluck="name",
        )

        payout_ids = frappe.get_all(
            "Orthodontic Commission Payout",
            filters={"orthodontic_case": ["in", case_ids]} if case_ids else {"name": "__missing__"},
            pluck="name",
        )
        for payout_id in payout_ids:
            if frappe.db.exists("Orthodontic Commission Payout", payout_id):
                frappe.delete_doc(
                    "Orthodontic Commission Payout",
                    payout_id,
                    force=True,
                    ignore_permissions=True,
                )

        ledger_ids = frappe.get_all(
            "Orthodontic Ledger Entry",
            filters={"patient": patient_id},
            pluck="name",
        )
        for ledger_id in ledger_ids:
            if frappe.db.exists("Orthodontic Ledger Entry", ledger_id):
                frappe.delete_doc(
                    "Orthodontic Ledger Entry",
                    ledger_id,
                    force=True,
                    ignore_permissions=True,
                )

        for case_id in case_ids:
            if frappe.db.exists("Orthodontic Case", case_id):
                frappe.delete_doc(
                    "Orthodontic Case",
                    case_id,
                    force=True,
                    ignore_permissions=True,
                )

        invoices = frappe.get_all(
            "Sales Invoice",
            filters={"patient": patient_id},
            fields=["name", "customer"],
        )
        customer_ids = {invoice.customer for invoice in invoices if invoice.customer}
        for invoice in invoices:
            payment_refs = frappe.get_all(
                "Payment Entry Reference",
                filters={"reference_name": invoice.name},
                pluck="parent",
            )
            for payment_id in payment_refs:
                if frappe.db.exists("Payment Entry", payment_id):
                    payment_doc = frappe.get_doc("Payment Entry", payment_id)
                    if payment_doc.docstatus == 1:
                        payment_doc.cancel()
                    frappe.delete_doc("Payment Entry", payment_id, force=True)

            if frappe.db.exists("Sales Invoice", invoice.name):
                invoice_doc = frappe.get_doc("Sales Invoice", invoice.name)
                if invoice_doc.docstatus == 1:
                    invoice_doc.cancel()
                frappe.delete_doc("Sales Invoice", invoice.name, force=True)

        for customer_id in customer_ids:
            if frappe.db.exists("Customer", customer_id):
                frappe.delete_doc("Customer", customer_id, force=True)

        if frappe.db.exists("Patient", patient_id):
            frappe.delete_doc("Patient", patient_id, force=True)
    
    def test_01_create_invoice(self):
        """Test creating a new invoice"""
        from mob_clinic.mob_clinic.api.payment import create_invoice
        
        # Create invoice
        result = create_invoice(
            patient_id=self.patient_id,
            items=[
                {"item_code": "CONS-001", "qty": 1, "rate": 500, "description": "Initial consultation"},
                {"item_code": "CLEAN-001", "qty": 1, "rate": 1500, "description": "Teeth cleaning service"}
            ],
            posting_date=today(),
            due_date=add_days(today(), 7),
            remarks="First visit"
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertIn("invoice_id", result)
        self.assertEqual(result["grand_total"], 2000)  # 500 + 1500
        self.assertEqual(result["outstanding_amount"], 2000)  # Fully unpaid
        self.assertEqual(result["status"], "Unpaid")
        
        # Store for later tests
        self.__class__.test_invoice_id = result["invoice_id"]
        
        # Verify invoice exists
        invoice = frappe.get_doc("Sales Invoice", result["invoice_id"])
        self.assertEqual(invoice.patient, self.patient_id)
        self.assertEqual(len(invoice.items), 2)
    
    def test_02_get_invoices(self):
        """Test retrieving list of invoices"""
        from mob_clinic.mob_clinic.api.payment import get_invoices
        
        # Get all invoices
        result = get_invoices(
            patient_id=self.patient_id,
            limit_page_length=20
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertIn("invoices", result)
        self.assertGreater(len(result["invoices"]), 0)
        
        # Check first invoice
        invoice = result["invoices"][0]
        self.assertEqual(invoice["patient"], self.patient_id)
        self.assertIn("grand_total", invoice)
        self.assertIn("outstanding_amount", invoice)
        self.assertIn("paid_amount", invoice)
    
    def test_03_get_invoice_details(self):
        """Test retrieving detailed invoice information"""
        from mob_clinic.mob_clinic.api.payment import get_invoice
        
        # Get invoice details
        result = get_invoice(self.test_invoice_id)
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["invoice_id"], self.test_invoice_id)
        self.assertIn("patient", result)
        self.assertEqual(result["patient"]["patient_id"], self.patient_id)
        self.assertIn("items", result)
        self.assertEqual(len(result["items"]), 2)
        self.assertIn("payments", result)
        self.assertEqual(result["grand_total"], 2000)

    def test_03b_create_invoice_with_consultant_snapshot(self):
        """Test consultant commission snapshot is stored on invoice items."""
        from mob_clinic.mob_clinic.api.payment import create_invoice, get_invoice

        result = create_invoice(
            patient_id=self.patient_id,
            items=[
                {
                    "item_code": "CONS-001",
                    "qty": 1,
                    "rate": 500,
                    "description": "Consultation with consultant",
                    "consultant": {
                        "consultant_id": self.consultant_id,
                        "commission_type": "Fixed",
                        "commission_value": 120,
                        "override": True,
                    },
                }
            ],
            posting_date=today(),
            due_date=add_days(today(), 3),
            remarks="Consultant override test",
        )

        self.assertEqual(result["total_consultant_commission"], 120.0)

        invoice_data = get_invoice(result["invoice_id"])
        item = invoice_data["items"][0]
        self.assertEqual(item["consultant_id"], self.consultant_id)
        self.assertEqual(item["consultant_name"], "Payout Consultant")
        self.assertEqual(item["consultant_commission_type"], "Fixed")
        self.assertEqual(item["consultant_commission_value"], 120.0)
        self.assertEqual(item["consultant_commission_amount"], 120.0)
        self.assertEqual(item["consultant_commission_source"], "Override")

    def test_03c_create_invoice_with_explicit_associated_practitioner(self):
        """Test invoice stores the explicitly selected associated doctor."""
        from mob_clinic.mob_clinic.api.payment import create_invoice, get_invoice

        result = create_invoice(
            patient_id=self.patient_id,
            practitioner_id=self.associate_practitioner_id,
            items=[
                {
                    "item_code": "CONS-001",
                    "qty": 1,
                    "rate": 500,
                    "description": "Receptionist-created consultation invoice",
                }
            ],
            posting_date=today(),
            due_date=add_days(today(), 5),
            remarks="Explicit associated doctor test",
        )

        self.assertEqual(result["practitioner_id"], self.associate_practitioner_id)

        invoice = frappe.get_doc("Sales Invoice", result["invoice_id"])
        self.assertEqual(invoice.healthcare_practitioner, self.associate_practitioner_id)

        invoice_data = get_invoice(result["invoice_id"])
        self.assertEqual(invoice_data["healthcare_practitioner"], self.associate_practitioner_id)
    
    def test_04_update_payment_partial(self):
        """Test recording a partial payment"""
        from mob_clinic.mob_clinic.api.payment import update_payment
        
        # Record partial payment
        result = update_payment(
            invoice_id=self.test_invoice_id,
            paid_amount=1000,
            mode_of_payment="Cash",
            payment_date=today(),
            reference_no="CASH001"
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertIn("payment_id", result)
        self.assertEqual(result["paid_amount"], 1000)
        self.assertEqual(result["outstanding_amount"], 1000)  # 2000 - 1000
        self.assertEqual(result["status"], "Partly Paid")
        
        # Verify payment entry exists
        self.assertTrue(frappe.db.exists("Payment Entry", result["payment_id"]))
    
    def test_05_update_payment_full(self):
        """Test recording full payment (completing the invoice)"""
        from mob_clinic.mob_clinic.api.payment import update_payment
        
        # Record remaining payment
        result = update_payment(
            invoice_id=self.test_invoice_id,
            paid_amount=1000,
            mode_of_payment="UPI",
            payment_date=today(),
            reference_no="UPI123456",
            reference_date=today()
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["paid_amount"], 1000)
        self.assertEqual(result["outstanding_amount"], 0)
        self.assertEqual(result["status"], "Paid")
    
    def test_06_get_payment_summary(self):
        """Test retrieving payment summary for a patient"""
        from mob_clinic.mob_clinic.api.payment import get_payment_summary
        
        # Get payment summary
        result = get_payment_summary(self.patient_id)
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["patient_id"], self.patient_id)
        self.assertIn("total_invoiced", result)
        self.assertIn("total_paid", result)
        self.assertIn("total_pending", result)
        self.assertGreater(result["invoice_count"], 0)
        self.assertEqual(result["total_invoiced"], 3000)
        self.assertEqual(result["total_paid"], 2000)
        self.assertEqual(result["total_pending"], 1000)

    def test_06b_get_consultant_payout_report(self):
        """Test consultant payout report uses stored invoice item snapshots."""
        from mob_clinic.mob_clinic.api.dashboard import get_consultant_payout_report

        result = get_consultant_payout_report(
            from_date=today(),
            to_date=today(),
            clinic=self.company,
            consultant_id=self.consultant_id,
        )

        self.assertEqual(result["message"], "Success")
        report = result["data"]
        self.assertEqual(report["summary"]["consultant_count"], 1)
        self.assertEqual(report["summary"]["item_count"], 1)
        self.assertEqual(report["summary"]["total_revenue"], 500.0)
        self.assertEqual(report["summary"]["total_commission"], 120.0)
        self.assertEqual(report["consultants"][0]["consultant_id"], self.consultant_id)
        self.assertEqual(report["consultants"][0]["total_commission"], 120.0)
        self.assertEqual(report["rows"][0]["consultant_name"], "Payout Consultant")
        self.assertEqual(report["rows"][0]["commission_amount"], 120.0)
        self.assertEqual(report["rows"][0]["commission_source"], "Override")

    def test_06c_get_financial_stats_with_practitioner_filter(self):
        """Test financial dashboard returns clinic data with optional practitioner filter."""
        from mob_clinic.mob_clinic.api.dashboard import get_financial_stats

        result = get_financial_stats(
            from_date=today(),
            to_date=today(),
            clinic=self.company,
            practitioner_id=self.practitioner_id,
        )

        self.assertEqual(result["message"], "Success")
        dashboard = result["data"]
        self.assertEqual(dashboard["filters"]["clinic"], self.company)
        self.assertEqual(dashboard["filters"]["practitioner_id"], self.practitioner_id)
        self.assertIn("summary", dashboard)
        self.assertIn("recent_transactions", dashboard)
        self.assertIn("practitioner_revenue", dashboard)
        self.assertGreaterEqual(len(dashboard["practitioner_revenue"]), 1)
        if dashboard["recent_transactions"]:
            self.assertIn("invoice_id", dashboard["recent_transactions"][0])
    
    def test_07_create_invoice_with_appointment(self):
        """Test creating invoice linked to an appointment"""
        from mob_clinic.mob_clinic.api.payment import create_invoice
        import random
        
        # Create appointment with unique time to avoid overlaps (use random minute between 30-59)
        unique_minute = random.randint(30, 59)
        appointment = frappe.get_doc({
            "doctype": "Patient Appointment",
            "patient": self.patient_id,
            "practitioner": self.practitioner_id,
            "appointment_date": today(),
            "appointment_time": f"14:{unique_minute}:00",  # Unique time in afternoon
            "appointment_type": "Consultation",
            "appointment_for": "Practitioner",  # Must be: "", "Practitioner", "Department", or "Service Unit"
            "status": "Open"
        })
        appointment.insert(ignore_permissions=True)
        
        # Create invoice
        result = create_invoice(
            patient_id=self.patient_id,
            items=[
                {"item_code": "ROOT-001", "qty": 1, "rate": 5000}
            ]
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertEqual(result["grand_total"], 5000)
        
        # Verify invoice exists
        invoice = frappe.get_doc("Sales Invoice", result["invoice_id"])
        self.assertIsNotNone(invoice)
        
        # Cleanup
        if invoice.docstatus == 1:
            invoice.flags.ignore_permissions = True
            invoice.cancel()
        frappe.delete_doc("Sales Invoice", invoice.name, force=True, ignore_permissions=True)
        frappe.delete_doc("Patient Appointment", appointment.name, force=True, ignore_permissions=True)

    def test_07b_create_multiple_invoices_for_same_appointment(self):
        """Test split billing by allowing multiple invoices for the same appointment."""
        from mob_clinic.mob_clinic.api.payment import create_invoice
        import random

        unique_minute = random.randint(30, 59)
        appointment = frappe.get_doc({
            "doctype": "Patient Appointment",
            "patient": self.patient_id,
            "practitioner": self.practitioner_id,
            "appointment_date": today(),
            "appointment_time": f"15:{unique_minute}:00",
            "appointment_type": "Consultation",
            "appointment_for": "Practitioner",
            "status": "Pending Payment"
        })
        appointment.insert(ignore_permissions=True)

        first_invoice_id = None
        second_invoice_id = None

        try:
            first_result = create_invoice(
                patient_id=self.patient_id,
                appointment_reference=appointment.name,
                items=[{"item_code": "CONS-001", "qty": 1, "rate": 500, "description": "Consultation fee"}],
                posting_date=today(),
            )
            first_invoice_id = first_result["invoice_id"]

            second_result = create_invoice(
                patient_id=self.patient_id,
                appointment_reference=appointment.name,
                items=[{"item_code": "ROOT-001", "qty": 1, "rate": 5000, "description": "Additional procedure"}],
                posting_date=today(),
            )
            second_invoice_id = second_result["invoice_id"]

            self.assertNotEqual(first_invoice_id, second_invoice_id)

            referenced_invoices = frappe.get_all(
                "Sales Invoice Item",
                filters={"reference_dt": "Patient Appointment", "reference_dn": appointment.name},
                fields=["parent"],
                distinct=True,
            )
            self.assertEqual(len(referenced_invoices), 1)
        finally:
            for invoice_id in [first_invoice_id, second_invoice_id]:
                if not invoice_id or not frappe.db.exists("Sales Invoice", invoice_id):
                    continue
                invoice = frappe.get_doc("Sales Invoice", invoice_id)
                if invoice.docstatus == 1:
                    invoice.flags.ignore_permissions = True
                    invoice.cancel()
                frappe.delete_doc("Sales Invoice", invoice_id, force=True, ignore_permissions=True)

            if frappe.db.exists("Patient Appointment", appointment.name):
                frappe.delete_doc("Patient Appointment", appointment.name, force=True, ignore_permissions=True)
    
    def test_08_filter_invoices_by_status(self):
        """Test filtering invoices by status"""
        from mob_clinic.mob_clinic.api.payment import get_invoices
        
        # Get paid invoices
        result = get_invoices(
            patient_id=self.patient_id,
            status="Paid"
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertIn("invoices", result)
        for invoice in result["invoices"]:
            self.assertEqual(invoice["status"], "Paid")
    
    def test_09_filter_invoices_by_date(self):
        """Test filtering invoices by date range"""
        from mob_clinic.mob_clinic.api.payment import get_invoices
        
        # Get invoices for today
        result = get_invoices(
            patient_id=self.patient_id,
            start_date=today(),
            end_date=today()
        )
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertIn("invoices", result)
    
    def test_10_create_invoice_validation_no_items(self):
        """Test invoice creation fails without items"""
        from mob_clinic.mob_clinic.api.payment import create_invoice
        
        # Try to create invoice without items
        with self.assertRaises(Exception) as context:
            create_invoice(
                patient_id=self.patient_id,
                items=[]
            )
        
        self.assertIn("item", str(context.exception).lower())
    
    def test_11_create_invoice_validation_invalid_patient(self):
        """Test invoice creation fails with invalid patient"""
        from mob_clinic.mob_clinic.api.payment import create_invoice
        
        # Try to create invoice with non-existent patient
        with self.assertRaises(Exception) as context:
            create_invoice(
                patient_id="INVALID-PATIENT",
                items=[{"item_code": "CONS-001", "qty": 1, "rate": 500}]
            )
        
        self.assertIn("patient", str(context.exception).lower())
    
    def test_12_update_payment_validation_exceeds_outstanding(self):
        """Test payment fails when exceeding outstanding amount"""
        from mob_clinic.mob_clinic.api.payment import create_invoice, update_payment
        
        # Create new invoice
        result = create_invoice(
            patient_id=self.patient_id,
            items=[{"item_code": "CONS-001", "qty": 1, "rate": 500}]
        )
        invoice_id = result["invoice_id"]
        
        try:
            # Try to pay more than outstanding
            with self.assertRaises(Exception) as context:
                update_payment(
                    invoice_id=invoice_id,
                    paid_amount=1000,  # Invoice is only 500
                    mode_of_payment="Cash"
                )
            
            self.assertIn("outstanding", str(context.exception).lower())
        
        finally:
            # Cleanup
            invoice = frappe.get_doc("Sales Invoice", invoice_id)
            if invoice.docstatus == 1:
                invoice.flags.ignore_permissions = True
                invoice.cancel()
            frappe.delete_doc("Sales Invoice", invoice_id, ignore_permissions=True, force=True)
    
    def test_13_send_payment_reminder(self):
        """Test sending payment reminder"""
        from mob_clinic.mob_clinic.api.payment import create_invoice, send_payment_reminder
        
        # Create unpaid invoice with today's date and short due date
        # Then manually mark it as overdue by updating the due_date after creation
        result = create_invoice(
            patient_id=self.patient_id,
            items=[{"item_code": "CONS-001", "qty": 1, "rate": 500}],
            posting_date=today(),
            due_date=add_days(today(), 1)  # Due tomorrow (valid for ERPNext)
        )
        invoice_id = result["invoice_id"]
        
        # Manually update the due_date to past to simulate overdue
        invoice = frappe.get_doc("Sales Invoice", invoice_id)
        invoice.db_set("due_date", add_days(today(), -3), update_modified=False)
        
        try:
            # Send reminder
            reminder_result = send_payment_reminder(
                invoice_id=invoice_id,
                reminder_type="sms",
                message="Your payment is overdue. Please pay soon."
            )
            
            # Assertions
            self.assertIsNotNone(reminder_result)
            self.assertIn("sent_via", reminder_result)
            
        finally:
            # Cleanup
            invoice = frappe.get_doc("Sales Invoice", invoice_id)
            if invoice.docstatus == 1:
                invoice.flags.ignore_permissions = True
                invoice.cancel()
            frappe.delete_doc("Sales Invoice", invoice_id, force=True, ignore_permissions=True)
    
    def test_14_pagination(self):
        """Test invoice list pagination"""
        from mob_clinic.mob_clinic.api.payment import get_invoices
        
        # Get first page
        result_page1 = get_invoices(
            patient_id=self.patient_id,
            limit_start=0,
            limit_page_length=1
        )
        
        # Assertions
        self.assertIsNotNone(result_page1)
        self.assertIn("invoices", result_page1)
        self.assertLessEqual(len(result_page1["invoices"]), 1)
    
    def test_15_invoice_overdue_detection(self):
        """Test overdue invoice detection"""
        from mob_clinic.mob_clinic.api.payment import create_invoice, get_invoice
        
        # Create invoice with today's date and short due date
        # Then manually mark it as overdue by updating the due_date after creation
        result = create_invoice(
            patient_id=self.patient_id,
            items=[{"item_code": "CONS-001", "qty": 1, "rate": 500}],
            posting_date=today(),
            due_date=add_days(today(), 1)  # Due tomorrow (valid for ERPNext)
        )
        invoice_id = result["invoice_id"]
        
        # Manually update the due_date to past to simulate overdue
        invoice = frappe.get_doc("Sales Invoice", invoice_id)
        invoice.db_set("due_date", add_days(today(), -5), update_modified=False)
        
        try:
            # Get invoice details
            invoice_data = get_invoice(invoice_id)
            
            # Assertions
            self.assertIsNotNone(invoice_data)
            self.assertTrue(invoice_data["is_overdue"])
            
        finally:
            # Cleanup
            invoice = frappe.get_doc("Sales Invoice", invoice_id)
            if invoice.docstatus == 1:
                invoice.flags.ignore_permissions = True
                invoice.cancel()
            frappe.delete_doc("Sales Invoice", invoice_id, force=True, ignore_permissions=True)

    def test_16_create_invoice_resolves_exact_procedure_template(self):
        """Invoice creation should use the exact procedure template item instead of Clinic Service."""
        from mob_clinic.mob_clinic.api.payment import create_invoice

        procedure_name = "Resolver Test Procedure"
        procedure_code = "PROC-RESOLVE-001"
        self._create_procedure_template(
            procedure_code,
            procedure_name,
            cost=1850,
            description="Resolver test procedure for invoice mapping",
        )

        result = create_invoice(
            patient_id=self.patient_id,
            items=[{"item_name": procedure_name, "qty": 1, "rate": 1850}],
            posting_date=today(),
            due_date=add_days(today(), 7),
        )

        invoice = frappe.get_doc("Sales Invoice", result["invoice_id"])
        self.assertEqual(invoice.items[0].item_code, procedure_code)
        self.assertEqual(invoice.items[0].item_name, procedure_name)
        self.assertNotEqual(invoice.items[0].item_name, "Clinic Service")
        self.assertTrue(frappe.db.exists("Item", procedure_code))

    def test_17_create_invoice_replaces_mismatched_existing_item_code(self):
        """A wrong preselected item code should be replaced when the exact procedure name is known."""
        from mob_clinic.mob_clinic.api.payment import create_invoice

        wrong_item_code = "WRONG-ADJ-001"
        procedure_name = "Resolver Re-RCT"
        procedure_code = "PROC-RESOLVE-002"

        frappe.set_user("Administrator")
        if frappe.db.exists("Item", wrong_item_code):
            frappe.delete_doc("Item", wrong_item_code, force=True, ignore_permissions=True)

        wrong_item = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": wrong_item_code,
                "item_name": "Wrong Adjacent Procedure",
                "item_group": "Services",
                "stock_uom": "Nos",
                "is_stock_item": 0,
                "is_sales_item": 1,
                "gst_hsn_code": "999312",
                "standard_rate": 0,
            }
        )
        wrong_item.insert(ignore_permissions=True)
        self.__class__._extra_item_codes.add(wrong_item_code)

        self._create_procedure_template(
            procedure_code,
            procedure_name,
            cost=3200,
            description="Resolver rerct mapping",
        )
        frappe.set_user("test_payment_doctor@example.com")

        result = create_invoice(
            patient_id=self.patient_id,
            items=[
                {
                    "item_code": wrong_item_code,
                    "item_name": procedure_name,
                    "description": procedure_name,
                    "qty": 1,
                    "rate": 3200,
                }
            ],
            posting_date=today(),
            due_date=add_days(today(), 7),
        )

        invoice = frappe.get_doc("Sales Invoice", result["invoice_id"])
        self.assertEqual(invoice.items[0].item_code, procedure_code)
        self.assertEqual(invoice.items[0].item_name, procedure_name)

    def test_18_create_invoice_repairs_corrupted_item_name_using_procedure_code(self):
        """Existing procedure items with polluted names should be repaired during invoice creation."""
        from mob_clinic.mob_clinic.api.payment import create_invoice

        procedure_name = "Resolver Simple Extraction"
        procedure_code = "PROC-RESOLVE-003"
        self._create_procedure_template(
            procedure_code,
            procedure_name,
            cost=600,
            description="Resolver simple extraction mapping",
        )

        frappe.set_user("Administrator")
        corrupted_item = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": procedure_code,
                "item_name": "14",
                "item_group": "Services",
                "stock_uom": "Nos",
                "is_stock_item": 0,
                "is_sales_item": 1,
                "gst_hsn_code": "999312",
                "description": "14",
                "standard_rate": 0,
            }
        )
        corrupted_item.insert(ignore_permissions=True)
        frappe.set_user("test_payment_doctor@example.com")

        result = create_invoice(
            patient_id=self.patient_id,
            items=[
                {
                    "item_code": procedure_code,
                    "item_name": "14",
                    "description": "14",
                    "qty": 1,
                    "rate": 600,
                }
            ],
            posting_date=today(),
            due_date=add_days(today(), 7),
        )

        invoice = frappe.get_doc("Sales Invoice", result["invoice_id"])
        repaired_item = frappe.get_doc("Item", procedure_code)

        self.assertEqual(invoice.items[0].item_code, procedure_code)
        self.assertEqual(invoice.items[0].item_name, procedure_name)
        self.assertEqual(repaired_item.item_name, procedure_name)
        self.assertEqual(repaired_item.description, "Resolver simple extraction mapping")

    def test_19_create_invoice_uses_procedure_code_even_without_matching_label(self):
        """Procedure codes should resolve to canonical items even when the incoming label is blank or stale."""
        from mob_clinic.mob_clinic.api.payment import create_invoice

        procedure_name = "Resolver Crown Procedure"
        procedure_code = "PROC-RESOLVE-004"
        self._create_procedure_template(
            procedure_code,
            procedure_name,
            cost=4200,
            description="Resolver crown mapping",
        )

        result = create_invoice(
            patient_id=self.patient_id,
            items=[
                {
                    "item_code": procedure_code,
                    "item_name": "",
                    "description": "",
                    "qty": 1,
                    "rate": 4200,
                }
            ],
            posting_date=today(),
            due_date=add_days(today(), 7),
        )

        invoice = frappe.get_doc("Sales Invoice", result["invoice_id"])
        self.assertEqual(invoice.items[0].item_code, procedure_code)
        self.assertEqual(invoice.items[0].item_name, procedure_name)

    def test_20_create_orthodontic_case_with_opening_advance(self):
        """Orthodontic case creation should calculate opening balance and accrue advance commission."""
        from mob_clinic.mob_clinic.api.orthodontic import create_orthodontic_case

        result = create_orthodontic_case(
            patient_id=self.patient_id,
            practitioner_id=self.practitioner_id,
            consultant_id=self.consultant_id,
            case_type="Fixed Braces",
            start_date=today(),
            estimated_duration_months=18,
            package_fee=45000,
            discount_amount=5000,
            advance_paid=10000,
            advance_payment_mode="Cash",
            commission_model="Percentage",
            commission_type="Percentage",
            commission_value=10,
            commission_basis="On collected amount",
            default_followup_days=30,
            notes="Upper and lower arch case",
            clinic=self.company,
        )

        case_data = result["case"]
        self.__class__.orthodontic_case_id = case_data["case_id"]

        self.assertEqual(case_data["net_fee"], 40000.0)
        self.assertEqual(case_data["total_paid"], 10000.0)
        self.assertEqual(case_data["balance_amount"], 30000.0)
        self.assertEqual(case_data["total_commission_accrued"], 1000.0)
        self.assertEqual(case_data["pending_commission_amount"], 1000.0)
        self.assertEqual(case_data["consultant_id"], self.consultant_id)
        self.assertEqual(case_data["status"], "Active")

        opening_entry = frappe.get_all(
            "Orthodontic Ledger Entry",
            filters={"orthodontic_case": case_data["case_id"]},
            fields=[
                "name",
                "payment_amount",
                "consultant_commission_amount",
                "is_adjustment",
                "sales_invoice",
                "payment_entry",
                "payment_mode",
            ],
            order_by="creation asc",
            limit_page_length=1,
        )[0]
        self.assertEqual(opening_entry.payment_amount, 10000.0)
        self.assertEqual(opening_entry.consultant_commission_amount, 1000.0)
        self.assertEqual(opening_entry.is_adjustment, 1)
        self.assertEqual(opening_entry.payment_mode, "Cash")
        self.assertTrue(opening_entry.sales_invoice)
        self.assertTrue(opening_entry.payment_entry)

    def test_20b_create_orthodontic_case_with_advance_and_no_commission(self):
        """Opening advance should still create receipt when a consultant is selected but commission is disabled."""
        from mob_clinic.mob_clinic.api.orthodontic import create_orthodontic_case

        unique = frappe.generate_hash(length=8)
        unique_digits = "".join(str(ord(char) % 10) for char in unique)[:8]
        patient = frappe.get_doc(
            {
                "doctype": "Patient",
                "first_name": "Ortho",
                "last_name": "No Commission",
                "sex": "Male",
                "mobile": f"+919900{unique_digits}",
                "email": f"ortho-no-commission-{unique}@mobclinic.test",
                "invite_user": 0,
            }
        )
        patient.insert(ignore_permissions=True)

        try:
            result = create_orthodontic_case(
                patient_id=patient.name,
                practitioner_id=self.practitioner_id,
                consultant_id=self.consultant_id,
                case_type="Retainer",
                start_date=today(),
                estimated_duration_months=6,
                package_fee=12000,
                advance_paid=2000,
                advance_payment_mode="Cash",
                clinic=self.company,
            )

            case_data = result["case"]
            opening_entry = frappe.get_all(
                "Orthodontic Ledger Entry",
                filters={"orthodontic_case": case_data["case_id"]},
                fields=[
                    "name",
                    "payment_amount",
                    "consultant_commission_amount",
                    "sales_invoice",
                    "payment_entry",
                ],
                order_by="creation asc",
                limit_page_length=1,
            )[0]

            self.assertEqual(case_data["total_paid"], 2000.0)
            self.assertEqual(case_data["total_commission_accrued"], 0.0)
            self.assertEqual(opening_entry.consultant_commission_amount, 0.0)
            self.assertTrue(opening_entry.sales_invoice)
            self.assertTrue(opening_entry.payment_entry)

            invoice = frappe.get_doc("Sales Invoice", opening_entry.sales_invoice)
            self.assertFalse(invoice.items[0].consultant_id)
            self.assertEqual(flt(invoice.items[0].consultant_commission_amount), 0.0)
        finally:
            self._cleanup_patient_records(patient.name)

    def test_20c_invoice_payload_skips_fixed_per_case_override(self):
        """Case-level fixed commission should stay on the ortho ledger and not be remapped onto invoice lines."""
        from mob_clinic.mob_clinic.api.orthodontic import _build_invoice_consultant_payload

        case_doc = frappe._dict(
            {
                "consultant_id": self.consultant_id,
                "company": self.company,
                "commission_model": "Fixed per case",
            }
        )
        commission_snapshot = {
            "consultant_commission_source": "Default",
            "consultant_commission_type": "Fixed",
            "consultant_commission_value": 1200,
        }

        with patch(
            "mob_clinic.mob_clinic.api.orthodontic._get_clinic_consultant",
            return_value={"commission_type": "Percentage", "commission_value": 10},
        ):
            payload = _build_invoice_consultant_payload(case_doc, commission_snapshot)

        self.assertIsNone(payload)

    def test_21_add_orthodontic_ledger_entry_with_receipt(self):
        """Paid orthodontic visits should always create linked accounting records."""
        from mob_clinic.mob_clinic.api.orthodontic import (
            add_orthodontic_ledger_entry,
            get_patient_orthodontic_summary,
        )

        result = add_orthodontic_ledger_entry(
            case_id=self.orthodontic_case_id,
            visit_date=today(),
            visit_notes="Wire change and review",
            payment_amount=2000,
            payment_mode="Cash",
            next_appointment_date=add_days(today(), 30),
        )

        ledger = result["ledger_entry"]
        case_data = result["case"]
        self.__class__.orthodontic_paid_ledger_id = ledger["ledger_entry_id"]

        self.assertTrue(ledger["sales_invoice"])
        self.assertTrue(ledger["payment_entry"])
        self.assertEqual(ledger["payment_amount"], 2000.0)
        self.assertEqual(ledger["commission_amount"], 200.0)
        self.assertEqual(ledger["balance_after_entry"], 28000.0)
        self.assertEqual(case_data["total_paid"], 12000.0)
        self.assertEqual(case_data["balance_amount"], 28000.0)
        self.assertEqual(case_data["total_commission_accrued"], 1200.0)
        self.assertEqual(case_data["pending_commission_amount"], 1200.0)
        self.assertEqual(case_data["next_appointment_date"], str(add_days(today(), 30)))

        invoice = frappe.get_doc("Sales Invoice", ledger["sales_invoice"])
        self.assertEqual(invoice.items[0].consultant_id, self.consultant_id)
        self.assertEqual(invoice.items[0].consultant_commission_amount, 200.0)

        summary = get_patient_orthodontic_summary(self.patient_id, clinic=self.company)
        self.assertEqual(summary["summary"]["case_id"], self.orthodontic_case_id)
        self.assertEqual(summary["summary"]["balance_amount"], 28000.0)
        self.assertGreaterEqual(len(summary["summary"]["recent_ledger"]), 2)

    def test_21b_linked_orthodontic_ledger_entry_locks_accounting_fields(self):
        """Accounting-linked orthodontic payments should not allow visit date or mode edits."""
        from mob_clinic.mob_clinic.api.orthodontic import update_orthodontic_ledger_entry

        with self.assertRaisesRegex(frappe.ValidationError, "visit date"):
            update_orthodontic_ledger_entry(
                ledger_entry_id=self.orthodontic_paid_ledger_id,
                visit_date=add_days(today(), 1),
            )

        with self.assertRaisesRegex(frappe.ValidationError, "payment mode"):
            update_orthodontic_ledger_entry(
                ledger_entry_id=self.orthodontic_paid_ledger_id,
                payment_mode="UPI",
            )

        updated = update_orthodontic_ledger_entry(
            ledger_entry_id=self.orthodontic_paid_ledger_id,
            visit_notes="Wire change completed",
            next_appointment_date=add_days(today(), 35),
        )
        self.assertEqual(updated["ledger_entry"]["visit_notes"], "Wire change completed")
        self.assertEqual(updated["ledger_entry"]["next_appointment_date"], str(add_days(today(), 35)))

    def test_22_record_and_reverse_orthodontic_commission_payout(self):
        """Commission payout history should update pending totals and remain reversible."""
        from mob_clinic.mob_clinic.api.orthodontic import (
            create_orthodontic_commission_payout,
            list_orthodontic_commission_payouts,
            reverse_orthodontic_commission_payout,
        )

        payout_result = create_orthodontic_commission_payout(
            case_id=self.orthodontic_case_id,
            paid_amount=600,
            posting_date=today(),
            payment_mode="Bank Transfer",
            reference_no="UTR-ORTHO-001",
            notes="March ortho commission payout",
        )

        payout = payout_result["payout"]
        case_data = payout_result["case"]

        self.assertEqual(payout["paid_amount"], 600.0)
        self.assertEqual(case_data["total_commission_paid"], 600.0)
        self.assertEqual(case_data["pending_commission_amount"], 600.0)
        self.assertEqual(
            sum(row["commission_paid_amount"] for row in payout["allocations"]),
            600.0,
        )

        payout_history = list_orthodontic_commission_payouts(case_id=self.orthodontic_case_id)
        self.assertEqual(len(payout_history["payouts"]), 1)
        self.assertEqual(payout_history["payouts"][0]["status"], "Submitted")

        reversed_result = reverse_orthodontic_commission_payout(
            payout_id=payout["payout_id"],
            notes="Correction",
        )
        reversed_case = reversed_result["case"]
        reversed_payout = reversed_result["payout"]

        self.assertEqual(reversed_payout["status"], "Reversed")
        self.assertEqual(reversed_case["total_commission_paid"], 0.0)
        self.assertEqual(reversed_case["pending_commission_amount"], 1200.0)

    def test_23_financial_dashboard_exposes_orthodontic_balance_separately(self):
        """Main financial dashboard should show invoice outstanding and orthodontic balance as separate metrics."""
        from mob_clinic.mob_clinic.api.dashboard import get_financial_stats

        result = get_financial_stats(
            from_date=today(),
            to_date=today(),
            clinic=self.company,
            practitioner_id=self.practitioner_id,
        )

        self.assertEqual(result["message"], "Success")
        summary = result["data"]["summary"]
        self.assertIn("orthodontic_balance", summary)
        self.assertIn("orthodontic_case_count", summary)
        self.assertIn("total_receivables", summary)
        self.assertEqual(summary["orthodontic_balance"], 28000.0)
        self.assertEqual(summary["orthodontic_case_count"], 1)
        self.assertGreaterEqual(summary["total_receivables"], summary["orthodontic_balance"])


def run_tests():
    """Helper function to run tests from command line"""
    unittest.main()


if __name__ == "__main__":
    run_tests()
