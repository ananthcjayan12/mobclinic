import json
import secrets
from contextlib import contextmanager
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, flt, getdate, now_datetime, today

from mob_clinic.mob_clinic.api import dental_chart as dental_chart_api
from mob_clinic.mob_clinic.api import orthodontic as orthodontic_api
from mob_clinic.mob_clinic.api import patient as patient_api
from mob_clinic.mob_clinic.api import payment as payment_api
from mob_clinic.mob_clinic.api import prescription as prescription_api
from mob_clinic.mob_clinic.playwright_seed import (
    PLAYWRIGHT_NAMESPACE_FIELD,
    collect_namespaced_records,
    ensure_playwright_custom_fields,
    list_stale_namespaces,
    normalize_seed_namespace,
    set_seed_namespace,
    tag_documents,
)

from erpnext.setup.doctype.company.company import Company as ERPNextCompany
from healthcare.healthcare.doctype.patient_appointment import patient_appointment as patient_appointment_module
from healthcare.healthcare.doctype.patient_appointment.patient_appointment import (
    PatientAppointment as HealthcarePatientAppointment,
)

try:
    from frappe.utils.file_manager import save_file
except Exception:  # pragma: no cover - depends on Frappe version
    save_file = None

try:
    from india_compliance.gst_india.overrides import company as india_company_override
except Exception:  # pragma: no cover - optional app
    india_company_override = None


DEFAULT_ADMIN_PAGES = [
    "home",
    "appointments",
    "patients",
    "prescriptions",
    "consent_forms",
    "invoice",
    "financial_dashboard",
    "whatsapp-manager",
    "settings",
]

LIMITED_USER_PAGES = [
    "home",
    "appointments",
    "patients",
    "prescriptions",
    "consent_forms",
    "invoice",
]

CLEANUP_ORDER = [
    "WhatsApp Conversation Message",
    "WhatsApp Conversation",
    "WhatsApp Message Log",
    "File",
    "Orthodontic Commission Payout",
    "Orthodontic Ledger Entry",
    "Orthodontic Case",
    "Payment Entry",
    "Sales Invoice",
    "Patient Encounter",
    "Patient Appointment",
    "Dental Chart Procedure Timeline",
    "Dental Chart Condition History",
    "Dental Chart Procedure",
    "Dental Chart Condition",
    "Dental Chart",
    "Clinic Settings",
    "Clinic Consultant",
    "Patient",
    "Customer",
    "Healthcare Practitioner",
    "User",
    "Company",
    "Item",
]


def _parse_json_arg(value):
    if not value:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return value


def _short_suffix(seed_namespace: str) -> str:
    return (seed_namespace or "pw")[-6:].upper()


def _record(manifest, doctype, name):
    if not name:
        return
    records = manifest.setdefault("records", {})
    entries = records.setdefault(doctype, [])
    if name not in entries:
        entries.append(name)


def _tag_and_record(manifest, doctype, name, seed_namespace):
    if not name:
        return
    set_seed_namespace(doctype, name, seed_namespace)
    _record(manifest, doctype, name)


@contextmanager
def _as_user(user):
    current_user = frappe.session.user
    frappe.set_user(user)
    try:
        yield
    finally:
        frappe.set_user(current_user)


@contextmanager
def _temporary_method_override(target, attribute, replacement):
    original = getattr(target, attribute, None)
    setattr(target, attribute, replacement)
    try:
        yield
    finally:
        if original is None:
            delattr(target, attribute)
        else:
            setattr(target, attribute, original)


def _default_company():
    company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
        "Global Defaults", "default_company"
    )
    if not company:
        frappe.throw(_("A default company is required on this site for Playwright billing seeds"))
    return company


def _generated_email(role, seed_namespace):
    return f"playwright.{role}.{seed_namespace}@example.test"


def _numeric_token(value, length=4):
    normalized = "".join(
        ch if ch.isdigit() else str((ord(ch.lower()) - 87) % 10)
        for ch in (value or "").lower()
        if ch.isalnum()
    )
    if not normalized:
        normalized = "0" * length
    return normalized[-length:].rjust(length, "0")


def _ensure_role(role_name):
    if frappe.db.exists("Role", role_name):
        return

    frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(ignore_permissions=True)


def _create_user(manifest, email, password, first_name, last_name, seed_namespace):
    user = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "new_password": password,
            "user_type": "System User",
            "send_welcome_email": 0,
            "enabled": 1,
        }
    )
    user.insert(ignore_permissions=True)
    user.add_roles("Healthcare Practitioner")
    _tag_and_record(manifest, "User", user.name, seed_namespace)
    return user


def _append_weekday_schedule(practitioner):
    practitioner.set("clinic_working_hours", [])
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]:
        practitioner.append(
            "clinic_working_hours",
            {
                "day": day,
                "is_working_day": 1,
                "start_time": "09:00:00",
                "end_time": "18:00:00",
            },
        )


