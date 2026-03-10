import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    custom_fields = {
        "Sales Invoice Item": [
            {
                "fieldname": "consultant_section_break",
                "label": "Consultant Commission",
                "fieldtype": "Section Break",
                "insert_after": "description",
                "collapsible": 1,
            },
            {
                "fieldname": "consultant_id",
                "label": "Consultant ID",
                "fieldtype": "Data",
                "insert_after": "consultant_section_break",
                "read_only": 1,
            },
            {
                "fieldname": "consultant_name",
                "label": "Consultant Name",
                "fieldtype": "Data",
                "insert_after": "consultant_id",
            },
            {
                "fieldname": "consultant_type",
                "label": "Consultant Type",
                "fieldtype": "Data",
                "insert_after": "consultant_name",
            },
            {
                "fieldname": "consultant_practitioner",
                "label": "Consultant Practitioner",
                "fieldtype": "Link",
                "options": "Healthcare Practitioner",
                "insert_after": "consultant_type",
            },
            {
                "fieldname": "consultant_commission_type",
                "label": "Commission Type",
                "fieldtype": "Data",
                "insert_after": "consultant_practitioner",
            },
            {
                "fieldname": "consultant_commission_value",
                "label": "Commission Value",
                "fieldtype": "Float",
                "insert_after": "consultant_commission_type",
            },
            {
                "fieldname": "consultant_commission_amount",
                "label": "Commission Amount",
                "fieldtype": "Currency",
                "insert_after": "consultant_commission_value",
            },
            {
                "fieldname": "consultant_commission_source",
                "label": "Commission Source",
                "fieldtype": "Data",
                "insert_after": "consultant_commission_amount",
            },
        ]
    }

    create_custom_fields(custom_fields, update=True)
    frappe.db.commit()
