# Authentication Guide for Mobile Clinic API

## Overview
The Mobile Clinic API uses Frappe's standard session-based authentication. After successful login, a session cookie (`sid`) is set, which must be included in all subsequent API requests.

## Important: Session Cookies
All authenticated requests require the `sid` cookie to be sent. Make sure your HTTP client (Axios, Fetch, etc.) is configured to:
1. **Accept and store cookies**
2. **Send cookies with requests**
3. **Handle credentials properly**

---

## Method 1: Use Frappe's Standard Login (Recommended)

### Login
Use Frappe's built-in login endpoint for the most reliable authentication:

```bash
curl -X POST http://dev2.localhost:8800/api/method/login \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -c cookies.txt \
  -d '{
    "usr": "doctor@clinic.com",
    "pwd": "YourPassword123"
  }'
```

**Response:**
```json
{
  "message": "Logged In",
  "home_page": "/app",
  "full_name": "Dr. John Smith"
}
```

**Cookie Set:**
```
sid=05d8d46aaebff1c87a90f570a3ff1c0f;
path=/;
HttpOnly
```

### Then Get Practitioner Profile
After login, get the enhanced practitioner profile:

```bash
curl -X GET http://dev2.localhost:8800/api/method/mob_clinic.mob_clinic.api.auth.get_practitioner_profile \
  -H 'Accept: application/json' \
  -b cookies.txt
```

**Response:**
```json
{
  "message": "success",
  "data": {
    "id": "HCP-00001",
    "name": "Dr. John Smith",
    "phone": "+1234567890",
    "email": "doctor@clinic.com",
    "consultation_fee": 500,
    "clinic_description": "City Medical Clinic",
    "working_hours": [...]
  }
}
```

---

## Method 2: Use Custom Mobile Login (Alternative)

### Login with Enhanced Response
Our custom login returns user and clinic data in a single call:

```bash
curl -X POST http://dev2.localhost:8800/api/method/mob_clinic.mob_clinic.api.auth.mobile_login \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -c cookies.txt \
  -d '{
    "usr": "doctor@clinic.com",
    "pwd": "YourPassword123"
  }'
```

**Response:**
```json
{
  "message": "Logged In",
  "home_page": "/app",
  "full_name": "Dr. John Smith",
  "user": {
    "id": "doctor@clinic.com",
    "name": "Dr. John Smith",
    "email": "doctor@clinic.com",
    "phone": "+1234567890",
    "role": "doctor",
    "clinic": {
      "practitioner_id": "HCP-00001",
      "name": "Dr. John Smith",
      "consultation_fee": 500,
      "clinic_description": "City Medical Clinic",
      "working_hours": [...]
    }
  }
}
```

---

## Frontend Implementation (React/JavaScript)

### Using Axios (Recommended)

```javascript
import axios from 'axios';

// Configure axios to send cookies
const api = axios.create({
  baseURL: 'http://dev2.localhost:8800',
  withCredentials: true, // CRITICAL: This sends cookies
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
});

// Login function
async function login(email, password) {
  try {
    // Option 1: Use Frappe's standard login
    const response = await api.post('/api/method/login', {
      usr: email,
      pwd: password
    });
    
    // Cookie is automatically stored by browser
    console.log('Logged in:', response.data);
    
    // Get practitioner profile
    const profile = await api.get('/api/method/mob_clinic.mob_clinic.api.auth.get_practitioner_profile');
    return profile.data;
    
  } catch (error) {
    console.error('Login failed:', error.response?.data);
    throw error;
  }
}

// Now all subsequent requests will include the sid cookie
async function getAppointments() {
  const response = await api.get('/api/method/mob_clinic.mob_clinic.api.appointment.get_appointments', {
    params: {
      limit_page_length: 20,
      limit_start: 0
    }
  });
  return response.data;
}

// Logout function
async function logout() {
  await api.post('/api/method/logout');
  // OR use custom logout
  await api.post('/api/method/mob_clinic.mob_clinic.api.auth.mobile_logout');
}
```

### Using Fetch API

```javascript
// Login with fetch
async function login(email, password) {
  const response = await fetch('http://dev2.localhost:8800/api/method/login', {
    method: 'POST',
    credentials: 'include', // CRITICAL: This sends cookies
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    },
    body: JSON.stringify({
      usr: email,
      pwd: password
    })
  });
  
  if (!response.ok) {
    throw new Error('Login failed');
  }
  
  return await response.json();
}

// Make authenticated requests
async function getAppointments() {
  const response = await fetch(
    'http://dev2.localhost:8800/api/method/mob_clinic.mob_clinic.api.appointment.get_appointments?limit_page_length=20',
    {
      method: 'GET',
      credentials: 'include', // CRITICAL: This sends cookies
      headers: {
        'Accept': 'application/json'
      }
    }
  );
  
  return await response.json();
}
```