def _create_practitioner(
    manifest,
    *,
    user_id,
    first_name,
    last_name,
    practitioner_name,
    primary_company,
    accessible_companies,
    mobile_phone,
    is_clinic_admin,
    allowed_pages,
    seed_namespace,
):
    practitioner = frappe.get_doc(
        {
            "doctype": "Healthcare Practitioner",
            "first_name": first_name,
            "last_name": last_name,
            "practitioner_name": practitioner_name,
            "status": "Active",
            "gender": "Male",
            "user_id": user_id,
            "mobile_phone": mobile_phone,
            "mobile_app_enabled": 1,
            "app_user_id": user_id,
            "primary_company": primary_company,
            "accessible_companies_json": json.dumps(accessible_companies),
            "is_clinic_admin": 1 if is_clinic_admin else 0,
            "allowed_pages_json": json.dumps(allowed_pages),
            "clinic_description": f"{practitioner_name} seed for {seed_namespace}",
        }
    )
    _append_weekday_schedule(practitioner)
    practitioner.flags.ignore_mandatory = True
    practitioner.insert(ignore_permissions=True)
    _tag_and_record(manifest, "Healthcare Practitioner", practitioner.name, seed_namespace)
    return practitioner


def _create_auxiliary_practitioner(
    manifest, clinic_name, practitioner_name, mobile_phone, seed_namespace
):
    practitioner = frappe.get_doc(
        {
            "doctype": "Healthcare Practitioner",
            "first_name": practitioner_name.split()[0],
            "last_name": practitioner_name.split()[-1],
            "practitioner_name": practitioner_name,
            "status": "Active",
            "gender": "Male",
            "mobile_phone": mobile_phone,
            "mobile_app_enabled": 1,
            "primary_company": clinic_name,
        }
    )
    _append_weekday_schedule(practitioner)
    practitioner.flags.ignore_mandatory = True
    practitioner.insert(ignore_permissions=True)
    _tag_and_record(manifest, "Healthcare Practitioner", practitioner.name, seed_namespace)
    return practitioner


def _create_company(manifest, company_name, abbr, seed_namespace):
    company = frappe.get_doc(
        {
            "doctype": "Company",
            "company_name": company_name,
            "abbr": abbr,
            "default_currency": "INR",
            "country": "India",
            "is_group": 0,
            "website": f"https://{company_name.lower().replace(' ', '-')}.example.test",
            "phone_no": "+91-9000000000",
            "email": f"{abbr.lower()}@example.test",
            "company_description": f"Playwright clinic {company_name}",
        }
    )
    company.flags.ignore_mandatory = True
    no_company_side_effect = lambda *args, **kwargs: None
    with _temporary_method_override(
        ERPNextCompany, "set_mode_of_payment_account", no_company_side_effect
    ):
        if india_company_override:
            with _temporary_method_override(
                india_company_override, "make_company_fixtures", no_company_side_effect
            ), _temporary_method_override(
                india_company_override, "create_company_fixtures", no_company_side_effect
            ):
                company.insert(ignore_permissions=True)
        else:
            company.insert(ignore_permissions=True)
    _tag_and_record(manifest, "Company", company.name, seed_namespace)
    return company


def _save_svg_asset(manifest, seed_namespace, doctype, docname, filename, label):
    if not save_file:
        return None

    content = (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='320' height='120'>"
        f"<rect width='100%' height='100%' fill='#ffffff'/>"
        f"<text x='16' y='64' font-size='28' fill='#0f172a'>{label}</text>"
        f"</svg>"
    )
    file_doc = save_file(
        filename,
        content.encode("utf-8"),
        doctype,
        docname,
        is_private=0,
    )
    _tag_and_record(manifest, "File", file_doc.name, seed_namespace)
    return file_doc.file_url


