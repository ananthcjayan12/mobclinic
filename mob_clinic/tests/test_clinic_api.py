import frappe
from frappe.tests.utils import FrappeTestCase
from mob_clinic.mob_clinic.api import auth, appointment, payment, patient, clinic as clinic_helper, clinic_profile

class TestClinicAPI(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("DocType", "Clinic Consultant"):
			frappe.reload_doc("mob_clinic", "doctype", "clinic_consultant")
		if not frappe.db.exists("DocField", {"parent": "Clinic Settings", "fieldname": "consultants"}):
			frappe.reload_doc("mob_clinic", "doctype", "clinic_settings")
		frappe.clear_cache(doctype="Clinic Settings")
		frappe.clear_cache(doctype="Clinic Consultant")

		# Create test companies (Clinics)
		self.clinic_a = "_Test Clinic A"
		self.clinic_b = "_Test Clinic B"
		
		for clinic in [self.clinic_a, self.clinic_b]:
			if not frappe.db.exists("Company", clinic):
				frappe.get_doc({
					"doctype": "Company",
					"company_name": clinic,
					"default_currency": "INR",
					"country": "India"
				}).insert(ignore_if_duplicate=True)

		# Create test user and practitioner
		self.user = "test_api_practitioner@example.com"
		if not frappe.db.exists("User", self.user):
			frappe.get_doc({
				"doctype": "User",
				"email": self.user,
				"first_name": "Test API",
				"last_name": "Practitioner",
				"roles": [{"role": "Physician"}]
			}).insert()

		self.practitioner_name = "_Test API Practitioner"
		if not frappe.db.exists("Healthcare Practitioner", self.practitioner_name):
			doc = frappe.get_doc({
				"doctype": "Healthcare Practitioner",
				"practitioner_name": self.practitioner_name,
				"first_name": "Test API",
				"last_name": "Practitioner",
				"user_id": self.user,
				"primary_company": self.clinic_a
			})
			doc.insert()
		else:
			frappe.db.set_value("Healthcare Practitioner", self.practitioner_name, "primary_company", self.clinic_a)
		frappe.db.set_value("Healthcare Practitioner", self.practitioner_name, "is_clinic_admin", 1)
		frappe.db.set_value(
			"Healthcare Practitioner",
			self.practitioner_name,
			"allowed_pages_json",
			'["home","appointments","patients","prescriptions","invoice","financial_dashboard","whatsapp-manager","settings"]',
		)

		self.consultant_user = "test_api_consultant@example.com"
		if not frappe.db.exists("User", self.consultant_user):
			frappe.get_doc({
				"doctype": "User",
				"email": self.consultant_user,
				"first_name": "Consultant",
				"last_name": "Doctor",
				"roles": [{"role": "Physician"}]
			}).insert()

		self.consultant_practitioner_name = "_Test Consultant Practitioner"
		if not frappe.db.exists("Healthcare Practitioner", self.consultant_practitioner_name):
			frappe.get_doc({
				"doctype": "Healthcare Practitioner",
				"practitioner_name": self.consultant_practitioner_name,
				"first_name": "Consultant",
				"last_name": "Doctor",
				"user_id": self.consultant_user,
				"primary_company": self.clinic_a
			}).insert()
		else:
			frappe.db.set_value("Healthcare Practitioner", self.consultant_practitioner_name, "primary_company", self.clinic_a)

		# Create a test patient
		self.patient_name = "_Test Patient API"
		if not frappe.db.exists("Patient", {"patient_name": self.patient_name}):
			p = frappe.get_doc({
				"doctype": "Patient",
				"first_name": "_Test Patient",
				"last_name": "API",
				"sex": "Male",
				"mobile": "9998887776"
			})
			p.insert(ignore_permissions=True)
			self.patient = p.name
		else:
			self.patient = frappe.db.get_value("Patient", {"patient_name": self.patient_name}, "name")

		# Mock session
		frappe.set_user(self.user)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.flags.in_test = True
		
		# Clean up test data
		if frappe.db.exists("Clinic Settings", self.clinic_a):
			frappe.delete_doc("Clinic Settings", self.clinic_a, force=True, ignore_permissions=True)
		frappe.db.sql("DELETE FROM `tabPatient Appointment` WHERE patient = %s", self.patient)
		frappe.db.sql("DELETE FROM `tabSales Invoice` WHERE patient = %s", self.patient)
			
		if frappe.db.exists("Patient", self.patient):
			frappe.delete_doc("Patient", self.patient, force=True, ignore_permissions=True)
		
		if frappe.db.exists("Healthcare Practitioner", self.consultant_practitioner_name):
			frappe.delete_doc("Healthcare Practitioner", self.consultant_practitioner_name, force=True, ignore_permissions=True)
		
		if frappe.db.exists("User", self.consultant_user):
			frappe.delete_doc("User", self.consultant_user, force=True, ignore_permissions=True)
			
		if frappe.db.exists("Healthcare Practitioner", self.practitioner_name):
			frappe.delete_doc("Healthcare Practitioner", self.practitioner_name, force=True, ignore_permissions=True)
			
		if frappe.db.exists("User", self.user):
			frappe.delete_doc("User", self.user, force=True, ignore_permissions=True)
			
		# Delete companies using raw SQL to avoid cascading deletes
		for company in [self.clinic_a, self.clinic_b]:
			if frappe.db.exists("Company", company):
				frappe.db.sql("DELETE FROM `tabHealthcare Service Unit` WHERE company = %s", company)
				frappe.db.sql("DELETE FROM `tabCompany` WHERE name = %s", company)
		
		frappe.db.commit()

	def test_switch_clinic(self):
		# Test switching to allowed clinic using helper
		clinic_helper.set_active_clinic_session(self.clinic_a)
		
		# Verify it was set
		active = frappe.local.session.get("active_clinic")
		self.assertEqual(active, self.clinic_a)
		
		# Verify practitioner has access
		self.assertTrue(clinic_helper.validate_practitioner_access(self.practitioner_name, self.clinic_a))
		
		# Test access to forbidden clinic
		self.assertFalse(clinic_helper.validate_practitioner_access(self.practitioner_name, self.clinic_b))

	def test_create_appointment_with_clinic(self):
		# Create appointment for Clinic A
		appt = appointment.create_appointment(
			patient_id=self.patient,
			appointment_date=frappe.utils.nowdate(),
			appointment_time="10:00:00",
			clinic=self.clinic_a
		)
		
		doc_name = appt.get("data", {}).get("appointment_id")
		doc = frappe.get_doc("Patient Appointment", doc_name)
		self.assertEqual(doc.company, self.clinic_a)

	def test_create_patient_with_clinic(self):
		# Create patient assigned to Clinic A
		result = patient.create_patient(
			first_name="Clinic A",
			last_name="Patient",
			sex="Female",
			mobile="5556667777",
			clinic=self.clinic_a
		)
		
		p_id = result.get("data", {}).get("patient_id")
		p_doc = frappe.get_doc("Patient", p_id)
		self.assertEqual(p_doc.primary_clinic, self.clinic_a)

	def test_create_invoice_with_clinic(self):
		# Skip this test - invoice creation requires complex ERP setup (customer, accounts, etc.)
		# which is beyond the scope of multi-clinic logic testing
		self.skipTest("Invoice creation requires full ERP setup")

	def test_manage_clinic_consultants(self):
		clinic_helper.set_active_clinic_session(self.clinic_a)

		save_internal = clinic_profile.save_clinic_consultant(
			clinic=self.clinic_a,
			consultant_type="Internal",
			practitioner=self.consultant_practitioner_name,
			commission_type="Percentage",
			commission_value=12.5,
			is_active=1,
		)

		self.assertEqual(save_internal.get("message"), "Consultant saved successfully")
		internal_row = save_internal.get("data") or {}
		self.assertEqual(internal_row.get("practitioner"), self.consultant_practitioner_name)
		self.assertEqual(internal_row.get("consultant_name"), "Consultant Doctor")
		self.assertEqual(internal_row.get("commission_type"), "Percentage")
		self.assertEqual(internal_row.get("commission_value"), 12.5)

		save_external = clinic_profile.save_clinic_consultant(
			clinic=self.clinic_a,
			consultant_type="External",
			consultant_name="Visiting Surgeon",
			mobile="9990011223",
			commission_type="Fixed",
			commission_value=750,
			is_active=1,
			notes="Weekend consultant",
		)

		self.assertEqual(save_external.get("message"), "Consultant saved successfully")
		external_row = save_external.get("data") or {}
		self.assertEqual(external_row.get("consultant_type"), "External")
		self.assertEqual(external_row.get("consultant_name"), "Visiting Surgeon")
		self.assertEqual(external_row.get("commission_type"), "Fixed")
		self.assertEqual(external_row.get("commission_value"), 750.0)

		listing = clinic_profile.get_clinic_consultants(self.clinic_a)
		self.assertEqual(listing.get("message"), "success")
		self.assertEqual(len(listing.get("data", {}).get("consultants", [])), 2)

		delete_result = clinic_profile.delete_clinic_consultant(
			clinic=self.clinic_a,
			consultant_id=external_row.get("consultant_id"),
		)
		self.assertEqual(delete_result.get("message"), "Consultant deleted successfully")

		updated_listing = clinic_profile.get_clinic_consultants(self.clinic_a)
		consultants = updated_listing.get("data", {}).get("consultants", [])
		self.assertEqual(len(consultants), 1)
		self.assertEqual(consultants[0].get("consultant_id"), internal_row.get("consultant_id"))
