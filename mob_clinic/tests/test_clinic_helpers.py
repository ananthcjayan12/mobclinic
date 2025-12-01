import frappe
from frappe.tests.utils import FrappeTestCase
from mob_clinic.mob_clinic.api import clinic as clinic_helper

class TestClinicHelpers(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# Create test companies (Clinics)
		if not frappe.db.exists("Company", "_Test Clinic A"):
			frappe.get_doc({
				"doctype": "Company",
				"company_name": "_Test Clinic A",
				"default_currency": "INR",
				"country": "India"
			}).insert()
		
		if not frappe.db.exists("Company", "_Test Clinic B"):
			frappe.get_doc({
				"doctype": "Company",
				"company_name": "_Test Clinic B",
				"default_currency": "INR",
				"country": "India"
			}).insert()

		# Create test user and practitioner
		self.user = "test_practitioner@example.com"
		if not frappe.db.exists("User", self.user):
			frappe.get_doc({
				"doctype": "User",
				"email": self.user,
				"first_name": "Test",
				"last_name": "Practitioner",
				"roles": [{"role": "Physician"}]
			}).insert()

		self.practitioner_name = "_Test Practitioner"
		if not frappe.db.exists("Healthcare Practitioner", self.practitioner_name):
			doc = frappe.get_doc({
				"doctype": "Healthcare Practitioner",
				"practitioner_name": self.practitioner_name,
				"first_name": "Test",
				"last_name": "Practitioner",
				"user_id": self.user,
				"primary_company": "_Test Clinic A"
			})
			doc.insert()
		else:
			# Ensure primary company is set
			frappe.db.set_value("Healthcare Practitioner", self.practitioner_name, "primary_company", "_Test Clinic A")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.flags.in_test = True
		
		# Clean up test data
		if frappe.db.exists("Healthcare Practitioner", self.practitioner_name):
			frappe.delete_doc("Healthcare Practitioner", self.practitioner_name, force=True, ignore_permissions=True)
		
		if frappe.db.exists("User", self.user):
			frappe.delete_doc("User", self.user, force=True, ignore_permissions=True)
			
		# Delete companies using raw SQL to avoid cascading deletes
		for company in ["_Test Clinic A", "_Test Clinic B"]:
			if frappe.db.exists("Company", company):
				# Delete related Healthcare Service Units first
				frappe.db.sql("DELETE FROM `tabHealthcare Service Unit` WHERE company = %s", company)
				frappe.db.sql("DELETE FROM `tabCompany` WHERE name = %s", company)
		
		frappe.db.commit()

	def test_get_accessible_companies(self):
		companies = clinic_helper.get_accessible_companies_for_practitioner(self.practitioner_name)
		self.assertIn("_Test Clinic A", companies)
		# Should not have access to Clinic B yet
		self.assertNotIn("_Test Clinic B", companies)

	def test_resolve_active_clinic_explicit(self):
		# Explicit param should override everything if valid
		clinic = clinic_helper.resolve_active_clinic(self.practitioner_name, "_Test Clinic A")
		self.assertEqual(clinic, "_Test Clinic A")

	def test_resolve_active_clinic_session(self):
		# Mock session
		frappe.session.user = self.user
		clinic_helper.set_active_clinic_session("_Test Clinic A")
		
		clinic = clinic_helper.resolve_active_clinic(self.practitioner_name, None)
		self.assertEqual(clinic, "_Test Clinic A")

	def test_resolve_active_clinic_fallback(self):
		# Clear session
		if hasattr(frappe.local, "session"):
			frappe.local.session.data = {}
		
		# Should fall back to primary_company
		clinic = clinic_helper.resolve_active_clinic(self.practitioner_name, None)
		self.assertEqual(clinic, "_Test Clinic A")

	def test_validate_practitioner_access(self):
		# Should have access to A
		self.assertTrue(clinic_helper.validate_practitioner_access(self.practitioner_name, "_Test Clinic A"))
		# Should NOT have access to B
		self.assertFalse(clinic_helper.validate_practitioner_access(self.practitioner_name, "_Test Clinic B"))

	def test_apply_clinic_filter(self):
		filters = {}
		filters = clinic_helper.apply_clinic_filter(filters, "_Test Clinic A")
		self.assertEqual(filters.get("company"), "_Test Clinic A")

		# Test with existing filters as list
		filters_list = [["status", "=", "Open"]]
		filters_list = clinic_helper.apply_clinic_filter(filters_list, "_Test Clinic A")
		found = False
		for f in filters_list:
			if f[0] == "company" and f[2] == "_Test Clinic A":
				found = True
		self.assertTrue(found)
