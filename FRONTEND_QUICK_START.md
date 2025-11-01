# Frontend Quick Start Guide

## ✅ Authentication is Working!

Your API authentication is now **working correctly**. Here's what your frontend team needs to know:

---

## 🔑 Login Flow

### Step 1: Configure Axios

```javascript
// src/api/client.js
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://dev2.localhost:8800',
  withCredentials: true, // ← MUST HAVE THIS
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
});

export default api;
```

### Step 2: Login

```javascript
// src/services/auth.js
import api from './client';

export async function login(email, password) {
  try {
    const response = await api.post('/api/method/mob_clinic.mob_clinic.api.auth.mobile_login', {
      usr: email,
      pwd: password
    });
    
    // The session cookie (sid) is automatically stored by browser
    const userData = response.data.message;
    
    return {
      success: true,
      user: userData.user,
      fullName: userData.full_name,
      homeUrl: userData.home_page
    };
  } catch (error) {
    return {
      success: false,
      error: error.response?.data?.message || 'Login failed'
    };
  }
}
```

### Step 3: Make Authenticated Requests

```javascript
// src/services/appointments.js
import api from './client';

export async function getAppointments(filters = {}) {
  const response = await api.get('/api/method/mob_clinic.mob_clinic.api.appointment.get_appointments', {
    params: {
      limit_page_length: 50,
      limit_start: 0,
      filters: JSON.stringify(filters)
    }
  });
  
  return response.data.message.data;
}

export async function createAppointment(appointmentData) {
  const response = await api.post('/api/method/mob_clinic.mob_clinic.api.appointment.create_appointment', appointmentData);
  return response.data.message.data;
}
```

---

## 📋 Complete Example - React

```javascript
import React, { useState, useEffect } from 'react';
import api from './api/client';

function App() {
  const [user, setUser] = useState(null);
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(false);
  
  // Login
  const handleLogin = async (email, password) => {
    setLoading(true);
    try {
      const response = await api.post('/api/method/mob_clinic.mob_clinic.api.auth.mobile_login', {
        usr: email,
        pwd: password
      });
      
      setUser(response.data.message.user);
      
      // Now fetch appointments
      loadAppointments();
    } catch (error) {
      console.error('Login failed:', error);
      alert('Login failed: ' + (error.response?.data?.message || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };
  
  // Load appointments
  const loadAppointments = async () => {
    try {
      const response = await api.get('/api/method/mob_clinic.mob_clinic.api.appointment.get_appointments', {
        params: {
          limit_page_length: 50,
          limit_start: 0,
          filters: JSON.stringify({
            appointment_date: ['>=', '2025-10-01']
          })
        }
      });
      
      setAppointments(response.data.message.data);
    } catch (error) {
      console.error('Failed to load appointments:', error);
    }
  };
  
  // Logout
  const handleLogout = async () => {
    try {
      await api.post('/api/method/mob_clinic.mob_clinic.api.auth.mobile_logout');
      setUser(null);
      setAppointments([]);
    } catch (error) {
      console.error('Logout error:', error);
    }
  };
  
  if (!user) {
    return (
      <LoginForm onLogin={handleLogin} loading={loading} />
    );
  }
  
  return (
    <div>
      <Header user={user} onLogout={handleLogout} />
      <AppointmentList 
        appointments={appointments} 
        onRefresh={loadAppointments}
      />
    </div>
  );
}

export default App;
```

---

## 🎯 Important Notes

### ✅ DO:
- Set `withCredentials: true` in Axios config
- Use the same Axios instance for all requests
- Let the browser handle cookies automatically
- Check `response.data.message` for actual data (Frappe wraps responses)

### ❌ DON'T:
- Manually manage cookies (browser does it)
- Store passwords in localStorage
- Forget to handle CORS in development
- Use Administrator account in production

---

## 🐛 Troubleshooting

### "Function is not whitelisted" Error
**Cause:** Cookies not being sent  
**Fix:** Verify `withCredentials: true` is set

### CORS Errors
**Fix on Backend:**
```bash
bench --site dev2.localhost set-config allow_cors '["http://localhost:3000"]'
bench --site dev2.localhost set-config ignore_csrf 1
bench restart
```

### Can't See Appointments
**Cause:** Logged in as Administrator (has no practitioner profile)  
**Fix:** Login with a doctor account created via registration

### _server_messages in Response
**Ignore:** These are internal Frappe messages. Use `response.data.message` for actual data.

---

## 📝 Test Credentials

### Create a Doctor Account First:
```bash
curl -X POST http://dev2.localhost:8800/api/method/mob_clinic.mob_clinic.api.auth.mobile_register \
  -H 'Content-Type: application/json' \
  -d '{
    "full_name": "Dr. Test Doctor",
    "email": "doctor@test.com",
    "phone": "+1234567890",
    "password": "Test@1234",
    "clinic_name": "Test Clinic"
  }'
```

### Then Login:
```javascript
login('doctor@test.com', 'Test@1234');
```

---

## 🚀 Ready to Use!

Your authentication is fully working. Just ensure:
1. ✅ `withCredentials: true` in Axios
2. ✅ CORS configured on backend
3. ✅ Use doctor account (not Administrator)
4. ✅ Access `response.data.message` for actual data

That's it! Happy coding! 🎉