def _create_clinic_settings(
    manifest,
    *,
    clinic_name,
    suffix,
    seed_namespace,
    allow_online_booking=0,
    whatsapp_enabled=0,
    consultant_practitioner=None,
):
    settings = frappe.get_doc({"doctype": "Clinic Settings", "clinic": clinic_name})
    settings.update(
        {
            "primary_color": "#0f766e",
            "secondary_color": "#f59e0b",
            "text_color": "#0f172a",
            "background_color": "#f8fafc",
            "font_family": "Lato",
            "invoice_header_text": f"DentCharts {suffix}",
            "invoice_footer_text": f"Seeded for Playwright {suffix}",
            "invoice_terms_conditions": "Payment due within 7 days.",
            "appointment_reminder_message": "Reminder: {patient_name} has an appointment tomorrow.",
            "payment_receipt_message": "Payment received for invoice {invoice_number}.",
            "prescription_message": "Prescription ready for {patient_name}.",
            "facebook_url": f"https://facebook.com/dentcharts-{suffix.lower()}",
            "instagram_url": f"https://instagram.com/dentcharts_{suffix.lower()}",
            "twitter_url": f"https://x.com/dentcharts_{suffix.lower()}",
            "google_maps_url": "https://maps.google.com/?q=DentCharts",
            "appointment_slot_duration": 30,
            "allow_online_booking": 1 if allow_online_booking else 0,
            "timezone": "Asia/Kolkata",
            "currency": "INR",
            "landing_page_tagline": f"Confident smiles, namespace {suffix}",
            "landing_page_stats_json": json.dumps(
                [
                    {"label": "Patients", "value": "1.2k+"},
                    {"label": "Years", "value": "12"},
                ]
            ),
            "landing_page_testimonials_json": json.dumps(
                [{"quote": f"Smooth care for namespace {suffix}", "author": "Playwright Patient"}]
            ),
            "landing_page_gallery_json": json.dumps([]),
            "whatsapp_enabled": 1 if whatsapp_enabled else 0,
            "whatsapp_phone_number_id": f"pnid-{suffix.lower()}",
            "whatsapp_business_account_id": f"waba-{suffix.lower()}",
            "whatsapp_appointment_template": "appointment_reminder",
            "whatsapp_review_template": "review_request",
            "whatsapp_prescription_template": "prescription_ready",
            "whatsapp_invoice_template": "invoice_ready",
            "invoice_template_id": "modern",
        }
    )
    settings.flags.ignore_mandatory = True
    settings.insert(ignore_permissions=True)
    _tag_and_record(manifest, "Clinic Settings", settings.name, seed_namespace)

    if consultant_practitioner:
        settings.append(
            "consultants",
            {
                "consultant_type": "Internal",
                "is_active": 1,
                "practitioner": consultant_practitioner.name,
                "consultant_name": consultant_practitioner.practitioner_name,
                "mobile": consultant_practitioner.mobile_phone,
                "commission_type": "Percentage",
                "commission_value": 10,
                PLAYWRIGHT_NAMESPACE_FIELD: seed_namespace,
            },
        )
        settings.append(
            "consultants",
            {
                "consultant_type": "External",
                "is_active": 1,
                "consultant_name": f"Referral Partner {suffix}",
                "mobile": f"+919999{_numeric_token(seed_namespace)}",
                "commission_type": "Fixed",
                "commission_value": 500,
                PLAYWRIGHT_NAMESPACE_FIELD: seed_namespace,
            },
        )
        settings.save(ignore_permissions=True)
        tag_documents(
            "Clinic Consultant",
            [row.name for row in settings.consultants if row.name],
            seed_namespace,
        )
        for row in settings.consultants:
            _record(manifest, "Clinic Consultant", row.name)

    logo_url = _save_svg_asset(
        manifest,
        seed_namespace,
        "Company",
        clinic_name,
        f"playwright-logo-{suffix.lower()}.svg",
        f"DentCharts {suffix}",
    )
    signature_url = _save_svg_asset(
        manifest,
        seed_namespace,
        "Clinic Settings",
        settings.name,
        f"playwright-signature-{suffix.lower()}.svg",
        f"Dr {suffix}",
    )
    seal_url = _save_svg_asset(
        manifest,
        seed_namespace,
        "Clinic Settings",
        settings.name,
        f"playwright-seal-{suffix.lower()}.svg",
        f"Seal {suffix}",
    )

    updates = {}
    if logo_url:
        updates["show_logo_on_invoice"] = 1
    if signature_url:
        updates["invoice_signature"] = signature_url
    if seal_url:
        updates["clinic_seal"] = seal_url
        updates["show_seal_on_prescription"] = 1
    if updates:
        frappe.db.set_value("Clinic Settings", settings.name, updates, update_modified=False)

    return settings


def _create_item(manifest, item_code, item_name, rate, seed_namespace):
    item = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_name,
            "item_group": "Services",
            "stock_uom": "Nos",
            "is_stock_item": 0,
            "is_sales_item": 1,
            "standard_rate": rate,
            "description": item_name,
            "gst_hsn_code": "999312",
        }
    )
    item.insert(ignore_permissions=True)
    _tag_and_record(manifest, "Item", item.name, seed_namespace)
    return item


def _create_patient(manifest, *, user_email, clinic, first_name, last_name, sex, mobile, email, seed_namespace):
    with _as_user(user_email):
        response = patient_api.create_patient(
            first_name=first_name,
            last_name=last_name,
            sex=sex,
            mobile=mobile,
            email=email,
            clinic=clinic,
            registration_date=today(),
        )
    patient_id = response.get("data", {}).get("patient_id")
    if not patient_id:
        patient_id = (
            frappe.db.get_value("Patient", {"email": email}, "name")
            or frappe.db.get_value("Patient", {"mobile": mobile}, "name")
        )
    if not patient_id:
        frappe.throw(_("Unable to resolve seeded patient record for {0}").format(email))
    _tag_and_record(manifest, "Patient", patient_id, seed_namespace)
    return patient_id


