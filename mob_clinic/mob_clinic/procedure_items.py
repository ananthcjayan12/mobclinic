import frappe
from frappe.utils import flt

DEFAULT_SERVICE_GST_HSN_CODE = "999312"


def normalize_procedure_label(value):
    return " ".join((value or "").strip().split())


def get_procedure_label_candidates(value):
    normalized = normalize_procedure_label(value)
    if not normalized:
        return []

    return [normalized]


def find_matching_procedure_definition(value, clinic=None):
    candidates = get_procedure_label_candidates(value)
    if not candidates:
        return None

    if clinic:
        for candidate in candidates:
            override = frappe.db.get_value(
                "Dental Procedure Clinic Override",
                {"clinic": clinic, "procedure_name": candidate, "is_active": 1},
                ["procedure_name", "code", "cost", "description"],
                as_dict=True,
            )
            if override:
                return {
                    "procedure_name": override.procedure_name,
                    "code": override.code,
                    "rate": override.cost,
                    "description": override.description,
                }

        for candidate in candidates:
            override = frappe.db.get_value(
                "Dental Procedure Clinic Override",
                {"clinic": clinic, "code": candidate, "is_active": 1},
                ["procedure_name", "code", "cost", "description"],
                as_dict=True,
            )
            if override:
                return {
                    "procedure_name": override.procedure_name,
                    "code": override.code,
                    "rate": override.cost,
                    "description": override.description,
                }

    for candidate in candidates:
        template = frappe.db.get_value(
            "Dental Procedure Template",
            {"procedure_name": candidate, "is_active": 1},
            ["procedure_name", "code", "default_cost", "description"],
            as_dict=True,
        )
        if template:
            return {
                "procedure_name": template.procedure_name,
                "code": template.code,
                "rate": template.default_cost,
                "description": template.description,
            }

    for candidate in candidates:
        template = frappe.db.get_value(
            "Dental Procedure Template",
            {"code": candidate, "is_active": 1},
            ["procedure_name", "code", "default_cost", "description"],
            as_dict=True,
        )
        if template:
            return {
                "procedure_name": template.procedure_name,
                "code": template.code,
                "rate": template.default_cost,
                "description": template.description,
            }

    return None


def _get_default_selling_price_list():
    return frappe.db.get_single_value(
        "Selling Settings", "selling_price_list"
    ) or frappe.db.get_value("Price List", {"selling": 1}, "name")


def _sync_item_price(item, rate):
    if rate is None:
        return

    price_list = _get_default_selling_price_list()
    if not price_list:
        return

    item_price_name = frappe.db.get_value(
        "Item Price",
        {"item_code": item.name, "price_list": price_list, "uom": item.stock_uom},
        "name",
    )

    if item_price_name:
        item_price = frappe.get_doc("Item Price", item_price_name)
        updated = False

        if flt(item_price.price_list_rate) != flt(rate):
            item_price.price_list_rate = rate
            updated = True
        if item_price.item_name != item.item_name:
            item_price.item_name = item.item_name
            updated = True
        if item_price.item_description != item.description:
            item_price.item_description = item.description
            updated = True
        if item_price.currency != frappe.defaults.get_global_default("currency"):
            item_price.currency = frappe.defaults.get_global_default("currency")
            updated = True

        if updated:
            item_price.save(ignore_permissions=True)
        return

    item_price = frappe.get_doc(
        {
            "doctype": "Item Price",
            "price_list": price_list,
            "item_code": item.name,
            "item_name": item.item_name,
            "item_description": item.description,
            "uom": item.stock_uom,
            "currency": frappe.defaults.get_global_default("currency"),
            "price_list_rate": rate,
        }
    )
    item_price.insert(ignore_permissions=True)


def ensure_procedure_item(item_code, item_name, rate=None, description=None):
    if not item_code:
        return None, "skipped"

    item_name = normalize_procedure_label(item_name) or item_code
    description = description or item_name
    rate = flt(rate) if rate is not None else None

    if frappe.db.exists("Item", item_code):
        item = frappe.get_doc("Item", item_code)
        updated = False

        if item.item_name != item_name:
            item.item_name = item_name
            updated = True
        if item.description != description:
            item.description = description
            updated = True
        if rate is not None and flt(item.standard_rate) != rate:
            item.standard_rate = rate
            updated = True
        if not item.is_sales_item:
            item.is_sales_item = 1
            updated = True
        if item.is_stock_item:
            item.is_stock_item = 0
            updated = True
        if not item.item_group:
            item.item_group = "Services"
            updated = True
        if not item.stock_uom:
            item.stock_uom = "Nos"
            updated = True
        if not item.gst_hsn_code:
            item.gst_hsn_code = DEFAULT_SERVICE_GST_HSN_CODE
            updated = True

        if updated:
            item.save(ignore_permissions=True)
            _sync_item_price(item, rate)
            return item.name, "updated"

        return item.name, "existing"

    item = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_name,
            "item_group": "Services",
            "stock_uom": "Nos",
            "is_stock_item": 0,
            "is_sales_item": 1,
            "gst_hsn_code": DEFAULT_SERVICE_GST_HSN_CODE,
            "description": description,
            "standard_rate": 0,
        }
    )
    item.insert(ignore_permissions=True)
    if rate is not None:
        item.db_set("standard_rate", rate, update_modified=False)
        item.standard_rate = rate
        _sync_item_price(item, rate)
    return item.name, "created"


def sync_procedure_template_items():
    results = {"created": 0, "updated": 0, "existing": 0, "skipped": 0}

    templates = frappe.get_all(
        "Dental Procedure Template",
        filters={"is_active": 1},
        fields=["code", "procedure_name", "default_cost", "description"],
    )

    for template in templates:
        if not template.code:
            results["skipped"] += 1
            continue

        _, action = ensure_procedure_item(
            template.code,
            template.procedure_name,
            rate=template.default_cost,
            description=template.description,
        )
        results[action] += 1

    return results
