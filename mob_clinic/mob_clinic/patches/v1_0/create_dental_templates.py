"""
Patch to populate Dental Procedure Templates and Dental Condition Templates
with initial data for all clinics
"""

import frappe
from frappe import _
from mob_clinic.mob_clinic.procedure_items import sync_procedure_template_items

def execute():
	"""Execute the patch to create initial templates"""
	
	# Create procedure templates
	create_procedure_templates()

	# Ensure invoiceable Item masters exist for every procedure template
	sync_results = sync_procedure_template_items()
	print(
		f"📦 Procedure Items: {sync_results['created']} created, "
		f"{sync_results['updated']} updated, {sync_results['existing']} existing, "
		f"{sync_results['skipped']} skipped"
	)
	
	# Create condition templates
	create_condition_templates()
	
	frappe.db.commit()
	print("✅ Successfully created dental procedure and condition templates")


def create_procedure_templates():
	"""Create all procedure templates from predefined list"""
	
	procedures = [
		{"code": "CON001", "name": "General Consultation", "cost": 300, "category": "Preventive", "description": "Basic checkup and diagnosis with treatment plan"},
		{"code": "CON002", "name": "Specialist Consultation", "cost": 500, "category": "Other", "description": "Consultation with Endodontist/Orthodontist/Surgeon"},
		{"code": "RAD001", "name": "IOPA X-Ray", "cost": 150, "category": "Preventive", "description": "Intra-oral periapical radiograph (Digital)"},
		{"code": "RAD002", "name": "OPG (Referral Review)", "cost": 200, "category": "Preventive", "description": "Review and analysis of panoramic x-ray"},
		{"code": "PRV001", "name": "Scaling & Polishing (Basic)", "cost": 600, "category": "Preventive", "description": "Ultrasonic cleaning for stain and calculus removal"},
		{"code": "PRV002", "name": "Deep Scaling / Curettage", "cost": 900, "category": "Periodontic", "description": "Gum treatment for periodontitis (Per Quadrant)"},
		{"code": "RES001", "name": "GIC Filling (Small)", "cost": 500, "category": "Restorative", "description": "Glass Ionomer Cement filling for minor cavities"},
		{"code": "RES002", "name": "Composite Filling (Anterior)", "cost": 1000, "category": "Restorative", "description": "Tooth-colored aesthetic filling for front teeth"},
		{"code": "RES003", "name": "Composite Filling (Posterior)", "cost": 800, "category": "Restorative", "description": "Tooth-colored durable filling for back teeth"},
		{"code": "RES004", "name": "Temporary Filling", "cost": 200, "category": "Restorative", "description": "Sedative dressing for pain relief"},
		{"code": "END001", "name": "Anterior RCT", "cost": 2500, "category": "Endodontic", "description": "Root canal treatment for front teeth (Incisors/Canines)", "duration": 60},
		{"code": "END002", "name": "Premolar RCT", "cost": 2500, "category": "Endodontic", "description": "Root canal treatment for premolars", "duration": 60},
		{"code": "END003", "name": "Molar RCT", "cost": 2500, "category": "Endodontic", "description": "Root canal treatment for back teeth (Molars)", "duration": 90},
		{"code": "END004", "name": "Re-RCT", "cost": 3000, "category": "Endodontic", "description": "Retreatment of previously failed root canal", "duration": 90},
		{"code": "PRO001", "name": "Metal Crown", "cost": 3000, "category": "Prosthodontic", "description": "Standard full metal crown (Co-Cr)", "duration": 45},
		{"code": "PRO002", "name": "PFM Crown (Standard)", "cost": 2500, "category": "Prosthodontic", "description": "Porcelain Fused to Metal crown", "duration": 45},
		{"code": "PRO003", "name": "PFM Crown (Premium)", "cost": 3500, "category": "Prosthodontic", "description": "Tilite/DMLS Ceramic crown", "duration": 45},
		{"code": "PRO004", "name": "Zirconia Crown (Basic)", "cost": 5000, "category": "Prosthodontic", "description": "Metal-free aesthetic crown (Standard Warranty)", "duration": 45},
		{"code": "PRO005", "name": "Zirconia Crown (Premium)", "cost": 6500, "category": "Prosthodontic", "description": "High translucency aesthetic crown (Extended Warranty)", "duration": 45},
		{"code": "SUR001", "name": "Simple Extraction", "cost": 500, "category": "Surgical", "description": "Removal of mobile or loose tooth (Non-surgical)", "duration": 20},
		{"code": "SUR002", "name": "Firm Extraction", "cost": 800, "category": "Surgical", "description": "Removal of firm tooth requiring elevation", "duration": 30},
		{"code": "SUR003", "name": "Surgical Extraction", "cost": 1200, "category": "Surgical", "description": "Complicated removal requiring bone guttering/sutures", "duration": 45},
		{"code": "SUR004", "name": "Impaction Surgery (Wisdom)", "cost": 3000, "category": "Surgical", "description": "Surgical removal of impacted wisdom tooth", "duration": 60},
		{"code": "PED001", "name": "Pediatric Extraction", "cost": 200, "category": "Surgical", "description": "Removal of deciduous (milk) tooth", "duration": 15},
		{"code": "PED002", "name": "Fluoride Application", "cost": 1000, "category": "Preventive", "description": "Topical fluoride application for cavity prevention", "duration": 20},
		{"code": "ORT001", "name": "Metal Braces Kit", "cost": 20000, "category": "Orthodontic", "description": "Traditional metal brackets orthodontic treatment (Full)"},
		{"code": "ORT002", "name": "Ceramic Braces Kit", "cost": 45000, "category": "Orthodontic", "description": "Tooth-colored brackets orthodontic treatment (Full)"},
		{"code": "ORT003", "name": "Clear Aligners (Basic)", "cost": 80000, "category": "Orthodontic", "description": "Invisible aligners for minor corrections"},
		{"code": "COS001", "name": "Teeth Whitening (Office)", "cost": 6000, "category": "Cosmetic", "description": "Chemical bleaching procedure for instant whitening", "duration": 60},
		{"code": "COS002", "name": "Jewelry / Skyce", "cost": 1500, "category": "Cosmetic", "description": "Crystal attachment on tooth surface", "duration": 15},
		{"code": "OP001", "name": "Checkup X Ray", "cost": 100, "category": "Preventive", "description": "Intra-oral periapical radiograph (Digital) and Consultation"},
	]
	
	created_count = 0
	skipped_count = 0
	
	for proc in procedures:
		# Check if already exists
		existing = frappe.db.exists("Dental Procedure Template", {"procedure_name": proc["name"]})
		
		if existing:
			print(f"⏭️  Skipping '{proc['name']}' - already exists")
			skipped_count += 1
			continue
		
		try:
			doc = frappe.get_doc({
				"doctype": "Dental Procedure Template",
				"procedure_name": proc["name"],
				"code": proc.get("code"),
				"category": proc.get("category", "Other"),
				"default_cost": proc["cost"],
				"duration_minutes": proc.get("duration", 30),
				"description": proc.get("description", ""),
				"is_active": 1
			})
			doc.insert(ignore_permissions=True)
			created_count += 1
			print(f"✅ Created procedure template: {proc['name']}")
		except Exception as e:
			print(f"❌ Failed to create '{proc['name']}': {str(e)}")
			frappe.log_error(frappe.get_traceback(), f"Procedure Template Creation Failed: {proc['name']}")
	
	print(f"\n📊 Procedure Templates: {created_count} created, {skipped_count} skipped")


