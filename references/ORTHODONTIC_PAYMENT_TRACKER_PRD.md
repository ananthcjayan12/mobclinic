# Orthodontic Payment Tracker PRD

## Document Info
- Product: Mobile Clinic / Dental SaaS
- Feature: Orthodontic Treatment Payment Tracking
- Target Users: Front desk staff, dentists, clinic admins
- Primary Goal: Replace the paper orthodontic appointment/payment card with a simple digital workflow tied to patient, appointment, and payment records

## 1. Executive Summary
Orthodontic patients typically follow a long treatment journey with repeated visits and installment-based payments. Today, many clinics track this on a paper appointment card with columns for:
- Date
- Next appointment
- Payment
- Balance

For many clinics, there is one more critical finance requirement:
- commission payable to the visiting orthodontist

The product opportunity is to digitize that exact mental model without forcing staff into a generic invoice-heavy workflow.

This feature should help the clinic answer, in under 10 seconds:
1. What is the total ortho package value?
2. How much has the patient paid?
3. What is the current balance?
4. When is the next orthodontic visit?
5. What happened on the last visit?
6. How much commission is accrued, paid, and pending for the orthodontist?

## 2. Problem Statement
Current clinic workflows for orthodontic patients are difficult because:
- Payment tracking is spread across multiple invoices and receipts
- Staff manually calculate running balance
- Next appointment tracking is separate from payment tracking
- Doctors cannot quickly review treatment-payment continuity
- Front desk staff rely on paper booklets that can be lost, damaged, or incomplete
- Commission payable to the orthodontist is tracked outside the patient journey or calculated manually later

## 3. Product Vision
Build an "Orthodontic Case Payment Tracker" that combines:
- treatment package setup
- recurring visit history
- payment collection
- running balance
- next appointment planning
- orthodontist commission accrual and payout visibility

The design principle should be:

`Patient -> Orthodontic Case -> Visit/Payment Ledger`

not:

`Patient -> Many separate invoices -> manual tracking`

## 4. Success Metrics
- Time to record an orthodontic payment under 1 minute
- 90%+ of orthodontic visits logged on the same day
- Reduction in manual paper tracking usage
- Faster front desk answer time for balance and next appointment queries
- Increased clarity for doctors reviewing active ortho cases
- Zero or near-zero manual commission calculator usage at month end
- Admin can reconcile orthodontist payout payable vs paid in under 5 minutes

## 5. User Personas

### Front Desk Staff
- Needs the fastest possible workflow
- Wants one simple screen to update visit, payment, and next appointment together
- Needs printable output when required

### Treating Doctor
- Wants quick summary of package, balance, and visit continuity
- Needs treatment notes and payment regularity in one place

### Clinic Admin / Owner
- Wants active case count, outstanding balance, and monthly collections
- Needs ability to edit package value, correct mistakes, and review all cases
- Needs visibility into orthodontist commission payable, paid out, and pending
- Needs a clean way to record commission already paid to the orthodontist, not just calculate what is owed

## 6. Core Jobs To Be Done
### Front Desk
- Start a new ortho case
- Record today's visit
- Record today's payment
- Book next appointment
- Print or share treatment/payment history

### Doctor
- Review last visit and upcoming visit
- See if the patient is regular with payments
- View total collected vs balance

### Admin
- Audit orthodontic revenue
- Track overdue balances
- Identify inactive or overdue cases
- Track orthodontist commission liability and payout status

## 7. Scope Definition

### V1 Must Have
- Orthodontic Case record
- Running payment ledger
- Case summary on patient page
- Visit + payment + next appointment modal
- Running balance calculation
- Optional linked invoice/receipt
- Orthodontist commission tracking aligned with invoice consultant logic
- Printable card view

### V2 Should Have
- Reminder automation
- Ortho dashboard and reports
- Overdue/no-visit indicators
- Better receipt/WhatsApp flows

### V3 Could Have
- Stage-based packages
- Milestone tracking
- Multi-case support if ever needed
- Advanced analytics

## 8. Functional Requirements

### 8.1 Orthodontic Case Creation
System should allow staff to create one active orthodontic case per patient.

