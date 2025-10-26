# Fix for "Function not whitelisted" Error

## The Problem
You're getting **"Function ... is not whitelisted"** errors because the session cookie (`sid`) is not being sent with your API requests after login.

## The Root Cause
Your frontend is calling `/api/method/mob_clinic.mob_clinic.api.auth.mobile_login` successfully, but **the session cookie is not being stored/sent** with subsequent requests.

## The Solution

### Option 1: Fix Your Frontend (Recommended)

Your frontend needs to **send cookies with every request**. Update your Axios configuration:

```javascript
// src/api/axios.js or wherever you configure axios
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://dev2.localhost:8800',
  withCredentials: true, // ← THIS IS CRITICAL!
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
});

export default api;
```

### Option 2: Check CORS Configuration

Make sure your Frappe site allows credentials from your frontend:

```bash
cd /workspace/development/frappe-bench

# Allow your React app origin
bench --site dev2.localhost set-config allow_cors '["http://localhost:3000"]'

# For development - ignore CSRF
bench --site dev2.localhost set-config ignore_csrf 1

# Restart bench
bench restart
```

### Option 3: Use Token-Based Authentication (Alternative)

If cookies don't work (mobile apps, etc.), you can use token-based auth. Add this to your frontend:

```javascript
// After login, store the API key/secret
const response = await api.post('/api/method/login', { usr, pwd });

// Get API key
const apiKey = await api.post('/api/method/frappe.core.doctype.user.user.generate_keys', {
  user: usr
});

// Store the API key
localStorage.setItem('api_key', apiKey.data.message.api_key);
localStorage.setItem('api_secret', apiKey.data.message.api_secret);

// Use in subsequent requests
api.defaults.headers.common['Authorization'] = `token ${apiKey}:${apiSecret}`;
```

## Quick Test

Test if your curl command works with cookies:

```bash
# 1. Login and save cookie
curl -X POST http://dev2.localhost:8800/api/method/mob_clinic.mob_clinic.api.auth.mobile_login \
  -H 'Content-Type: application/json' \
  -c /tmp/cookies.txt \
  -d '{"usr":"ananthcjayan@gmail.com","pwd":"Olapeepi@2468"}'

# 2. Use cookie for authenticated request
curl -X GET http://dev2.localhost:8800/api/method/mob_clinic.mob_clinic.api.auth.get_practitioner_profile \
  -b /tmp/cookies.txt

# 3. Test appointments
curl -X GET 'http://dev2.localhost:8800/api/method/mob_clinic.mob_clinic.api.appointment.get_appointments?limit_page_length=50' \
  -b /tmp/cookies.txt
```

If this works, the issue is **100% in your frontend** - it's not sending cookies.

## Frontend Checklist

✅ Set `withCredentials: true` in Axios config  
✅ Set `credentials: 'include'` if using Fetch  
✅ Check browser DevTools → Network → Request Headers for `Cookie: sid=...`  
✅ Verify CORS headers in Response: `Access-Control-Allow-Credentials: true`  
✅ Ensure cookies aren't blocked by browser privacy settings  
✅ Use same protocol (both HTTP or both HTTPS)  

## Still Not Working?

Check your site config:

```bash
cat sites/dev2.localhost/site_config.json
```

Should contain:
```json
{
  "allow_cors": ["http://localhost:3000"],
  "ignore_csrf": 1
}
```

And restart:
```bash
bench restart
```

---

**The key insight:** Frappe uses session-based authentication. After login, every request MUST include the `sid` cookie. Your frontend must be configured to accept, store, and send cookies automatically.
