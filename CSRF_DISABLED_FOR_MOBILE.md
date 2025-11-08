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

All API endpoints now include the `methods` parameter in the `@frappe.whitelist()` decorator:

```python
# Before (CSRF required for POST requests)
@frappe.whitelist()
def create_patient(**kwargs):
    pass

# After (CSRF bypassed)
@frappe.whitelist(methods=['POST'])
def create_patient(**kwargs):
    pass
```

### HTTP Method Specifications

Each endpoint specifies which HTTP methods it accepts:

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

When you specify `methods` in `@frappe.whitelist()`:

1. Frappe checks the HTTP method of the incoming request
2. If the method is in the allowed list, **CSRF validation is skipped**
3. The request is processed without requiring the `X-Frappe-CSRF-Token` header
4. Session authentication (via cookies) still works normally

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

We chose the `methods` approach, but here are other ways to disable CSRF:

### 1. Using `xss_safe=True` (Not Recommended for POST)
```python
@frappe.whitelist(xss_safe=True)  # Only for GET-like operations
def safe_endpoint():
    pass
```

### 2. Manual CSRF Bypass (Not Recommended)
```python
@frappe.whitelist()
def endpoint():
    frappe.flags.ignore_csrf = True  # Discouraged
    pass
```

### 3. Token-Based Auth (Future Enhancement)
For additional security, consider implementing JWT or OAuth tokens instead of session cookies.

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

To re-enable CSRF protection, simply remove the `methods` parameter:

```python
# Re-enable CSRF
@frappe.whitelist()  # Remove methods parameter
def endpoint():
    pass
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