def _create_appointment(
    manifest,
    *,
    patient_id,
    patient_name,
    practitioner,
    company,
    appointment_date,
    appointment_time,
    status,
    notes,
    seed_namespace,
    extra_updates=None,
):
    appointment = frappe.get_doc(
        {
            "doctype": "Patient Appointment",
            "patient": patient_id,
            "patient_name": patient_name,
            "practitioner": practitioner.name,
            "practitioner_name": practitioner.practitioner_name,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "duration": 30,
            "status": status,
            "appointment_type": "Consultation",
            "appointment_for": "Practitioner",
            "company": company,
            "booked_via_app": 1,
            "app_booking_source": "Playwright",
            "chief_complaint": notes,
            "notes": notes,
        }
    )
    appointment.flags.ignore_mandatory = True
    appointment.flags.ignore_overlap_validation = True
    no_side_effect = lambda *args, **kwargs: None
    with _temporary_method_override(
        HealthcarePatientAppointment, "insert_calendar_event", no_side_effect
    ), _temporary_method_override(
        patient_appointment_module, "send_confirmation_msg", no_side_effect
    ):
        appointment.insert(ignore_permissions=True)
    _tag_and_record(manifest, "Patient Appointment", appointment.name, seed_namespace)
    if extra_updates:
        appointment.db_set(extra_updates)
    return appointment


def _create_invoice(
    manifest,
    *,
    user_email,
    patient_id,
    clinic,
    appointment_id,
    items,
    remarks,
    posting_date,
    due_date,
    seed_namespace,
):
    with _as_user(user_email):
        response = payment_api.create_invoice(
            patient_id=patient_id,
            items=json.dumps(items),
            posting_date=posting_date,
            due_date=due_date,
            appointment_reference=appointment_id,
            clinic=clinic,
            remarks=remarks,
        )
    invoice_id = response.get("invoice_id")
    customer_id = frappe.db.get_value("Sales Invoice", invoice_id, "customer")
    _tag_and_record(manifest, "Sales Invoice", invoice_id, seed_namespace)
    _tag_and_record(manifest, "Customer", customer_id, seed_namespace)
    return invoice_id


def _record_payment(
    manifest,
    *,
    user_email,
    invoice_id,
    amount,
    mode_of_payment,
    payment_date,
    seed_namespace,
):
    with _as_user(user_email):
        response = payment_api.update_payment(
            invoice_id=invoice_id,
            paid_amount=amount,
            mode_of_payment=mode_of_payment,
            payment_date=payment_date,
        )
    payment_id = response.get("payment_id")
    _tag_and_record(manifest, "Payment Entry", payment_id, seed_namespace)
    return payment_id


def _create_prescription(manifest, *, user_email, patient_id, clinic, suffix, seed_namespace):
    with _as_user(user_email):
        response = prescription_api.create_prescription(
            patient_id=patient_id,
            clinic=clinic,
            chief_complaint=f"Routine review {suffix}",
            diagnosis="Mild gingivitis",
            treatment_plan="Cleaning and follow-up in 6 months",
            medications=[
                {
                    "drug_name": f"Analgesic {suffix}",
                    "dosage": "BID",
                    "period": "5 Day",
                    "dosage_form": "Tablet",
                },
            ],
        )
    record_id = response.get("data", {}).get("record_id")
    _tag_and_record(manifest, "Patient Encounter", record_id, seed_namespace)
    return record_id


def _tag_dental_chart_tree(manifest, patient_id, seed_namespace):
    chart_name = frappe.db.get_value("Dental Chart", {"patient": patient_id}, "name")
    if not chart_name:
        return None

    _tag_and_record(manifest, "Dental Chart", chart_name, seed_namespace)
    chart = frappe.get_doc("Dental Chart", chart_name)

    condition_ids = []
    history_ids = []
    for condition in chart.conditions:
        condition_ids.append(condition.name)
        condition_doc = frappe.get_doc("Dental Chart Condition", condition.name)
        history_ids.extend([row.name for row in condition_doc.history if row.name])

    procedure_ids = []
    timeline_ids = []
    for procedure in chart.procedures:
        procedure_ids.append(procedure.name)
        procedure_doc = frappe.get_doc("Dental Chart Procedure", procedure.name)
        timeline_ids.extend([row.name for row in procedure_doc.timeline if row.name])

    tag_documents("Dental Chart Condition", condition_ids, seed_namespace)
    tag_documents("Dental Chart Procedure", procedure_ids, seed_namespace)
    tag_documents("Dental Chart Condition History", history_ids, seed_namespace)
    tag_documents("Dental Chart Procedure Timeline", timeline_ids, seed_namespace)

    for doctype, names in (
        ("Dental Chart Condition", condition_ids),
        ("Dental Chart Procedure", procedure_ids),
        ("Dental Chart Condition History", history_ids),
        ("Dental Chart Procedure Timeline", timeline_ids),
    ):
        for name in names:
            _record(manifest, doctype, name)

    return chart_name


def _seed_rich_clinical_data(manifest, *, user_email, patient_id, seed_namespace):
    with _as_user(user_email):
        dental_chart_api.add_condition(
            patient_id,
            [16, 17],
            {"type": "cavity", "severity": "Moderate", "notes": "Occlusal decay", "date": today()},
        )
        dental_chart_api.add_procedure(
            patient_id,
            [16],
            {"name": "Root Canal", "status": "in-progress", "notes": "Stage 2 of treatment", "date": today()},
        )

    _tag_dental_chart_tree(manifest, patient_id, seed_namespace)


