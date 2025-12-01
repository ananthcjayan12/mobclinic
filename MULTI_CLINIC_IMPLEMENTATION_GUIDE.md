# Multi-Clinic (Multi-Tenancy) Implementation Guide

**Version:** 1.0  
**Date:** December 1, 2025  
**Branch:** `Br-Multitenancy-start-1`

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Backend Changes](#backend-changes)
4. [Database Schema Changes](#database-schema-changes)
5. [Frontend Integration Guide](#frontend-integration-guide)
6. [API Reference](#api-reference)
7. [Testing](#testing)
8. [Migration Guide](#migration-guide)

---

## Overview

### What Changed?

The mobile clinic app now supports **multi-clinic (multi-tenancy)** functionality, allowing:

- A single practitioner to work across multiple clinics
- Clinic-specific data isolation (patients, appointments, invoices)
- Session-based clinic switching
- Automatic clinic scoping for all clinical operations

### Key Concepts

- **Clinic = Company**: We use ERPNext's `Company` doctype to represent clinics
- **Primary Clinic**: Each practitioner has a default/primary clinic (`primary_company` field)
- **Active Clinic**: The currently selected clinic in the user's session
- **Clinic Scoping**: All data operations (appointments, invoices, etc.) are scoped to the active clinic

---

## Architecture

### Clinic Resolution Order

When determining which clinic to use for an operation:

1. **Explicit Parameter** - `clinic` parameter passed in API call (highest priority)
2. **Session Data** - `frappe.session.data['active_clinic']` set by user
3. **Primary Company** - Practitioner's `primary_company` field (fallback)
4. **None** - No clinic restriction applied

### Data Model

```
Healthcare Practitioner
├── primary_company (Link to Company) - Default clinic
└── practitioner_companies (Table) - Additional accessible clinics [Future]

Patient
└── primary_clinic (Link to Company) - Assigned clinic

Patient Appointment
└── company (Link to Company) - Clinic where appointment occurs

Sales Invoice
└── company (Link to Company) - Billing clinic

Patient Encounter
└── company (Link to Company) - Treatment clinic
```

---

## Backend Changes

### 1. New Helper Module: `clinic.py`

**Location:** `mob_clinic/mob_clinic/api/clinic.py`

Core functions for clinic management:

- `get_accessible_companies_for_practitioner(practitioner_name)` - Returns list of accessible clinics
- `resolve_active_clinic(practitioner_name, clinic_param)` - Resolves which clinic to use
- `validate_practitioner_access(practitioner_name, clinic)` - Checks if practitioner can access clinic
- `apply_clinic_filter(filters, clinic)` - Adds clinic filter to query
- `set_active_clinic_session(clinic)` - Sets active clinic in session

### 2. Modified API Endpoints

All major API endpoints now support clinic scoping:

#### Modified Files:
- `auth.py` - Added clinic list on login, `switch_clinic` endpoint
- `patient.py` - Clinic filtering and assignment
- `appointment.py` - Appointment clinic scoping
- `prescription.py` - Encounter clinic scoping
- `payment.py` - Invoice clinic scoping
- `dental_chart.py` - Chart access validation
- `file_upload.py` - Clinic-specific folders

### 3. Custom Fields Added

**Healthcare Practitioner:**
- `primary_company` (Link to Company) - Primary clinic assignment

**Patient:**
- `primary_clinic` (Link to Company) - Patient's home clinic

---

## Database Schema Changes

### Migration Patches

**Patch File:** `mob_clinic/mob_clinic/patches/v1_0/install_custom_fields.py`

Adds custom fields to:
- Healthcare Practitioner (`primary_company`)
- Patient (`primary_clinic`)
- Patient Appointment (already has `company`)
- Sales Invoice (already has `company`)
- Patient Encounter (already has `company`)

**Run Migration:**
```bash
bench --site [your-site] migrate
```

---

## Frontend Integration Guide

### 1. Login Flow Changes

#### What Changed:
Login response now includes:
- List of accessible clinics
- Currently active clinic
- Clinic information

#### Frontend Updates Required:

**Store Additional Data:**
```javascript
// After successful login
const loginResponse = {
  user: {
    // ... existing fields
    clinics: ["Clinic A", "Clinic B"],  // NEW
    active_clinic: "Clinic A",          // NEW
    clinic: {                            // Existing, enhanced
      name: "Dr. John Doe Clinic",
      working_hours: [...]
    }
  }
}

// Store in your state management (Redux/Context/Vuex)
setUserClinics(loginResponse.user.clinics);
setActiveClinic(loginResponse.user.active_clinic);
```

**UI Changes:**
- Add clinic selector dropdown in app header/navigation
- Show active clinic name prominently
- Display clinic list if user has access to multiple clinics

### 2. Clinic Switching

#### New Feature:
Users can switch between clinics without re-login.

#### Implementation:

**Add Clinic Selector Component:**
```javascript
// Example: React/React Native
import React from 'react';
import { Picker } from 'react-native';

function ClinicSelector({ clinics, activeClinic, onSwitchClinic }) {
  return (
    <Picker
      selectedValue={activeClinic}
      onValueChange={onSwitchClinic}
    >
      {clinics.map(clinic => (
        <Picker.Item key={clinic} label={clinic} value={clinic} />
      ))}
    </Picker>
  );
}

// Usage
<ClinicSelector
  clinics={userClinics}
  activeClinic={activeClinic}
  onSwitchClinic={handleClinicSwitch}
/>
```

**Switch Clinic Handler:**
```javascript
async function handleClinicSwitch(newClinic) {
  try {
    const response = await fetch('/api/method/mob_clinic.mob_clinic.api.auth.switch_clinic', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `token ${apiKey}:${apiSecret}`
      },
      body: JSON.stringify({
        clinic: newClinic
      })
    });

    const data = await response.json();
    
    if (data.message.active_clinic) {
      // Update local state
      setActiveClinic(data.message.active_clinic);
      
      // Refresh current screen data
      refreshCurrentData();
      
      // Show success message
      showToast('Switched to ' + newClinic);
    }
  } catch (error) {
    showToast('Failed to switch clinic');
  }
}
```

### 3. API Calls - Adding Clinic Parameter

#### General Pattern:
Add optional `clinic` parameter to API calls when you want to override the session clinic.

**Example: Create Appointment**
```javascript
// Before (still works, uses session clinic):
await createAppointment({
  patient_id: "PAT-00001",
  appointment_date: "2025-12-01",
  appointment_time: "10:00:00"
});

// After (explicit clinic):
await createAppointment({
  patient_id: "PAT-00001",
  appointment_date: "2025-12-01",
  appointment_time: "10:00:00",
  clinic: "Clinic A"  // NEW - Optional explicit clinic
});
```

**Example: Get Patients**
```javascript
// Before (returns all accessible patients):
const patients = await getPatients({
  limit_page_length: 20
});

// After (filter by specific clinic):
const patients = await getPatients({
  limit_page_length: 20,
  clinic: "Clinic A"  // NEW - Filter by clinic
});
```

### 4. Patient Creation Flow

#### Change:
Patients now belong to a specific clinic.

**Update Patient Form:**
```javascript
async function createPatient(formData) {
  const payload = {
    first_name: formData.firstName,
    last_name: formData.lastName,
    sex: formData.gender,
    mobile: formData.phone,
    clinic: activeClinic,  // NEW - Assign to current clinic
    // ... other fields
  };

  const response = await fetch('/api/method/mob_clinic.mob_clinic.api.patient.create_patient', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `token ${apiKey}:${apiSecret}`
    },
    body: JSON.stringify(payload)
  });

  return await response.json();
}
```

### 5. List Views - Clinic Filtering

#### Change:
All list views (patients, appointments, invoices) now support clinic filtering.

**Add Clinic Filter:**
```javascript
// Example: Patient List
function PatientList() {
  const [patients, setPatients] = useState([]);
  const { activeClinic } = useAuth();

  useEffect(() => {
    loadPatients();
  }, [activeClinic]); // Reload when clinic changes

  async function loadPatients() {
    const response = await fetch(
      `/api/method/mob_clinic.mob_clinic.api.patient.get_patients?clinic=${activeClinic}`,
      {
        headers: {
          'Authorization': `token ${apiKey}:${apiSecret}`
        }
      }
    );
    
    const data = await response.json();
    setPatients(data.message.data);
  }

  return (
    <View>
      <Text>Patients - {activeClinic}</Text>
      {patients.map(patient => (
        <PatientCard key={patient.patient_id} patient={patient} />
      ))}
    </View>
  );
}
```

### 6. Error Handling

#### New Error: Permission Denied

When user tries to access data from unauthorized clinic:

```javascript
async function handleApiCall() {
  try {
    const response = await fetch(apiUrl, options);
    const data = await response.json();
    
    // NEW: Check for permission error
    if (response.status === 403) {
      if (data.exc_type === 'PermissionError') {
        showAlert('Access Denied', 'You do not have permission to access this clinic.');
        // Optionally switch back to primary clinic
        switchToPrimaryClinic();
      }
    }
    
    return data;
  } catch (error) {
    console.error('API Error:', error);
  }
}
```

---

## API Reference

### 1. Login API (Modified)

**Endpoint:** `POST /api/method/mob_clinic.mob_clinic.api.auth.mobile_login`

**Request:**
```json
{
  "usr": "practitioner@example.com",
  "pwd": "password"
}
```

**Response (Enhanced):**
```json
{
  "message": {
    "status": "success",
    "message": "Login successful",
    "user": {
      "user_id": "practitioner@example.com",
      "full_name": "Dr. John Doe",
      "practitioner_id": "PRAC-00001",
      "clinic": {
        "name": "Dr. John Doe Clinic",
        "description": "General Practice",
        "logo": "/files/clinic-logo.png",
        "working_hours": [...]
      },
      "clinics": [                    // NEW
        "Clinic A",
        "Clinic B"
      ],
      "active_clinic": "Clinic A"     // NEW
    },
    "token": {
      "api_key": "abc123...",
      "api_secret": "xyz789..."
    }
  }
}
```

---

### 2. Switch Clinic API (New)

**Endpoint:** `POST /api/method/mob_clinic.mob_clinic.api.auth.switch_clinic`

**Request:**
```json
{
  "clinic": "Clinic B"
}
```

**Response (Success):**
```json
{
  "message": {
    "message": "active_clinic_set",
    "active_clinic": "Clinic B"
  }
}
```

**Response (Error - No Access):**
```json
{
  "exc_type": "PermissionError",
  "message": "Practitioner does not have access to the requested clinic"
}
```
**HTTP Status:** 403

---

### 3. Get Patients API (Modified)

**Endpoint:** `GET /api/method/mob_clinic.mob_clinic.api.patient.get_patients`

**Query Parameters:**
```
?clinic=Clinic%20A          // NEW - Optional clinic filter
&limit_page_length=20       // Existing
&limit_start=0              // Existing
&filters={"status":"Active"}// Existing
```

**Response:**
```json
{
  "message": {
    "data": [
      {
        "patient_id": "PAT-00001",
        "patient_name": "John Smith",
        "primary_clinic": "Clinic A",  // NEW
        // ... other fields
      }
    ],
    "total_count": 45,
    "page_length": 20
  }
}
```

---

### 4. Create Patient API (Modified)

**Endpoint:** `POST /api/method/mob_clinic.mob_clinic.api.patient.create_patient`

**Request:**
```json
{
  "first_name": "Jane",
  "last_name": "Doe",
  "sex": "Female",
  "mobile": "1234567890",
  "email": "jane@example.com",
  "clinic": "Clinic A"          // NEW - Optional, defaults to active clinic
}
```

**Response:**
```json
{
  "message": {
    "status": "success",
    "message": "Patient created successfully",
    "data": {
      "patient_id": "PAT-00042",
      "patient_name": "Jane Doe",
      "primary_clinic": "Clinic A"  // NEW
    }
  }
}
```

---

### 5. Create Appointment API (Modified)

**Endpoint:** `POST /api/method/mob_clinic.mob_clinic.api.appointment.create_appointment`

**Request:**
```json
{
  "patient_id": "PAT-00001",
  "appointment_date": "2025-12-05",
  "appointment_time": "10:00:00",
  "duration": 30,
  "appointment_type": "Consultation",
  "clinic": "Clinic A"              // NEW - Optional
}
```

**Response:**
```json
{
  "message": {
    "status": "success",
    "message": "Appointment created successfully",
    "data": {
      "appointment_id": "APT-00123",
      "company": "Clinic A",          // NEW - Assigned clinic
      "appointment_date": "2025-12-05",
      "appointment_time": "10:00:00"
    }
  }
}
```

---

### 6. Get Appointments API (Modified)

**Endpoint:** `GET /api/method/mob_clinic.mob_clinic.api.appointment.get_appointments`

**Query Parameters:**
```
?clinic=Clinic%20A          // NEW - Optional clinic filter
&limit_page_length=20
&order_by=appointment_date desc
```

**Response:**
```json
{
  "message": {
    "data": [
      {
        "appointment_id": "APT-00123",
        "patient_name": "John Smith",
        "company": "Clinic A",      // NEW - Shows clinic
        "appointment_date": "2025-12-05",
        "status": "Open"
      }
    ],
    "total_count": 15
  }
}
```

---

### 7. Create Invoice API (Modified)

**Endpoint:** `POST /api/method/mob_clinic.mob_clinic.api.payment.create_invoice`

**Request:**
```json
{
  "patient_id": "PAT-00001",
  "items": [
    {
      "item_code": "CONSULTATION",
      "qty": 1,
      "rate": 500
    }
  ],
  "clinic": "Clinic A",             // NEW - Optional
  "posting_date": "2025-12-01",
  "due_date": "2025-12-15"
}
```

**Response:**
```json
{
  "message": {
    "status": "success",
    "invoice_id": "SINV-00234",
    "company": "Clinic A",            // NEW - Assigned clinic
    "grand_total": 500,
    "outstanding_amount": 500
  }
}
```

---

### 8. Get Invoices API (Modified)

**Endpoint:** `GET /api/method/mob_clinic.mob_clinic.api.payment.get_invoices`

**Query Parameters:**
```
?clinic=Clinic%20A          // NEW - Optional clinic filter
&patient_id=PAT-00001
&status=Unpaid
&limit_page_length=20
```

**Response:**
```json
{
  "message": {
    "data": [
      {
        "invoice_id": "SINV-00234",
        "patient_name": "John Smith",
        "company": "Clinic A",      // NEW - Shows billing clinic
        "grand_total": 500,
        "outstanding_amount": 500,
        "status": "Unpaid"
      }
    ],
    "total_count": 8
  }
}
```

---

### 9. Get Prescriptions API (Modified)

**Endpoint:** `GET /api/method/mob_clinic.mob_clinic.api.prescription.get_prescriptions`

**Query Parameters:**
```
?clinic=Clinic%20A          // NEW - Optional clinic filter
&patient_id=PAT-00001
&limit_page_length=20
```

**Response:**
```json
{
  "message": {
    "data": [
      {
        "encounter_id": "ENC-00045",
        "patient_name": "John Smith",
        "company": "Clinic A",      // NEW - Shows clinic
        "encounter_date": "2025-12-01",
        "medications": [...]
      }
    ],
    "total_count": 12
  }
}
```

---

### 10. Create Prescription API (Modified)

**Endpoint:** `POST /api/method/mob_clinic.mob_clinic.api.prescription.create_prescription`

**Request:**
```json
{
  "patient_id": "PAT-00001",
  "encounter_date": "2025-12-01",
  "symptoms": "Fever, headache",
  "diagnosis": "Viral infection",
  "medications": [...],
  "clinic": "Clinic A"              // NEW - Optional
}
```

**Response:**
```json
{
  "message": {
    "status": "success",
    "encounter_id": "ENC-00046",
    "company": "Clinic A"             // NEW - Assigned clinic
  }
}
```

---

## Testing

### Unit Tests

**File:** `mob_clinic/tests/test_clinic_helpers.py`

Tests core clinic helper functions:
- ✅ `test_get_accessible_companies` - Verify practitioner clinic access
- ✅ `test_resolve_active_clinic_explicit` - Test explicit clinic parameter
- ✅ `test_resolve_active_clinic_session` - Test session-based resolution
- ✅ `test_resolve_active_clinic_fallback` - Test primary_company fallback
- ✅ `test_validate_practitioner_access` - Test access validation
- ✅ `test_apply_clinic_filter` - Test filter application

**Run Tests:**
```bash
cd /workspace/development/frappe-bench
bench run-tests --app mob_clinic --module mob_clinic.tests.test_clinic_helpers
```

### Integration Tests

**File:** `mob_clinic/tests/test_clinic_api.py`

Tests API endpoints with clinic scoping:
- ✅ `test_switch_clinic` - Test clinic switching
- ✅ `test_create_appointment_with_clinic` - Test appointment clinic assignment
- ✅ `test_create_patient_with_clinic` - Test patient clinic assignment
- ⏭️ `test_create_invoice_with_clinic` - Skipped (requires full ERP setup)

**Run Tests:**
```bash
bench run-tests --app mob_clinic --module mob_clinic.tests.test_clinic_api
```

---

## Migration Guide

### For Existing Installations

#### 1. Run Database Migration

```bash
# Navigate to frappe-bench directory
cd /workspace/development/frappe-bench

# Run migration to add custom fields
bench --site [your-site] migrate

# Or execute specific patch
bench --site [your-site] execute mob_clinic.mob_clinic.patches.v1_0.install_custom_fields.execute
```

#### 2. Assign Primary Clinics

After migration, assign primary clinics to existing practitioners:

```bash
# Via bench console
bench --site [your-site] console

# In console:
import frappe

# Get all practitioners
practitioners = frappe.get_all("Healthcare Practitioner", fields=["name"])

# Assign primary company
for prac in practitioners:
    doc = frappe.get_doc("Healthcare Practitioner", prac.name)
    doc.primary_company = "Your Default Clinic Name"  # Replace with actual clinic
    doc.save()
    print(f"Assigned {prac.name} to default clinic")

frappe.db.commit()
```

#### 3. Assign Patients to Clinics (Optional)

If you want to assign existing patients to clinics:

```bash
# Via bench console
bench --site [your-site] console

# In console:
import frappe

patients = frappe.get_all("Patient", fields=["name"])

for patient in patients:
    doc = frappe.get_doc("Patient", patient.name)
    doc.primary_clinic = "Your Default Clinic Name"
    doc.save()

frappe.db.commit()
```

#### 4. Frontend Update Checklist

- [ ] Update login flow to store `clinics` and `active_clinic`
- [ ] Add clinic selector component in navigation
- [ ] Update all API calls to include optional `clinic` parameter
- [ ] Add clinic filter to list views (patients, appointments, etc.)
- [ ] Handle 403 permission errors for unauthorized clinic access
- [ ] Test clinic switching functionality
- [ ] Update patient creation form to assign clinic
- [ ] Test data isolation between clinics

---

## Best Practices

### 1. Always Use Active Clinic

```javascript
// ✅ Good - Uses active clinic from context
const activeClinic = useActiveClinic();
await createAppointment({ ...data, clinic: activeClinic });

// ❌ Bad - Hardcoded clinic
await createAppointment({ ...data, clinic: "Clinic A" });
```

### 2. Refresh Data on Clinic Switch

```javascript
// Listen for clinic change events
useEffect(() => {
  refreshData();
}, [activeClinic]);
```

### 3. Show Clinic Context to User

```javascript
// Always display which clinic is active
<Header>
  <Text>Active Clinic: {activeClinic}</Text>
  <ClinicSwitcher />
</Header>
```

### 4. Handle Permission Errors Gracefully

```javascript
if (error.status === 403 && error.exc_type === 'PermissionError') {
  showAlert('You do not have access to this clinic');
  // Optionally redirect to primary clinic
  await switchClinic(user.primary_clinic);
}
```

---

## Troubleshooting

### Issue: Login doesn't return clinics

**Solution:** Ensure practitioner has `primary_company` set:
```sql
UPDATE `tabHealthcare Practitioner` 
SET primary_company = 'Your Clinic Name' 
WHERE user_id = 'practitioner@example.com';
```

### Issue: 403 Permission Error

**Cause:** Practitioner doesn't have access to requested clinic.

**Solution:** 
1. Check practitioner's `primary_company` field
2. Verify clinic name matches exactly (case-sensitive)
3. In future: Add practitioner to additional clinics via `practitioner_companies` child table

### Issue: Data shows from wrong clinic

**Cause:** Clinic filter not applied or wrong clinic in session.

**Solution:**
1. Verify `activeClinic` state is updated
2. Check API calls include `clinic` parameter
3. Use browser dev tools to inspect API requests

---

## Future Enhancements

### 1. Child Table for Additional Clinics

Add `practitioner_companies` child table to Healthcare Practitioner to support multiple clinic access beyond primary.

### 2. Clinic-Specific Settings

- Different working hours per clinic
- Different fee structures per clinic
- Clinic-specific templates

### 3. Cross-Clinic Reports

- Consolidated reports across all accessible clinics
- Comparison dashboards

### 4. Referral System

- Refer patients between clinics
- Track inter-clinic referrals

---

## Support

For issues or questions:
1. Check this documentation
2. Review test files for examples
3. Check error logs: `frappe-bench/logs/`
4. Consult Frappe/ERPNext documentation

---

## Appendix A: Complete API Endpoint List

| Endpoint | Method | Clinic Support | Description |
|----------|--------|----------------|-------------|
| `/api/method/mob_clinic.mob_clinic.api.auth.mobile_login` | POST | ✅ Returns clinics | Enhanced login |
| `/api/method/mob_clinic.mob_clinic.api.auth.switch_clinic` | POST | ✅ New | Switch active clinic |
| `/api/method/mob_clinic.mob_clinic.api.patient.get_patients` | GET | ✅ Filter param | Get patients by clinic |
| `/api/method/mob_clinic.mob_clinic.api.patient.create_patient` | POST | ✅ Clinic param | Assign patient to clinic |
| `/api/method/mob_clinic.mob_clinic.api.appointment.get_appointments` | GET | ✅ Filter param | Get appointments by clinic |
| `/api/method/mob_clinic.mob_clinic.api.appointment.create_appointment` | POST | ✅ Clinic param | Create clinic appointment |
| `/api/method/mob_clinic.mob_clinic.api.prescription.get_prescriptions` | GET | ✅ Filter param | Get prescriptions by clinic |
| `/api/method/mob_clinic.mob_clinic.api.prescription.create_prescription` | POST | ✅ Clinic param | Create clinic prescription |
| `/api/method/mob_clinic.mob_clinic.api.payment.get_invoices` | GET | ✅ Filter param | Get invoices by clinic |
| `/api/method/mob_clinic.mob_clinic.api.payment.create_invoice` | POST | ✅ Clinic param | Create clinic invoice |

---

## Appendix B: Code Examples

### React Native Complete Example

```javascript
import React, { useState, useEffect, createContext, useContext } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Clinic Context
const ClinicContext = createContext();

export function ClinicProvider({ children }) {
  const [clinics, setClinics] = useState([]);
  const [activeClinic, setActiveClinic] = useState(null);

  useEffect(() => {
    loadClinicData();
  }, []);

  async function loadClinicData() {
    const savedClinics = await AsyncStorage.getItem('user_clinics');
    const savedActive = await AsyncStorage.getItem('active_clinic');
    
    if (savedClinics) setClinics(JSON.parse(savedClinics));
    if (savedActive) setActiveClinic(savedActive);
  }

  async function switchClinic(clinic) {
    try {
      const response = await api.post('/auth/switch_clinic', { clinic });
      
      if (response.data.message.active_clinic) {
        setActiveClinic(clinic);
        await AsyncStorage.setItem('active_clinic', clinic);
        return true;
      }
    } catch (error) {
      console.error('Switch clinic error:', error);
      return false;
    }
  }

  return (
    <ClinicContext.Provider value={{ 
      clinics, 
      activeClinic, 
      switchClinic,
      setClinics
    }}>
      {children}
    </ClinicContext.Provider>
  );
}

export const useClinic = () => useContext(ClinicContext);

// Usage in Login Screen
function LoginScreen() {
  const { setClinics, setActiveClinic } = useClinic();

  async function handleLogin(email, password) {
    const response = await api.post('/auth/mobile_login', {
      usr: email,
      pwd: password
    });

    if (response.data.message.status === 'success') {
      const user = response.data.message.user;
      
      // Store clinic data
      setClinics(user.clinics);
      setActiveClinic(user.active_clinic);
      
      await AsyncStorage.setItem('user_clinics', JSON.stringify(user.clinics));
      await AsyncStorage.setItem('active_clinic', user.active_clinic);
      
      // Navigate to home
      navigation.navigate('Home');
    }
  }

  return <LoginForm onSubmit={handleLogin} />;
}

// Usage in Patient List Screen
function PatientListScreen() {
  const [patients, setPatients] = useState([]);
  const { activeClinic } = useClinic();

  useEffect(() => {
    if (activeClinic) {
      loadPatients();
    }
  }, [activeClinic]);

  async function loadPatients() {
    const response = await api.get('/patient/get_patients', {
      params: { clinic: activeClinic }
    });
    
    setPatients(response.data.message.data);
  }

  return (
    <View>
      <Text>Patients - {activeClinic}</Text>
      <FlatList
        data={patients}
        renderItem={({ item }) => <PatientCard patient={item} />}
      />
    </View>
  );
}

// Clinic Selector Component
function ClinicSelector() {
  const { clinics, activeClinic, switchClinic } = useClinic();
  const [visible, setVisible] = useState(false);

  async function handleSelect(clinic) {
    const success = await switchClinic(clinic);
    if (success) {
      setVisible(false);
      Alert.alert('Success', `Switched to ${clinic}`);
    } else {
      Alert.alert('Error', 'Failed to switch clinic');
    }
  }

  return (
    <>
      <TouchableOpacity onPress={() => setVisible(true)}>
        <Text>{activeClinic}</Text>
        <Icon name="chevron-down" />
      </TouchableOpacity>

      <Modal visible={visible} onClose={() => setVisible(false)}>
        {clinics.map(clinic => (
          <TouchableOpacity 
            key={clinic}
            onPress={() => handleSelect(clinic)}
          >
            <Text style={clinic === activeClinic ? styles.active : null}>
              {clinic}
            </Text>
          </TouchableOpacity>
        ))}
      </Modal>
    </>
  );
}
```

---

**End of Document**