Case fields:
- Patient
- Treating doctor
- Orthodontist consultant link
- Case type
- Start date
- Estimated duration
- Package amount
- Discount amount or percentage
- Net case fee
- Advance paid
- Current balance
- Default visit interval
- Status
- Notes
- Consultant ID
- Consultant name
- Consultant type
- Consultant practitioner
- Commission model
- Commission type
- Commission value
- Commission basis
- Total commission accrued
- Total commission paid
- Pending commission

Business rules:
- Only one active ortho case per patient by default
- Advance paid should reduce opening balance
- Net case fee = package fee - discount
- Commission should be configurable at case level
- Commission should follow the same commercial language as existing invoice consultant commission where possible
- Commission setup should point to the orthodontist/consultant master where available so reports stay consistent with invoice reports
- Case should store consultant identity snapshot fields so the commercial setup remains readable even if the linked consultant master changes later

Recommended commission options:
- Commission model:
  - `None`
  - `Percentage`
  - `Fixed per payment`
  - `Fixed per case`
- Commission basis:
  - `On collected amount`
  - `On net case value`

Recommendation:
- V1 should support `Percentage on collected amount` first, because that matches the real installment workflow and is easiest to audit

### 8.2 Ortho Ledger Entry
Every ortho visit should create a ledger entry with:
- Visit date
- Next appointment date
- Payment collected today
- Balance after payment
- Payment mode
- Notes / treatment done
- Linked invoice or receipt
- Created by
- Consultant ID
- Consultant name
- Consultant practitioner
- Commission snapshot for this entry
- Commission payout status
- Commission payout reference
- Commission paid amount

Business rules:
- Balance should auto-calculate
- Zero-payment visits should still be allowed
- Negative balances should not be allowed
- Overpayment should either:
  - be blocked, or
  - be captured as advance credit if enabled by admin
- Each payment-bearing ledger entry should store commission snapshot values so later case-rule edits do not rewrite historical payouts
- If an invoice is created, the ledger entry should store or map the same consultant snapshot fields used on invoice items:
  - `consultant_id`
  - `consultant_name`
  - `consultant_type`
  - `consultant_practitioner`
  - `consultant_commission_type`
  - `consultant_commission_value`
  - `consultant_commission_amount`
  - `consultant_commission_source`
- Commission paid amount may be lower than commission accrued amount because partial payout should be supported

### 8.3 Patient Summary View
Patient page should show an orthodontic summary widget with:
- Case status
- Start date
- Total package fee
- Total paid
- Balance
- Last visit
- Next appointment
- Last payment date

Admin/finance-only metrics:
- Commission accrued
- Commission paid
- Commission pending

### 8.4 Visit Workflow
At every ortho follow-up, the staff should be able to:
1. Open patient
2. Click `Add Visit`
3. Enter notes
4. Enter amount paid today
5. Choose next appointment
6. Save

Save action should:
- create ledger row
- update case totals
- update next appointment
- optionally create receipt/invoice
- calculate commission for that payment entry
- update pending commission balance

### 8.5 Commission Tracking and Payout Workflow
The system should support the full orthodontist commission lifecycle in the ortho module, similar to invoice consultant commission reporting.

Workflow:
1. Configure the orthodontist consultant details at case level
2. Accrue commission automatically whenever an eligible ortho payment is recorded
3. Show running commission totals on the case, ledger, and dashboard
4. Allow admin to mark commission as fully or partially paid
5. Preserve payout history with date, amount, method, and reference

Minimum payout actions:
- `Mark Commission Paid`
- `Mark Partial Commission Paid`
- `View Payout History`

Payout fields:
- Payout date
- Paid amount
- Payment mode
- Reference number
- Notes
- Paid by

Business rules:
- Only admin or permitted finance users can mark commission payout
- Paid commission cannot exceed pending commission
- Partial payout must reduce only the pending portion and remain auditable
- Reversals or corrections must create an audit trail, not silently overwrite payout history

