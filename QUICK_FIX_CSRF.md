# Quick Fix: CSRF Exemption for Mobile APIs

## What Was Changed

The CSRF exemption has been implemented properly using a **before_request hook** instead of just the `methods` parameter.

## Files Modified

1. **`mob_clinic/hooks.py`** - Enabled the `before_request` hook
2. **`mob_clinic/mob_clinic/utils.py`** - Added CSRF exemption logic to `before_request()` function
3. **`CSRF_DISABLED_FOR_MOBILE.md`** - Updated documentation

## How It Works

```
Request Flow:
1. POST /api/method/mob_clinic.mob_clinic.api.auth.mobile_login
2. → before_request() hook executes
3. → Checks if path contains "/api/method/mob_clinic.mob_clinic.api."
4. → Sets frappe.flags.ignore_csrf = True
5. → CSRF validation sees flag and skips check ✓
6. → Your endpoint executes normally
```

## Commands to Deploy

### In your development environment:

```bash
# Navigate to your app directory
cd /workspace/development/frappe-bench/apps/mob_clinic

# Pull the latest changes
git pull

# Restart bench to apply the hooks
bench restart

# Or if using bench start in foreground, stop and restart:
# Ctrl+C to stop
# bench start
```

### If you get merge conflicts:

```bash
# Stash your local changes
git stash

# Pull the remote changes
git pull

# Apply your stashed changes (if needed)
git stash pop

# Resolve any conflicts, then restart
bench restart
```

## Test the Fix

```bash
# Test login without CSRF token
curl -X POST 'http://dev2.localhost:8000/api/method/mob_clinic.mob_clinic.api.auth.mobile_login' \
  -H 'Content-Type: application/json' \
  -d '{"usr": "Administrator", "pwd": "admin"}'

# Should return success without "Invalid Request" error
```

## What Changed in Code

### Before (Didn't Work):
```python
# Just specifying methods wasn't enough
@frappe.whitelist(methods=['POST'])
def mobile_login(usr, pwd):
    pass
```

### After (Works):
```python
# hooks.py
before_request = ["mob_clinic.mob_clinic.utils.before_request"]

# utils.py
def before_request():
    if "/api/method/mob_clinic.mob_clinic.api." in frappe.request.path:
        frappe.flags.ignore_csrf = True
```

## Why This Fix Works

1. **Timing**: The hook runs **before** CSRF validation, not after
2. **Scope**: Only exempts mobile API paths, not the entire application  
3. **Flag**: Uses the official `frappe.flags.ignore_csrf` mechanism
4. **Centralized**: All exemptions managed in one place (`utils.py`)

## Verify It's Working

After restart, you should see:

✅ No more "Invalid Request" or CSRFTokenError  
✅ Login endpoint works without CSRF token  
✅ All other mobile API endpoints work  
✅ Session authentication still enforced  

## Troubleshooting

### Still getting CSRF errors?

1. **Check bench restarted properly:**
   ```bash
   bench restart
   ```

2. **Verify hook is loaded:**
   ```bash
   bench console
   >>> import mob_clinic.hooks
   >>> print(mob_clinic.hooks.before_request)
   ['mob_clinic.mob_clinic.utils.before_request']
   ```

3. **Check the function exists:**
   ```bash
   bench console
   >>> from mob_clinic.mob_clinic.utils import before_request
   >>> before_request
   <function before_request at 0x...>
   ```

4. **Enable debug logging:**
   Add this to `utils.py` temporarily:
   ```python
   def before_request():
       print(f"Request path: {frappe.request.path if frappe.request else 'None'}")
       # ... rest of code
   ```

## Next Steps

Once this is working, you can:

1. ✅ Test all API endpoints from your React app
2. ✅ Remove CSRF token handling from frontend code
3. ✅ Deploy to production (after thorough testing)

---

**Created:** November 8, 2025  
**Status:** Ready to Deploy
