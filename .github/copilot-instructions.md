# Copilot Agent Instructions (Backend: mob_clinic)

This file defines mandatory behavior for GitHub Copilot coding agents working on backend tickets in this app.

## Scope
- Applies to all files under this repository path.
- Primary domain: Frappe/ERPNext APIs, permissions, clinic/practitioner scoping.

## WhatsApp Manager Ticket Override
- For tickets with ID prefix `WM-`, this file must be used together with:
   - [plans/WHATSAPP_COPILOT_INSTRUCTIONS.md](../../../../plans/WHATSAPP_COPILOT_INSTRUCTIONS.md)
- If there is any conflict, follow the stricter rule.
- For `WM-*` completion, update the tracker in [plans/plan.md](../../../../plans/plan.md).

## Non-Negotiable Rules
1. **Ticket-first execution**
   - Read the ticket from [plans/plan.md](../../../../plans/plan.md).
   - Implement only the requested ticket scope.
   - Do not add extra features.
2. **Security before UI assumptions**
   - Any access control must be enforced in backend API logic.
   - Never rely only on frontend hiding.
3. **Clinic scoping is mandatory**
   - Any practitioner update/read must validate same-clinic access.
   - Avoid cross-clinic data leakage.
4. **Backward-compatible changes**
   - Do not break existing response keys unless ticket explicitly allows it.
   - Additive fields are preferred.
5. **Migration safety**
   - Patches must be idempotent.
   - Safe defaults for existing records.

## Implementation Standards
- Prefer small helper functions over duplicated permission checks.
- Reuse existing clinic helpers in [mob_clinic/api/clinic.py](../mob_clinic/mob_clinic/api/clinic.py).
- Keep whitelisted methods explicit and minimal.
- Use defensive parsing for JSON fields (fallback defaults).

## Ticket Workflow (Required)
1. Identify target files from ticket.
2. Make minimal code edits.
3. Run lint/syntax checks or focused tests if available.
4. Verify acceptance criteria from ticket.
5. Produce a short changelog:
   - What changed
   - Why
   - Any migration/patch command needed

## PR/Commit Notes Format
- `Ticket:`
- `Files changed:`
- `Behavior change:`
- `Security impact:`
- `Verification:`

## Do Not
- Do not modify unrelated APIs.
- Do not remove existing clinic filters unless ticket requires it.
- Do not hardcode practitioner/user IDs.