def _tag_orthodontic_tree(manifest, patient_id, seed_namespace):
    case_id = frappe.db.get_value("Orthodontic Case", {"patient": patient_id}, "name")
    if not case_id:
        return None

    _tag_and_record(manifest, "Orthodontic Case", case_id, seed_namespace)

    ledger_rows = frappe.get_all(
        "Orthodontic Ledger Entry",
        filters={"orthodontic_case": case_id},
        fields=["name", "sales_invoice", "payment_entry"],
        ignore_permissions=True,
    )
    for row in ledger_rows:
        _tag_and_record(manifest, "Orthodontic Ledger Entry", row.name, seed_namespace)
        if row.sales_invoice:
            _tag_and_record(manifest, "Sales Invoice", row.sales_invoice, seed_namespace)
        if row.payment_entry:
            _tag_and_record(manifest, "Payment Entry", row.payment_entry, seed_namespace)

    payouts = frappe.get_all(
        "Orthodontic Commission Payout",
        filters={"orthodontic_case": case_id},
        pluck="name",
        ignore_permissions=True,
    )
    for payout_id in payouts:
        _tag_and_record(manifest, "Orthodontic Commission Payout", payout_id, seed_namespace)

    return case_id


def _create_whatsapp_shell(manifest, clinic_name, suffix, seed_namespace):
    phone_suffix = _numeric_token(seed_namespace)
    conversation = frappe.get_doc(
        {
            "doctype": "WhatsApp Conversation",
            "clinic": clinic_name,
            "wa_id": f"wa-{suffix.lower()}",
            "customer_name": f"WhatsApp Patient {suffix}",
            "customer_phone": f"+9198800{phone_suffix}",
            "last_message_preview": "Looking forward to tomorrow's appointment.",
            "last_message_at": now_datetime(),
            "last_message_direction": "Inbound",
            "last_message_status": "Read",
            "unread_count": 1,
            "is_session_active": 1,
        }
    )
    conversation.insert(ignore_permissions=True)
    _tag_and_record(manifest, "WhatsApp Conversation", conversation.name, seed_namespace)

    for idx, direction in enumerate(["Inbound", "Outbound"], start=1):
        message = frappe.get_doc(
            {
                "doctype": "WhatsApp Conversation Message",
                "conversation": conversation.name,
                "clinic": clinic_name,
                "direction": direction,
                "message_type": "text",
                "status": "Read" if direction == "Inbound" else "Sent",
                "message_timestamp": add_to_date(now_datetime(), minutes=-idx),
                "content": f"{direction} message {idx} for {suffix}",
                "sender_phone": conversation.customer_phone,
                "recipient_phone": conversation.customer_phone,
            }
        )
        message.insert(ignore_permissions=True)
        _tag_and_record(manifest, "WhatsApp Conversation Message", message.name, seed_namespace)

    for message_type, status in [
        ("Appointment Reminder", "Sent"),
        ("Invoice", "Delivered"),
        ("Prescription", "Read"),
    ]:
        log = frappe.get_doc(
            {
                "doctype": "WhatsApp Message Log",
                "clinic": clinic_name,
                "recipient_phone": conversation.customer_phone,
                "template_name": message_type.lower().replace(" ", "_"),
                "message_type": message_type,
                "status": status,
                "sent_at": now_datetime(),
                "reference_doctype": "WhatsApp Conversation",
                "reference_name": conversation.name,
            }
        )
        log.insert(ignore_permissions=True)
        _tag_and_record(manifest, "WhatsApp Message Log", log.name, seed_namespace)


def _serialize_manifest(manifest):
    return json.loads(json.dumps(manifest))


def _delete_record(doctype, name):
    if not frappe.db.exists(doctype, name):
        return

    meta = frappe.get_meta(doctype)
    if meta.istable:
        frappe.db.delete(doctype, {"name": name})
        return

    try:
        doc = frappe.get_doc(doctype, name)
        if getattr(doc, "docstatus", 0) == 1 and hasattr(doc, "cancel"):
            try:
                doc.cancel()
            except Exception:
                pass
    except Exception:
        doc = None

    if doctype == "Company" and india_company_override:
        no_side_effect = lambda *args, **kwargs: None
        with _temporary_method_override(
            india_company_override, "delete_gst_settings_for_company", no_side_effect
        ):
            frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
        return

    frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)


def _cleanup_namespace(seed_namespace):
    records = collect_namespaced_records(seed_namespace)
    deleted = {}

    for doctype in CLEANUP_ORDER:
        for name in records.get(doctype, []):
            try:
                _delete_record(doctype, name)
                deleted.setdefault(doctype, []).append(name)
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    f"Playwright cleanup failed for {doctype} {name}",
                )
        frappe.db.commit()

    leftovers = collect_namespaced_records(seed_namespace)
    return {"deleted": deleted, "leftovers": leftovers}


