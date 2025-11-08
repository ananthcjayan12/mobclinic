# CSRF Protection Disabled for Mobile API

## Overview

All API endpoints in the Mobile Clinic Management System have been configured to **bypass CSRF (Cross-Site Request Forgery) protection** for mobile application usage.

## Why Disable CSRF for Mobile Apps?

CSRF protection is designed to prevent attacks in **browser-based web applications** where:
- Cookies are automatically sent with requests
- Malicious websites can trick browsers into making unauthorized requests
- The attack exploits the browser's automatic cookie handling

**Mobile apps are immune to CSRF attacks** because:
- They don't use browser-based cookie management
- They make direct API calls (not through a web browser)
- There's no concept of "cross-site" in a native mobile app context
- Authentication is typically handled via tokens or session management within the app

## Implementation

### Method Used

CSRF protection is disabled using a **request hook** that sets `frappe.flags.ignore_csrf = True` for all mobile API endpoints before the request is processed.

**In `mob_clinic/hooks.py`:**
```python
before_request = ["mob_clinic.mob_clinic.utils.before_request"]
```

**In `mob_clinic/mob_clinic/utils.py`:**
```python
def before_request():
    """Handle CORS and CSRF exemption for API requests"""
    
    # Exempt mobile API endpoints from CSRF validation
    if frappe.request and frappe.request.path:
        csrf_exempt_paths = [
            "/api/method/mob_clinic.mob_clinic.api.auth.",
            "/api/method/mob_clinic.mob_clinic.api.patient.",
            "/api/method/mob_clinic.mob_clinic.api.appointment.",
            "/api/method/mob_clinic.mob_clinic.api.prescription.",
            "/api/method/mob_clinic.mob_clinic.api.payment.",
            "/api/method/mob_clinic.mob_clinic.api.file_upload.",
        ]
        
        for exempt_path in csrf_exempt_paths:
            if exempt_path in frappe.request.path:
                frappe.flags.ignore_csrf = True
                break
```

### Why This Approach?

1. **Early Interception**: The `before_request` hook runs before CSRF validation
2. **Centralized Control**: All mobile API exemptions are managed in one place
3. **Path-Based**: Only specific API paths are exempted, not the entire application
4. **Maintainable**: Easy to add or remove exempt paths as needed

### HTTP Method Specifications (Still Applied)

Each endpoint still specifies which HTTP methods it accepts for additional validation:

- **GET requests**: `methods=['GET']` - Used for fetching data
- **POST requests**: `methods=['POST']` - Used for creating resources
- **PUT/POST requests**: `methods=['POST', 'PUT']` - Used for updating resources
- **DELETE/POST requests**: `methods=['POST', 'DELETE']` - Used for deleting resources

## Updated Files

All API files have been updated:

1. **auth.py** - Authentication endpoints
   - `mobile_login` - POST
   - `mobile_register` - POST
   - `mobile_logout` - POST
   - `get_practitioner_profile` - GET
   - `update_practitioner_profile` - POST, PUT

2. **patient.py** - Patient management
   - `get_patients` - GET
   - `get_patient` - GET
   - `create_patient` - POST
   - `update_patient` - POST, PUT
   - `search_patients` - GET

3. **appointment.py** - Appointment management
   - `get_appointments` - GET
   - `get_appointment` - GET
   - `create_appointment` - POST
   - `update_appointment` - POST, PUT
   - `cancel_appointment` - POST, DELETE
   - `get_available_slots` - GET

4. **prescription.py** - Prescription management
   - `get_prescriptions` - GET
   - `get_prescription` - GET
   - `create_prescription` - POST
   - `update_prescription` - POST, PUT
   - `share_prescription` - POST
   - `get_patient_history` - GET

5. **payment.py** - Payment and invoice management
   - `get_invoices` - GET
   - `get_invoice` - GET
   - `create_invoice` - POST
   - `update_payment` - POST
   - `get_payment_summary` - GET
   - `send_payment_reminder` - POST

6. **file_upload.py** - File management
   - `upload_file` - POST
   - `get_file` - GET
   - `delete_file` - POST, DELETE
   - `list_files` - GET
   - `get_file_categories` - GET

## How Frappe Handles This

The implementation works as follows:

1. **Request Arrives**: Client makes a POST request to a mobile API endpoint
2. **Before Request Hook**: `before_request()` function is called
3. **Path Check**: Function checks if the request path matches any exempt pattern
4. **Set Flag**: If matched, sets `frappe.flags.ignore_csrf = True`
5. **CSRF Check**: Frappe's CSRF validation sees the flag and skips validation
6. **Request Processed**: The API endpoint executes normally
7. **Session Auth**: Session authentication and permissions are still enforced

