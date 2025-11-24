# Mobile Clinic API Endpoints Summary

## Patient Endpoints

### Delete Patient
**Endpoint:** `/api/method/mob_clinic.mob_clinic.api.patient.delete_patient`  
**Methods:** DELETE, POST  
**Parameters:**
- `patient_id` (required): Patient ID

**Response:**
```json
{
  "message": "Patient deleted successfully",
  "data": {
    "patient_id": "PAT-00001",
    "patient_name": "John Doe",
    "mobile": "1234567890"
  }
}
```

**Validation:**
- Cannot delete patients with active appointments
- Cannot delete patients with medical records

---

## Appointment Endpoints

### Delete Appointment
**Endpoint:** `/api/method/mob_clinic.mob_clinic.api.appointment.delete_appointment`  
**Methods:** DELETE, POST  
**Parameters:**
- `appointment_id` (required): Appointment ID

**Response:**
```json
{
  "message": "Appointment deleted successfully",
  "data": {
    "appointment_id": "HLC-APP-2025-00001",
    "patient_name": "John Doe",
    "appointment_date": "2025-11-21",
    "appointment_time": "10:00:00"
  }
}
```

**Validation:**
- Cannot delete submitted appointments
- Cannot delete invoiced appointments

---

### Add to Today's Queue
**Endpoint:** `/api/method/mob_clinic.mob_clinic.api.appointment.add_to_todays_queue`  
**Method:** POST  
**Parameters:**
- `patient_id` (required): Patient ID
- `duration` (optional, default: 30): Appointment duration in minutes
- `chief_complaint` (optional): Chief complaint
- `notes` (optional): Additional notes
- `appointment_type` (optional, default: "Walk In"): Appointment type

**Response:**
```json
{
  "message": "Patient added to today's queue successfully",
  "queue_position": 3,
  "data": {
    "appointment_id": "HLC-APP-2025-00199",
    "patient_id": "Ananth.C Jayan",
    "patient_name": "Ananth.C Jayan",
    "appointment_date": "2025-11-21",
    "appointment_time": "10:30:00",
    "status": "Open",
    "queue_position": 3
  }
}
```

**Features:**
- Automatically finds the nearest available slot
- If no slots available, adds to end of queue
- Returns queue position
- Creates appointment with status "Open"

---

### Get Today's Queue
**Endpoint:** `/api/method/mob_clinic.mob_clinic.api.appointment.get_todays_queue`  
**Method:** GET  
**Parameters:** None (uses current practitioner from session)

**Response:**
```json
{
  "message": "success",
  "data": {
    "date": "2025-11-21",
    "total_queue": 5,
    "queue": [
      {
        "name": "HLC-APP-2025-00195",
        "patient": "PAT-00001",
        "patient_name": "John Doe",
        "patient_mobile": "1234567890",
        "appointment_time": "09:00:00",
        "duration": 30,
        "status": "Open",
        "appointment_type": "Walk In",
        "chief_complaint": "Headache",
        "queue_position": 1,
        "estimated_time": "09:00:00"
      },
      {
        "name": "HLC-APP-2025-00196",
        "patient": "PAT-00002",
        "patient_name": "Jane Smith",
        "patient_mobile": "0987654321",
        "appointment_time": "09:30:00",
        "duration": 30,
        "status": "Open",
        "appointment_type": "Follow-up",
        "chief_complaint": "Follow-up visit",
        "queue_position": 2,
        "estimated_time": "09:30:00"
      }
    ]
  }
}
```

**Features:**
- Returns today's appointments for current practitioner
- Excludes cancelled appointments
- Ordered by appointment time
- Includes queue position for each appointment
- Shows estimated time based on queue
- Includes patient contact information

---

## Prescription Endpoints

### Delete Prescription
**Endpoint:** `/api/method/mob_clinic.mob_clinic.api.prescription.delete_prescription`  
**Methods:** DELETE, POST  
**Parameters:**
- `record_id` (required): Prescription/Patient Encounter ID

**Response:**
```json
{
  "message": "Prescription deleted successfully",
  "data": {
    "record_id": "HLC-ENC-2025-00001",
    "patient_name": "John Doe",
    "encounter_date": "2025-11-21"
  }
}
```

**Validation:**
- Cannot delete submitted prescriptions
- Cannot delete invoiced prescriptions

---