def create_condition_templates():
	"""Create all condition templates from predefined list"""
	
	conditions = [
		{"code": "COND-001", "type": "cavity", "label": "Cavity", "category": "Decay", "severity": ["mild", "moderate", "severe"], "description": "Tooth decay or dental caries", "icon": "🦷", "color": "#DC2626", "treatment": True},
		{"code": "COND-002", "type": "crown", "label": "Crown Required", "category": "Structural", "severity": None, "description": "Tooth requires crown restoration", "icon": "👑", "color": "#CA8A04", "treatment": True},
		{"code": "COND-003", "type": "bridge", "label": "Bridge Required", "category": "Structural", "severity": None, "description": "Missing tooth requiring bridge", "icon": "🌉", "color": "#2563EB", "treatment": True},
		{"code": "COND-004", "type": "implant", "label": "Implant Required", "category": "Structural", "severity": None, "description": "Missing tooth requiring implant", "icon": "🔩", "color": "#4B5563", "treatment": True},
		{"code": "COND-005", "type": "root-canal", "label": "Root Canal Needed", "category": "Infection", "severity": ["mild", "moderate", "severe"], "description": "Tooth infection requiring root canal treatment", "icon": "🩺", "color": "#9333EA", "treatment": True},
		{"code": "COND-006", "type": "filling", "label": "Filling Required", "category": "Decay", "severity": ["small", "medium", "large"], "description": "Tooth requires filling restoration", "icon": "⚪", "color": "#16A34A", "treatment": True},
		{"code": "COND-007", "type": "extraction", "label": "Extraction Recommended", "category": "Other", "severity": None, "description": "Tooth requires removal", "icon": "❌", "color": "#B91C1C", "treatment": True},
		{"code": "COND-008", "type": "fracture", "label": "Fractured Tooth", "category": "Trauma", "severity": ["minor", "moderate", "severe"], "description": "Broken or cracked tooth", "icon": "⚡", "color": "#EA580C", "treatment": True},
		{"code": "COND-009", "type": "abscess", "label": "Abscess", "category": "Infection", "severity": ["acute", "chronic"], "description": "Tooth or gum infection with pus", "icon": "🔴", "color": "#EF4444", "treatment": True},
		{"code": "COND-010", "type": "gingivitis", "label": "Gum Disease", "category": "Gum Disease", "severity": ["gingivitis", "periodontitis"], "description": "Inflammation or infection of gums", "icon": "🩸", "color": "#EC4899", "treatment": True},
		{"code": "COND-011", "type": "other", "label": "Tooth Sensitivity", "category": "Other", "severity": ["mild", "moderate", "severe"], "description": "Pain or discomfort from hot/cold", "icon": "❄️", "color": "#06B6D4", "treatment": False},
		{"code": "COND-012", "type": "other", "label": "Impacted Tooth", "category": "Structural", "severity": None, "description": "Tooth unable to erupt properly", "icon": "⛔", "color": "#6366F1", "treatment": True},
		{"code": "COND-013", "type": "other", "label": "Discoloration", "category": "Cosmetic", "severity": ["mild", "moderate", "severe"], "description": "Tooth staining or color change", "icon": "🎨", "color": "#F59E0B", "treatment": False},
		{"code": "COND-014", "type": "other", "label": "Mobile Tooth", "category": "Gum Disease", "severity": ["grade-1", "grade-2", "grade-3"], "description": "Loose tooth with movement", "icon": "↔️", "color": "#F97316", "treatment": True},
		{"code": "COND-015", "type": "other", "label": "Other Condition", "category": "Other", "severity": None, "description": "Other dental conditions", "icon": "📝", "color": "#6B7280", "treatment": False},
	]
	
	created_count = 0
	skipped_count = 0
	
	for cond in conditions:
		# Check if already exists
		existing = frappe.db.exists("Dental Condition Template", {"condition_name": cond["label"]})
		
		if existing:
			print(f"⏭️  Skipping '{cond['label']}' - already exists")
			skipped_count += 1
			continue
		
		try:
			doc = frappe.get_doc({
				"doctype": "Dental Condition Template",
				"condition_name": cond["label"],
				"code": cond.get("code"),
				"type": cond.get("type", "other"),
				"category": cond.get("category", "Other"),
				"description": cond.get("description", ""),
				"icon": cond.get("icon"),
				"color": cond.get("color"),
				"treatment_required": 1 if cond.get("treatment") else 0,
				"is_active": 1
			})
			
			# Add severity levels if provided
			if cond.get("severity"):
				for severity in cond["severity"]:
					doc.append("severity_levels", {
						"severity_level": severity
					})
			
			doc.insert(ignore_permissions=True)
			created_count += 1
			print(f"✅ Created condition template: {cond['label']}")
		except Exception as e:
			print(f"❌ Failed to create '{cond['label']}': {str(e)}")
			frappe.log_error(frappe.get_traceback(), f"Condition Template Creation Failed: {cond['label']}")
	
	print(f"\n📊 Condition Templates: {created_count} created, {skipped_count} skipped")
