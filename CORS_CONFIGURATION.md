# CORS Configuration for Mobile Clinic API

## Problem
Getting CORS errors when calling API from frontend (`http://localhost:3000`) to backend (`http://dev2.localhost:8800`)

## Solution
Added CORS handling in the application hooks to allow cross-origin requests from the frontend development server.

## Files Modified

### 1. `/mob_clinic/hooks.py`
- Added `before_request` hook to handle CORS

### 2. `/mob_clinic/mob_clinic/utils.py` (New file)
- Added `before_request()` function to set CORS headers
- Configured allowed origins for development and production

## Allowed Origins
The following origins are allowed for CORS:
- `http://localhost:3000` (React development server)
- `http://localhost:3001` (Alternative React port)
- `http://127.0.0.1:3000` (Local IP variant)
- `http://192.168.1.100:3000` (Local network access)
- Production domains (to be configured)

## Additional Configuration for Development

### Option 1: Site Configuration (Recommended)
Add to your site's `site_config.json` file:
```json
{
  "cors_origins": [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000"
  ],
  "developer_mode": 1
}
```

### Option 2: Bench Configuration
Run this command in your Frappe bench:
```bash
bench set-config cors_origins '["http://localhost:3000", "http://localhost:3001"]'
bench set-config developer_mode 1
```

### Option 3: Site-specific CORS
For your specific site, run:
```bash
bench --site dev2.localhost set-config cors_origins '["http://localhost:3000"]'
```

## Frontend Integration

### Headers to Include
When making requests from your frontend, include these headers:
```javascript
{
  'Content-Type': 'application/json',
  'Accept': 'application/json',
  'X-Requested-With': 'XMLHttpRequest'
}
```

### Example Fetch Request
```javascript
fetch('http://dev2.localhost:8800/api/method/mob_clinic.mob_clinic.api.auth.mobile_register', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
  body: JSON.stringify({
    full_name: "Pooja",
    email: "ananthcjayan@gmail.com", 
    phone: "9400475408",
    password: "Olapeepi@2468",
    clinic_name: "Pooja"
  }),
  credentials: 'include' // Important for session management
})
```

### Example Axios Request
```javascript
import axios from 'axios';

// Set default axios config
axios.defaults.withCredentials = true;
axios.defaults.baseURL = 'http://dev2.localhost:8800';

// Make request
const response = await axios.post('/api/method/mob_clinic.mob_clinic.api.auth.mobile_register', {
  full_name: "Pooja",
  email: "ananthcjayan@gmail.com",
  phone: "9400475408", 
  password: "Olapeepi@2468",
  clinic_name: "Pooja"
});
```

## Testing the Fix

1. Restart your Frappe development server:
   ```bash
   bench restart
   ```

2. Test the API call from your frontend
3. Check browser console for any remaining CORS errors
4. Verify that preflight OPTIONS requests are handled correctly

## Troubleshooting

### If CORS errors persist:

1. **Check site_config.json**: Ensure CORS origins are properly configured
2. **Restart bench**: Run `bench restart` after configuration changes
3. **Check network tab**: Verify OPTIONS requests return 200 status
4. **Clear browser cache**: Sometimes cached preflight responses cause issues
5. **Check Frappe logs**: Look for CORS-related error messages

### Common Issues:
- Missing `credentials: 'include'` in frontend requests
- Incorrect site URL in frontend configuration
- Frappe site not running on expected port
- Multiple Frappe sites with different CORS configurations

## Production Considerations

For production deployment:
1. Replace localhost URLs with actual production domains
2. Use HTTPS for all API calls
3. Configure reverse proxy (nginx) for additional CORS handling
4. Set secure cookie configurations
5. Implement rate limiting and security headers