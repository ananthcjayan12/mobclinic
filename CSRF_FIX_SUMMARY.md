# CSRF Fix Summary

## Problem
Mobile app API requests were failing with `CSRFTokenError: Invalid Request` because:
1. CSRF validation happens in `HTTPRequest.__init__()` (frappe/auth.py:50)
2. The `before_request` hook runs AFTER CSRF validation (in init_request at line 199)
3. Setting `frappe.flags.ignore_csrf` in `before_request` was too late

## Solution
Used Frappe's built-in `ignore_csrf` hook in `hooks.py` to exempt specific mobile API endpoints from CSRF validation.

## Changes Made

### 1. `/mob_clinic/hooks.py`
Added `ignore_csrf` list with all mobile API endpoints that should bypass CSRF validation:

```python
ignore_csrf = [
    "mob_clinic.mob_clinic.api.auth.mobile_login",
    "mob_clinic.mob_clinic.api.auth.mobile_logout",
    "mob_clinic.mob_clinic.api.auth.verify_otp",
    "mob_clinic.mob_clinic.api.patient.create_patient",
    "mob_clinic.mob_clinic.api.appointment.create_appointment",
    # ... etc
]
```

### 2. `/mob_clinic/mob_clinic/utils.py`
- Removed CSRF handling from `before_request()` (it was too late)
- Kept `after_request()` for CORS headers
- Added comment explaining that CSRF is handled via hooks

## Why This Works

The `ignore_csrf` hook is checked BEFORE `HTTPRequest.__init__()` validates CSRF tokens. Here's the flow:

1. Request comes in → `application()` in frappe/app.py
2. Frappe checks `ignore_csrf` hook (our list)
3. If method is in the list → `frappe.conf.ignore_csrf` is set
4. `HTTPRequest.__init__()` runs → `validate_csrf_token()` checks `frappe.conf.ignore_csrf`
5. If True → CSRF validation is skipped ✅

## Security Note

Only exempt endpoints that:
- Are designed for mobile/external API access
- Have their own authentication (session, JWT, API keys)
- Don't rely on browser cookies for auth

Login endpoint (`mobile_login`) is safe to exempt because:
- It's the initial auth step (no session yet)
- Requires username/password
- Creates a new session with its own security

## Testing

After restart, mobile API endpoints should work without CSRF errors:
```bash
bench --site dev2.localhost clear-cache
bench restart
```

Test with:
```bash
curl -X POST http://localhost:8000/api/method/mob_clinic.mob_clinic.api.auth.mobile_login \
  -H "Content-Type: application/json" \
  -d '{"usr":"user@example.com","pwd":"password"}'
```

Should return 200 with session data (not 400 CSRF error).
