import frappe


def execute():
    target_group = _get_valid_customer_group()

    _set_safe_selling_default(target_group)
    _set_safe_healthcare_default(target_group)
    patient_count = _fix_patient_customer_groups(target_group)
    customer_count = _fix_customer_customer_groups(target_group)

    frappe.db.commit()
    frappe.logger().info(
        {
            "patch": "fix_invalid_customer_groups_patch",
            "target_group": target_group,
            "patients_updated": patient_count,
            "customers_updated": customer_count,
        }
    )


def _get_valid_customer_group():
    selling_group = _safe_get_single_value("Selling Settings", "customer_group")
    if _is_leaf_customer_group(selling_group):
        return selling_group

    # Healthcare Settings normally doesn't have customer_group in v15.
    # Keep this optional for older/custom sites.
    healthcare_group = _safe_get_single_value("Healthcare Settings", "customer_group")
    if _is_leaf_customer_group(healthcare_group):
        return healthcare_group

    if _is_leaf_customer_group("Individual"):
        return "Individual"

    fallback_group = frappe.db.sql(
        """
        select name
        from `tabCustomer Group`
        where ifnull(is_group, 0) = 0
        order by case when name = 'Individual' then 0 else 1 end, name asc
        limit 1
        """,
        as_dict=1,
    )

    if not fallback_group:
        frappe.throw("No non-group Customer Group found. Create a leaf Customer Group first.")

    return fallback_group[0]["name"]


def _is_leaf_customer_group(group_name):
    if not group_name:
        return False

    is_group = frappe.db.get_value("Customer Group", group_name, "is_group")
    return bool(group_name and is_group == 0)


def _set_safe_selling_default(target_group):
    current_group = _safe_get_single_value("Selling Settings", "customer_group")
    if current_group == target_group:
        return

    if not _is_leaf_customer_group(current_group):
        frappe.db.set_single_value("Selling Settings", "customer_group", target_group)


def _set_safe_healthcare_default(target_group):
    current_group = _safe_get_single_value("Healthcare Settings", "customer_group")
    if current_group is None:
        return
    if current_group == target_group:
        return

    if not _is_leaf_customer_group(current_group):
        frappe.db.set_single_value("Healthcare Settings", "customer_group", target_group)


def _fix_patient_customer_groups(target_group):
    count_result = frappe.db.sql(
        """
        select count(*) as count
        from `tabPatient`
        where ifnull(customer_group, '') in (
            select name from `tabCustomer Group` where ifnull(is_group, 0) = 1
        )
        """,
        as_dict=1,
    )
    updated_count = count_result[0]["count"] if count_result else 0

    if updated_count:
        frappe.db.sql(
            """
            update `tabPatient`
            set customer_group = %s
            where ifnull(customer_group, '') in (
                select name from `tabCustomer Group` where ifnull(is_group, 0) = 1
            )
            """,
            target_group,
        )

    return updated_count


def _fix_customer_customer_groups(target_group):
    count_result = frappe.db.sql(
        """
        select count(*) as count
        from `tabCustomer`
        where ifnull(customer_group, '') in (
            select name from `tabCustomer Group` where ifnull(is_group, 0) = 1
        )
        """,
        as_dict=1,
    )
    updated_count = count_result[0]["count"] if count_result else 0

    if updated_count:
        frappe.db.sql(
            """
            update `tabCustomer`
            set customer_group = %s
            where ifnull(customer_group, '') in (
                select name from `tabCustomer Group` where ifnull(is_group, 0) = 1
            )
            """,
            target_group,
        )

    return updated_count


def _safe_get_single_value(doctype, fieldname):
    """Return single value only when doctype + field exist, else None."""
    try:
        if not frappe.db.exists("DocType", doctype):
            return None
        meta = frappe.get_meta(doctype)
        if not meta or not meta.has_field(fieldname):
            return None
        return frappe.db.get_single_value(doctype, fieldname)
    except Exception:
        return None
