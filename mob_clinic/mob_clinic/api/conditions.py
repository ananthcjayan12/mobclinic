"""
Multi-Clinic Dental Conditions API
Supports both global templates and clinic-specific overrides
"""

import frappe
from frappe import _

@frappe.whitelist()
def get_conditions(clinic=None, search=None, category=None):
	"""
	Get all available conditions for a clinic
	Merges global templates with clinic-specific overrides
	
	Resolution order:
	1. Clinic overrides (custom conditions + template overrides)
	2. Global templates (if not overridden by clinic)
	
	Args:
		clinic: Clinic name/ID (required)
		search: Search term for condition name, code, or type
		category: Filter by category
	"""
	try:
		if not clinic:
			return {"message": "Clinic parameter is required", "conditions": []}, 400
		
		# Verify clinic exists
		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic", "conditions": []}, 404
		
		conditions = []
		# Get clinic overrides into a dictionary for quick lookup
		overrides = {
			o.condition_template: o for o in frappe.get_all(
				"Dental Condition Clinic Override",
				filters={"clinic": clinic, "is_custom_condition": 0},
				fields=["condition_template", "is_active", "condition_name", "code", "type", "category", "description", "icon", "color", "treatment_required"]
			)
		}

		# Get custom conditions
		custom_conditions = frappe.get_all(
			"Dental Condition Clinic Override",
			filters={"clinic": clinic, "is_custom_condition": 1},
			fields=["name", "condition_name", "code", "type", "category", "description", "icon", "color", "treatment_required", "is_active"]
		)

		# Process custom conditions
		for override in custom_conditions:
			severity_levels = frappe.get_all(
				"Dental Condition Severity Level",
				filters={"parent": override.name},
				fields=["severity_level"]
			)
			condition_data = {
				"condition_name": override.condition_name,
				"code": override.code,
				"type": override.type,
				"category": override.category,
				"description": override.description,
				"icon": override.icon,
				"color": override.color,
				"treatment_required": override.treatment_required,
				"severity_levels": [sl.severity_level for sl in severity_levels],
				"is_custom": True,
				"is_active": bool(override.is_active),
				"template_name": None,
				"source": "clinic_custom"
			}
			# Apply search filter
			if search:
				search_lower = search.lower()
				if not (search_lower in condition_data["condition_name"].lower() or
						(condition_data["code"] and search_lower in condition_data["code"].lower()) or
						(condition_data["type"] and search_lower in condition_data["type"].lower())):
					continue
			conditions.append(condition_data)

		# Get global templates
		template_filters = {"is_active": 1}
		if category:
			template_filters["category"] = category

		templates = frappe.get_all(
			"Dental Condition Template",
			filters=template_filters,
			fields=["name", "condition_name", "code", "type", "category", "description",
					"icon", "color", "treatment_required"]
		)

		# Process templates, applying overrides
		for template in templates:
			override = overrides.get(template.name)
			
			if override:
				is_active = override.is_active
				condition_name = override.condition_name or template.condition_name
				code = override.code or template.code
				condition_type = override.type or template.type
				category = override.category or template.category
				description = override.description or template.description
				icon = override.icon or template.icon
				color = override.color or template.color
				treatment_required = override.treatment_required if override.treatment_required is not None else template.treatment_required
				source = "template_override"
			else:
				is_active = True
				condition_name = template.condition_name
				code = template.code
				condition_type = template.type
				category = template.category
				description = template.description
				icon = template.icon
				color = template.color
				treatment_required = template.treatment_required
				source = "template_default"

			severity_levels = frappe.get_all(
				"Dental Condition Severity Level",
				filters={"parent": template.name},
				fields=["severity_level"]
			)
			condition_data = {
				"condition_name": condition_name,
				"code": code,
				"type": condition_type,
				"category": category,
				"description": description,
				"icon": icon,
				"color": color,
				"treatment_required": treatment_required,
				"severity_levels": [sl.severity_level for sl in severity_levels],
				"is_custom": False,
				"is_active": bool(is_active),
				"template_name": template.name,
				"source": source
			}

			# Apply search filter
			if search:
				search_lower = search.lower()
				if not (search_lower in condition_data["condition_name"].lower() or
						(condition_data["code"] and search_lower in condition_data["code"].lower()) or
						(condition_data["type"] and search_lower in condition_data["type"].lower())):
					continue
			
			conditions.append(condition_data)
		
		return {"message": "success", "conditions": conditions}
	
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Get Conditions Error")
		return {"message": str(e), "conditions": []}, 500