def _assert_harness_enabled():
    if not frappe.conf.get("developer_mode"):
        frappe.throw(_("Playwright harness is only available in developer mode"), frappe.PermissionError)
    if frappe.session.user == "Guest":
        frappe.set_user("Administrator")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def prepare_run(seed_namespace_prefix="pw"):
    _assert_harness_enabled()
    ensure_playwright_custom_fields()

    prefix = normalize_seed_namespace(seed_namespace_prefix) or "pw"
    run_id = secrets.token_hex(8)
    timestamp = now_datetime().strftime("%Y%m%d%H%M%S")
    seed_namespace = f"{prefix}-{timestamp}-{run_id[:6]}"

    return {
        "message": "Playwright run prepared",
        "data": {
            "run_id": run_id,
            "seed_namespace": seed_namespace,
            "seed_suffix": _short_suffix(seed_namespace),
            "prepared_at": str(now_datetime()),
        },
    }


@frappe.whitelist(allow_guest=True, methods=["POST"])
def cleanup_stale_runs(seed_namespace_prefix="pw", ttl_hours=24):
    _assert_harness_enabled()
    ensure_playwright_custom_fields()

    cutoff = add_to_date(now_datetime(), hours=-int(ttl_hours))
    namespaces = list_stale_namespaces(seed_namespace_prefix, cutoff)
    cleaned = []
    for namespace in namespaces:
        result = _cleanup_namespace(namespace)
        cleaned.append(
            {
                "seed_namespace": namespace,
                "leftovers": result["leftovers"],
            }
        )

    return {
        "message": "Stale Playwright runs cleaned",
        "data": {
            "ttl_hours": int(ttl_hours),
            "cleaned_runs": cleaned,
        },
    }


