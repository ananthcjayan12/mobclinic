import frappe
import unittest
from datetime import datetime, timedelta
from frappe.tests.utils import FrappeTestCase


class TestAppointmentAPI(FrappeTestCase):
    """Test cases for Appointment Management APIs"""

    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests"""
        super().setUpClass()
        frappe.set_user("Administrator")
        
        # Clean up any existing test data first
        cls.cleanup_test_data()
        
        # Initialize naming series for patients if not exists
        cls.initialize_naming_series()
        
        # Create test practitioner
        cls.test_practitioner = cls.create_test_practitioner()
        
        # Create test patient
        cls.test_patient = cls.create_test_patient()
        
        # Set up working hours for the practitioner
        cls.setup_working_hours()

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
            # Delete test appointments using Frappe ORM
            test_appointments = frappe.get_all("Patient Appointment",
                filters=[
                    ["patient_name", "like", "%Test Patient Appt%"]
                ],
                pluck="name"
            )
            for appt in test_appointments:
                try:
                    frappe.delete_doc("Patient Appointment", appt, force=True, ignore_permissions=True)
                except Exception as e:
                    pass
            
            # Delete test patients
            test_patients = frappe.get_all("Patient",
                filters=[
                    ["mobile", "in", ["+1444444444"]]
                ],
                pluck="name"
            )
            for patient in test_patients:
                try:
                    frappe.delete_doc("Patient", patient, force=True, ignore_permissions=True)
                except Exception as e:
                    pass
            
            # Delete test practitioners
            test_practitioners = frappe.get_all("Healthcare Practitioner",
                filters=[["practitioner_name", "like", "%Test Practitioner Appt%"]],
                pluck="name"
            )
            for p in test_practitioners:
                try:
                    frappe.delete_doc("Healthcare Practitioner", p, force=True, ignore_permissions=True)
                except Exception as e:
                    pass
            
            # Delete test users
            if frappe.db.exists("User", "test_practitioner_appt@test.com"):
                try:
                    frappe.delete_doc("User", "test_practitioner_appt@test.com", force=True, ignore_permissions=True)
                except Exception as e:
                    pass
            
            frappe.db.commit()
        except Exception as e:
            print(f"Cleanup error: {str(e)}")
            frappe.db.rollback()

    @classmethod
    def create_test_practitioner(cls):
        """Create a test healthcare practitioner"""
        practitioner_email = "test_practitioner_appt@test.com"
        
        # Create User first
        if not frappe.db.exists("User", practitioner_email):
            user = frappe.get_doc({
                "doctype": "User",
                "email": practitioner_email,
                "first_name": "Test",
                "last_name": "Practitioner",
                "mobile_no": "+1444444444",  # Unique mobile number for appointment tests
                "enabled": 1,
                "send_welcome_email": 0
            })
            user.insert(ignore_permissions=True)
        
        # Create Healthcare Practitioner
        practitioner_name = "Test Practitioner Appt"
        
        # Check if already exists
        existing = frappe.db.get_value("Healthcare Practitioner", 
                                      {"practitioner_name": practitioner_name}, "name")
        if existing:
            return existing
        
        practitioner = frappe.get_doc({
            "doctype": "Healthcare Practitioner",
            "first_name": "Test",
            "last_name": "Practitioner",
            "practitioner_name": practitioner_name,
            "mobile_phone": "+1444444444",  # Unique mobile number for appointment tests
            "status": "Active",
            "user_id": practitioner_email,
            "department": "Cardiology"
        })
        practitioner.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return practitioner.name

    @classmethod
    def create_test_patient(cls):
        """Create a test patient"""
        # Check if patient already exists
        existing = frappe.db.get_value("Patient", {"mobile": "+1444444444"}, "name")
        if existing:
            return existing
        
        patient = frappe.get_doc({
            "doctype": "Patient",
            "first_name": "Test",
            "last_name": "Patient Appt",
            "patient_name": "Test Patient Appt",
            "mobile": "+1444444444",
            "email": "test_patient_appt@test.com",
            "sex": "Male",
            "blood_group": "O Positive",
            "invite_user": 0  # Don't create website user
        })
        patient.insert(ignore_permissions=True)
        frappe.db.commit()
        return patient.name

    @classmethod
    def setup_working_hours(cls):
        """Set up working hours for test practitioner"""
        # Note: Since Healthcare Practitioner doesn't have clinic_working_hours child table by default,
        # we'll rely on the default working hours (9 AM - 5 PM) in the get_working_hours function
        # This can be enhanced later by adding custom fields
        pass

    def setUp(self):
        """Set up before each test"""
        super().setUp()
        frappe.set_user("Administrator")
        
    def tearDown(self):
        """Clean up after each test"""
        super().tearDown()
        frappe.set_user("Administrator")
        # Clean up appointments created in individual tests
        frappe.db.sql("""
            DELETE FROM `tabPatient Appointment` 
            WHERE patient = %s 
            AND creation > DATE_SUB(NOW(), INTERVAL 1 HOUR)
        """, (self.test_patient,))
        frappe.db.commit()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        cls.cleanup_test_data()
        super().tearDownClass()

    def test_01_get_available_slots(self):
        """Test getting available time slots"""
        from mob_clinic.mob_clinic.api.appointment import get_available_slots
        
        # Get tomorrow's date (ensure it's a weekday)
        tomorrow = datetime.now() + timedelta(days=1)
        while tomorrow.strftime("%A") not in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            tomorrow += timedelta(days=1)
        
        appointment_date = tomorrow.strftime("%Y-%m-%d")
        
        result = get_available_slots(
            practitioner=self.test_practitioner,
            date=appointment_date
        )
        
        self.assertIn("slots", result)
        self.assertIsInstance(result["slots"], list)
        self.assertGreater(len(result["slots"]), 0, "Should have available slots")
        
        # Check slot structure
        if result["slots"]:
            slot = result["slots"][0]
            self.assertIn("time", slot)
            self.assertIn("available", slot)

    def test_02_create_appointment_success(self):
        """Test creating an appointment successfully"""
        from mob_clinic.mob_clinic.api.appointment import create_appointment, get_available_slots
        
        # Get an available slot
        tomorrow = datetime.now() + timedelta(days=1)
        while tomorrow.strftime("%A") not in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            tomorrow += timedelta(days=1)
        
        appointment_date = tomorrow.strftime("%Y-%m-%d")
        slots_result = get_available_slots(
            practitioner=self.test_practitioner,
            date=appointment_date
        )
        
        self.assertGreater(len(slots_result["slots"]), 0, "Need available slots for test")
        first_slot = slots_result["slots"][0]["time"]
        
        # Create appointment
        result = create_appointment(
            patient=self.test_patient,
            practitioner=self.test_practitioner,
            appointment_date=appointment_date,
            appointment_time=first_slot,
            duration=30,
            notes="Test appointment"
        )
        
        self.assertIn("appointment_id", result)
        self.assertIn("message", result)
        self.assertEqual(result["status"], "Open")
        
        # Store for later tests
        self.appointment_id = result["appointment_id"]

    def test_03_create_appointment_conflict(self):
        """Test creating appointment with time conflict"""
        from mob_clinic.mob_clinic.api.appointment import create_appointment
        
        # Try to create appointment at same time as previous test
        if hasattr(self, 'appointment_id'):
            # Get the existing appointment details
            existing_appt = frappe.get_doc("Patient Appointment", self.appointment_id)
            
            with self.assertRaises(Exception) as context:
                create_appointment(
                    patient=self.test_patient,
                    practitioner=self.test_practitioner,
                    appointment_date=existing_appt.appointment_date,
                    appointment_time=existing_appt.appointment_time,
                    duration=30
                )
            
            self.assertIn("conflict", str(context.exception).lower())

    def test_04_get_appointment_details(self):
        """Test getting appointment details"""
        from mob_clinic.mob_clinic.api.appointment import get_appointment
        
        if not hasattr(self, 'appointment_id'):
            self.skipTest("No appointment created in previous test")
        
        result = get_appointment(self.appointment_id)
        
        self.assertIn("name", result)
        self.assertIn("patient", result)
        self.assertIn("practitioner", result)
        self.assertEqual(result["name"], self.appointment_id)
        self.assertIn("patient_name", result)
        self.assertIn("practitioner_name", result)

    def test_05_get_appointments_list(self):
        """Test getting list of appointments"""
        from mob_clinic.mob_clinic.api.appointment import get_appointments
        
        # Get all appointments
        result = get_appointments()
        
        self.assertIn("appointments", result)
        self.assertIsInstance(result["appointments"], list)
        
        # Get appointments for specific patient
        result = get_appointments(patient=self.test_patient)
        
        self.assertIn("appointments", result)
        if result["appointments"]:
            # Verify it's for our patient
            for appt in result["appointments"]:
                self.assertEqual(appt["patient"], self.test_patient)

    def test_06_get_appointments_with_filters(self):
        """Test getting appointments with status filter"""
        from mob_clinic.mob_clinic.api.appointment import get_appointments
        
        # Get open appointments
        result = get_appointments(status="Open")
        
        self.assertIn("appointments", result)
        if result["appointments"]:
            for appt in result["appointments"]:
                self.assertEqual(appt["status"], "Open")

    def test_07_update_appointment(self):
        """Test updating/rescheduling an appointment"""
        from mob_clinic.mob_clinic.api.appointment import update_appointment, get_available_slots
        
        if not hasattr(self, 'appointment_id'):
            self.skipTest("No appointment created in previous test")
        
        # Get a different available slot
        existing_appt = frappe.get_doc("Patient Appointment", self.appointment_id)
        appointment_date = existing_appt.appointment_date
        
        slots_result = get_available_slots(
            practitioner=self.test_practitioner,
            date=appointment_date
        )
        
        # Find a different slot
        current_time = existing_appt.appointment_time.strftime("%H:%M:%S")
        new_slot = None
        for slot in slots_result["slots"]:
            if slot["time"] != current_time and slot["available"]:
                new_slot = slot["time"]
                break
        
        if new_slot:
            result = update_appointment(
                appointment_id=self.appointment_id,
                appointment_time=new_slot,
                notes="Rescheduled appointment"
            )
            
            self.assertIn("message", result)
            self.assertIn("appointment", result)

    def test_08_cancel_appointment(self):
        """Test cancelling an appointment"""
        from mob_clinic.mob_clinic.api.appointment import cancel_appointment
        
        if not hasattr(self, 'appointment_id'):
            self.skipTest("No appointment created in previous test")
        
        result = cancel_appointment(
            appointment_id=self.appointment_id,
            reason="Patient requested cancellation"
        )
        
        self.assertIn("message", result)
        self.assertIn("cancelled", result["message"].lower())
        
        # Verify status changed
        appt = frappe.get_doc("Patient Appointment", self.appointment_id)
        self.assertEqual(appt.status, "Cancelled")

    def test_09_create_appointment_outside_working_hours(self):
        """Test creating appointment outside working hours"""
        from mob_clinic.mob_clinic.api.appointment import create_appointment
        
        tomorrow = datetime.now() + timedelta(days=1)
        while tomorrow.strftime("%A") not in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            tomorrow += timedelta(days=1)
        
        appointment_date = tomorrow.strftime("%Y-%m-%d")
        
        # Try to book at 20:00 (outside 09:00-17:00)
        with self.assertRaises(Exception) as context:
            create_appointment(
                patient=self.test_patient,
                practitioner=self.test_practitioner,
                appointment_date=appointment_date,
                appointment_time="20:00:00",
                duration=30
            )
        
        error_msg = str(context.exception).lower()
        self.assertTrue(
            "working hours" in error_msg or "not available" in error_msg,
            "Should indicate outside working hours"
        )

    def test_10_create_appointment_weekend(self):
        """Test creating appointment on weekend (no working hours)"""
        from mob_clinic.mob_clinic.api.appointment import create_appointment
        
        # Find next Saturday
        date = datetime.now() + timedelta(days=1)
        while date.strftime("%A") != "Saturday":
            date += timedelta(days=1)
        
        appointment_date = date.strftime("%Y-%m-%d")
        
        with self.assertRaises(Exception) as context:
            create_appointment(
                patient=self.test_patient,
                practitioner=self.test_practitioner,
                appointment_date=appointment_date,
                appointment_time="10:00:00",
                duration=30
            )
        
        error_msg = str(context.exception).lower()
        self.assertTrue(
            "not available" in error_msg or "working hours" in error_msg,
            "Should indicate practitioner not available on weekend"
        )

    def test_11_get_available_slots_custom_duration(self):
        """Test getting available slots with custom duration"""
        from mob_clinic.mob_clinic.api.appointment import get_available_slots
        
        tomorrow = datetime.now() + timedelta(days=1)
        while tomorrow.strftime("%A") not in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            tomorrow += timedelta(days=1)
        
        appointment_date = tomorrow.strftime("%Y-%m-%d")
        
        # Get slots with 60-minute duration
        result = get_available_slots(
            practitioner=self.test_practitioner,
            date=appointment_date,
            duration=60
        )
        
        self.assertIn("slots", result)
        # Should have fewer slots with longer duration
        slots_60 = len(result["slots"])
        
        # Compare with 30-minute slots
        result_30 = get_available_slots(
            practitioner=self.test_practitioner,
            date=appointment_date,
            duration=30
        )
        slots_30 = len(result_30["slots"])
        
        self.assertLessEqual(slots_60, slots_30, 
                             "60-min slots should be equal or fewer than 30-min slots")

    def test_12_create_appointment_missing_required_fields(self):
        """Test creating appointment with missing required fields"""
        from mob_clinic.mob_clinic.api.appointment import create_appointment
        
        with self.assertRaises(Exception):
            create_appointment(
                patient=self.test_patient,
                # Missing practitioner
                appointment_date="2025-10-23",
                appointment_time="10:00:00"
            )

    def test_13_get_appointments_pagination(self):
        """Test appointment list pagination"""
        from mob_clinic.mob_clinic.api.appointment import get_appointments
        
        # Test with limit
        result = get_appointments(limit=5)
        
        self.assertIn("appointments", result)
        self.assertLessEqual(len(result["appointments"]), 5)
        
        # Test with start
        result = get_appointments(start=0, limit=2)
        first_page = result["appointments"]
        
        result = get_appointments(start=2, limit=2)
        second_page = result["appointments"]
        
        # Pages should be different (if we have enough data)
        if len(first_page) == 2 and len(second_page) > 0:
            self.assertNotEqual(
                first_page[0]["name"] if first_page else None,
                second_page[0]["name"] if second_page else None
            )

    def test_14_update_nonexistent_appointment(self):
        """Test updating non-existent appointment"""
        from mob_clinic.mob_clinic.api.appointment import update_appointment
        
        with self.assertRaises(Exception) as context:
            update_appointment(
                appointment_id="NONEXISTENT-APPT-001",
                notes="Updated notes"
            )
        
        error_msg = str(context.exception).lower()
        self.assertTrue(
            "not found" in error_msg or "does not exist" in error_msg,
            "Should indicate appointment not found"
        )

    def test_15_cancel_already_cancelled_appointment(self):
        """Test cancelling an already cancelled appointment"""
        from mob_clinic.mob_clinic.api.appointment import create_appointment, cancel_appointment, get_available_slots
        
        # Create a new appointment to cancel
        tomorrow = datetime.now() + timedelta(days=2)
        while tomorrow.strftime("%A") not in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
            tomorrow += timedelta(days=1)
        
        appointment_date = tomorrow.strftime("%Y-%m-%d")
        slots_result = get_available_slots(
            practitioner=self.test_practitioner,
            date=appointment_date
        )
        
        if slots_result["slots"]:
            first_slot = slots_result["slots"][0]["time"]
            
            # Create appointment
            result = create_appointment(
                patient=self.test_patient,
                practitioner=self.test_practitioner,
                appointment_date=appointment_date,
                appointment_time=first_slot,
                duration=30
            )
            
            appt_id = result["appointment_id"]
            
            # Cancel it
            cancel_appointment(
                appointment_id=appt_id,
                reason="First cancellation"
            )
            
            # Try to cancel again
            with self.assertRaises(Exception) as context:
                cancel_appointment(
                    appointment_id=appt_id,
                    reason="Second cancellation"
                )
            
            error_msg = str(context.exception).lower()
            self.assertTrue(
                "already" in error_msg or "cancelled" in error_msg,
                "Should indicate appointment already cancelled"
            )


def run_tests():
    """Helper function to run tests"""
    unittest.main(module=__name__, verbosity=2, exit=False)


if __name__ == "__main__":
    run_tests()