@frappe.whitelist()
def create_custom_condition(clinic, condition_name, code, type, category, severity_levels=None, 
							 description=None, icon=None, color=None, treatment_required=0):
	"""
	Create a custom condition for a specific clinic
	
	Args:
		clinic: Clinic name/ID
		condition_name: Name of the condition
		code: Unique code for the condition
		type: Type (cavity, crown, etc.)
		category: Category (Decay, Gum Disease, etc.)
		severity_levels: JSON array of severity levels (e.g., ["Mild", "Moderate", "Severe"])
		description: Optional description
		icon: Optional icon identifier
		color: Optional color code
		treatment_required: Whether treatment is required (0 or 1)
	"""
	try:
		# Verify clinic exists
		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404
		
		# Check for duplicate custom condition name in this clinic
		existing = frappe.db.exists({
			"doctype": "Dental Condition Clinic Override",
			"clinic": clinic,
			"condition_name": condition_name,
			"is_custom_condition": 1
		})
		
		if existing:
			return {"message": f"Custom condition '{condition_name}' already exists for this clinic"}, 400
		
		# Check for duplicate code in this clinic
		existing_code = frappe.db.exists({
			"doctype": "Dental Condition Clinic Override",
			"clinic": clinic,
			"code": code.upper(),
			"is_custom_condition": 1
		})
		
		if existing_code:
			return {"message": f"Code '{code}' already exists for this clinic"}, 400
		
		# Parse severity_levels if it's a JSON string
		if isinstance(severity_levels, str):
			import json
			severity_levels = json.loads(severity_levels)
		
		# Create the custom condition override
		doc = frappe.get_doc({
			"doctype": "Dental Condition Clinic Override",
			"clinic": clinic,
			"is_custom_condition": 1,
			"condition_name": condition_name,
			"code": code.upper(),
			"type": type,
			"category": category,
			"description": description,
			"icon": icon,
			"color": color,
			"treatment_required": int(treatment_required),
			"is_active": 1
		})
		
		# Add severity levels
		if severity_levels:
			for level in severity_levels:
				doc.append("severity_levels", {
					"severity_level": level
				})
		
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		
		return {
			"message": "Custom condition created successfully",
			"condition": {
				"name": doc.name,
				"condition_name": doc.condition_name,
				"code": doc.code,
				"type": doc.type,
				"category": doc.category,
				"description": doc.description,
				"icon": doc.icon,
				"color": doc.color,
				"treatment_required": doc.treatment_required,
				"severity_levels": [sl.severity_level for sl in doc.severity_levels]
			}
		}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Create Custom Condition Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def override_template_condition(clinic, condition_template, **kwargs):
	"""
	Override a template condition for a specific clinic
	
	Args:
		clinic: Clinic name/ID
		condition_template: Name of the template to override
		**kwargs: Fields to override (condition_name, code, type, category, description, icon, color, treatment_required, severity_levels, is_active)
	"""
	try:
		# Verify clinic and template exist
		if not frappe.db.exists("Company", clinic):
			return {"message": "Invalid clinic"}, 404
		
		if not frappe.db.exists("Dental Condition Template", condition_template):
			return {"message": "Invalid condition template"}, 404
		
		# Check if override already exists
		existing = frappe.db.exists({
			"doctype": "Dental Condition Clinic Override",
			"clinic": clinic,
			"condition_template": condition_template
		})
		
		allowed_fields = ["condition_name", "code", "type", "category", "description", "icon", "color", "treatment_required", "is_active"]
		
		if existing:
			# Update existing override
			doc = frappe.get_doc("Dental Condition Clinic Override", existing)
			
			for field in allowed_fields:
				if field in kwargs:
					value = kwargs[field]
					if field in ["is_active", "treatment_required"]:
						value = int(value)
					elif field == "code" and value:
						value = value.upper()
					
					setattr(doc, field, value)
			
			# Handle severity_levels separately
			if "severity_levels" in kwargs:
				severity_levels = kwargs["severity_levels"]
				if isinstance(severity_levels, str):
					import json
					severity_levels = json.loads(severity_levels)
				
				# Clear existing severity levels
				doc.severity_levels = []
				
				# Add new severity levels
				if severity_levels:
					for level in severity_levels:
						doc.append("severity_levels", {"severity_level": level})
			
			doc.flags.ignore_permissions = True
			doc.save(ignore_permissions=True)
		else:
			# Create new override
			template = frappe.get_doc("Dental Condition Template", condition_template)
			
			doc_data = {
				"doctype": "Dental Condition Clinic Override",
				"clinic": clinic,
				"condition_template": condition_template,
				"is_active": int(kwargs.get("is_active", 1))
			}
			
			# Add override fields if provided
			for field in allowed_fields:
				if field in kwargs and kwargs[field] is not None:
					value = kwargs[field]
					if field in ["treatment_required"]:
						value = int(value)
					elif field == "code" and value:
						value = value.upper()
					
					doc_data[field] = value
			
			doc = frappe.get_doc(doc_data)
			
			# Handle severity_levels for new override
			if "severity_levels" in kwargs:
				severity_levels = kwargs["severity_levels"]
				if isinstance(severity_levels, str):
					import json
					severity_levels = json.loads(severity_levels)
				
				if severity_levels:
					for level in severity_levels:
						doc.append("severity_levels", {"severity_level": level})
			
			doc.flags.ignore_permissions = True
			doc.insert(ignore_permissions=True)
		
		frappe.db.commit()
		
		template = frappe.get_doc("Dental Condition Template", condition_template)
		
		# Get severity levels from override or template
		severity_levels = frappe.get_all(
			"Dental Condition Severity Level",
			filters={"parent": doc.name if doc.severity_levels else template.name},
			fields=["severity_level"]
		)
		
		return {
			"message": "Condition override saved successfully",
			"condition": {
				"condition_name": doc.condition_name or template.condition_name,
				"code": doc.code or template.code,
				"type": doc.type or template.type,
				"category": doc.category or template.category,
				"description": doc.description or template.description,
				"icon": doc.icon or template.icon,
				"color": doc.color or template.color,
				"treatment_required": doc.treatment_required if doc.treatment_required is not None else template.treatment_required,
				"severity_levels": [sl.severity_level for sl in severity_levels],
				"is_active": doc.is_active
			}
		}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Override Template Condition Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def update_custom_condition(clinic, condition_name, **kwargs):
	"""
	Update a custom condition created by a clinic
	
	Args:
		clinic: Clinic name/ID
		condition_name: Name of the custom condition to update
		**kwargs: Fields to update (code, type, category, severity_levels, description, icon, color, treatment_required, is_active)
	"""
	try:
		# Find the custom condition
		override = frappe.db.exists({
			"doctype": "Dental Condition Clinic Override",
			"clinic": clinic,
			"condition_name": condition_name,
			"is_custom_condition": 1
		})
		
		if not override:
			return {"message": "Custom condition not found"}, 404
		
		# Get the document
		doc = frappe.get_doc("Dental Condition Clinic Override", override)
		
		# Update allowed fields
		allowed_fields = ["code", "type", "category", "description", "icon", "color", "treatment_required", "is_active"]
		updates = {}
		
		for field in allowed_fields:
			if field in kwargs:
				value = kwargs[field]
				if field == "code" and value:
					value = value.upper()
					# Check for duplicate code
					existing_code = frappe.db.exists({
						"doctype": "Dental Condition Clinic Override",
						"clinic": clinic,
						"code": value,
						"is_custom_condition": 1,
						"name": ["!=", override]
					})
					if existing_code:
						return {"message": f"Code '{value}' already exists for this clinic"}, 400
				elif field == "treatment_required":
					value = int(value)
				elif field == "is_active":
					value = int(value)
				
				setattr(doc, field, value)
				updates[field] = value
		
		# Handle severity_levels separately
		if "severity_levels" in kwargs:
			severity_levels = kwargs["severity_levels"]
			if isinstance(severity_levels, str):
				import json
				severity_levels = json.loads(severity_levels)
			
			# Clear existing severity levels
			doc.severity_levels = []
			
			# Add new severity levels
			if severity_levels:
				for level in severity_levels:
					doc.append("severity_levels", {"severity_level": level})
			
			updates["severity_levels"] = severity_levels
		
		if updates:
			doc.flags.ignore_permissions = True
			doc.save(ignore_permissions=True)
			frappe.db.commit()
		
		return {
			"message": "Custom condition updated successfully",
			"updated_fields": list(updates.keys()),
			"condition": {
				"name": doc.name,
				"condition_name": doc.condition_name,
				"code": doc.code,
				"type": doc.type,
				"category": doc.category,
				"description": doc.description,
				"icon": doc.icon,
				"color": doc.color,
				"treatment_required": doc.treatment_required,
				"severity_levels": [sl.severity_level for sl in doc.severity_levels],
				"is_active": doc.is_active
			}
		}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Update Custom Condition Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def delete_custom_condition(clinic, condition_name):
	"""
	Delete a custom condition created by a clinic
	
	Args:
		clinic: Clinic name/ID
		condition_name: Name of the custom condition to delete
	"""
	try:
		# Find the custom condition
		override = frappe.db.exists({
			"doctype": "Dental Condition Clinic Override",
			"clinic": clinic,
			"condition_name": condition_name,
			"is_custom_condition": 1
		})
		
		if not override:
			return {"message": "Custom condition not found"}, 404
		
		# Delete the override
		frappe.delete_doc("Dental Condition Clinic Override", override, ignore_permissions=True)
		frappe.db.commit()
		
		return {"message": "Custom condition deleted successfully"}
	
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "Delete Custom Condition Error")
		return {"message": str(e)}, 500


@frappe.whitelist()
def get_condition_categories():
	"""Get list of all condition categories"""
	return {
		"message": "success",
		"categories": [
			"Decay",
			"Gum Disease",
			"Structural",
			"Trauma",
			"Infection",
			"Congenital",
			"Cosmetic",
			"Other"
		]
	}


@frappe.whitelist()
def get_condition_types():
	"""Get list of all condition types"""
	return {
		"message": "success",
		"types": [
			"cavity",
			"crown",
			"bridge",
			"implant",
			"root-canal",
			"filling",
			"extraction",
			"fracture",
			"abscess",
			"gingivitis",
			"periodontitis",
			"other"
		]
	}
