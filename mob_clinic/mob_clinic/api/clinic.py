import frappe
from typing import List, Optional, Union


def get_accessible_companies_for_practitioner(practitioner_name: Optional[str]) -> List[str]:
    """Return a list of company names accessible to the practitioner.

    - Reads `primary_company` from Healthcare Practitioner custom field.
    - If a child table `practitioner_companies` exists, includes those too.
    - If `practitioner_name` is falsy, returns an empty list.
    """
    if not practitioner_name:
        return []

    try:
        doc = frappe.get_doc("Healthcare Practitioner", practitioner_name)
    except frappe.DoesNotExistError:
        return []

    companies = []
    primary = doc.get("primary_company")
    if primary:
        companies.append(primary)

    # Optional child table for additional companies
    if hasattr(doc, "practitioner_companies") and doc.get("practitioner_companies"):
        for row in doc.get("practitioner_companies"):
            company = row.get("company") if isinstance(row, dict) else getattr(row, "company", None)
            if company and company not in companies:
                companies.append(company)

    return companies


def resolve_active_clinic(practitioner_name: Optional[str] = None, clinic_param: Optional[str] = None) -> Optional[str]:
    """Resolve the active clinic (Company name) in this order:

    1. Explicit `clinic_param` passed by caller
    2. `frappe.local.session['active_clinic']` if set
    3. Practitioner `primary_company` (if practitioner provided)
    4. None
    """
    # 1) explicit param takes precedence
    if clinic_param:
        return clinic_param

    # 2) session-scoped active clinic
    sess = getattr(frappe.local, "session", None) or getattr(frappe, "session", None)
    if sess:
        ac = sess.get("active_clinic")
        if ac:
            return ac

    # 3) fallback to practitioner's primary_company
    if practitioner_name:
        try:
            doc = frappe.get_doc("Healthcare Practitioner", practitioner_name)
            primary = doc.get("primary_company")
            if primary:
                return primary
        except Exception:
            pass

    return None


def validate_practitioner_access(practitioner_name: Optional[str], clinic: Optional[str]) -> bool:
    """Return True if practitioner has access to `clinic`.

    - If `practitioner_name` is falsy, we assume no practitioner-specific restriction.
    - If `clinic` is falsy, treat as allowed (no clinic-scoping requested).
    """
    if not practitioner_name or not clinic:
        return True

    accessible = get_accessible_companies_for_practitioner(practitioner_name)
    # If practitioner has no configured companies, deny by default (require explicit mapping in future)
    if not accessible:
        return False

    return clinic in accessible


def apply_clinic_filter(filters: Optional[Union[dict, list]], clinic: Optional[str], clinic_field: str = "company") -> Union[dict, list]:
    """Return modified filters that include company == clinic.

    Accepts `filters` as a dict or a list (frappe-style). If `clinic` is None, returns original filters.
    """
    if not clinic:
        return filters or {}

    if not filters:
        return {clinic_field: clinic}

    if isinstance(filters, dict):
        filters[clinic_field] = clinic
        return filters

    # list form: append a condition
    if isinstance(filters, list):
        filters.append([clinic_field, "=", clinic])
        return filters

    # fallback
    return {clinic_field: clinic}


def set_active_clinic_session(clinic: Optional[str]):
    """Set the active clinic in the current session.

    This function attempts to set `frappe.local.session['active_clinic']` where available.
    """
    if not clinic:
        return

    # Prefer frappe.local.session
    if hasattr(frappe, "local") and getattr(frappe.local, "session", None) is not None:
        frappe.local.session["active_clinic"] = clinic
        # Also set in session.data for persistent storage
        if hasattr(frappe.session, "data"):
            frappe.session.data["active_clinic"] = clinic
        return

    # Fallback to frappe.session dict if available
    sess = getattr(frappe, "session", None)
    if sess is not None:
        sess["active_clinic"] = clinic