@frappe.whitelist(allow_guest=True, methods=["POST"])
def seed_run(
    run_id,
    seed_namespace,
    admin_email=None,
    admin_password=None,
    limited_user_email=None,
    limited_user_password=None,
):
    _assert_harness_enabled()
    ensure_playwright_custom_fields()

    namespace = normalize_seed_namespace(seed_namespace)
    if not namespace:
        frappe.throw(_("A valid seed_namespace is required"))

    suffix = _short_suffix(namespace)
    phone_suffix = _numeric_token(namespace)
    manifest = {
        "run_id": run_id,
        "seed_namespace": namespace,
        "seed_suffix": suffix,
        "auth": {},
        "clinics": {},
        "patients": {},
        "appointments": {},
        "invoices": {},
        "payments": {},
        "prescriptions": {},
        "orthodontic": {},
        "records": {},
    }

    _cleanup_namespace(namespace)

    default_company = _default_company()
    secondary_company_name = f"PW Admin Clinic {suffix}"
    public_company_name = f"PW Public Clinic {suffix}"

    secondary_company = _create_company(manifest, secondary_company_name, f"PA{suffix[-2:]}", namespace)
    public_company = _create_company(manifest, public_company_name, f"PP{suffix[-2:]}", namespace)

    admin_email = admin_email or _generated_email("admin", namespace)
    limited_user_email = limited_user_email or _generated_email("limited", namespace)
    admin_password = admin_password or "Playwright123!"
    limited_user_password = limited_user_password or "Playwright123!"

    _ensure_role("Healthcare Practitioner")

    admin_user = _create_user(
        manifest,
        admin_email,
        admin_password,
        "Playwright",
        f"Admin {suffix}",
        namespace,
    )
    limited_user = _create_user(
        manifest,
        limited_user_email,
        limited_user_password,
        "Playwright",
        f"Limited {suffix}",
        namespace,
    )

    admin_practitioner = _create_practitioner(
        manifest,
        user_id=admin_user.name,
        first_name="Playwright",
        last_name=f"Admin {suffix}",
        practitioner_name=f"Playwright Admin {suffix}",
        primary_company=default_company,
        accessible_companies=[default_company, secondary_company.name, public_company.name],
        mobile_phone=f"+9198100{phone_suffix}",
        is_clinic_admin=True,
        allowed_pages=DEFAULT_ADMIN_PAGES,
        seed_namespace=namespace,
    )
    limited_practitioner = _create_practitioner(
        manifest,
        user_id=limited_user.name,
        first_name="Playwright",
        last_name=f"Limited {suffix}",
        practitioner_name=f"Playwright Limited {suffix}",
        primary_company=default_company,
        accessible_companies=[default_company],
        mobile_phone=f"+9198200{phone_suffix}",
        is_clinic_admin=False,
        allowed_pages=LIMITED_USER_PAGES,
        seed_namespace=namespace,
    )

    secondary_practitioner = _create_auxiliary_practitioner(
        manifest,
        secondary_company.name,
        f"Secondary Doctor {suffix}",
        f"+9198300{phone_suffix}",
        namespace,
    )
    public_practitioner = _create_auxiliary_practitioner(
        manifest,
        public_company.name,
        f"Public Doctor {suffix}",
        f"+9198400{phone_suffix}",
        namespace,
    )

    _create_clinic_settings(
        manifest,
        clinic_name=secondary_company.name,
        suffix=suffix,
        seed_namespace=namespace,
        allow_online_booking=0,
        whatsapp_enabled=1,
        consultant_practitioner=secondary_practitioner,
    )
    _create_clinic_settings(
        manifest,
        clinic_name=public_company.name,
        suffix=suffix,
        seed_namespace=namespace,
        allow_online_booking=1,
        whatsapp_enabled=0,
        consultant_practitioner=public_practitioner,
    )

    item_consult = _create_item(manifest, f"PW-CONS-{suffix}", f"Consultation {suffix}", 800, namespace)
    item_cleaning = _create_item(manifest, f"PW-CLN-{suffix}", f"Cleaning {suffix}", 1500, namespace)
    item_braces = _create_item(manifest, f"PW-ORTHO-{suffix}", f"Ortho Plan {suffix}", 5000, namespace)

    patients = {
        "empty_new": _create_patient(
            manifest,
            user_email=admin_email,
            clinic=default_company,
            first_name="Playwright Empty",
            last_name=suffix,
            sex="Male",
            mobile=f"+9198500{phone_suffix}",
            email=f"patient.empty.{namespace}@example.test",
            seed_namespace=namespace,
        ),
        "rich_clinical": _create_patient(
            manifest,
            user_email=admin_email,
            clinic=default_company,
            first_name="Playwright Rich",
            last_name=suffix,
            sex="Female",
            mobile=f"+9198600{phone_suffix}",
            email=f"patient.rich.{namespace}@example.test",
            seed_namespace=namespace,
        ),
        "billing_heavy": _create_patient(
            manifest,
            user_email=admin_email,
            clinic=default_company,
            first_name="Playwright Billing",
            last_name=suffix,
            sex="Male",
            mobile=f"+9198700{phone_suffix}",
            email=f"patient.billing.{namespace}@example.test",
            seed_namespace=namespace,
        ),
        "orthodontic": _create_patient(
            manifest,
            user_email=admin_email,
            clinic=default_company,
            first_name="Playwright Ortho",
            last_name=suffix,
            sex="Female",
            mobile=f"+9198800{phone_suffix}",
            email=f"patient.ortho.{namespace}@example.test",
            seed_namespace=namespace,
        ),
    }
    manifest["patients"] = patients

    patient_names = {
        key: frappe.db.get_value("Patient", patient_id, "patient_name")
        for key, patient_id in patients.items()
    }

    appointment_specs = {
        "scheduled": ("empty_new", "Scheduled", "Initial consult scheduled", add_days(today(), 1), "09:00:00"),
        "confirmed": ("empty_new", "Confirmed", "Confirmed recall visit", add_days(today(), 2), "10:00:00"),
        "waiting": ("rich_clinical", "Waiting", "Patient is in queue", today(), "11:00:00"),
        "in_progress": ("rich_clinical", "In Progress", "Procedure underway", today(), "12:00:00"),
        "to_be_invoiced": ("billing_heavy", "To Be Invoiced", "Ready for billing handoff", today(), "13:00:00"),
        "pending_payment": ("billing_heavy", "Pending Payment", "Invoice raised and awaiting payment", today(), "14:00:00"),
        "files_to_be_uploaded": ("rich_clinical", "Files To Be Uploaded", "Needs x-rays upload", today(), "15:00:00"),
        "completed": ("rich_clinical", "Completed", "Completed and reviewed", add_days(today(), -1), "16:00:00"),
        "cancelled": ("empty_new", "Cancelled", "Cancelled by clinic", add_days(today(), -1), "17:00:00"),
    }

    for key, (patient_key, status, notes, date_value, time_value) in appointment_specs.items():
        appointment = _create_appointment(
            manifest,
            patient_id=patients[patient_key],
            patient_name=patient_names[patient_key],
            practitioner=admin_practitioner,
            company=default_company,
            appointment_date=getdate(date_value),
            appointment_time=time_value,
            status=status,
            notes=notes,
            seed_namespace=namespace,
            extra_updates={"review_requested": 1} if key == "completed" else None,
        )
        manifest["appointments"][key] = appointment.name

    pending_invoice_id = _create_invoice(
        manifest,
        user_email=admin_email,
        patient_id=patients["billing_heavy"],
        clinic=default_company,
        appointment_id=manifest["appointments"]["pending_payment"],
        items=[
            {"item_code": item_consult.item_code, "qty": 1, "rate": 800, "description": item_consult.item_name},
            {"item_code": item_cleaning.item_code, "qty": 1, "rate": 1500, "description": item_cleaning.item_name},
        ],
        remarks=f"Pending payment seed {suffix}",
        posting_date=today(),
        due_date=add_days(today(), 7),
        seed_namespace=namespace,
    )
    paid_invoice_id = _create_invoice(
        manifest,
        user_email=admin_email,
        patient_id=patients["rich_clinical"],
        clinic=default_company,
        appointment_id=manifest["appointments"]["completed"],
        items=[
            {"item_code": item_cleaning.item_code, "qty": 1, "rate": 1500, "description": item_cleaning.item_name},
        ],
        remarks=f"Paid seed invoice {suffix}",
        posting_date=add_days(today(), -1),
        due_date=add_days(today(), 5),
        seed_namespace=namespace,
    )
    heavy_invoice_id = _create_invoice(
        manifest,
        user_email=admin_email,
        patient_id=patients["billing_heavy"],
        clinic=default_company,
        appointment_id=None,
        items=[
            {"item_code": item_braces.item_code, "qty": 1, "rate": 5000, "description": item_braces.item_name},
        ],
        remarks=f"High balance invoice {suffix}",
        posting_date=add_days(today(), -3),
        due_date=add_days(today(), 10),
        seed_namespace=namespace,
    )

    pending_payment_id = _record_payment(
        manifest,
        user_email=admin_email,
        invoice_id=paid_invoice_id,
        amount=1500,
        mode_of_payment="Cash",
        payment_date=add_days(today(), -1),
        seed_namespace=namespace,
    )

    manifest["invoices"] = {
        "pending_payment": pending_invoice_id,
        "paid": paid_invoice_id,
        "billing_heavy": heavy_invoice_id,
    }
    manifest["payments"] = {"paid_invoice_receipt": pending_payment_id}

    frappe.db.set_value(
        "Patient Appointment",
        manifest["appointments"]["pending_payment"],
        {
            "invoice_id": pending_invoice_id,
            "invoice_status": "Unpaid",
            "invoiced": 1,
        },
        update_modified=False,
    )
    frappe.db.set_value(
        "Patient Appointment",
        manifest["appointments"]["completed"],
        {
            "invoice_id": paid_invoice_id,
            "invoice_status": "Paid",
            "invoiced": 1,
            "paid_amount": 1500,
        },
        update_modified=False,
    )

    manifest["prescriptions"]["rich_clinical"] = _create_prescription(
        manifest,
        user_email=admin_email,
        patient_id=patients["rich_clinical"],
        clinic=default_company,
        suffix=suffix,
        seed_namespace=namespace,
    )
    _seed_rich_clinical_data(
        manifest,
        user_email=admin_email,
        patient_id=patients["rich_clinical"],
        seed_namespace=namespace,
    )

    with _as_user(admin_email):
        orthodontic_api.create_orthodontic_case(
            patient_id=patients["orthodontic"],
            practitioner_id=admin_practitioner.name,
            package_fee=5000,
            advance_paid=1000,
            advance_payment_mode="Cash",
            case_type="Fixed Braces",
            clinic=default_company,
            notes=f"Orthodontic seed {suffix}",
        )
    manifest["orthodontic"]["case_id"] = _tag_orthodontic_tree(
        manifest,
        patients["orthodontic"],
        namespace,
    )

    _create_whatsapp_shell(manifest, secondary_company.name, suffix, namespace)

    manifest["auth"] = {
        "clinic_admin": {
            "email": admin_email,
            "password": admin_password,
            "practitioner_id": admin_practitioner.name,
        },
        "limited_practitioner": {
            "email": limited_user_email,
            "password": limited_user_password,
            "practitioner_id": limited_practitioner.name,
        },
    }
    manifest["clinics"] = {
        "primary": default_company,
        "secondary": secondary_company.name,
        "public_booking": public_company.name,
        "public_booking_path": f"/public/clinic/{quote(public_company.name, safe='')}",
    }

    frappe.db.commit()
    return {
        "message": "Playwright run seeded",
        "data": _serialize_manifest(manifest),
    }