### Update Prescription
**Endpoint:** `/api/method/mob_clinic.mob_clinic.api.prescription.update_prescription`  
**Method:** POST  
**Parameters:**
- `record_id` (required): Prescription ID
- `chief_complaint` (optional): Chief complaint
- `symptoms` (optional): Symptoms text
- `diagnosis` (optional): Diagnosis text
- `treatment_plan` (optional): Treatment plan text
- `status` (optional): Status ("Active" will be converted to "Open")
- `medical_code` (optional): Medical code

**Response:**
```json
{
  "message": "Prescription updated successfully",
  "data": {
    "record_id": "HLC-ENC-2025-00079",
    "updated_fields": ["chief_complaint", "symptoms", "diagnosis", "treatment_plan", "status"],
    "status": "Active",
    "medications_count": 0,
    "investigations_count": 0
  }
}
```

**Note:** Status "Active" from mobile app is automatically converted to "Open" (which is then returned as "Active" in responses)

---

## Frontend Usage Examples

### Delete Patient
```javascript
async function deletePatient(patientId) {
  const response = await fetch(
    `${API_URL}/api/method/mob_clinic.mob_clinic.api.patient.delete_patient`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ patient_id: patientId })
    }
  );
  return response.json();
}
```

### Delete Appointment
```javascript
async function deleteAppointment(appointmentId) {
  const response = await fetch(
    `${API_URL}/api/method/mob_clinic.mob_clinic.api.appointment.delete_appointment`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ appointment_id: appointmentId })
    }
  );
  return response.json();
}
```

### Add to Today's Queue
```javascript
async function addToQueue(patientId, chiefComplaint = '') {
  const response = await fetch(
    `${API_URL}/api/method/mob_clinic.mob_clinic.api.appointment.add_to_todays_queue`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        patient_id: patientId,
        duration: 30,
        chief_complaint: chiefComplaint
      })
    }
  );
  return response.json();
}

// Usage
addToQueue('PAT-00001', 'Routine checkup')
  .then(result => {
    console.log(`Added to queue at position ${result.queue_position}`);
  });
```

### Get Today's Queue
```javascript
async function getTodaysQueue() {
  const response = await fetch(
    `${API_URL}/api/method/mob_clinic.mob_clinic.api.appointment.get_todays_queue`,
    {
      method: 'GET',
      credentials: 'include'
    }
  );
  const result = await response.json();
  return result.message.data;
}

// Usage
getTodaysQueue().then(queueData => {
  console.log(`Total patients in queue: ${queueData.total_queue}`);
  queueData.queue.forEach(patient => {
    console.log(`${patient.queue_position}. ${patient.patient_name} - ${patient.appointment_time}`);
  });
});
```

### Update Prescription
```javascript
async function updatePrescription(recordId, updates) {
  const response = await fetch(
    `${API_URL}/api/method/mob_clinic.mob_clinic.api.prescription.update_prescription`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        record_id: recordId,
        ...updates
      })
    }
  );
  return response.json();
}

// Usage
updatePrescription('HLC-ENC-2025-00079', {
  chief_complaint: 'Updated complaint',
  symptoms: 'Updated symptoms',
  diagnosis: 'Updated diagnosis',
  treatment_plan: 'Updated plan',
  status: 'Active'
});
```

---

## Error Responses

All endpoints follow a consistent error response format:

### 404 Not Found
```json
{
  "exc_type": "NotFound",
  "message": "Patient PAT-00001 not found"
}
```

### 400 Validation Error
```json
{
  "exc_type": "ValidationError",
  "message": "Cannot delete patient with 3 active appointments. Please cancel appointments first."
}
```

### 403 Permission Error
```json
{
  "exc_type": "PermissionError",
  "message": "Healthcare Practitioner profile not found"
}
```

### 500 Server Error
```json
{
  "exc_type": "ServerError",
  "message": "Error deleting patient: [error details]"
}
```

---

## Summary of All New Endpoints

1. **Delete Patient** - Remove patient from system (with validations)
2. **Delete Appointment** - Permanently delete appointment (with validations)
3. **Add to Today's Queue** - Quick add patient to today's schedule with automatic slot finding
4. **Get Today's Queue** - View all today's appointments in order with queue positions
5. **Delete Prescription** - Remove prescription/medical record (already existed, documented here)
6. **Update Prescription** - Modify prescription details (already existed, now with proper field mapping)

All endpoints include:
- Proper HTTP status codes
- Consistent error handling
- Permission checks
- Data validation
- Transaction commits
- Detailed logging