### 8.6 Print Workflow
System should support a print-friendly "Ortho Card" layout that mirrors the paper booklet:
- Header with clinic details
- Patient details
- Table with Date, Next Appointment, Payment, Balance, Notes

## 9. Screen-by-Screen UI Plan

## 9.1 Patient Page: Orthodontic Summary Card
Location:
- Patient details page, near payments/history

Contents:
- Status badge
- Total fee
- Paid till date
- Balance
- Next appointment
- Last visit

Admin-only commercial strip:
- Commission model
- Commission accrued
- Commission paid
- Commission pending

Primary actions:
- `Start Case` or `Edit Case`
- `Add Visit`
- `Collect Payment`
- `View Ledger`
- `Print Card`

Admin-only finance actions:
- `Mark Commission Paid`
- `View Payout History`

UX notes:
- Summary must be visible without entering the finance module
- If no active case exists, show a clean empty state with `Start Orthodontic Case`

## 9.2 Create/Edit Orthodontic Case Modal
Fields:
- Doctor
- Case type
- Start date
- Estimated duration/months
- Package fee
- Discount
- Advance paid
- Default follow-up interval
- Notes

Admin/commercial fields:
- Commission model
- Commission type
- Commission value
- Commission basis

Derived values shown live:
- Net case fee
- Opening balance
- Estimated commission logic summary

Buttons:
- `Save Case`
- `Save and Add First Visit`

UX notes:
- Keep form short
- Use section grouping:
  - Treatment details
  - Commercial details
  - Scheduling defaults

## 9.3 Add Visit / Collect Payment Modal
This should be the primary day-to-day workflow screen.

Fields:
- Visit date
- Procedure/notes
- Payment collected today
- Payment mode
- Receipt needed toggle
- Next appointment date
- Internal note

Admin or permitted user fields:
- Commission override toggle
- Commission type
- Commission value
- Commission note

Read-only helper info:
- Case total
- Total paid till now
- Current balance before entry
- Projected balance after save
- Commission for this payment
- Total pending commission

Buttons:
- `Save Visit`
- `Save and Print Receipt`
- `Save and Book Next Appointment`

UX notes:
- This modal should be optimized for speed
- Front desk should be able to finish it in under 30 seconds

## 9.4 Orthodontic Ledger Page
Page title:
- `Orthodontic Ledger`

Header summary:
- Patient
- Doctor
- Status
- Total fee
- Paid
- Balance
- Next appointment
- Commission accrued
- Commission pending

Main table columns:
- Date
- Notes / visit summary
- Payment
- Balance
- Next appointment
- Commission
- Payout status
- Receipt
- Created by

Filters:
- Date range
- Payment status
- Doctor

Actions per row:
- View receipt
- Edit entry
- Delete entry (admin only)
- Mark commission paid (admin only, only when pending exists)

Mobile UI:
- Stack each ledger row into a card
- Keep payment, balance, and next appointment prominent

## 9.5 Orthodontic Dashboard
Audience:
- Admin / clinic owner

Widgets:
- Active cases
- Total outstanding
- Collected this month
- New ortho cases this month
- Patients due this week
- Patients overdue for payment
- Commission accrued this month
- Commission unpaid
- Commission paid this month

Table views:
- Active cases list
- High balance pending
- No visit in last X days
- Orthodontist commission payable list
- Orthodontist commission payout history

## 9.6 Commission Payout Drawer or Modal
Audience:
- Admin / finance

Purpose:
- record how much commission was actually paid to the orthodontist

Fields:
- Orthodontist / consultant
- Linked case or multiple eligible ledger entries
- Accrued amount
- Already paid
- Pending amount
- Paid now
- Payment mode
- Reference number
- Payout date
- Notes

Buttons:
- `Save Payout`
- `Save and Print`

UX notes:
- This should feel similar to recording a payout or settlement, not like editing a visit
- Default the user toward paying from eligible pending rows so reconciliation stays clear

## 9.7 Printable Card
Format:
- Compact A5 or booklet style
- Simple, high contrast
- Designed to match the existing paper card mental model

Sections:
- Clinic header
- Patient name, age, sex, doctor
- Package fee, paid, balance
- Optional commission summary for admin/internal print
- Ledger table