@frappe.whitelist(allow_guest=True, methods=["POST"])
def cleanup_run(manifest=None, seed_namespace=None):
    _assert_harness_enabled()
    ensure_playwright_custom_fields()

    parsed_manifest = _parse_json_arg(manifest) or {}
    namespace = normalize_seed_namespace(seed_namespace or parsed_manifest.get("seed_namespace"))
    if not namespace:
        frappe.throw(_("A valid seed_namespace is required for cleanup"))

    result = _cleanup_namespace(namespace)
    return {
        "message": "Playwright run cleaned",
        "data": {
            "seed_namespace": namespace,
            "deleted": result["deleted"],
            "leftovers": result["leftovers"],
        },
    }


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def verify_run_cleanup(seed_namespace):
    _assert_harness_enabled()
    ensure_playwright_custom_fields()

    namespace = normalize_seed_namespace(seed_namespace)
    leftovers = collect_namespaced_records(namespace)
    if leftovers:
        frappe.local.response["http_status_code"] = 409
        return {
            "exc_type": "ValidationError",
            "message": "Namespaced Playwright data still exists after cleanup",
            "data": {"seed_namespace": namespace, "leftovers": leftovers},
        }

    return {
        "message": "Playwright namespace is clean",
        "data": {"seed_namespace": namespace, "leftovers": {}},
    }
