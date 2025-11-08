/**
 * Debug script for testing session-based authentication
 * 
 * Run this in your browser console OR as a Node.js script with axios
 * This demonstrates the CORRECT way to handle authentication
 */

// Configuration
const BASE_URL = 'http://dev2.localhost:8800';
const EMAIL = 'Administrator';
const PASSWORD = 'Olapeepi@2468';

// ============================================================================
// OPTION 1: Browser Fetch API (for testing in browser console)
// ============================================================================

async function testAuthWithFetch() {
  console.log('='.repeat(80));
  console.log('Testing Authentication with Fetch API');
  console.log('='.repeat(80));
  
  try {
    // Step 1: Login
    console.log('\n[1] Login...');
    const loginResponse = await fetch(`${BASE_URL}/api/method/mob_clinic.mob_clinic.api.auth.mobile_login`, {
      method: 'POST',
      credentials: 'include', // ← CRITICAL: This sends/receives cookies
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({
        usr: EMAIL,
        pwd: PASSWORD
      })
    });
    
    const loginData = await loginResponse.json();
    console.log('Login Status:', loginResponse.status);
    console.log('Login Response:', loginData);
    
    if (loginResponse.status !== 200) {
      console.error('❌ Login failed!');
      return;
    }
    
    console.log('✅ Login successful!');
    
    // Step 2: Get Practitioner Profile (authenticated request)
    console.log('\n[2] Get Practitioner Profile...');
    const profileResponse = await fetch(`${BASE_URL}/api/method/mob_clinic.mob_clinic.api.auth.get_practitioner_profile`, {
      method: 'GET',
      credentials: 'include', // ← CRITICAL: This sends cookies
      headers: {
        'Accept': 'application/json'
      }
    });
    
    console.log('Profile Status:', profileResponse.status);
    
    if (profileResponse.status === 200) {
      const profileData = await profileResponse.json();
      console.log('✅ Profile retrieved successfully!');
      console.log('Profile Data:', profileData);
    } else {
      const errorText = await profileResponse.text();
      console.error('❌ Profile request failed!');
      console.error('Error:', errorText);
    }
    
    // Step 3: Get Appointments
    console.log('\n[3] Get Appointments...');
    const appointmentsResponse = await fetch(`${BASE_URL}/api/method/mob_clinic.mob_clinic.api.appointment.get_appointments?limit_page_length=50&limit_start=0`, {
      method: 'GET',
      credentials: 'include', // ← CRITICAL: This sends cookies
      headers: {
        'Accept': 'application/json'
      }
    });
    
    console.log('Appointments Status:', appointmentsResponse.status);
    
    if (appointmentsResponse.status === 200) {
      const appointmentsData = await appointmentsResponse.json();
      console.log('✅ Appointments retrieved successfully!');
      console.log('Appointments:', appointmentsData);
    } else {
      console.error('❌ Appointments request failed!');
    }
    
    // Step 4: Get Patients
    console.log('\n[4] Get Patients...');
    const patientsResponse = await fetch(`${BASE_URL}/api/method/mob_clinic.mob_clinic.api.patient.get_patients?limit_page_length=10&limit_start=0`, {
      method: 'GET',
      credentials: 'include', // ← CRITICAL: This sends cookies
      headers: {
        'Accept': 'application/json'
      }
    });
    
    console.log('Patients Status:', patientsResponse.status);
    
    if (patientsResponse.status === 200) {
      const patientsData = await patientsResponse.json();
      console.log('✅ Patients retrieved successfully!');
      console.log('Patients:', patientsData);
    } else {
      console.error('❌ Patients request failed!');
    }
    
    console.log('\n' + '='.repeat(80));
    console.log('Test Complete!');
    console.log('='.repeat(80));
    
  } catch (error) {
    console.error('Error:', error);
  }
}

// ============================================================================
// OPTION 2: Axios (for React/Vue apps) - The CORRECT configuration
// ============================================================================

/**
 * This is the CORRECT way to configure Axios for your React app
 * Put this in a file like src/api/axiosConfig.js
 */

const axiosConfig = `
// src/api/axiosConfig.js
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://dev2.localhost:8800',
  withCredentials: true, // ← CRITICAL: This enables cookie handling
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
});

// Request interceptor (optional - for debugging)
api.interceptors.request.use(
  (config) => {
    console.log('Making request to:', config.url);
    console.log('With credentials:', config.withCredentials);
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor (optional - for error handling)
api.interceptors.response.use(
  (response) => {
    console.log('Response status:', response.status);
    return response;
  },
  (error) => {
    if (error.response?.status === 403 || error.response?.status === 401) {
      console.error('Authentication error - session may have expired');
      // Redirect to login or refresh token
    }
    return Promise.reject(error);
  }
);

export default api;
`;

/**
 * Usage in your React components
 */
const reactUsageExample = `
// src/services/authService.js
import api from '../api/axiosConfig';

export const authService = {
  // Login
  async login(email, password) {
    const response = await api.post('/api/method/mob_clinic.mob_clinic.api.auth.mobile_login', {
      usr: email,
      pwd: password
    });
    return response.data;
  },

  // Get Profile
  async getProfile() {
    const response = await api.get('/api/method/mob_clinic.mob_clinic.api.auth.get_practitioner_profile');
    return response.data;
  },

  // Logout
  async logout() {
    const response = await api.post('/api/method/mob_clinic.mob_clinic.api.auth.mobile_logout');
    return response.data;
  }
};

// src/services/appointmentService.js
import api from '../api/axiosConfig';

export const appointmentService = {
  async getAppointments(filters = {}) {
    const response = await api.get('/api/method/mob_clinic.mob_clinic.api.appointment.get_appointments', {
      params: {
        limit_page_length: 50,
        limit_start: 0,
        ...filters
      }
    });
    return response.data;
  }
};

// In your React component:
// import { authService } from './services/authService';
// import { appointmentService } from './services/appointmentService';
//
// const handleLogin = async () => {
//   try {
//     const result = await authService.login(email, password);
//     console.log('Logged in:', result);
//     
//     // Now get appointments - cookie is automatically sent!
//     const appointments = await appointmentService.getAppointments();
//     console.log('Appointments:', appointments);
//   } catch (error) {
//     console.error('Error:', error);
//   }
// };
`;

// ============================================================================
// Run the test
// ============================================================================

console.log(`
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║  Mobile Clinic API - Authentication Debug Script                         ║
║                                                                           ║
║  This script demonstrates the CORRECT way to handle authentication       ║
║  with session cookies in your frontend application.                      ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝

INSTRUCTIONS:
1. Open your browser console (F12)
2. Navigate to http://localhost:3000 (your React app)
3. Paste this entire file into the console
4. Run: testAuthWithFetch()

The key is to use credentials: 'include' with fetch or withCredentials: true with axios!

---

For your React app, use the Axios configuration shown below:
`);

console.log(axiosConfig);
console.log('\n' + '='.repeat(80));
console.log('Usage in React:');
console.log('='.repeat(80));
console.log(reactUsageExample);

// Export for use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { testAuthWithFetch };
}