---

## Registration

### Register New Doctor

```bash
curl -X POST http://dev2.localhost:8800/api/method/mob_clinic.mob_clinic.api.auth.mobile_register \
  -H 'Content-Type: application/json' \
  -d '{
    "full_name": "Dr. Jane Doe",
    "email": "jane@clinic.com",
    "phone": "+1987654321",
    "password": "SecurePass123!",
    "clinic_name": "Jane Medical Center"
  }'
```

**Response:**
```json
{
  "message": "Registration successful",
  "user_id": "jane@clinic.com",
  "practitioner_id": "HCP-00002"
}
```

**After registration, you must login to get the session cookie!**

---

## Common Issues & Solutions

### Issue 1: "Function is not whitelisted" Error
**Problem:** Session cookie is not being sent with requests.

**Solution:**
- Ensure `withCredentials: true` (Axios) or `credentials: 'include'` (Fetch)
- Check that cookies are not being blocked by browser
- Verify CORS settings allow credentials

### Issue 2: CORS Errors
**Problem:** Browser blocks cross-origin requests.

**Solution:**
Configure site to allow CORS:
```bash
# Allow your frontend origin
bench --site dev2.localhost set-config allow_cors '["http://localhost:3000"]'

# For development only - ignore CSRF
bench --site dev2.localhost set-config ignore_csrf 1

# Restart
bench restart
```

### Issue 3: 403 Forbidden After Login
**Problem:** Session cookie expired or not sent.

**Solution:**
- Check cookie expiration (default 3 days)
- Verify `withCredentials` is set
- Re-login to get new session

### Issue 4: Cookie Not Set (SameSite Issues)
**Problem:** Modern browsers block third-party cookies.

**Solution for Development:**
- Use same domain for frontend and backend, OR
- Configure SameSite cookie settings, OR
- Use browser extensions to disable cookie restrictions in dev

---

## Testing Authentication

### Test Login Flow

```bash
# 1. Login and save cookies
curl -X POST http://dev2.localhost:8800/api/method/login \
  -H 'Content-Type: application/json' \
  -c cookies.txt \
  -d '{"usr":"doctor@clinic.com","pwd":"YourPassword123"}'

# 2. Test authenticated request with cookies
curl -X GET http://dev2.localhost:8800/api/method/mob_clinic.mob_clinic.api.appointment.get_appointments \
  -b cookies.txt

# 3. Logout
curl -X POST http://dev2.localhost:8800/api/method/logout \
  -b cookies.txt
```

### Verify Session

```bash
# Check who is logged in
curl -X GET http://dev2.localhost:8800/api/method/frappe.auth.get_logged_user \
  -b cookies.txt
```

**Response:**
```json
{
  "message": "doctor@clinic.com"
}
```

---

## Security Best Practices

### For Development
✅ Use `allow_cors` with specific origins  
✅ Set `ignore_csrf: 1` for easier testing  
✅ Use HTTP (non-secure) for local development

### For Production
✅ Use HTTPS only  
✅ Set specific CORS origins (no wildcards)  
✅ Enable CSRF protection (`ignore_csrf: 0`)  
✅ Use secure cookie settings  
✅ Implement rate limiting  
✅ Use strong password policies

---

## API Endpoints Summary

### Authentication
- `POST /api/method/login` - Standard Frappe login
- `POST /api/method/mob_clinic.mob_clinic.api.auth.mobile_login` - Enhanced login
- `POST /api/method/mob_clinic.mob_clinic.api.auth.mobile_register` - Register doctor
- `GET /api/method/mob_clinic.mob_clinic.api.auth.get_practitioner_profile` - Get profile
- `POST /api/method/mob_clinic.mob_clinic.api.auth.update_practitioner_profile` - Update profile
- `POST /api/method/logout` - Logout

### All Other APIs Require Authentication
All appointment, patient, prescription, payment, and file upload APIs require the user to be logged in (send `sid` cookie).

---

## Quick Start for Frontend Team

1. **Configure your HTTP client to send cookies:**
   ```javascript
   axios.defaults.withCredentials = true;
   ```

2. **Login first:**
   ```javascript
   await axios.post('/api/method/login', { usr, pwd });
   ```

3. **Make authenticated requests:**
   ```javascript
   await axios.get('/api/method/mob_clinic.mob_clinic.api.appointment.get_appointments');
   ```

4. **That's it!** The session cookie handles everything automatically.

---

## Need Help?

- Check browser DevTools → Network tab to see if cookies are being sent
- Verify `sid` cookie is present in request headers
- Check CORS configuration if getting preflight errors
- Ensure `withCredentials` / `credentials: 'include'` is set
