import json
from typing import List, Optional, Union

import frappe


def _parse_company_list(value) -> List[str]:
    if not value:
        return []

    parsed = value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except Exception:
            parsed = [item.strip() for item in stripped.split(",") if item.strip()]

    if not isinstance(parsed, (list, tuple)):
        return []

    companies: List[str] = []
    seen = set()
    for item in parsed:
        if not isinstance(item, str):
            continue
        company = item.strip()
        if company and company not in seen:
            seen.add(company)
            companies.append(company)

    return companies


def get_accessible_companies_for_practitioner(practitioner_name: Optional[str]) -> List[str]:
    """Return a list of company names accessible to the practitioner.

    - Reads `primary_company` from Healthcare Practitioner custom field.
    - Reads optional `accessible_companies_json` when present.
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

    # Optional JSON field for multi-clinic access without a child table.
    extra_companies = _parse_company_list(getattr(doc, "accessible_companies_json", None))
    for company in extra_companies:
        if company not in companies:
            companies.append(company)

    # Optional child table for additional companies
    if hasattr(doc, "practitioner_companies") and doc.get("practitioner_companies"):
        for row in doc.get("practitioner_companies"):
            company = row.get("company") if isinstance(row, dict) else getattr(row, "company", None)
            if company and company not in companies:
                companies.append(company)

    return companies


def resolve_active_clinic(practitioner_name: Optional[str] = None, clinic_param: Optional[str] = None, ignore_session: bool = False) -> Optional[str]:
    """Resolve the active clinic (Company name) in this order:

    1. Explicit `clinic_param` passed by caller
    2. `frappe.local.session['active_clinic']` if set (unless ignore_session=True)
    3. Practitioner `primary_company` (if practitioner provided)
    4. None
    
    Args:
        practitioner_name: Healthcare Practitioner name
        clinic_param: Explicitly passed clinic/company name
        ignore_session: If True, skip reading from session (useful during login)
    """
    # 1) explicit param takes precedence
    if clinic_param:
        return clinic_param

    # 2) session-scoped active clinic (skip if ignore_session=True)
    if not ignore_session:
        sess = getattr(frappe.local, "session", None) or getattr(frappe, "session", None)
        if sess:
            # Handle both dict and object access patterns
            ac = None
            if isinstance(sess, dict):
                ac = sess.get("data", {}).get("active_clinic") or sess.get("active_clinic")
            else:
                session_data = getattr(sess, "data", {})
                if isinstance(session_data, dict):
                    ac = session_data.get("active_clinic")
                else:
                    ac = getattr(sess, "active_clinic", None)
            
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
    Also persists to database for session continuity.
    """
    if not clinic:
        return

    # Set in frappe.local.session.data (in-memory session data)
    if hasattr(frappe, "local") and hasattr(frappe.local, "session"):
        if isinstance(frappe.local.session, dict):
            frappe.local.session["active_clinic"] = clinic
            if "data" not in frappe.local.session:
                frappe.local.session["data"] = {}
            frappe.local.session["data"]["active_clinic"] = clinic
        else:
            frappe.local.session.active_clinic = clinic
            if not hasattr(frappe.local.session, "data") or frappe.local.session.data is None:
                frappe.local.session.data = {}
            frappe.local.session.data["active_clinic"] = clinic
    
    # Also persist to Sessions table in database
    try:
        if hasattr(frappe, "session") and hasattr(frappe.session, "sid"):
            sid = frappe.session.sid
            if sid and frappe.db.exists("Sessions", sid):
                session_data = frappe.db.get_value("Sessions", sid, "data")
                if session_data:
                    import json
                    data_dict = json.loads(session_data) if isinstance(session_data, str) else session_data
                    data_dict["active_clinic"] = clinic
                    frappe.db.set_value("Sessions", sid, "data", json.dumps(data_dict), update_modified=False)
                    frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Error persisting active_clinic to session: {str(e)}")
