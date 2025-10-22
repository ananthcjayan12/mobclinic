import frappe
import unittest
from datetime import datetime, timedelta
from frappe.tests.utils import FrappeTestCase
import json


class TestPrescriptionAPI(FrappeTestCase):
    """Test cases for Prescription Management APIs"""

    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests"""
        super().setUpClass()
        frappe.set_user("Administrator")
        
        # Clean up any existing test data first
        cls.cleanup_test_data()
        
        # Initialize naming series for patients if not exists
        cls.initialize_naming_series()
        
        # Create test drug items
        cls.create_test_drugs()
        
        # Create test practitioner
        cls.test_practitioner = cls.create_test_practitioner()
        
        # Create test patient
        cls.test_patient = cls.create_test_patient()
    
    @classmethod
    def create_test_drugs(cls):
        """Create test drug items"""
        drugs = ["Amoxicillin", "Ibuprofen", "Paracetamol"]
        
        for drug_name in drugs:
            if not frappe.db.exists("Item", drug_name):
                drug = frappe.get_doc({
                    "doctype": "Item",
                    "item_code": drug_name,
                    "item_name": drug_name,
                    "item_group": "Drug",
                    "stock_uom": "Nos",
                    "is_stock_item": 1
                })
                try:
                    drug.insert(ignore_permissions=True)
                except Exception as e:
                    print(f"Note: Could not create drug {drug_name}: {str(e)}")
        
        # Create test lab test templates
        lab_tests = ["Dental X-Ray", "Blood Test", "Urine Test"]
        for lab_test in lab_tests:
            if not frappe.db.exists("Lab Test Template", lab_test):
                template = frappe.get_doc({
                    "doctype": "Lab Test Template",
                    "lab_test_name": lab_test,
                    "lab_test_code": lab_test
                    # Don't set department - it's optional and requires Medical Department records
                })
                try:
                    template.insert(ignore_permissions=True)
                except Exception as e:
                    print(f"Note: Could not create lab test {lab_test}: {str(e)}")

    @classmethod
    def initialize_naming_series(cls):
        """Initialize the naming series for patients"""
        try:
            if not frappe.db.exists("Series", "HLC-PAT-.2025.-"):
                frappe.db.sql("""
                    INSERT INTO tabSeries (name, current) 
                    VALUES ('HLC-PAT-.2025.-', 0)
                    ON DUPLICATE KEY UPDATE current = current
                """)
                frappe.db.commit()
        except Exception as e:
            print(f"Note: Series initialization: {str(e)}")
    
    @classmethod
    def cleanup_test_data(cls):
        """Clean up all test data"""
        frappe.set_user("Administrator")
        
        try:
            # Delete test medical records - first get test patient IDs
            test_patients = frappe.get_all("Patient",
                filters=[["mobile", "in", ["+1555555555"]]],
                pluck="name"
            )
            
            # Delete medical records for test patients
            if test_patients:
                test_records = frappe.get_all("Patient Encounter",
                    filters=[["patient", "in", test_patients]],
                    pluck="name"
                )
                for record in test_records:
                    try:
                        frappe.delete_doc("Patient Encounter", record, force=True, ignore_permissions=True)
                    except Exception as e:
                        pass
            
            # Delete test patients
            test_patients = frappe.get_all("Patient",
                filters=[["mobile", "in", ["+1555555555"]]],
                pluck="name"
            )
            for patient in test_patients:
                try:
                    frappe.delete_doc("Patient", patient, force=True, ignore_permissions=True)
                except Exception as e:
                    pass
            
            # Delete specific test practitioner by name
            if frappe.db.exists("Healthcare Practitioner", "Test Practitioner Pres"):
                try:
                    frappe.delete_doc("Healthcare Practitioner", "Test Practitioner Pres", force=True, ignore_permissions=True)
                except Exception as e:
                    pass
            
            # Delete test user
            if frappe.db.exists("User", "test_practitioner_pres@test.com"):
                try:
                    frappe.delete_doc("User", "test_practitioner_pres@test.com", force=True, ignore_permissions=True)
                except Exception as e:
                    pass
            
            # Delete test drugs
            for drug_name in ["Amoxicillin", "Ibuprofen", "Paracetamol"]:
                if frappe.db.exists("Item", drug_name):
                    try:
                        frappe.delete_doc("Item", drug_name, force=True, ignore_permissions=True)
                    except Exception as e:
                        pass
            
            # Delete test lab templates
            for lab_test in ["Dental X-Ray", "Blood Test", "Urine Test"]:
                if frappe.db.exists("Lab Test Template", lab_test):
                    try:
                        frappe.delete_doc("Lab Test Template", lab_test, force=True, ignore_permissions=True)
                    except Exception as e:
                        pass
            
            frappe.db.commit()
        except Exception as e:
            print(f"Cleanup error: {str(e)}")
            frappe.db.rollback()

    @classmethod
    def create_test_practitioner(cls):
        """Create a test healthcare practitioner"""
        practitioner_email = "test_practitioner_pres@test.com"
        practitioner_name = "Test Practitioner Pres"
        
        # Check if already exists and return it
        if frappe.db.exists("Healthcare Practitioner", practitioner_name):
            return practitioner_name
        
        # Create User first
        if not frappe.db.exists("User", practitioner_email):
            user = frappe.get_doc({
                "doctype": "User",
                "email": practitioner_email,
                "first_name": "Test",
                "last_name": "Practitioner",
                "mobile_no": "+1555555555",
                "enabled": 1,
                "send_welcome_email": 0
            })
            user.insert(ignore_permissions=True)
        
        # Create Healthcare Practitioner without department (optional field)
        practitioner = frappe.get_doc({
            "doctype": "Healthcare Practitioner",
            "first_name": "Test",
            "last_name": "Practitioner",
            "practitioner_name": practitioner_name,
            "mobile_phone": "+1555555555",
            "status": "Active",
            "user_id": practitioner_email
        })
        practitioner.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return practitioner.name

    @classmethod
    def create_test_patient(cls):
        """Create a test patient"""
        # Check if patient already exists
        existing = frappe.db.get_value("Patient", {"mobile": "+1555555555"}, "name")
        if existing:
            return existing
        
        patient = frappe.get_doc({
            "doctype": "Patient",
            "first_name": "Test",
            "last_name": "Patient Pres",
            "patient_name": "Test Patient Pres",
            "mobile": "+1555555555",
            "email": "test_patient_pres@test.com",
            "sex": "Male",
            "blood_group": "O Positive",
            "invite_user": 0
        })
        patient.insert(ignore_permissions=True)
        frappe.db.commit()
        return patient.name

    def setUp(self):
        """Set up before each test"""
        super().setUp()
        frappe.set_user("Administrator")
        
    def tearDown(self):
        """Clean up after each test"""
        super().tearDown()
        frappe.set_user("Administrator")
        # Clean up patient encounters created in individual tests
        frappe.db.sql("""
            DELETE FROM `tabPatient Encounter` 
            WHERE patient = %s 
            AND creation > DATE_SUB(NOW(), INTERVAL 1 HOUR)
        """, (self.test_patient,))
        frappe.db.commit()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        cls.cleanup_test_data()
        super().tearDownClass()

    def test_01_create_prescription(self):
        """Test creating a new prescription"""
        from mob_clinic.mob_clinic.api.prescription import create_prescription
        
        # Login as practitioner
        frappe.set_user("test_practitioner_pres@test.com")
        
        # Create prescription - simple version without medications for now
        result = create_prescription(
            patient_id=self.test_patient,
            chief_complaint="Tooth pain",
            symptoms="Pain in lower right molar for 3 days",
            diagnosis="Dental cavity",
            treatment_plan="Root canal treatment required"
        )
        
        # Print full error details if creation failed
        if result.get("message") != "Prescription created successfully":
            print(f"\n[DEBUG] Create prescription full result: {result}")
            # Check error log for more details
            error_logs = frappe.get_all("Error Log", 
                filters={"error": ["like", "%Prescription%"]},
                fields=["error"],
                order_by="creation desc",
                limit=1
            )
            if error_logs:
                print(f"[DEBUG] Latest error log: {error_logs[0].get('error')[:1000]}")
        
        self.assertEqual(result.get("message"), "Prescription created successfully")
        self.assertIn("data", result)
        self.assertIn("record_id", result["data"])
        self.assertEqual(result["data"]["medications_count"], 2)
        self.assertEqual(result["data"]["investigations_count"], 1)
        # Patient Encounter uses docstatus instead of follow_up_required
        self.assertIn("docstatus", result["data"])
        
        # Store for later tests
        self.prescription_id = result["data"]["record_id"]
        
        frappe.set_user("Administrator")
        print("✓ Create prescription test passed")

    def test_02_get_prescriptions_list(self):
        """Test getting list of prescriptions"""
        from mob_clinic.mob_clinic.api.prescription import get_prescriptions
        
        # Login as practitioner
        frappe.set_user("test_practitioner_pres@test.com")
        
        # Get all prescriptions
        result = get_prescriptions()
        
        # Print error details if failed
        if result.get("message") != "success":
            print(f"\n[DEBUG] Get prescriptions error: {result}")
        
        self.assertEqual(result.get("message"), "success")
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
        self.assertIn("total_count", result)
        
        # Get prescriptions for specific patient
        result = get_prescriptions(patient_id=self.test_patient)
        
        self.assertEqual(result.get("message"), "success")
        if result["data"]:
            for record in result["data"]:
                self.assertEqual(record["patient"], self.test_patient)
        
        frappe.set_user("Administrator")
        print("✓ Get prescriptions list test passed")

    def test_03_get_prescription_details(self):
        """Test getting detailed prescription"""
        from mob_clinic.mob_clinic.api.prescription import get_prescription
        
        if not hasattr(self, 'prescription_id'):
            self.skipTest("No prescription created in previous test")
        
        # Login as practitioner
        frappe.set_user("test_practitioner_pres@test.com")
        
        result = get_prescription(self.prescription_id)
        
        self.assertEqual(result.get("message"), "success")
        self.assertIn("data", result)
        
        data = result["data"]
        self.assertEqual(data["record_id"], self.prescription_id)
        self.assertEqual(data["patient_id"], self.test_patient)
        self.assertIn("medications", data)
        self.assertIn("investigations", data)
        self.assertIsInstance(data["medications"], list)
        self.assertIsInstance(data["investigations"], list)
        
        # Verify medication details
        if data["medications"]:
            med = data["medications"][0]
            self.assertIn("drug_name", med)
            self.assertIn("dosage", med)
            self.assertIn("period", med)
        
        frappe.set_user("Administrator")
        print("✓ Get prescription details test passed")

    def test_04_update_prescription(self):
        """Test updating a prescription"""
        from mob_clinic.mob_clinic.api.prescription import update_prescription
        
        if not hasattr(self, 'prescription_id'):
            self.skipTest("No prescription created in previous test")
        
        # Login as practitioner
        frappe.set_user("test_practitioner_pres@test.com")
        
        result = update_prescription(
            record_id=self.prescription_id,
            treatment_plan="Root canal completed, crown placement scheduled",
            status="In Progress",
            follow_up_notes="Patient responding well to treatment"
        )
        
        self.assertEqual(result.get("message"), "Prescription updated successfully")
        self.assertIn("data", result)
        self.assertIn("updated_fields", result["data"])
        self.assertIn("treatment_plan", result["data"]["updated_fields"])
        self.assertIn("status", result["data"]["updated_fields"])
        
        frappe.set_user("Administrator")
        print("✓ Update prescription test passed")

    def test_05_share_prescription(self):
        """Test sharing prescription with patient"""
        from mob_clinic.mob_clinic.api.prescription import share_prescription
        
        if not hasattr(self, 'prescription_id'):
            self.skipTest("No prescription created in previous test")
        
        # Login as practitioner
        frappe.set_user("test_practitioner_pres@test.com")
        
        result = share_prescription(
            record_id=self.prescription_id,
            patient_email="test_patient_pres@test.com"
        )
        
        self.assertEqual(result.get("message"), "Prescription shared successfully")
        self.assertIn("data", result)
        self.assertEqual(result["data"]["shared_with_patient"], 1)
        
        frappe.set_user("Administrator")
        print("✓ Share prescription test passed")

    def test_06_get_patient_history(self):
        """Test getting patient medical history"""
        from mob_clinic.mob_clinic.api.prescription import get_patient_history
        
        # Login as practitioner
        frappe.set_user("test_practitioner_pres@test.com")
        
        result = get_patient_history(
            patient_id=self.test_patient,
            limit=10
        )
        
        self.assertEqual(result.get("message"), "success")
        self.assertIn("data", result)
        
        data = result["data"]
        self.assertEqual(data["patient_id"], self.test_patient)
        self.assertIn("appointments", data)
        self.assertIn("prescriptions", data)
        self.assertIn("invoices", data)
        self.assertIsInstance(data["appointments"], list)
        self.assertIsInstance(data["prescriptions"], list)
        self.assertIsInstance(data["invoices"], list)
        
        frappe.set_user("Administrator")
        print("✓ Get patient history test passed")

    def test_07_get_patient_history_filtered(self):
        """Test getting filtered patient history"""
        from mob_clinic.mob_clinic.api.prescription import get_patient_history
        
        # Login as practitioner
        frappe.set_user("test_practitioner_pres@test.com")
        
        # Get only prescriptions
        result = get_patient_history(
            patient_id=self.test_patient,
            record_type="prescriptions",
            limit=5
        )
        
        self.assertEqual(result.get("message"), "success")
        self.assertIn("data", result)
        
        data = result["data"]
        self.assertIn("prescriptions", data)
        self.assertNotIn("appointments", data)
        
        frappe.set_user("Administrator")
        print("✓ Get filtered patient history test passed")

    def test_08_create_prescription_with_minimal_data(self):
        """Test creating prescription with minimal required data"""
        from mob_clinic.mob_clinic.api.prescription import create_prescription
        
        # Login as practitioner
        frappe.set_user("test_practitioner_pres@test.com")
        
        result = create_prescription(
            patient_id=self.test_patient,
            chief_complaint="Regular checkup",
            diagnosis="Healthy teeth"
        )
        
        self.assertEqual(result.get("message"), "Prescription created successfully")
        self.assertIn("data", result)
        self.assertIn("record_id", result["data"])
        
        frappe.set_user("Administrator")
        print("✓ Create prescription with minimal data test passed")

    def test_09_update_prescription_medications(self):
        """Test updating prescription medications"""
        from mob_clinic.mob_clinic.api.prescription import update_prescription
        
        if not hasattr(self, 'prescription_id'):
            self.skipTest("No prescription created in previous test")
        
        # Login as practitioner
        frappe.set_user("test_practitioner_pres@test.com")
        
        result = update_prescription(
            record_id=self.prescription_id,
            medications=json.dumps([
                {
                    "drug_code": "Paracetamol",
                    "drug_name": "Paracetamol",
                    "interval": "3",
                    "interval_uom": "Day",
                    "comment": "500mg dosage, Take for 3 days"
                }
            ])
        )
        
        self.assertEqual(result.get("message"), "Prescription updated successfully")
        self.assertIn("medications", result["data"]["updated_fields"])
        self.assertEqual(result["data"]["medications_count"], 1)
        
        frappe.set_user("Administrator")
        print("✓ Update prescription medications test passed")

    def test_10_get_prescriptions_with_filters(self):
        """Test getting prescriptions with filters"""
        from mob_clinic.mob_clinic.api.prescription import get_prescriptions
        
        # Login as practitioner
        frappe.set_user("test_practitioner_pres@test.com")
        
        # Filter by status
        filters = json.dumps({"status": "Open"})
        result = get_prescriptions(filters=filters)
        
        self.assertEqual(result.get("message"), "success")
        self.assertIn("data", result)
        
        # Verify all returned records have Open status
        if result["data"]:
            for record in result["data"]:
                self.assertEqual(record.get("status"), "Open")
        
        frappe.set_user("Administrator")
        print("✓ Get prescriptions with filters test passed")

    def test_11_get_prescriptions_pagination(self):
        """Test prescription list pagination"""
        from mob_clinic.mob_clinic.api.prescription import get_prescriptions
        
        # Login as practitioner
        frappe.set_user("test_practitioner_pres@test.com")
        
        # Test with limit
        result = get_prescriptions(limit_page_length=5)
        
        self.assertEqual(result.get("message"), "success")
        self.assertIn("data", result)
        self.assertLessEqual(len(result["data"]), 5)
        self.assertEqual(result["page_length"], 5)
        
        frappe.set_user("Administrator")
        print("✓ Get prescriptions pagination test passed")

    def test_12_get_nonexistent_prescription(self):
        """Test getting a non-existent prescription"""
        from mob_clinic.mob_clinic.api.prescription import get_prescription
        
        # Login as practitioner
        frappe.set_user("test_practitioner_pres@test.com")
        
        result = get_prescription("NONEXISTENT-PRESCRIPTION-001")
        
        self.assertEqual(result.get("exc_type"), "NotFound")
        self.assertIn("not found", result.get("message").lower())
        
        frappe.set_user("Administrator")
        print("✓ Get non-existent prescription test passed")

    def test_13_update_nonexistent_prescription(self):
        """Test updating a non-existent prescription"""
        from mob_clinic.mob_clinic.api.prescription import update_prescription
        
        # Login as practitioner
        frappe.set_user("test_practitioner_pres@test.com")
        
        result = update_prescription(
            record_id="NONEXISTENT-PRESCRIPTION-001",
            diagnosis="Updated diagnosis"
        )
        
        self.assertEqual(result.get("exc_type"), "NotFound")
        self.assertIn("not found", result.get("message").lower())
        
        frappe.set_user("Administrator")
        print("✓ Update non-existent prescription test passed")

    def test_14_create_prescription_without_patient(self):
        """Test creating prescription without patient ID"""
        from mob_clinic.mob_clinic.api.prescription import create_prescription
        
        # Login as practitioner
        frappe.set_user("test_practitioner_pres@test.com")
        
        result = create_prescription(
            patient_id=None,
            chief_complaint="Test complaint"
        )
        
        self.assertEqual(result.get("exc_type"), "ValidationError")
        self.assertIn("required", result.get("message").lower())
        
        frappe.set_user("Administrator")
        print("✓ Create prescription without patient test passed")

    def test_15_share_nonexistent_prescription(self):
        """Test sharing a non-existent prescription"""
        from mob_clinic.mob_clinic.api.prescription import share_prescription
        
        # Login as practitioner
        frappe.set_user("test_practitioner_pres@test.com")
        
        result = share_prescription(
            record_id="NONEXISTENT-PRESCRIPTION-001"
        )
        
        self.assertEqual(result.get("exc_type"), "NotFound")
        self.assertIn("not found", result.get("message").lower())
        
        frappe.set_user("Administrator")
        print("✓ Share non-existent prescription test passed")


def run_tests():
    """Helper function to run tests"""
    unittest.main(module=__name__, verbosity=2, exit=False)


if __name__ == "__main__":
    run_tests()
