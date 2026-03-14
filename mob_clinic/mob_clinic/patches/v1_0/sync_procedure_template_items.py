import frappe

from mob_clinic.mob_clinic.procedure_items import sync_procedure_template_items


def execute():
    results = sync_procedure_template_items()
    frappe.db.commit()
    print(
        f"✅ Synced procedure items: {results['created']} created, "
        f"{results['updated']} updated, {results['existing']} existing, "
        f"{results['skipped']} skipped"
    )