## 10. Backend Data Model Plan

## 10.1 New DocType: Orthodontic Case
Recommended fields:
- `patient`
- `patient_name`
- `practitioner`
- `practitioner_name`
- `consultant_id`
- `consultant_name`
- `consultant_type`
- `consultant_practitioner`
- `case_type`
- `start_date`
- `estimated_duration_months`
- `estimated_end_date`
- `package_fee`
- `discount_amount`
- `discount_percentage`
- `net_fee`
- `advance_paid`
- `total_paid`
- `balance_amount`
- `next_appointment_date`
- `status`
- `notes`
- `default_followup_days`
- `is_active`
- `commission_model`
- `commission_type`
- `commission_value`
- `commission_basis`
- `total_commission_accrued`
- `total_commission_paid`
- `pending_commission_amount`

Computed fields:
- `net_fee`
- `total_paid`
- `balance_amount`
- `total_commission_accrued`
- `pending_commission_amount`

Status values:
- `Planned`
- `Active`
- `On Hold`
- `Completed`
- `Cancelled`

## 10.2 New Child DocType or Linked DocType: Orthodontic Ledger Entry
Recommended fields:
- `orthodontic_case`
- `visit_date`
- `visit_notes`
- `payment_amount`
- `payment_mode`
- `balance_after_entry`
- `next_appointment_date`
- `sales_invoice`
- `payment_entry`
- `receipt_number`
- `created_by`
- `is_adjustment`
- `adjustment_reason`
- `consultant_id`
- `consultant_name`
- `consultant_type`
- `consultant_practitioner`
- `commission_type`
- `commission_value`
- `commission_basis`
- `commission_amount`
- `commission_status`
- `commission_payout_reference`
- `commission_paid_date`
- `commission_paid_amount`

Recommendation:
- Use a separate linked DocType instead of only a child table if reporting and editing are important

## 10.3 New Optional DocType: Orthodontic Commission Payout
Recommended fields:
- `orthodontic_case`
- `consultant_id`
- `consultant_name`
- `consultant_practitioner`
- `posting_date`
- `paid_amount`
- `payment_mode`
- `reference_no`
- `notes`
- `created_by`
- `status`

Child rows:
- linked ledger entry
- commission accrued amount
- commission paid amount

Recommendation:
- If existing payout reporting already has a reusable payout object, extend that instead of introducing a totally separate payout engine
- If not, create this DocType so "commission accrued" and "commission actually paid" remain separately auditable

## 10.4 Optional Reuse of Existing Objects
Appointments:
- Existing `Patient Appointment`
- Add/standardize appointment type `Orthodontic Follow-up`

Payments:
- Reuse current Sales Invoice / Payment Entry flow where possible
- Ledger entry should link to invoice/payment records, not duplicate accounting truth

Commission:
- Reuse the current invoice consultant/commission pattern wherever possible
- If an ortho payment creates an invoice, the commission snapshot should map cleanly to the existing consultant commission fields
- Orthodontic Case should act as the business summary layer; invoice/payment records should remain the accounting layer
- Use the same consultant identity and commission snapshot vocabulary already present on invoice items so financial dashboards can eventually combine both sources cleanly

## 11. API Plan

## 11.1 Case APIs
- `create_orthodontic_case`
- `get_orthodontic_case`
- `update_orthodontic_case`
- `list_orthodontic_cases`
- `close_orthodontic_case`
- `get_orthodontic_case_commission_summary`

## 11.2 Ledger APIs
- `add_orthodontic_ledger_entry`
- `update_orthodontic_ledger_entry`
- `delete_orthodontic_ledger_entry`
- `get_orthodontic_ledger`
- `mark_orthodontic_commission_paid`
- `get_orthodontic_commission_payout_history`

## 11.3 Commission Payout APIs
- `create_orthodontic_commission_payout`
- `get_orthodontic_commission_payout`
- `list_orthodontic_commission_payouts`
- `reverse_orthodontic_commission_payout`

