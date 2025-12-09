"""
Multi-Clinic Dental Procedures API
Supports both global templates and clinic-specific overrides
"""

import frappe
from frappe import _

@frappe.whitelist()
def get_procedures(clinic=None, search=None, category=None):
	"""
	Get all available procedures for a clinic
	Merges global templates with clinic-specific overrides
	
	Resolution order:
	1. Clinic overrides (custom procedures + template overrides)
	2. Global templates (if not overridden by clinic)
	
	Args:
		clinic: Clinic name/ID (required)
		search: Search term for procedure name or code
		category: Filter by category
	"""
	try:
		if not clinic:
			return {"message": "Clinic parameter is required", "procedures": []}, 400
		
		# Verify clinic exists
		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic", "procedures": []}, 404
		
		procedures = []
		
		# Get all clinic overrides (both custom and template-based)
		overrides = {
			o.procedure_template: o for o in frappe.get_all(
				"Dental Procedure Clinic Override",
				filters={"clinic": clinic, "is_custom_procedure": 0},
				fields=["procedure_template", "is_active", "cost", "procedure_name", "code", "category", "duration_minutes", "description"]
			)
		}

		# Get all custom procedures for the clinic
		custom_procedures = frappe.get_all(
			"Dental Procedure Clinic Override",
			filters={"clinic": clinic, "is_custom_procedure": 1},
			fields=["procedure_name", "code", "category", "cost", "duration_minutes", "description", "is_active"]
		)

		# Process custom procedures
		for proc in custom_procedures:
			procedure_data = {
				"procedure_name": proc.procedure_name,
				"code": proc.code,
				"category": proc.category,
				"cost": proc.cost,
				"duration_minutes": proc.duration_minutes,
				"description": proc.description,
				"is_custom": True,
				"is_active": bool(proc.is_active),
				"template_name": None,
				"source": "clinic_custom"
			}
			# Apply search filter
			if search:
				search_lower = search.lower()
				if not (search_lower in procedure_data["procedure_name"].lower() or
						(procedure_data["code"] and search_lower in procedure_data["code"].lower())):
					continue
			procedures.append(procedure_data)

		# Get global templates
		template_filters = {"is_active": 1}
		if category:
			template_filters["category"] = category

		templates = frappe.get_all(
			"Dental Procedure Template",
			filters=template_filters,
			fields=["name", "procedure_name", "code", "category", "default_cost",
					"duration_minutes", "description"]
		)

		# Process templates, applying overrides
		for template in templates:
			override = overrides.get(template.name)

			if override:
				is_active = override.is_active
				cost = override.cost if override.cost is not None else template.default_cost
				procedure_name = override.procedure_name or template.procedure_name
				code = override.code or template.code
				category = override.category or template.category
				duration_minutes = override.duration_minutes or template.duration_minutes
				description = override.description or template.description
				source = "template_override"
			else:
				is_active = True
				cost = template.default_cost
				procedure_name = template.procedure_name
				code = template.code
				category = template.category
				duration_minutes = template.duration_minutes
				description = template.description
				source = "template_default"

			procedure_data = {
				"procedure_name": procedure_name,
				"code": code,
				"category": category,
				"cost": cost,
				"duration_minutes": duration_minutes,
				"description": description,
				"is_custom": False,
				"is_active": bool(is_active),
				"template_name": template.name,
				"source": source
			}

			# Apply search filter
			if search:
				search_lower = search.lower()
				if not (search_lower in procedure_data["procedure_name"].lower() or
						(procedure_data["code"] and search_lower in procedure_data["code"].lower())):
					continue

			procedures.append(procedure_data)
		
		return {"message": "success", "procedures": procedures}
	
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Procedures Error")
		return {"message": str(e), "procedures": []}, 500


