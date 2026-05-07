# Expense Sheet for Financial Dashboard

## Summary
- Build the expense sheet **inside the existing Financial Dashboard** as a new `ExpenseSheetSection`, with its own local expense filters and its own data pipeline so we do not overload the current revenue/collection filters.
- Support two expense periods:
  - `Specific Month`: one selected month + year.
  - `Financial Year`: one selected FY (`Apr-Mar`), with rows aggregated by expense item across the FY.
- Persist **manual expenses** in backend doctypes; compute **system-generated expenses** at read time from existing invoice consultant-commission snapshots.
- Use the user-approved mapping for system rows:
  - `Vendor Payment` = invoice-derived consultant commission where `consultant_type = External`
  - `Practitioner Salary` = invoice-derived consultant commission where `consultant_type = Internal`
- Recurrence rules:
  - `Recurring Fixed`: amount auto-carries forward; month cells are read-only; edit action updates the rule **effective forward**.
  - `Recurring Variable`: row auto-appears every month; new months start as **blank editable rows** and are excluded from totals until saved.
  - `One-Time`: exists only in creation month.

## Public APIs, Types, and Behavior
- Add new backend module: `mob_clinic/mob_clinic/api/expense_sheet.py`.
- Add new doctypes:
  - `Expense Rule`: `clinic`, `expense_name`, `expense_category`, `effective_from_month`, `effective_to_month`, `fixed_amount`, `is_active`.
  - `Expense Monthly Value`: `clinic`, `expense_rule`, `period_month`, `fiscal_year`, `amount`, `payment_date`, `expense_name_snapshot`.
- Add frontend service/hooks/query keys for:
  - `getExpenseSheet(filter_mode, month, year, fiscal_year, clinic)`
  - `getExpenseBreakdown(row_key, filter_mode, month, year, fiscal_year, clinic)`
  - `createExpense(payload)`
  - `saveExpenseChanges(changes, filter_context, clinic)`
  - `updateExpenseRule(payload)`
  - `deleteExpense(payload)`
  - `searchExpenseItems(q, clinic)`
- `getExpenseSheet` response should include:
  - `summary`
  - `rows`
  - `totals`
  - `filters`
  - `default_selected_row_key`
- Row contract should include stable keys and action flags:
  - `row_key`
  - `row_type = manual | system`
  - `expense_category`
  - `is_system_generated`
  - `can_edit_amount`
  - `can_edit_rule`
  - `can_delete`
  - `is_read_only`
- Key format:
  - `manual:<rule_id>:<period_month>`
  - `system:vendor_payment:<period_id>`
  - `system:practitioner_salary:<period_id>`
- FY breakdown shape:
  - FY table row = item total across FY
  - breakdown panel = month groups, then contributor rows inside each month
- Month breakdown shape:
  - manual rows = entry detail only
  - system rows = contributor rows directly

## Sequential Agent Tickets
1. **Ticket 1: Backend schema and recurrence engine**
   - Ownership: backend only.
   - Create `Expense Rule` and `Expense Monthly Value`.
   - Implement recurrence resolution for month/FY reads.
   - Implement forward-only rule splitting for recurring-fixed edits and fixed-to-variable conversion.
   - Implement recurring-variable blank-month generation without persisting empty monthly rows.
   - Implement delete semantics:
     - one-time: remove the month entry and its rule
     - recurring variable/fixed: stop recurrence effective selected month forward, preserve history

2. **Ticket 2: Backend read/write APIs and system-generated aggregation**
   - Ownership: backend only. Depends on Ticket 1.
   - Build `get_expense_sheet`, `get_expense_breakdown`, `create_expense`, `save_expense_changes`, `update_expense_rule`, `delete_expense`, `search_expense_items`.
   - Derive `Vendor Payment` and `Practitioner Salary` from `Sales Invoice Item.consultant_commission_amount`, split by `consultant_type`.
   - Enforce permissions:
     - read/breakdown/search: `financial_dashboard` access
     - create/update/delete/save: clinic admin only
   - Enforce validations:
     - amount numeric, non-negative, max 2 decimals
     - description/category required for manual creation
     - reject writes to system rows
     - reject direct amount edits to carried fixed rows

3. **Ticket 3: Frontend data layer and section scaffold**
   - Ownership: frontend only. Depends on Ticket 2 contracts being fixed.
   - Extract `ExpenseSheetSection` from the dashboard page and place it below the high-level finance cards and above the existing analytics blocks.
   - Add expense-local filters:
     - mode switch: `Specific Month` / `Financial Year`
     - month + year controls for month mode
     - FY dropdown for FY mode
     - `Apply Filter` commits draft filter to applied filter
   - Add TS types, query keys, service methods, hooks, and loading/error states.
   - On filter apply, refresh KPI cards, table, and breakdown from the same applied filter and auto-select the first visible row.

4. **Ticket 4: Frontend table, modal, actions, breakdown, and export**
   - Ownership: frontend only. Depends on Ticket 3.
   - Build:
     - `ExpenseSummaryCards`
     - `ExpenseTable`
     - `ExpenseBreakdownPanel`
     - `ExpenseEntryModal`
   - Table behavior:
     - row click highlights row, loads breakdown, scrolls to breakdown section
     - edit/delete buttons use `stopPropagation()`
     - icons render only when backend action flags allow them
   - Edit behavior:
     - recurring variable: inline amount/payment-date editing for selected month
     - recurring fixed: edit action opens forward-effective rule modal
     - one-time: edit current month entry
   - Modal behavior:
     - searchable expense name with suggestion support
     - allow custom text creation
     - optional payment date
     - required category excluding system-generated
     - required amount
     - unsaved-close warning
   - Export:
     - client-side CSV from the currently loaded filtered rows + totals snapshot

5. **Ticket 5: Verification, regression coverage, and acceptance pass**
   - Ownership: mixed verification. Depends on Tickets 1-4.
   - Backend tests: add `test_expense_sheet.py`.
   - Frontend tests: add service/query serialization coverage and section interaction coverage.
   - Validate full acceptance flow for month and FY modes, including row selection, breakdown sync, action gating, save filtering, and CSV export.

## Test Plan
- Backend scenarios:
  - recurring fixed carries forward and future month amount is read-only
  - recurring fixed edit creates successor rule effective forward
  - recurring fixed converts to recurring variable effective forward
  - recurring variable appears blank in new month and is excluded from totals until saved
  - one-time does not repeat
  - vendor/practitioner system rows are invoice-derived and read-only
  - month/FY totals, KPIs, table rows, and breakdown remain consistent
  - non-admin users cannot create/update/delete
  - clinic scoping and cross-clinic denial work correctly
- Frontend scenarios:
  - expense-local filter apply refreshes KPIs/table/breakdown together
  - row click highlights selection and calls `scrollIntoView`
  - edit/delete icons are hidden for disallowed rows
  - modal blocks invalid save and warns on dirty close
  - `Save Changes` excludes read-only/system rows from payload
  - CSV export matches current filtered snapshot and totals

## Assumptions and Defaults
- FY uses `Apr 1 - Mar 31`.
- FY table is **aggregated by item**, not month-columns.
- The current backend does not have true payroll/vendor-ledger models, so `Vendor Payment` and `Practitioner Salary` are implemented as labels over existing invoice consultant-commission snapshots split by `consultant_type`.
- The expected UI image is not visible in this thread, so implementation should follow the current financial dashboard visual language unless that mockup is re-shared during execution.