## 11.4 Summary APIs
- `get_patient_orthodontic_summary`
- `get_orthodontic_dashboard`
- `get_orthodontic_overdue_cases`
- `get_orthodontic_commission_dashboard`
- `get_orthodontic_consultant_payout_report`

## 11.5 Print / Share APIs
- `get_orthodontic_print_data`
- `share_orthodontic_receipt`
- `share_orthodontic_card`

## 11.6 Suggested API Payloads

### Create Case
```json
{
  "patient_id": "PAT-0001",
  "practitioner_id": "DOC-0001",
  "consultant_id": "CONSULTANT-0001",
  "case_type": "Fixed Braces",
  "start_date": "2026-03-20",
  "estimated_duration_months": 18,
  "package_fee": 45000,
  "discount_amount": 5000,
  "advance_paid": 10000,
  "commission_model": "Percentage",
  "commission_type": "Percentage",
  "commission_value": 30,
  "commission_basis": "On collected amount",
  "default_followup_days": 30,
  "notes": "Upper and lower arch case"
}
```

### Add Ledger Entry
```json
{
  "case_id": "ORTHO-CASE-0001",
  "visit_date": "2026-04-20",
  "visit_notes": "Wire change and review",
  "payment_amount": 2000,
  "payment_mode": "Cash",
  "next_appointment_date": "2026-05-20",
  "commission_override": false,
  "create_receipt": true
}
```

### Create Commission Payout
```json
{
  "case_id": "ORTHO-CASE-0001",
  "consultant_id": "CONSULTANT-0001",
  "posting_date": "2026-05-25",
  "paid_amount": 1200,
  "payment_mode": "Bank Transfer",
  "reference_no": "UTR123456",
  "notes": "April ortho collection commission payout",
  "ledger_entries": [
    {
      "ledger_entry_id": "ORTHO-LEDGER-0004",
      "commission_paid_amount": 600
    },
    {
      "ledger_entry_id": "ORTHO-LEDGER-0005",
      "commission_paid_amount": 600
    }
  ]
}
```

## 12. Business Rules
- One patient should normally have one active ortho case
- Ledger entry can exist even if payment is zero
- Next appointment is optional but strongly encouraged
- Case balance must auto-update after each ledger/payment event
- Linked invoice/payment should remain accounting source of truth
- Commission accrual should happen at the time of eligible payment logging
- Historical ledger commission should not change retroactively if case-level commission rules are edited later
- Commission payout marking should be auditable
- Commission payout should be a separate event from commission accrual
- Commission paid totals should roll up from payout records, not from manual direct edits on the case
- The same commission should not be paid twice across ledger rows or payout records
- If invoice-side consultant commission already exists for the same ortho payment, the ortho layer should reference that snapshot rather than create conflicting values
- Case cannot be marked completed if balance remains unpaid unless override by admin
- Case edits to package fee must be audited

## 13. Permissions Model

### Front Desk
- View case
- Add visit
- Collect payment
- Update next appointment
- Print card
- View commission only if permitted by clinic settings

### Doctor
- View all case and ledger information
- Add treatment notes
- Review continuity
- View own accrued/pending commission if clinic allows

### Admin
- Edit package details
- Adjust balance
- Reverse ledger entry
- Close or reopen case
- Access dashboard/reporting
- Edit commission rules
- Mark commission as paid
- Review commission payout history

## 14. Edge Cases
- Visit recorded but no payment
- Payment collected without appointment
- Missed visit with same next appointment
- Doctor changes package value mid-treatment
- Additional discount after case start
- Refund or correction entry
- Treatment paused for a few months
- Patient shifts doctor
- Orthodontist commission rule changes mid-case
- Payment received but commission intentionally withheld
- Partial commission payout
- Case closed with pending balance
- Accidental duplicate ledger entry

## 15. Notifications and Reminders

### V1
- Optional receipt sharing
- Optional next appointment confirmation

### V2
- Reminder 1 day before next ortho visit
- Balance due reminder
- Missed visit follow-up reminder

