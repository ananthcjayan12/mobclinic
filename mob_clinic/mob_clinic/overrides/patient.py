"""
Custom Patient overrides for mob_clinic
Handles duplicate customer names during patient creation/import
"""

import frappe
from frappe import _


def patient_validate(doc, method=None):
	"""
	Hook: runs during Patient validate (before save).
	If customer linking is enabled and no customer exists, pre-create one with unique name.
	"""
	if not frappe.db.get_single_value("Healthcare Settings", "link_customer_to_patient"):
		return
	
	# Only handle new patients without a customer
	if doc.customer or not doc.is_new():
		return
	
	# Check if a customer with patient name already exists
	customer_name = doc.patient_name
	existing_customer = frappe.db.exists("Customer", customer_name)
	
	if existing_customer:
		# Find next available name (Phylomina-1, Phylomina-2, etc.)
		counter = 1
		while frappe.db.exists("Customer", f"{customer_name}-{counter}"):
			counter += 1
		
		unique_customer_name = f"{customer_name}-{counter}"
		
		# Pre-create customer before healthcare's on_update tries to
		customer = frappe.get_doc({
			"doctype": "Customer",
			"customer_name": unique_customer_name,
			"customer_group": doc.customer_group
			or frappe.db.get_single_value("Selling Settings", "customer_group"),
			"territory": doc.territory or frappe.db.get_single_value("Selling Settings", "territory"),
			"customer_type": "Individual",
			"default_currency": doc.default_currency,
			"default_price_list": doc.default_price_list,
			"language": doc.language,
			"image": doc.image,
		})
		customer.insert(ignore_permissions=True, ignore_mandatory=True)
		
		# Link it to patient immediately
		doc.customer = customer.name
		frappe.logger().info(f"Pre-created customer {customer.name} for patient {doc.name or 'new'}")

