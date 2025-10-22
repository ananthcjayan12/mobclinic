import frappe
import unittest
from frappe.tests.utils import FrappeTestCase


class TestPatientAPI(FrappeTestCase):
    """Test cases for Patient Management APIs"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data before running tests"""
        super().setUpClass()
        
        # Clean up any existing test data
        cls.cleanup_test_data()
        
        # Create test practitioner
        cls.create_test_practitioner()
        
        # Test patient data
        cls.test_patient_data = {
            "first_name": "Test",
            "last_name": "Patient",
            "sex": "Male",
            "mobile": "+1234567890",
            "email": "testpatient@example.com",
            "dob": "1990-01-01"
        }
        # Ensure a patient exists for tests and store its id
        from mob_clinic.mob_clinic.api.patient import create_patient
        frappe.set_user(cls.practitioner_email)
        result = create_patient(**cls.test_patient_data)
        # If patient already exists, find it; otherwise use returned id
        if result.get("message") == "Patient created successfully":
            cls.test_patient_id = result["data"]["patient_id"]
        else:
            # Try to find by mobile
            pid = frappe.db.get_value("Patient", {"mobile": cls.test_patient_data["mobile"]})
            cls.test_patient_id = pid
        frappe.set_user("Administrator")
    
    def setUp(self):
        """Set up before each test"""
        super().setUp()
        frappe.set_user("Administrator")
    
    @classmethod
    def create_test_practitioner(cls):
        """Create a test healthcare practitioner"""
        cls.practitioner_email = "testpractitioner@mobclinic.com"
        
        frappe.set_user("Administrator")
        
        # Create user if not exists
        if not frappe.db.exists("User", cls.practitioner_email):
            user = frappe.get_doc({
                "doctype": "User",
                "email": cls.practitioner_email,
                "first_name": "Test",
                "last_name": "Practitioner",
                "new_password": "Test@1234",
                "user_type": "System User",
                "send_welcome_email": 0
            })
            user.flags.ignore_permissions = True
            user.flags.ignore_password_policy = True
            user.insert(ignore_permissions=True)
            frappe.db.commit()
        
        # Create healthcare practitioner if not exists
        if not frappe.db.exists("Healthcare Practitioner", {"user_id": cls.practitioner_email}):
            practitioner = frappe.get_doc({
                "doctype": "Healthcare Practitioner",
                "first_name": "Test",
                "last_name": "Practitioner",
                "status": "Active",
                "user_id": cls.practitioner_email,
                "mobile_phone": "+9876543210",
                "mobile_app_enabled": 1
            })
            practitioner.flags.ignore_permissions = True
            practitioner.flags.ignore_mandatory = True
            practitioner.insert(ignore_permissions=True)
            cls.practitioner_id = practitioner.name
        else:
            cls.practitioner_id = frappe.db.get_value("Healthcare Practitioner", 
                                                      {"user_id": cls.practitioner_email}, "name")
        
        frappe.db.commit()
    
    @classmethod
    def cleanup_test_data(cls):
        """Clean up test data"""
        frappe.set_user("Administrator")
        
        # Delete test patients - search by multiple criteria
        test_mobiles = ["+1234567890", "+9876543210"]
        test_emails = ["testpatient@example.com", "updated@example.com"]
        
        for mobile in test_mobiles:
            patients = frappe.get_all("Patient", filters={"mobile": mobile})
            for p in patients:
                frappe.delete_doc("Patient", p.name, force=True, ignore_permissions=True)
        
        for email in test_emails:
            patients = frappe.get_all("Patient", filters={"email": email})
            for p in patients:
                frappe.delete_doc("Patient", p.name, force=True, ignore_permissions=True)
        
        # Also delete by name pattern
        patients = frappe.get_all("Patient", filters=[["patient_name", "like", "%Test Patient%"]])
        for p in patients:
            frappe.delete_doc("Patient", p.name, force=True, ignore_permissions=True)
        
        # Delete test practitioner
        if frappe.db.exists("User", "testpractitioner@mobclinic.com"):
            practitioners = frappe.get_all("Healthcare Practitioner", 
                                          filters={"user_id": "testpractitioner@mobclinic.com"})
            for p in practitioners:
                frappe.delete_doc("Healthcare Practitioner", p.name, force=True, ignore_permissions=True)
            
            frappe.delete_doc("User", "testpractitioner@mobclinic.com", force=True, ignore_permissions=True)
        
        frappe.db.commit()
    
    def test_01_create_patient(self):
        """Test creating a new patient"""
        from mob_clinic.mob_clinic.api.patient import create_patient
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Create a NEW patient with different data
        new_patient_data = {
            "first_name": "New",
            "last_name": "Patient",
            "sex": "Female",
            "mobile": "+9999999999",
            "email": "newpatient@example.com",
            "dob": "1995-05-05"
        }
        
        result = create_patient(**new_patient_data)
        
        # Verify creation success
        self.assertEqual(result.get("message"), "Patient created successfully",
                        f"Expected success but got: {result.get('message')}")
        self.assertIsNotNone(result.get("data"))
        
        patient_data = result["data"]
        self.assertEqual(patient_data["name"], "New Patient")
        self.assertEqual(patient_data["mobile"], new_patient_data["mobile"])
        self.assertEqual(patient_data["sex"], new_patient_data["sex"])
        
        # Clean up this test patient
        if result.get("data"):
            frappe.delete_doc("Patient", patient_data["patient_id"], force=True, ignore_permissions=True)
            frappe.db.commit()
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Create patient test passed")
    
    def test_02_create_duplicate_patient(self):
        """Test creating patient with duplicate mobile"""
        from mob_clinic.mob_clinic.api.patient import create_patient
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Try to create patient with same mobile
        result = create_patient(**self.test_patient_data)
        
        # Verify duplicate is handled
        self.assertEqual(result.get("exc_type"), "ValidationError")
        self.assertIn("already exists", result.get("message").lower())
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Duplicate patient validation test passed")
    
    def test_03_get_patient(self):
        """Test getting a single patient"""
        from mob_clinic.mob_clinic.api.patient import get_patient
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Get patient
        result = get_patient(self.test_patient_id)
        
        # Verify patient data
        self.assertEqual(result.get("message"), "success")
        self.assertIsNotNone(result.get("data"))
        
        patient_data = result["data"]
        self.assertEqual(patient_data["patient_id"], self.test_patient_id)
        self.assertEqual(patient_data["name"], "Test Patient")
        self.assertEqual(patient_data["mobile"], self.test_patient_data["mobile"])
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Get patient test passed")
    
    def test_04_get_patients_list(self):
        """Test getting list of patients"""
        from mob_clinic.mob_clinic.api.patient import get_patients
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Get patients list
        result = get_patients(limit_page_length=10)
        
        # Verify response structure
        self.assertEqual(result.get("message"), "success")
        self.assertIsNotNone(result.get("data"))
        self.assertIsInstance(result["data"], list)
        self.assertIsNotNone(result.get("total_count"))
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Get patients list test passed")
    
    def test_05_search_patients(self):
        """Test searching patients"""
        from mob_clinic.mob_clinic.api.patient import search_patients
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Search by name
        result = search_patients(search_term="Test", limit=10)
        
        # Verify search results
        self.assertEqual(result.get("message"), "success")
        self.assertIsNotNone(result.get("data"))
        self.assertIsInstance(result["data"], list)
        
        # Search by mobile
        result = search_patients(search_term="+1234567890", limit=10)
        
        # Verify search results contain our patient
        self.assertEqual(result.get("message"), "success")
        self.assertTrue(len(result["data"]) > 0)
        
        found = any(p["mobile"] == self.test_patient_data["mobile"] 
                   for p in result["data"])
        self.assertTrue(found, "Patient not found in search results")
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Search patients test passed")
    
    def test_06_update_patient(self):
        """Test updating patient information"""
        from mob_clinic.mob_clinic.api.patient import update_patient
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Update patient
        new_email = "updated@example.com"
        new_occupation = "Software Engineer"
        
        result = update_patient(
            patient_id=self.test_patient_id,
            email=new_email,
            occupation=new_occupation,
            preferred_language="English"
        )
        
        # Verify update success
        self.assertEqual(result.get("message"), "Patient updated successfully")
        self.assertIn("email", result.get("updated_fields"))
        self.assertIn("occupation", result.get("updated_fields"))
        
        # Verify data was updated
        patient = frappe.get_doc("Patient", self.test_patient_id)
        self.assertEqual(patient.email, new_email)
        self.assertEqual(patient.occupation, new_occupation)
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Update patient test passed")
    
    def test_07_get_patients_with_filters(self):
        """Test getting patients with filters"""
        from mob_clinic.mob_clinic.api.patient import get_patients
        import json
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Get patients with filter
        filters = {"sex": "Male"}
        result = get_patients(
            filters=json.dumps(filters),
            limit_page_length=10
        )
        
        # Verify filtered results
        self.assertEqual(result.get("message"), "success")
        self.assertIsNotNone(result.get("data"))
        
        # All patients should be male
        for patient in result["data"]:
            if patient.get("sex"):
                self.assertEqual(patient["sex"], "Male")
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Get patients with filters test passed")
    
    def test_08_get_nonexistent_patient(self):
        """Test getting a non-existent patient"""
        from mob_clinic.mob_clinic.api.patient import get_patient
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Try to get non-existent patient
        result = get_patient("NONEXISTENT-PATIENT-ID")
        
        # Verify error handling
        self.assertEqual(result.get("exc_type"), "NotFound")
        self.assertIn("not found", result.get("message").lower())
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Get non-existent patient test passed")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        cls.cleanup_test_data()
        super().tearDownClass()


def run_tests():
    """Helper function to run patient tests"""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPatientAPI)
    unittest.TextTestRunner(verbosity=2).run(suite)


if __name__ == "__main__":
    run_tests()