## 16. Reporting Requirements
- Active orthodontic cases
- Total outstanding by patient
- Monthly ortho collections
- Patients with no visit in 45+ days
- Cases with overdue balance
- Doctor-wise active ortho load
- Commission accrued by orthodontist
- Commission paid by orthodontist
- Pending commission by orthodontist
- Commission liability by month
- Commission payout history by orthodontist
- Case-wise commission reconciliation report

## 17. Phased Development Task Breakdown

## Phase 1: Foundation
Goal:
- establish data model and basic summary

Tasks:
- create `Orthodontic Case` DocType
- create `Orthodontic Ledger Entry` DocType
- define orthodontist consultant linkage and snapshot fields
- add patient linkage
- create case create/get/update APIs
- create summary API
- add patient-page ortho summary widget
- design commission model to align with existing invoice consultant logic

Deliverable:
- team can create and view orthodontic cases

## Phase 2: Daily Workflow
Goal:
- make front desk workflow usable

Tasks:
- build `Add Visit / Collect Payment` modal
- create ledger entry API
- auto-calculate balance
- update next appointment from modal
- surface ledger table in patient page or dedicated page
- support receipt/invoice linking
- auto-calculate commission on payment entries
- store invoice-aligned consultant commission snapshot fields on each eligible payment row

Deliverable:
- clinic can manage day-to-day ortho tracking digitally

## Phase 3: Print and Sharing
Goal:
- replace paper booklet behavior

Tasks:
- print-friendly ortho card template
- ledger print layout
- optional WhatsApp receipt/card sharing

Deliverable:
- clinic can operate with digital + printable fallback

## Phase 4: Admin Control and Reporting
Goal:
- support management and scale

Tasks:
- ortho dashboard
- reporting filters
- overdue cases list
- correction and audit flows
- admin-only adjustments
- commission payout tracking and payout reporting
- payout history and reconciliation view

Deliverable:
- owner/admin has financial visibility and control

## Phase 5: Automation
Goal:
- reduce manual follow-up work

Tasks:
- appointment reminders
- balance reminders
- missed-visit detection
- smart follow-up queues

Deliverable:
- lower front desk effort and better collection discipline

## 18. Suggested Sprint Plan

### Sprint 1
- DocTypes
- base APIs
- patient summary card
- create case modal
- case-level commission model

### Sprint 2
- ledger entry flow
- running balance
- next appointment update
- receipt linkage
- commission accrual on payment entries

### Sprint 3
- ledger page
- print card
- mobile UX cleanup

### Sprint 4
- dashboard
- filters
- permissions
- corrections and audit
- commission payout workflow
- payout reconciliation report

## 19. Acceptance Criteria for MVP
- Staff can create one ortho case for a patient
- Staff can add a visit and payment in a single flow
- Balance auto-updates correctly
- Next appointment is visible on patient page
- Doctor can view full payment ledger
- Admin can see accrued and pending orthodontist commission
- Admin can mark commission as paid and see payout history
- Staff can print a booklet-style ortho card
- No manual balance calculation is needed

## 20. Open Questions
- Should every installment create a Sales Invoice, or should some entries be receipt-only?
- Should overpayment be blocked or stored as credit?
- Should package revisions require admin approval?
- Should case completion require zero balance?
- Should commission always be calculated on collected amount, or do some clinics need fixed-per-visit rules?
- Should commission be visible only to admin, or also to the treating orthodontist?
- Should commission payout use a separate payout record or integrate with existing consultant payout reporting?
- Should ortho commission appear inside the existing consultant payout dashboard as a combined data source, or stay as a separate ortho payout report first?

## 21. Recommendation
Start with the simplest possible product that mirrors the paper card:
- one active ortho case
- one running ledger
- one fast visit/payment modal
- one visible patient summary
- one print card

But commission should still be planned from day one. The best approach is:
- keep V1 commission model simple
- align it with the existing invoice consultant commission logic
- calculate commission on collected payments
- store consultant snapshot fields in the same commercial vocabulary used by invoice items
- support explicit payout recording so the clinic can track what was actually given to the orthodontist, not just what is theoretically owed
- expose payout visibility to admins without making front-desk workflow heavier

That will solve the real clinic problem without creating unnecessary finance complexity in V1.