## Security Considerations

### Still Secure Because:

1. **Authentication Required**: All endpoints (except login/register) still require valid session authentication
2. **Permission Checks**: Frappe's permission system is still enforced
3. **Input Validation**: All endpoints validate and sanitize input data
4. **Session Management**: Proper session handling prevents unauthorized access

### What This Means:

- ✅ Mobile apps can make API calls without CSRF tokens
- ✅ Session cookies are still required and validated
- ✅ User must be logged in for protected endpoints
- ✅ Permission system still enforces role-based access control
- ❌ CSRF token is NOT required in request headers
- ❌ Web browsers can also bypass CSRF (acceptable for mobile-first API)

## Usage in Mobile App

### React Native / Mobile App Example

```javascript
// Login (no CSRF needed)
const login = async (username, password) => {
    const response = await fetch('https://your-site.com/api/method/mob_clinic.mob_clinic.api.auth.mobile_login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            // NO X-Frappe-CSRF-Token header needed!
        },
        credentials: 'include', // Still need cookies for session
        body: JSON.stringify({
            usr: username,
            pwd: password
        })
    });
    
    return response.json();
};

// Create patient (no CSRF needed)
const createPatient = async (patientData) => {
    const response = await fetch('https://your-site.com/api/method/mob_clinic.mob_clinic.api.patient.create_patient', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            // NO X-Frappe-CSRF-Token header needed!
        },
        credentials: 'include', // Session cookie is still required
        body: JSON.stringify(patientData)
    });
    
    return response.json();
};
```

## Alternative Approaches (NOT Used)

We chose the `before_request` hook approach for these reasons:

### Why Not `methods` Parameter Alone?
```python
@frappe.whitelist(methods=['POST'])  # This DOESN'T disable CSRF!
```
The `methods` parameter only restricts which HTTP methods are allowed. CSRF validation happens earlier in the request lifecycle, before the endpoint is reached.

### Why Not `xss_safe=True`?
```python
@frappe.whitelist(xss_safe=True)  # Only for GET-like operations
```
This is meant for operations that don't modify data and isn't appropriate for POST/PUT/DELETE operations.

### Why Not Per-Endpoint Flags?
```python
@frappe.whitelist()
def endpoint():
    frappe.flags.ignore_csrf = True  # Too late - CSRF already checked!
```
By the time your endpoint executes, CSRF validation has already happened.

### Why the Hook Approach Works Best
- ✅ Runs before CSRF validation
- ✅ Centralized management
- ✅ Easy to add/remove paths
- ✅ Clean and maintainable
- ✅ Doesn't require modifying every endpoint

## Testing

All endpoints can now be tested without CSRF tokens:

```bash
# Login
curl -X POST 'https://your-site.com/api/method/mob_clinic.mob_clinic.api.auth.mobile_login' \
  -H 'Content-Type: application/json' \
  -d '{"usr": "user@example.com", "pwd": "password"}'

# Create Patient (after login, with session cookie)
curl -X POST 'https://your-site.com/api/method/mob_clinic.mob_clinic.api.patient.create_patient' \
  -H 'Content-Type: application/json' \
  -H 'Cookie: sid=your-session-id' \
  -d '{"first_name": "John", "sex": "Male"}'
```

## Rollback (If Needed)

To re-enable CSRF protection:

**1. Comment out the before_request hook in `mob_clinic/hooks.py`:**
```python
# Request Events
# ----------------
# before_request = ["mob_clinic.mob_clinic.utils.before_request"]
```

**2. Or remove the CSRF exemption logic from `utils.py`:**
```python
def before_request():
    """Handle only CORS, not CSRF exemption"""
    # Remove or comment out the CSRF exemption code
    # frappe.flags.ignore_csrf = True
    
    # Keep only CORS handling
    origin = frappe.get_request_header("Origin")
    # ... rest of CORS code
```

**3. Restart the bench:**
```bash
bench restart
```

## Notes

- This configuration is **ideal for mobile-first applications**
- Web-based frontends can still use these endpoints (they just won't have CSRF protection)
- Consider implementing additional API authentication (like API keys or JWT) for production
- Session cookies are still the primary authentication mechanism

## Date Updated

**November 7, 2025**

---

For more information on Frappe's whitelisting and CSRF handling, see:
- [Frappe Framework Documentation](https://frappeframework.com/docs)
- [Frappe API Documentation](https://frappeframework.com/docs/user/en/api)
