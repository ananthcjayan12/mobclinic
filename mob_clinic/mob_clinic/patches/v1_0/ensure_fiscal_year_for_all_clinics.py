"""
Ensure a fiscal year exists for a target date and is linked to all clinic companies.

This is intentionally kept in patches (not API) so it can be run via:
bench --site <site> execute \
  mob_clinic.mob_clinic.patches.v1_0.ensure_fiscal_year_for_all_clinics.ensure_fiscal_year_for_all_clinics \
  --kwargs "{'target_date':'2026-04-04'}"
"""

import frappe
from frappe import _
from frappe.utils import add_days, add_years, cstr, getdate, nowdate


def _active_fiscal_years():
	return frappe.get_all(
		"Fiscal Year",
		filters={"disabled": 0},
		fields=["name", "year_start_date", "year_end_date"],
		order_by="year_end_date asc",
	)


def _fiscal_years_covering(target_date):
	return frappe.get_all(
		"Fiscal Year",
		filters={
			"disabled": 0,
			"year_start_date": ["<=", target_date],
			"year_end_date": [">=", target_date],
		},
		fields=["name", "year_start_date", "year_end_date"],
		order_by="year_end_date asc",
	)


def _companies_without_group(include_disabled=False):
	filters = {"is_group": 0}
	return frappe.get_all("Company", filters=filters, pluck="name")


def _company_link_exists(fiscal_year_name, company):
	return frappe.db.exists(
		"Fiscal Year Company",
		{"parent": fiscal_year_name, "company": company},
	)


def _create_next_fiscal_year(current_fy_name):
	current_fy = frappe.get_doc("Fiscal Year", current_fy_name)
	new_fy = frappe.copy_doc(current_fy, ignore_no_copy=False)

	new_fy.year_start_date = add_days(current_fy.year_end_date, 1)
	new_fy.year_end_date = add_years(current_fy.year_end_date, 1)

	start_year = cstr(new_fy.year_start_date.year)
	end_year = cstr(new_fy.year_end_date.year)
	new_fy.year = start_year if start_year == end_year else f"{start_year}-{end_year}"
	new_fy.auto_created = 1
	new_fy.disabled = 0
	new_fy.insert(ignore_permissions=True)

	return new_fy.name


def _ensure_fiscal_year_for_date(target_date):
	covering = _fiscal_years_covering(target_date)
	if covering:
		return covering[-1].name, []

	active = _active_fiscal_years()
	if not active:
		frappe.throw(_("No active Fiscal Year exists. Create the first Fiscal Year manually first."))

	latest_name = active[-1].name
	created = []

	while True:
		latest_fy = frappe.get_doc("Fiscal Year", latest_name)
		if latest_fy.year_start_date <= target_date <= latest_fy.year_end_date:
			return latest_name, created

		if target_date > latest_fy.year_end_date:
			latest_name = _create_next_fiscal_year(latest_name)
			created.append(latest_name)
			continue

		frappe.throw(
			_(
				"Target date {0} is before the earliest active Fiscal Year. "
				"Create older Fiscal Year manually if needed."
			).format(target_date)
		)


def ensure_fiscal_year_for_all_clinics(target_date=None, set_default=1, include_disabled_companies=0):
	"""
	Create/ensure fiscal year for target date and link to all clinic companies.
	"""
	target_date = getdate(target_date) if target_date else getdate(nowdate())
	set_default = int(set_default)
	include_disabled_companies = int(include_disabled_companies)

	fiscal_year_name, created_fiscal_years = _ensure_fiscal_year_for_date(target_date)
	companies = _companies_without_group(include_disabled=bool(include_disabled_companies))

	linked_companies = []
	fy_doc = frappe.get_doc("Fiscal Year", fiscal_year_name)
	for company in companies:
		if not _company_link_exists(fiscal_year_name, company):
			fy_doc.append("companies", {"company": company})
			linked_companies.append(company)

	if linked_companies:
		fy_doc.save(ignore_permissions=True)

	if set_default:
		frappe.db.set_default("fiscal_year", fiscal_year_name)

	frappe.db.commit()

	return {
		"target_date": cstr(target_date),
		"fiscal_year": fiscal_year_name,
		"created_fiscal_years": created_fiscal_years,
		"linked_companies_count": len(linked_companies),
		"linked_companies": linked_companies,
		"total_companies_seen": len(companies),
		"set_default": bool(set_default),
	}


def execute():
	"""Patch entrypoint for migrate."""
	ensure_fiscal_year_for_all_clinics()