@frappe.whitelist()
def create_custom_procedure(clinic, procedure_name, code, category, cost, duration_minutes, description=None):
	"""
	Create a custom procedure for a specific clinic
	
	Args:
		clinic: Clinic name/ID
		procedure_name: Name of the procedure
		code: Unique code for the procedure
		category: Category (Preventive, Restorative, etc.)
		cost: Procedure cost
		duration_minutes: Duration in minutes
		description: Optional description
	"""
	try:
		# Verify clinic exists
		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404
		
		# Check for duplicate custom procedure name in this clinic
		existing = frappe.db.exists({
			"doctype": "Dental Procedure Clinic Override",
			"clinic": clinic,
			"procedure_name": procedure_name,
			"is_custom_procedure": 1
		})
		
		if existing:
			return {"message": f"Custom procedure '{procedure_name}' already exists for this clinic"}, 400
		
		# Check for duplicate code in this clinic
		existing_code = frappe.db.exists({
			"doctype": "Dental Procedure Clinic Override",
			"clinic": clinic,
			"code": code.upper(),
			"is_custom_procedure": 1
		})
		
		if existing_code:
			return {"message": f"Code '{code}' already exists for this clinic"}, 400
		
		# Create the custom procedure override
		doc = frappe.get_doc({
			"doctype": "Dental Procedure Clinic Override",
			"clinic": clinic,
			"is_custom_procedure": 1,
			"procedure_name": procedure_name,
			"code": code.upper(),
			"category": category,
			"cost": float(cost),
			"duration_minutes": int(duration_minutes),
			"description": description,
			"is_active": 1
		})
		
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		
		return {
			"message": "Custom procedure created successfully",
			"procedure": {
				"name": doc.name,
				"procedure_name": doc.procedure_name,
				"code": doc.code,
				"category": doc.category,
				"cost": doc.cost,
				"duration_minutes": doc.duration_minutes,
				"description": doc.description
			}
		}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Create Custom Procedure Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def override_template_procedure(clinic, procedure_template, **kwargs):
	"""
	Override a template procedure for a specific clinic
	
	Args:
		clinic: Clinic name/ID
		procedure_template: Name of the template to override
		**kwargs: Fields to override (cost, duration_minutes, description, category, code, procedure_name, is_active)
	"""
	try:
		# Verify clinic and template exist
		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404
		
		if not frappe.db.exists("Dental Procedure Template", procedure_template):
			return {"message": "Invalid procedure template"}, 404
		
		# Check if override already exists
		existing = frappe.db.exists({
			"doctype": "Dental Procedure Clinic Override",
			"clinic": clinic,
			"procedure_template": procedure_template
		})
		
		allowed_fields = ["cost", "duration_minutes", "description", "category", "code", "procedure_name", "is_active"]
		
		if existing:
			# Update existing override
			doc = frappe.get_doc("Dental Procedure Clinic Override", existing)
			
			for field in allowed_fields:
				if field in kwargs:
					value = kwargs[field]
					if field == "cost" and value:
						value = float(value)
					elif field == "duration_minutes" and value:
						value = int(value)
					elif field == "is_active":
						value = int(value)
					elif field == "code" and value:
						value = value.upper()
					
					setattr(doc, field, value)
			
			doc.flags.ignore_permissions = True
			doc.save(ignore_permissions=True)
		else:
			# Create new override
			template = frappe.get_doc("Dental Procedure Template", procedure_template)
			
			doc_data = {
				"doctype": "Dental Procedure Clinic Override",
				"clinic": clinic,
				"procedure_template": procedure_template,
				"is_active": int(kwargs.get("is_active", 1))
			}
			
			# Add override fields if provided, otherwise use template defaults
			for field in allowed_fields:
				if field in kwargs and kwargs[field] is not None:
					value = kwargs[field]
					if field == "cost":
						value = float(value)
					elif field == "duration_minutes":
						value = int(value)
					elif field == "code" and value:
						value = value.upper()
					
					doc_data[field] = value
			
			doc = frappe.get_doc(doc_data)
			doc.flags.ignore_permissions = True
			doc.insert(ignore_permissions=True)
		
		frappe.db.commit()
		
		template = frappe.get_doc("Dental Procedure Template", procedure_template)
		
		return {
			"message": "Procedure override saved successfully",
			"procedure": {
				"procedure_name": doc.procedure_name or template.procedure_name,
				"code": doc.code or template.code,
				"category": doc.category or template.category,
				"cost": doc.cost,
				"duration_minutes": doc.duration_minutes or template.duration_minutes,
				"description": doc.description or template.description,
				"is_active": doc.is_active
			}
		}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Override Template Procedure Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def update_custom_procedure(clinic, procedure_name, **kwargs):
	"""
	Update a custom procedure created by a clinic
	
	Args:
		clinic: Clinic name/ID
		procedure_name: Name of the custom procedure to update
		**kwargs: Fields to update (code, category, cost, duration_minutes, description, is_active)
	"""
	try:
		# Find the custom procedure
		override = frappe.db.exists({
			"doctype": "Dental Procedure Clinic Override",
			"clinic": clinic,
			"procedure_name": procedure_name,
			"is_custom_procedure": 1
		})
		
		if not override:
			return {"message": "Custom procedure not found"}, 404
		
		# Get the document
		doc = frappe.get_doc("Dental Procedure Clinic Override", override)
		
		# Update allowed fields
		allowed_fields = ["code", "category", "cost", "duration_minutes", "description", "is_active"]
		updates = {}
		
		for field in allowed_fields:
			if field in kwargs:
				value = kwargs[field]
				if field == "code" and value:
					value = value.upper()
					# Check for duplicate code
					existing_code = frappe.db.exists({
						"doctype": "Dental Procedure Clinic Override",
						"clinic": clinic,
						"code": value,
						"is_custom_procedure": 1,
						"name": ["!=", override]
					})
					if existing_code:
						return {"message": f"Code '{value}' already exists for this clinic"}, 400
				elif field == "cost":
					value = float(value)
				elif field == "duration_minutes":
					value = int(value)
				elif field == "is_active":
					value = int(value)
				
				setattr(doc, field, value)
				updates[field] = value
		
		if updates:
			doc.flags.ignore_permissions = True
			doc.save(ignore_permissions=True)
			frappe.db.commit()
		
		return {
			"message": "Custom procedure updated successfully",
			"updated_fields": list(updates.keys()),
			"procedure": {
				"name": doc.name,
				"procedure_name": doc.procedure_name,
				"code": doc.code,
				"category": doc.category,
				"cost": doc.cost,
				"duration_minutes": doc.duration_minutes,
				"description": doc.description,
				"is_active": doc.is_active
			}
		}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Update Custom Procedure Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def delete_custom_procedure(clinic, procedure_name):
	"""
	Delete a custom procedure created by a clinic
	
	Args:
		clinic: Clinic name/ID
		procedure_name: Name of the custom procedure to delete
	"""
	try:
		# Find the custom procedure
		override = frappe.db.exists({
			"doctype": "Dental Procedure Clinic Override",
			"clinic": clinic,
			"procedure_name": procedure_name,
			"is_custom_procedure": 1
		})
		
		if not override:
			return {"message": "Custom procedure not found"}, 404
		
		# Delete the override
		frappe.delete_doc("Dental Procedure Clinic Override", override)
		frappe.db.commit()
		
		return {"message": "Custom procedure deleted successfully"}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Delete Custom Procedure Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def get_procedure_categories():
	"""Get list of all procedure categories"""
	return {
		"message": "success",
		"categories": [
			"Preventive",
			"Restorative",
			"Surgical",
			"Endodontic",
			"Periodontic",
			"Orthodontic",
			"Prosthodontic",
			"Cosmetic",
			"Other"
		]
	}
