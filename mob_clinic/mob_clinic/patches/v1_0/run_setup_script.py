import frappe
from mob_clinic.mob_clinic.install import create_default_appointment_types
from mob_clinic.mob_clinic.patches.v1_0 import (
    install_custom_fields,
    add_company_custom_fields,
    initialize_clinic_settings,
    create_payment_modes,
    create_dental_templates,
    sync_procedure_template_items,
    create_medicine_templates,
    create_consultant_invoice_fields,
    ensure_fiscal_year_for_all_clinics,
)

def execute():
    """
    Execute all setup patches in the correct order.
    1. Schema Changes (Custom Fields)
    2. Settings Initialization
    3. Master Data Creation (Payment Modes, Templates)
    """
    frappe.log("Starting Mobile Clinic Setup...")
    
    # 1. Install Custom Fields (Schema)
    frappe.log("\n--- Installing Custom Fields ---")
    install_custom_fields.execute()
    
    # 2. Add Company Custom Fields (Schema)
    frappe.log("\n--- Adding Company Custom Fields ---")
    add_company_custom_fields.execute()
    
    # 3. Initialize Settings
    frappe.log("\n--- Initializing Clinic Settings ---")
    initialize_clinic_settings.execute()
    
    # 4. Create Payment Modes
    frappe.log("\n--- Creating Payment Modes ---")
    create_payment_modes.execute()
    
    # 5. Create Dental Templates
    frappe.log("\n--- Creating Dental Templates ---")
    create_dental_templates.execute()
    
    # 6. Sync procedure items from dental templates
    frappe.log("\n--- Syncing Procedure Template Items ---")
    sync_procedure_template_items.execute()

    # 7. Create Medicine Templates
    frappe.log("\n--- Creating Medicine Templates ---")
    create_medicine_templates.execute()

    # 8. Ensure consultant invoice custom fields exist
    frappe.log("\n--- Ensuring Consultant Invoice Fields ---")
    create_consultant_invoice_fields.execute()

    # 9. Ensure default appointment types exist
    frappe.log("\n--- Ensuring Default Appointment Types ---")
    create_default_appointment_types()

    # 10. Ensure current fiscal year is present and linked to all clinics
    frappe.log("\n--- Ensuring Fiscal Year For All Clinics ---")
    ensure_fiscal_year_for_all_clinics.execute()
    
    frappe.db.commit()
    frappe.log("\nMobile Clinic Setup Completed Successfully!")
