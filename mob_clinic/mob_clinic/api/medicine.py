"""
Medicine API for mob_clinic.

Supports:
1. Global medicine templates
2. Clinic-specific medicine overrides
3. Clinic-specific custom medicines
"""

import frappe
from frappe import _
from frappe.utils import cint


DOSAGE_INT_FIELDS = [
    "default_morning",
    "default_lunch",
    "default_evening",
    "default_night",
    "default_days",
]


def get_current_practitioner():
    """Get current logged-in practitioner."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Please login to continue"))

    practitioner = frappe.db.get_value(
        "Healthcare Practitioner",
        {"user_id": user},
        ["name", "practitioner_name"],
        as_dict=True,
    )

    if not practitioner:
        frappe.throw(_("Healthcare practitioner profile not found"))

    return practitioner


def _validate_clinic(clinic):
    if not clinic:
        return
    if not frappe.db.exists("Company", clinic):
        frappe.throw(_("Invalid clinic"))


def _apply_search(items, search):
    if not search:
        return items

    search_lower = search.lower()
    filtered = []
    for med in items:
        medicine_name = (med.get("medicine_name") or "").lower()
        generic_name = (med.get("generic_name") or "").lower()
        if search_lower in medicine_name or search_lower in generic_name:
            filtered.append(med)
    return filtered


def _paginate(items, limit_start, limit_page_length):
    start = max(cint(limit_start), 0)
    page_length = cint(limit_page_length)
    if page_length <= 0:
        return items[start:]
    return items[start:start + page_length]


def _int_or_default(value, default_value):
    if value is None:
        return default_value
    return cint(value)


def _build_template_or_override_row(template, override):
    if override:
        return {
            "name": template.name,
            "medicine_name": override.medicine_name or template.medicine_name,
            "generic_name": override.generic_name or template.generic_name,
            "dosage_form": override.dosage_form or template.dosage_form,
            "strength": override.strength or template.strength,
            "category": override.category or template.category,
            "default_morning": _int_or_default(override.default_morning, cint(template.default_morning)),
            "default_lunch": _int_or_default(override.default_lunch, cint(template.default_lunch)),
            "default_evening": _int_or_default(override.default_evening, cint(template.default_evening)),
            "default_night": _int_or_default(override.default_night, cint(template.default_night)),
            "default_days": _int_or_default(override.default_days, cint(template.default_days)),
            "default_condition": override.default_condition or template.default_condition,
            "instructions": override.instructions or template.instructions,
            "description": override.description or template.description,
            "is_active": bool(override.is_active),
            "is_custom": False,
            "template_name": template.name,
            "source": "template_override",
        }

    return {
        "name": template.name,
        "medicine_name": template.medicine_name,
        "generic_name": template.generic_name,
        "dosage_form": template.dosage_form,
        "strength": template.strength,
        "category": template.category,
        "default_morning": cint(template.default_morning or 0),
        "default_lunch": cint(template.default_lunch or 0),
        "default_evening": cint(template.default_evening or 0),
        "default_night": cint(template.default_night or 0),
        "default_days": cint(template.default_days or 5),
        "default_condition": template.default_condition,
        "instructions": template.instructions,
        "description": template.description,
        "is_active": True,
        "is_custom": False,
        "template_name": template.name,
        "source": "template_default",
    }


def _build_custom_row(override):
    return {
        "name": override.name,
        "medicine_name": override.medicine_name,
        "generic_name": override.generic_name,
        "dosage_form": override.dosage_form or "Tablet",
        "strength": override.strength,
        "category": override.category or "Other",
        "default_morning": cint(override.default_morning or 0),
        "default_lunch": cint(override.default_lunch or 0),
        "default_evening": cint(override.default_evening or 0),
        "default_night": cint(override.default_night or 0),
        "default_days": cint(override.default_days or 5),
        "default_condition": override.default_condition or "After Food",
        "instructions": override.instructions,
        "description": override.description,
        "is_active": bool(override.is_active),
        "is_custom": True,
        "template_name": None,
        "source": "clinic_custom",
    }


def _parse_medicine_fields(kwargs):
    payload = {}
    for fieldname in [
        "medicine_name",
        "generic_name",
        "dosage_form",
        "strength",
        "category",
        "default_condition",
        "instructions",
        "description",
        "is_active",
    ]:
        if fieldname in kwargs:
            payload[fieldname] = kwargs.get(fieldname)

    for fieldname in DOSAGE_INT_FIELDS:
        if fieldname in kwargs:
            payload[fieldname] = cint(kwargs.get(fieldname))

    return payload


@frappe.whitelist(methods=["GET"])
def get_medicines(clinic=None, search=None, category=None, limit_start=0, limit_page_length=50):
    """Alias for UI parity with procedures/conditions."""
    return get_medicine_templates(
        clinic=clinic,
        search=search,
        category=category,
        limit_start=limit_start,
        limit_page_length=limit_page_length,
    )


@frappe.whitelist(methods=["GET"])
def get_medicine_templates(clinic=None, search=None, category=None, limit_start=0, limit_page_length=50):
    """
    Get medicines.

    If clinic is provided:
    - Returns merged global templates + clinic overrides + clinic custom medicines.
    If clinic is not provided:
    - Returns global active medicine templates only (legacy behavior).
    """
    try:
        if clinic:
            _validate_clinic(clinic)

            override_rows = frappe.get_all(
                "Medicine Clinic Override",
                filters={"clinic": clinic, "is_custom_medicine": 0},
                fields=[
                    "name",
                    "medicine_template",
                    "medicine_name",
                    "generic_name",
                    "dosage_form",
                    "strength",
                    "category",
                    "default_morning",
                    "default_lunch",
                    "default_evening",
                    "default_night",
                    "default_days",
                    "default_condition",
                    "instructions",
                    "description",
                    "is_active",
                ],
            )
            overrides = {row.medicine_template: row for row in override_rows}

            custom_rows = frappe.get_all(
                "Medicine Clinic Override",
                filters={"clinic": clinic, "is_custom_medicine": 1},
                fields=[
                    "name",
                    "medicine_name",
                    "generic_name",
                    "dosage_form",
                    "strength",
                    "category",
                    "default_morning",
                    "default_lunch",
                    "default_evening",
                    "default_night",
                    "default_days",
                    "default_condition",
                    "instructions",
                    "description",
                    "is_active",
                ],
            )

            template_filters = {"is_active": 1}
            if category and category != "all":
                template_filters["category"] = category

            template_rows = frappe.get_all(
                "Medicine Template",
                filters=template_filters,
                fields=[
                    "name",
                    "medicine_name",
                    "generic_name",
                    "dosage_form",
                    "strength",
                    "category",
                    "default_morning",
                    "default_lunch",
                    "default_evening",
                    "default_night",
                    "default_days",
                    "default_condition",
                    "instructions",
                    "description",
                ],
            )

            medicines = [_build_custom_row(row) for row in custom_rows]
            for template in template_rows:
                medicines.append(_build_template_or_override_row(template, overrides.get(template.name)))

            medicines = _apply_search(medicines, search)
            medicines.sort(key=lambda x: (x.get("medicine_name") or "").lower())

            return {
                "medicines": _paginate(medicines, limit_start, limit_page_length),
                "total_count": len(medicines),
            }

        filters = {"is_active": 1}
        if category and category != "all":
            filters["category"] = category

        template_rows = frappe.get_all(
            "Medicine Template",
            filters=filters,
            fields=[
                "name",
                "medicine_name",
                "generic_name",
                "dosage_form",
                "strength",
                "category",
                "default_morning",
                "default_lunch",
                "default_evening",
                "default_night",
                "default_days",
                "default_condition",
                "instructions",
                "description",
            ],
        )

        medicines = []
        for row in template_rows:
            medicines.append({
                "name": row.name,
                "medicine_name": row.medicine_name,
                "generic_name": row.generic_name,
                "dosage_form": row.dosage_form,
                "strength": row.strength,
                "category": row.category,
                "default_morning": cint(row.default_morning or 0),
                "default_lunch": cint(row.default_lunch or 0),
                "default_evening": cint(row.default_evening or 0),
                "default_night": cint(row.default_night or 0),
                "default_days": cint(row.default_days or 5),
                "default_condition": row.default_condition,
                "instructions": row.instructions,
                "description": row.description,
                "is_active": True,
                "is_custom": False,
                "template_name": row.name,
                "source": "template_default",
            })

        medicines = _apply_search(medicines, search)
        medicines.sort(key=lambda x: (x.get("medicine_name") or "").lower())

        return {
            "medicines": _paginate(medicines, limit_start, limit_page_length),
            "total_count": len(medicines),
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Medicines Error")
        frappe.throw(_("Error fetching medicines: {0}").format(str(e)))


@frappe.whitelist(methods=["GET"])
def search_medicines(query, limit=20, clinic=None):
    """Quick search for autocomplete."""
    try:
        if not query or len(query) < 2:
            return []

        result = get_medicine_templates(
            clinic=clinic,
            search=query,
            limit_start=0,
            limit_page_length=limit,
        )
        medicines = result.get("medicines", [])
        return [m for m in medicines if m.get("is_active", True)][:cint(limit)]

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Search Medicines Error")
        return []


@frappe.whitelist(methods=["POST"])
def create_custom_medicine(clinic, medicine_name, **kwargs):
    """Create a custom medicine for a specific clinic."""
    try:
        get_current_practitioner()
        _validate_clinic(clinic)

        if not medicine_name:
            return {"message": "Medicine name is required"}, 400

        existing = frappe.db.exists({
            "doctype": "Medicine Clinic Override",
            "clinic": clinic,
            "medicine_name": medicine_name,
            "is_custom_medicine": 1,
        })
        if existing:
            return {"message": f"Custom medicine '{medicine_name}' already exists for this clinic"}, 400

        payload = _parse_medicine_fields(kwargs)
        payload.update({
            "doctype": "Medicine Clinic Override",
            "clinic": clinic,
            "is_custom_medicine": 1,
            "medicine_name": medicine_name,
            "dosage_form": payload.get("dosage_form") or "Tablet",
            "category": payload.get("category") or "Other",
            "default_condition": payload.get("default_condition") or "After Food",
            "default_morning": payload.get("default_morning", 0),
            "default_lunch": payload.get("default_lunch", 0),
            "default_evening": payload.get("default_evening", 0),
            "default_night": payload.get("default_night", 0),
            "default_days": payload.get("default_days", 5),
            "is_active": cint(payload.get("is_active", 1)),
        })

        doc = frappe.get_doc(payload)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {"message": "Custom medicine created successfully", "medicine": _build_custom_row(doc)}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Create Custom Medicine Error")
        return {"message": str(e)}, 500


@frappe.whitelist(methods=["POST"])
def override_template_medicine(clinic, medicine_template, **kwargs):
    """Override a template medicine for a specific clinic."""
    try:
        get_current_practitioner()
        _validate_clinic(clinic)

        if not frappe.db.exists("Medicine Template", medicine_template):
            return {"message": "Invalid medicine template"}, 404

        existing = frappe.db.exists({
            "doctype": "Medicine Clinic Override",
            "clinic": clinic,
            "medicine_template": medicine_template,
            "is_custom_medicine": 0,
        })

        payload = _parse_medicine_fields(kwargs)
        payload["is_active"] = cint(payload.get("is_active", kwargs.get("is_active", 1)))

        if existing:
            doc = frappe.get_doc("Medicine Clinic Override", existing)
            for fieldname, value in payload.items():
                setattr(doc, fieldname, value)
            doc.save(ignore_permissions=True)
        else:
            doc_data = {
                "doctype": "Medicine Clinic Override",
                "clinic": clinic,
                "medicine_template": medicine_template,
                "is_custom_medicine": 0,
                "is_active": cint(kwargs.get("is_active", 1)),
            }
            doc_data.update(payload)
            doc = frappe.get_doc(doc_data)
            doc.insert(ignore_permissions=True)

        frappe.db.commit()
        return {"message": "Medicine override saved successfully"}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Override Template Medicine Error")
        return {"message": str(e)}, 500


@frappe.whitelist(methods=["POST"])
def update_custom_medicine(clinic, medicine_name, original_name=None, **kwargs):
    """Update a clinic custom medicine."""
    try:
        get_current_practitioner()
        _validate_clinic(clinic)

        lookup_name = original_name or medicine_name
        existing = frappe.db.exists({
            "doctype": "Medicine Clinic Override",
            "clinic": clinic,
            "medicine_name": lookup_name,
            "is_custom_medicine": 1,
        })
        if not existing:
            return {"message": "Custom medicine not found"}, 404

        doc = frappe.get_doc("Medicine Clinic Override", existing)
        payload = _parse_medicine_fields(kwargs)
        if "medicine_name" not in payload and medicine_name:
            payload["medicine_name"] = medicine_name

        for fieldname, value in payload.items():
            setattr(doc, fieldname, value)

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {"message": "Custom medicine updated successfully", "medicine": _build_custom_row(doc)}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Update Custom Medicine Error")
        return {"message": str(e)}, 500


@frappe.whitelist(methods=["POST", "DELETE"])
def delete_custom_medicine(clinic, medicine_name):
    """Delete a clinic custom medicine."""
    try:
        get_current_practitioner()
        _validate_clinic(clinic)

        existing = frappe.db.exists({
            "doctype": "Medicine Clinic Override",
            "clinic": clinic,
            "medicine_name": medicine_name,
            "is_custom_medicine": 1,
        })
        if not existing:
            return {"message": "Custom medicine not found"}, 404

        frappe.delete_doc("Medicine Clinic Override", existing, ignore_permissions=True)
        frappe.db.commit()
        return {"message": "Custom medicine deleted successfully"}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Delete Custom Medicine Error")
        return {"message": str(e)}, 500


@frappe.whitelist(methods=["POST"])
def create_medicine_template(**kwargs):
    """
    Legacy endpoint retained for compatibility.
    If clinic is passed, create clinic custom medicine.
    Otherwise create global medicine template.
    """
    try:
        clinic = kwargs.get("clinic")
        if clinic:
            custom_kwargs = dict(kwargs)
            medicine_name = custom_kwargs.pop("medicine_name", None)
            custom_kwargs.pop("clinic", None)
            return create_custom_medicine(clinic=clinic, medicine_name=medicine_name, **custom_kwargs)

        get_current_practitioner()

        medicine_name = kwargs.get("medicine_name")
        if not medicine_name:
            frappe.throw(_("Medicine name is required"))

        existing = frappe.db.exists("Medicine Template", {"medicine_name": medicine_name})
        if existing:
            frappe.throw(_("Medicine template with this name already exists"))

        doc = frappe.get_doc({
            "doctype": "Medicine Template",
            "medicine_name": medicine_name,
            "generic_name": kwargs.get("generic_name"),
            "dosage_form": kwargs.get("dosage_form", "Tablet"),
            "strength": kwargs.get("strength"),
            "category": kwargs.get("category", "Other"),
            "default_morning": cint(kwargs.get("default_morning", 0)),
            "default_lunch": cint(kwargs.get("default_lunch", 0)),
            "default_evening": cint(kwargs.get("default_evening", 0)),
            "default_night": cint(kwargs.get("default_night", 0)),
            "default_days": cint(kwargs.get("default_days", 5)),
            "default_condition": kwargs.get("default_condition", "After Food"),
            "instructions": kwargs.get("instructions"),
            "description": kwargs.get("description"),
            "is_active": 1,
        })

        doc.insert(ignore_permissions=True)

        return {
            "message": "Medicine template created successfully",
            "medicine_id": doc.name,
            "medicine_name": doc.medicine_name,
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Medicine Template Error")
        frappe.throw(_("Error creating medicine template: {0}").format(str(e)))


@frappe.whitelist(methods=["POST", "PUT"])
def update_medicine_template(medicine_id, **kwargs):
    """Update a global medicine template (legacy endpoint)."""
    try:
        get_current_practitioner()

        if not frappe.db.exists("Medicine Template", medicine_id):
            frappe.throw(_("Medicine template not found"))

        doc = frappe.get_doc("Medicine Template", medicine_id)
        for fieldname in [
            "medicine_name",
            "generic_name",
            "dosage_form",
            "strength",
            "category",
            "default_morning",
            "default_lunch",
            "default_evening",
            "default_night",
            "default_days",
            "default_condition",
            "instructions",
            "description",
            "is_active",
        ]:
            if fieldname in kwargs:
                setattr(doc, fieldname, kwargs[fieldname])

        doc.save(ignore_permissions=True)

        return {
            "message": "Medicine template updated successfully",
            "medicine_id": doc.name,
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Update Medicine Template Error")
        frappe.throw(_("Error updating medicine template: {0}").format(str(e)))


@frappe.whitelist(methods=["POST", "DELETE"])
def delete_medicine_template(medicine_id):
    """Delete a global medicine template (legacy endpoint)."""
    try:
        get_current_practitioner()

        if not frappe.db.exists("Medicine Template", medicine_id):
            frappe.throw(_("Medicine template not found"))

        frappe.delete_doc("Medicine Template", medicine_id, ignore_permissions=True)

        return {"message": "Medicine template deleted successfully"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Medicine Template Error")
        frappe.throw(_("Error deleting medicine template: {0}").format(str(e)))


@frappe.whitelist(methods=["GET"])
def get_medicine_categories():
    """Get list of medicine categories."""
    return [
        "Antibiotic",
        "Analgesic",
        "Anti-inflammatory",
        "Antifungal",
        "Antiviral",
        "Antiseptic",
        "Anesthetic",
        "Vitamin",
        "Mineral",
        "Antacid",
        "Antihistamine",
        "Steroid",
        "Muscle Relaxant",
        "Other",
    ]


@frappe.whitelist(methods=["GET"])
def get_dosage_conditions():
    """Get list of dosage conditions."""
    return [
        "After Food",
        "Before Food",
        "With Food",
        "Empty Stomach",
        "As Needed",
        "Bedtime",
    ]
