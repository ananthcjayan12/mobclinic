import frappe
import unittest
from frappe.tests.utils import FrappeTestCase


class TestAuthenticationAPI(FrappeTestCase):
    """Test cases for Authentication APIs"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data before running tests"""
        super().setUpClass()
        
        # Clean up any existing test data
        cls.cleanup_test_data()
        
        # Test user credentials
        cls.test_email = "test_doctor@mobclinic.com"
        cls.test_password = "Test@1234"
        cls.test_name = "Test Doctor"
        cls.test_phone = "+1111111111"  # Unique phone number
        cls.test_clinic = "Test Clinic"
    
    def setUp(self):
        """Set up before each test"""
        super().setUp()
        frappe.set_user("Administrator")
    
    @classmethod
    def cleanup_test_data(cls):
        """Clean up test data"""
        frappe.set_user("Administrator")
        
        # Delete test healthcare practitioner if exists
        practitioners = frappe.get_all("Healthcare Practitioner", 
                                       filters={"user_id": "test_doctor@mobclinic.com"})
        for p in practitioners:
            frappe.delete_doc("Healthcare Practitioner", p.name, force=True, ignore_permissions=True)
        
        # Delete test user if exists
        if frappe.db.exists("User", "test_doctor@mobclinic.com"):
            frappe.delete_doc("User", "test_doctor@mobclinic.com", force=True, ignore_permissions=True)
        
        frappe.db.commit()
    
    def test_01_mobile_register(self):
        """Test doctor registration"""
        from mob_clinic.mob_clinic.api.auth import mobile_register
        
        frappe.set_user("Administrator")
        
        # Test registration with valid data
        result = mobile_register(
            full_name=self.test_name,
            email=self.test_email,
            phone=self.test_phone,
            password=self.test_password,
            clinic_name=self.test_clinic
        )
        
        # Verify registration success
        self.assertEqual(result.get("message"), "Registration successful", 
                        f"Expected success but got: {result.get('message')}")
        self.assertIsNotNone(result.get("user_id"))
        self.assertIsNotNone(result.get("practitioner_id"))
        
        # Verify user was created
        user = frappe.get_doc("User", self.test_email)
        self.assertEqual(user.email, self.test_email)
        self.assertEqual(user.first_name, "Test")
        self.assertEqual(user.last_name, "Doctor")
        
        # Verify healthcare practitioner was created
        practitioner = frappe.get_doc("Healthcare Practitioner", 
                                     {"user_id": self.test_email})
        self.assertEqual(practitioner.user_id, self.test_email)
        self.assertEqual(practitioner.mobile_phone, self.test_phone)
        self.assertEqual(practitioner.mobile_app_enabled, 1)
        
        print("✓ Doctor registration test passed")
    
    def test_02_mobile_register_duplicate_email(self):
        """Test registration with duplicate email"""
        from mob_clinic.mob_clinic.api.auth import mobile_register
        
        # Try to register with same email again
        result = mobile_register(
            full_name="Another Doctor",
            email=self.test_email,
            phone="+9876543210",
            password="Test@5678",
            clinic_name="Another Clinic"
        )
        
        # Verify duplicate email is handled
        self.assertEqual(result.get("exc_type"), "ValidationError")
        self.assertIn("already exists", result.get("message").lower())
        
        print("✓ Duplicate email validation test passed")
    
    def test_03_mobile_login_valid_credentials(self):
        """Test login with valid credentials"""
        from mob_clinic.mob_clinic.api.auth import mobile_login
        
        frappe.set_user("Guest")
        
        # Login with valid credentials
        result = mobile_login(
            usr=self.test_email,
            pwd=self.test_password
        )
        
        # Print result for debugging
        if result.get("exc_type"):
            frappe.log_error(f"Login test error: {result}")
        
        # Verify login success
        self.assertEqual(result.get("message"), "Logged In",
                        f"Expected 'Logged In' but got: {result.get('message')}")
        self.assertIsNotNone(result.get("user"))
        self.assertEqual(result["user"]["email"], self.test_email)
        self.assertEqual(result["user"]["role"], "doctor")
        
        # Verify clinic data is returned
        self.assertIsNotNone(result["user"].get("clinic"))
        self.assertEqual(result["user"]["clinic"]["phone"], self.test_phone)
        
        print("✓ Valid login test passed")
    
    def test_04_mobile_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        from mob_clinic.mob_clinic.api.auth import mobile_login
        
        frappe.set_user("Guest")
        
        # Try login with wrong password
        result = mobile_login(
            usr=self.test_email,
            pwd="WrongPassword123"
        )
        
        # Verify login fails
        self.assertEqual(result.get("exc_type"), "AuthenticationError",
                        f"Expected 'AuthenticationError' but got: {result.get('exc_type')}")
        self.assertIn("invalid", result.get("message").lower())
        
        print("✓ Invalid credentials test passed")
    
    def test_05_get_practitioner_profile(self):
        """Test getting practitioner profile"""
        from mob_clinic.mob_clinic.api.auth import get_practitioner_profile
        
        # Login first
        frappe.set_user(self.test_email)
        
        # Get profile
        result = get_practitioner_profile()
        
        # Verify profile data
        self.assertEqual(result.get("message"), "success")
        self.assertIsNotNone(result.get("data"))
        
        profile = result["data"]
        self.assertEqual(profile["email"], self.test_email)
        self.assertEqual(profile["phone"], self.test_phone)
        self.assertEqual(profile["mobile_app_enabled"], 1)
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Get practitioner profile test passed")
    
    def test_06_update_practitioner_profile(self):
        """Test updating practitioner profile"""
        from mob_clinic.mob_clinic.api.auth import update_practitioner_profile
        
        # Login first
        frappe.set_user(self.test_email)
        
        # Update profile
        new_fee = 500
        new_description = "Updated clinic description"
        
        result = update_practitioner_profile(
            consultation_fee=new_fee,
            clinic_description=new_description,
            online_consultation=1
        )
        
        # Verify update success
        self.assertEqual(result.get("message"), "Profile updated successfully")
        self.assertIn("consultation_fee", result.get("updated_fields"))
        self.assertIn("clinic_description", result.get("updated_fields"))
        
        # Verify data was updated
        practitioner = frappe.get_doc("Healthcare Practitioner", 
                                     {"user_id": self.test_email})
        self.assertEqual(practitioner.consultation_fee, new_fee)
        self.assertEqual(practitioner.clinic_description, new_description)
        self.assertEqual(practitioner.online_consultation, 1)
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Update practitioner profile test passed")
    
    def test_07_mobile_logout(self):
        """Test logout functionality"""
        from mob_clinic.mob_clinic.api.auth import mobile_logout
        
        # Login first
        frappe.set_user(self.test_email)
        
        # Logout
        result = mobile_logout()
        
        # Verify logout success
        self.assertEqual(result.get("message"), "Logged Out",
                        f"Expected 'Logged Out' but got: {result.get('message')}")
        
        frappe.set_user("Administrator")
        
        print("✓ Logout test passed")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        cls.cleanup_test_data()
        super().tearDownClass()


def run_tests():
    """Helper function to run authentication tests"""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAuthenticationAPI)
    unittest.TextTestRunner(verbosity=2).run(suite)


if __name__ == "__main__":
    run_tests()