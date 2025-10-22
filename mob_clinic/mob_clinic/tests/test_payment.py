"""
Unit tests for Payment and Invoice Management APIs
Tests Sales Invoice creation, payment tracking, and reminders
"""

import frappe
import unittest
from frappe.utils import today, add_days, getdate, flt


class TestPaymentAPI(unittest.TestCase):
    """Test cases for Payment & Invoice Management APIs"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests"""
        frappe.set_user("Administrator")
        
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
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test data after all tests"""
        frappe.set_user("Administrator")
        
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
        
        # Delete test patient
        if frappe.db.exists("Patient", cls.patient_id):
            frappe.delete_doc("Patient", cls.patient_id, force=True)
        
        # Delete test practitioner
        if frappe.db.exists("Healthcare Practitioner", cls.practitioner_id):
            frappe.delete_doc("Healthcare Practitioner", cls.practitioner_id, force=True)
        
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
        self.assertEqual(result["total_invoiced"], 2000)
        self.assertEqual(result["total_paid"], 2000)
        self.assertEqual(result["total_pending"], 0)
    
    def test_07_create_invoice_with_appointment(self):
        """Test creating invoice linked to an appointment"""
        from mob_clinic.mob_clinic.api.payment import create_invoice
        
        # Create appointment first
        appointment = frappe.get_doc({
            "doctype": "Patient Appointment",
            "patient": self.patient_id,
            "practitioner": self.practitioner_id,
            "appointment_date": today(),
            "appointment_time": "10:00:00",
            "appointment_type": "Consultation",
            "routine_checkup": 1,  # This is what the validation is checking for
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
            invoice.cancel()
        frappe.delete_doc("Sales Invoice", invoice.name, force=True)
        frappe.delete_doc("Patient Appointment", appointment.name, force=True)
    
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
            frappe.delete_doc("Sales Invoice", invoice_id, force=True)
    
    def test_13_send_payment_reminder(self):
        """Test sending payment reminder"""
        from mob_clinic.mob_clinic.api.payment import create_invoice, send_payment_reminder
        
        # Create unpaid invoice with overdue date
        past_date = add_days(today(), -10)
        due_date = add_days(today(), -5)  # Due date is in the past (overdue) but AFTER posting date
        
        result = create_invoice(
            patient_id=self.patient_id,
            items=[{"item_code": "CONS-001", "qty": 1, "rate": 500}],
            posting_date=past_date,
            due_date=due_date
        )
        invoice_id = result["invoice_id"]
        
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
            frappe.delete_doc("Sales Invoice", invoice_id, force=True)
    
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
        
        # Create overdue invoice - post it in the past with due date also in past but after posting
        past_date = add_days(today(), -15)
        due_date = add_days(today(), -10)  # Due 5 days after posting, but still overdue today
        
        result = create_invoice(
            patient_id=self.patient_id,
            items=[{"item_code": "CONS-001", "qty": 1, "rate": 500}],
            posting_date=past_date,
            due_date=due_date
        )
        invoice_id = result["invoice_id"]
        
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
            frappe.delete_doc("Sales Invoice", invoice_id, force=True)


def run_tests():
    """Helper function to run tests from command line"""
    unittest.main()


if __name__ == "__main__":
    run_tests()
