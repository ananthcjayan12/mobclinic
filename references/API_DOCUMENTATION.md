# DentCharts Clinic Management - API Documentation

This document outlines all the API endpoints required for the DentCharts mobile application backend using Frappe framework.

## Table of Contents
1. [Authentication APIs](#1-authentication-apis)
2. [User/Doctor Management APIs](#2-userdoctor-management-apis)
3. [Patient Management APIs](#3-patient-management-apis)
4. [Appointment Management APIs](#4-appointment-management-apis)
5. [Prescription/Medical History APIs](#5-prescriptionmedical-history-apis)
6. [Payment/Invoice Management APIs](#6-paymentinvoice-management-apis)
7. [File Upload APIs](#7-file-upload-apis)
8. [Dashboard/Statistics APIs](#8-dashboardstatistics-apis)

---

## 1. Authentication APIs

### 1.1 Login
**Endpoint:** `POST /api/method/login`

**Description:** Authenticates a doctor/user with email/phone and password.

**Request Body:**
```json
{
  "usr": "pooja@smilecraft.com",  // or phone: "+919400475408"
  "pwd": "password123"
}
```

**Response (Success):**
```json
{
  "message": "Logged In",
  "home_page": "/app",
  "full_name": "Dr Pooja Satheesh",
  "user": {
    "id": "1",
    "name": "Dr Pooja Satheesh",
    "email": "pooja@smilecraft.com",
    "phone": "+919400475408",
    "role": "doctor",
    "avatar": "/files/avatar.jpg",
    "clinic": {
      "name": "Dr Pooja's Smilecraft Dental Clinic",
      "address": "21, Block -C, Road 132, Gulshan, Dhaka - 1211",
      "phone": "+8801234567890"
    }
  }
}
```

**Response (Error):**
```json
{
  "exc_type": "AuthenticationError",
  "message": "Invalid credentials"
}
```

---

### 1.2 Logout
**Endpoint:** `POST /api/method/logout`

**Description:** Logs out the current user session.

**Response:**
```json
{
  "message": "Logged Out"
}
```

---

### 1.3 Register
**Endpoint:** `POST /api/method/register`

**Description:** Registers a new doctor/clinic account.

**Request Body:**
```json
{
  "full_name": "Dr Pooja Satheesh",
  "email": "pooja@smilecraft.com",
  "phone": "+919400475408",
  "password": "password123",
  "clinic_name": "Dr Pooja's Smilecraft Dental Clinic",
  "clinic_address": "21, Block -C, Road 132, Gulshan, Dhaka - 1211",
  "specialization": "Dental Surgeon",
  "registration_number": "MCI-12345",
  "qualification": "BDS, MDS"
}
```

**Response:**
```json
{
  "message": "Registration successful",
  "user_id": "DOC001"
}
```

---

## 2. User/Doctor Management APIs

### 2.1 Get Doctor Profile
**Endpoint:** `GET /api/resource/Doctor/{doctor_id}`

**Description:** Retrieves the logged-in doctor's profile information.

**Response:**
```json
{
  "data": {
    "id": "DOC001",
    "name": "Dr. Kamal Rahman",
    "phone": "+919400475408",
    "email": "drkamal@dentalcare.com",
    "specialization": "Dental Surgeon",
    "experience": "8 years",
    "qualification": "BDS, MDS",
    "registration_number": "MCI-12345",
    "avatar": "/files/doctor_avatar.jpg",
    "clinic": {
      "name": "DentCare Clinic",
      "address": "21, Block -C, Road 132, Gulshan, Dhaka - 1211",
      "phone": "+8801234567890",
      "email": "info@dentcare.com",
      "website": "www.dentcare.com",
      "timings": "9:00 AM - 6:00 PM",
      "working_days": "Monday - Saturday"
    },
    "services": [
      "General Dentistry",
      "Root Canal Treatment",
      "Dental Implants",
      "Teeth Whitening",
      "Orthodontics"
    ]
  }
}
```

---

### 2.2 Update Doctor Profile
**Endpoint:** `PUT /api/resource/Doctor/{doctor_id}`

**Description:** Updates doctor/clinic profile information.

**Request Body:**
```json
{
  "name": "Dr. Kamal Rahman",
  "phone": "+919400475408",
  "email": "drkamal@dentalcare.com",
  "clinic": {
    "name": "DentCare Clinic",
    "address": "21, Block -C, Road 132, Gulshan, Dhaka - 1211",
    "phone": "+8801234567890",
    "timings": "9:00 AM - 6:00 PM"
  }
}
```

**Response:**
```json
{
  "message": "Profile updated successfully",
  "data": { /* Updated doctor object */ }
}
```

---

## 3. Patient Management APIs

### 3.1 Get All Patients
**Endpoint:** `GET /api/resource/Patient`

**Description:** Retrieves list of all patients with pagination and search.

**Query Parameters:**
- `fields` - Comma-separated list of fields to return
- `filters` - JSON string of filters
- `limit_start` - Pagination start (default: 0)
- `limit_page_length` - Number of records per page (default: 20)
- `order_by` - Sort order (e.g., "creation desc")

**Example:**
```
GET /api/resource/Patient?fields=["name","patient_id","phone","age"]&limit_page_length=20
```

**Response:**
```json
{
  "data": [
    {
      "name": "Sample Patient Name",
      "patient_id": "P0001",
      "age": 33,
      "gender": "Male",
      "phone": "+919400475408",
      "email": "patient@example.com",
      "avatar": "/files/patient_avatar.jpg"
    },
    {
      "name": "John Doe",
      "patient_id": "P0002",
      "age": 45,
      "gender": "Male",
      "phone": "+918765432109",
      "email": "john.doe@example.com",
      "avatar": "/files/patient_avatar.jpg"
    }
  ]
}
```

---

### 3.2 Get Patient by ID
**Endpoint:** `GET /api/resource/Patient/{patient_id}`

**Description:** Retrieves detailed information for a specific patient.

**Response:**
```json
{
  "data": {
    "patient_id": "P0001",
    "name": "Sample Patient Name",
    "age": 33,
    "gender": "Male",
    "date_of_birth": "1989-08-29",
    "phone": "+919400475408",
    "email": "patient@example.com",
    "address": "21, Block -C, Road 132. Gulshan, Dhaka - 1211",
    "avatar": "/files/patient_avatar.jpg",
    "medical_history": {
      "diabetic": true,
      "blood_pressure": "Moderate High",
      "cardiac_history": false,
      "allergies": false,
      "family_heart_disease": false,
      "covid_vaccinated": true,
      "occupation": "Software Developer"
    },
    "created_at": "2024-01-15T10:30:00",
    "last_visit": "2025-01-25T14:30:00"
  }
}
```

---

### 3.3 Create New Patient
**Endpoint:** `POST /api/resource/Patient`

**Description:** Creates a new patient record.

**Request Body:**
```json
{
  "name": "Sample Patient Name",
  "age": 33,
  "gender": "Male",
  "date_of_birth": "1989-08-29",
  "phone": "+919400475408",
  "email": "patient@example.com",
  "address": "21, Block -C, Road 132. Gulshan, Dhaka - 1211",
  "occupation": "Software Developer",
  "medical_history": {
    "diabetic": true,
    "blood_pressure": "Moderate High",
    "cardiac_history": false,
    "allergies": false,
    "family_heart_disease": false,
    "covid_vaccinated": true
  }
}
```

**Response:**
```json
{
  "data": {
    "name": "P0001",
    "patient_id": "P0001",
    "message": "Patient created successfully"
  }
}
```

---

### 3.4 Update Patient
**Endpoint:** `PUT /api/resource/Patient/{patient_id}`

**Description:** Updates existing patient information.

**Request Body:**
```json
{
  "phone": "+919400475408",
  "email": "newemail@example.com",
  "address": "New Address",
  "medical_history": {
    "diabetic": true,
    "blood_pressure": "Normal"
  }
}
```

**Response:**
```json
{
  "message": "Patient updated successfully",
  "data": { /* Updated patient object */ }
}
```

---

### 3.5 Delete Patient
**Endpoint:** `DELETE /api/resource/Patient/{patient_id}`

**Description:** Soft deletes a patient record.

**Response:**
```json
{
  "message": "Patient deleted successfully"
}
```

---

### 3.6 Search Patients
**Endpoint:** `GET /api/resource/Patient?filters=[["name","like","%search_term%"]]`

**Description:** Searches patients by name, phone, or patient ID.

**Query Parameters:**
- `search_term` - Search query

**Response:**
```json
{
  "data": [
    {
      "patient_id": "P0001",
      "name": "Sample Patient Name",
      "phone": "+919400475408",
      "age": 33
    }
  ]
}
```

---

## 4. Appointment Management APIs

### 4.1 Get All Appointments
**Endpoint:** `GET /api/resource/Appointment`

**Description:** Retrieves appointments with filtering by date range.

**Query Parameters:**
- `start_date` - Filter appointments from this date (YYYY-MM-DD)
- `end_date` - Filter appointments until this date (YYYY-MM-DD)
- `status` - Filter by status (confirmed, pending, scheduled, cancelled)
- `limit_page_length` - Number of records

**Example:**
```
GET /api/resource/Appointment?filters=[["appointment_date",">=","2025-01-20"]]
```

**Response:**
```json
{
  "data": [
    {
      "name": "APT-001",
      "appointment_id": "APT-001",
      "patient_id": "P0001",
      "patient_name": "Sample Patient Name",
      "appointment_date": "2025-09-23",
      "appointment_time": "02:00 PM",
      "appointment_type": "Regular checkup",
      "status": "confirmed",
      "notes": "Regular checkup appointment",
      "created_at": "2025-09-20T10:00:00"
    },
    {
      "name": "APT-002",
      "appointment_id": "APT-002",
      "patient_id": "P0002",
      "patient_name": "John Doe",
      "appointment_date": "2025-09-23",
      "appointment_time": "02:00 PM",
      "appointment_type": "Emergency",
      "status": "scheduled",
      "notes": "Emergency consultation",
      "created_at": "2025-09-22T14:30:00"
    }
  ]
}
```

---

### 4.2 Get Appointment by ID
**Endpoint:** `GET /api/resource/Appointment/{appointment_id}`

**Description:** Retrieves detailed information for a specific appointment.

**Response:**
```json
{
  "data": {
    "appointment_id": "APT-001",
    "patient_id": "P0001",
    "patient_name": "Sample Patient Name",
    "patient_phone": "+919400475408",
    "appointment_date": "2025-09-23",
    "appointment_time": "02:00 PM",
    "appointment_type": "Regular checkup",
    "status": "confirmed",
    "notes": "Patient requested morning slot",
    "doctor_id": "DOC001",
    "created_at": "2025-09-20T10:00:00",
    "updated_at": "2025-09-22T11:00:00"
  }
}
```

---

### 4.3 Create New Appointment
**Endpoint:** `POST /api/resource/Appointment`

**Description:** Creates a new appointment.

**Request Body:**
```json
{
  "patient_id": "P0001",
  "appointment_date": "2025-09-25",
  "appointment_time": "10:00 AM",
  "appointment_type": "Regular checkup",
  "status": "scheduled",
  "notes": "Patient complained of tooth pain",
  "doctor_id": "DOC001"
}
```

**Response:**
```json
{
  "data": {
    "name": "APT-003",
    "appointment_id": "APT-003",
    "message": "Appointment created successfully"
  }
}
```

---

### 4.4 Update Appointment
**Endpoint:** `PUT /api/resource/Appointment/{appointment_id}`

**Description:** Updates an existing appointment (reschedule, change status, etc.).

**Request Body:**
```json
{
  "appointment_date": "2025-09-26",
  "appointment_time": "03:00 PM",
  "status": "confirmed",
  "notes": "Rescheduled as per patient request"
}
```

**Response:**
```json
{
  "message": "Appointment updated successfully",
  "data": { /* Updated appointment object */ }
}
```

---

### 4.5 Cancel Appointment
**Endpoint:** `PUT /api/resource/Appointment/{appointment_id}`

**Description:** Cancels an appointment.

**Request Body:**
```json
{
  "status": "cancelled",
  "cancellation_reason": "Patient unavailable"
}
```

**Response:**
```json
{
  "message": "Appointment cancelled successfully"
}
```

---

### 4.6 Get Appointments by Date
**Endpoint:** `GET /api/resource/Appointment?filters=[["appointment_date","=","2025-09-23"]]`

**Description:** Retrieves all appointments for a specific date.

**Response:**
```json
{
  "data": [
    {
      "appointment_id": "APT-001",
      "patient_name": "Sample Patient Name",
      "appointment_time": "02:00 PM",
      "appointment_type": "Regular checkup",
      "status": "confirmed"
    }
  ]
}
```

---

## 5. Prescription/Medical History APIs

### 5.1 Get Patient Prescriptions
**Endpoint:** `GET /api/resource/Prescription?filters=[["patient_id","=","P0001"]]`

**Description:** Retrieves all prescriptions/medical history for a patient.

**Response:**
```json
{
  "data": [
    {
      "name": "PRESC-001",
      "prescription_id": "PRESC-001",
      "patient_id": "P0001",
      "prescription_date": "2025-01-25",
      "doctor_id": "DOC001",
      "investigations": [
        "Complete Blood Count (CBC)",
        "Blood Sugar Level (Fasting)",
        "Dental X-Ray"
      ],
      "medications": [
        "Paracetamol 500mg - 2 times daily for 3 days",
        "Amoxicillin 250mg - 3 times daily for 5 days"
      ],
      "notes": "Patient shows good response to treatment. Continue medication as prescribed.",
      "attachments": [
        {
          "file_name": "prescription_25012025.pdf",
          "file_url": "/files/prescription_25012025.pdf",
          "file_type": "application/pdf"
        },
        {
          "file_name": "xray_25012025.jpg",
          "file_url": "/files/xray_25012025.jpg",
          "file_type": "image/jpeg"
        }
      ],
      "created_at": "2025-01-25T15:30:00"
    },
    {
      "name": "PRESC-002",
      "prescription_id": "PRESC-002",
      "patient_id": "P0001",
      "prescription_date": "2024-12-05",
      "doctor_id": "DOC001",
      "investigations": [
        "Activated Partial thromboplastin time (APTT)",
        "Dehydroepiandrosterone sulphate (blood)",
        "CA 125 (Serum)"
      ],
      "medications": [
        "Metronidazole 400mg - 3 times daily for 7 days",
        "Chlorhexidine mouthwash - twice daily"
      ],
      "notes": "Monitor for allergic reactions. Follow-up in 1 week.",
      "attachments": [],
      "created_at": "2024-12-05T10:15:00"
    }
  ]
}
```

---

### 5.2 Get Prescription by ID
**Endpoint:** `GET /api/resource/Prescription/{prescription_id}`

**Description:** Retrieves detailed information for a specific prescription.

**Response:**
```json
{
  "data": {
    "prescription_id": "PRESC-001",
    "patient_id": "P0001",
    "patient_name": "Sample Patient Name",
    "prescription_date": "2025-01-25",
    "doctor_id": "DOC001",
    "doctor_name": "Dr Pooja Satheesh",
    "investigations": [
      "Complete Blood Count (CBC)",
      "Blood Sugar Level (Fasting)",
      "Dental X-Ray"
    ],
    "medications": [
      "Paracetamol 500mg - 2 times daily for 3 days",
      "Amoxicillin 250mg - 3 times daily for 5 days"
    ],
    "notes": "Patient shows good response to treatment.",
    "attachments": [
      {
        "file_name": "prescription_25012025.pdf",
        "file_url": "/files/prescription_25012025.pdf",
        "file_type": "application/pdf",
        "file_size": 1024000
      }
    ],
    "created_at": "2025-01-25T15:30:00"
  }
}
```

---

### 5.3 Create New Prescription
**Endpoint:** `POST /api/resource/Prescription`

**Description:** Creates a new prescription/medical record.

**Request Body:**
```json
{
  "patient_id": "P0001",
  "prescription_date": "2025-01-25",
  "doctor_id": "DOC001",
  "investigations": [
    "Complete Blood Count (CBC)",
    "Blood Sugar Level (Fasting)",
    "Dental X-Ray"
  ],
  "medications": [
    "Paracetamol 500mg - 2 times daily for 3 days",
    "Amoxicillin 250mg - 3 times daily for 5 days"
  ],
  "notes": "Patient shows good response to treatment.",
  "attachments": [
    {
      "file_url": "/files/prescription_25012025.pdf"
    }
  ]
}
```

**Response:**
```json
{
  "data": {
    "name": "PRESC-003",
    "prescription_id": "PRESC-003",
    "message": "Prescription created successfully"
  }
}
```

---

### 5.4 Update Prescription
**Endpoint:** `PUT /api/resource/Prescription/{prescription_id}`

**Description:** Updates an existing prescription.

**Request Body:**
```json
{
  "investigations": [
    "Complete Blood Count (CBC)",
    "Blood Sugar Level (Fasting)",
    "Dental X-Ray",
    "Vitamin D Test"
  ],
  "medications": [
    "Paracetamol 500mg - 2 times daily for 5 days",
    "Amoxicillin 250mg - 3 times daily for 7 days",
    "Ibuprofen 400mg - as needed for pain"
  ],
  "notes": "Extended medication duration based on patient condition."
}
```

**Response:**
```json
{
  "message": "Prescription updated successfully",
  "data": { /* Updated prescription object */ }
}
```

---

### 5.5 Delete Prescription
**Endpoint:** `DELETE /api/resource/Prescription/{prescription_id}`

**Description:** Deletes a prescription record.

**Response:**
```json
{
  "message": "Prescription deleted successfully"
}
```

---

## 6. Payment/Invoice Management APIs

### 6.1 Get Patient Payments
**Endpoint:** `GET /api/resource/Payment?filters=[["patient_id","=","P0001"]]`

**Description:** Retrieves all payment records for a patient.

**Response:**
```json
{
  "data": [
    {
      "name": "PAY-001",
      "payment_id": "PAY001",
      "invoice_number": "INV-001",
      "patient_id": "P0001",
      "patient_name": "Sample Patient Name",
      "payment_date": "2025-01-25",
      "treatment": "Root Canal Treatment",
      "total_amount": 15000,
      "paid_amount": 10000,
      "pending_amount": 5000,
      "status": "Partially Paid",
      "payment_method": "Cash",
      "next_due_date": "2025-02-15",
      "created_at": "2025-01-25T16:00:00"
    },
    {
      "name": "PAY-002",
      "payment_id": "PAY002",
      "invoice_number": "INV-002",
      "patient_id": "P0001",
      "patient_name": "Sample Patient Name",
      "payment_date": "2024-12-05",
      "treatment": "Dental Cleaning & Consultation",
      "total_amount": 3500,
      "paid_amount": 3500,
      "pending_amount": 0,
      "status": "Paid",
      "payment_method": "UPI",
      "next_due_date": null,
      "created_at": "2024-12-05T11:30:00"
    }
  ]
}
```

---

### 6.2 Get Payment by ID
**Endpoint:** `GET /api/resource/Payment/{payment_id}`

**Description:** Retrieves detailed information for a specific payment/invoice.

**Response:**
```json
{
  "data": {
    "payment_id": "PAY001",
    "invoice_number": "INV-001",
    "patient_id": "P0001",
    "patient_name": "Sample Patient Name",
    "payment_date": "2025-01-25",
    "treatment": "Root Canal Treatment",
    "treatment_details": "Root canal treatment for upper molar",
    "total_amount": 15000,
    "paid_amount": 10000,
    "pending_amount": 5000,
    "status": "Partially Paid",
    "payment_method": "Cash",
    "payment_transactions": [
      {
        "transaction_date": "2025-01-25",
        "amount": 10000,
        "method": "Cash",
        "receipt_number": "RCP-001"
      }
    ],
    "next_due_date": "2025-02-15",
    "notes": "Patient agreed to pay remaining amount by Feb 15",
    "created_at": "2025-01-25T16:00:00",
    "updated_at": "2025-01-25T16:30:00"
  }
}
```

---

### 6.3 Create New Invoice/Payment
**Endpoint:** `POST /api/resource/Payment`

**Description:** Creates a new invoice or payment record.

**Request Body:**
```json
{
  "patient_id": "P0001",
  "payment_date": "2025-01-25",
  "treatment": "Root Canal Treatment",
  "treatment_details": "Root canal treatment for upper molar",
  "total_amount": 15000,
  "paid_amount": 10000,
  "payment_method": "Cash",
  "next_due_date": "2025-02-15",
  "notes": "Patient agreed to pay remaining amount by Feb 15"
}
```

**Response:**
```json
{
  "data": {
    "name": "PAY-003",
    "payment_id": "PAY003",
    "invoice_number": "INV-003",
    "pending_amount": 5000,
    "message": "Invoice created successfully"
  }
}
```

---

### 6.4 Update Payment Record
**Endpoint:** `PUT /api/resource/Payment/{payment_id}`

**Description:** Updates payment information (typically to record partial or full payment).

**Request Body:**
```json
{
  "paid_amount": 15000,
  "payment_method": "UPI",
  "status": "Paid",
  "payment_transactions": [
    {
      "transaction_date": "2025-01-25",
      "amount": 10000,
      "method": "Cash",
      "receipt_number": "RCP-001"
    },
    {
      "transaction_date": "2025-02-10",
      "amount": 5000,
      "method": "UPI",
      "receipt_number": "RCP-002",
      "transaction_id": "UPI123456789"
    }
  ]
}
```

**Response:**
```json
{
  "message": "Payment updated successfully",
  "data": {
    "payment_id": "PAY001",
    "pending_amount": 0,
    "status": "Paid"
  }
}
```

---

### 6.5 Get Payment Summary for Patient
**Endpoint:** `GET /api/method/get_patient_payment_summary`

**Description:** Retrieves aggregated payment summary for a patient.

**Query Parameters:**
- `patient_id` - Patient ID (required)

**Example:**
```
GET /api/method/get_patient_payment_summary?patient_id=P0001
```

**Response:**
```json
{
  "message": "success",
  "data": {
    "patient_id": "P0001",
    "patient_name": "Sample Patient Name",
    "total_invoiced": 21000,
    "total_paid": 13500,
    "total_pending": 7500,
    "payment_count": 3,
    "pending_invoices": 2,
    "next_due_date": "2025-02-15",
    "payment_history": [
      {
        "invoice_number": "INV-001",
        "date": "2025-01-25",
        "amount": 15000,
        "paid": 10000,
        "pending": 5000
      }
    ]
  }
}
```

---

### 6.6 Send Payment Reminder
**Endpoint:** `POST /api/method/send_payment_reminder`

**Description:** Sends payment reminder to patient via SMS/Email.

**Request Body:**
```json
{
  "payment_id": "PAY001",
  "reminder_type": "sms",  // or "email" or "both"
  "message": "Your payment of ₹5000 is due on 15-02-2025. Please clear the dues."
}
```

**Response:**
```json
{
  "message": "Payment reminder sent successfully",
  "sent_via": ["sms"],
  "sent_to": "+919400475408"
}
```

---

## 7. File Upload APIs

### 7.1 Upload File
**Endpoint:** `POST /api/method/upload_file`

**Description:** Uploads a file (prescription, X-ray, report, etc.).

**Request (Multipart Form Data):**
```
file: [Binary file data]
doctype: "Prescription"  // or "Patient", "Payment", etc.
docname: "PRESC-001"     // ID of the related record
is_private: 0            // 0 for public, 1 for private
folder: "Home/Prescriptions"
file_name: "prescription_25012025.pdf"
```

**Response:**
```json
{
  "message": "File uploaded successfully",
  "data": {
    "file_name": "prescription_25012025.pdf",
    "file_url": "/files/prescription_25012025.pdf",
    "file_size": 1024000,
    "file_type": "application/pdf"
  }
}
```

---

### 7.2 Get File
**Endpoint:** `GET /files/{file_name}`

**Description:** Downloads or displays a file.

**Response:**
Binary file data with appropriate content-type header.

---

### 7.3 Delete File
**Endpoint:** `DELETE /api/resource/File/{file_id}`

**Description:** Deletes an uploaded file.

**Response:**
```json
{
  "message": "File deleted successfully"
}
```

---

## 8. Dashboard/Statistics APIs

### 8.1 Get Dashboard Statistics
**Endpoint:** `GET /api/method/get_dashboard_stats`

**Description:** Retrieves dashboard statistics for the doctor.

**Query Parameters:**
- `date` - Date for which to fetch stats (default: today, format: YYYY-MM-DD)

**Example:**
```
GET /api/method/get_dashboard_stats?date=2025-09-23
```

**Response:**
```json
{
  "message": "success",
  "data": {
    "date": "2025-09-23",
    "todays_appointments": {
      "total": 5,
      "confirmed": 3,
      "pending": 1,
      "scheduled": 1,
      "cancelled": 0
    },
    "upcoming_appointments": {
      "count": 3,
      "next_7_days": 8,
      "next_30_days": 24
    },
    "total_patients": 5,
    "new_patients_this_month": 2,
    "pending_payments": {
      "total_amount": 7500,
      "count": 2
    },
    "todays_revenue": 13500,
    "monthly_revenue": 45000
  }
}
```

---

### 8.2 Get Appointment Statistics
**Endpoint:** `GET /api/method/get_appointment_stats`

**Description:** Retrieves appointment statistics for a date range.

**Query Parameters:**
- `start_date` - Start date (YYYY-MM-DD)
- `end_date` - End date (YYYY-MM-DD)

**Example:**
```
GET /api/method/get_appointment_stats?start_date=2025-09-01&end_date=2025-09-30
```

**Response:**
```json
{
  "message": "success",
  "data": {
    "period": {
      "start_date": "2025-09-01",
      "end_date": "2025-09-30"
    },
    "total_appointments": 45,
    "completed": 38,
    "cancelled": 5,
    "no_show": 2,
    "by_type": {
      "Regular checkup": 20,
      "Emergency": 8,
      "Follow-up": 12,
      "Consultation": 5
    },
    "by_status": {
      "confirmed": 30,
      "pending": 10,
      "scheduled": 5
    },
    "peak_days": [
      {
        "date": "2025-09-15",
        "count": 8
      },
      {
        "date": "2025-09-22",
        "count": 7
      }
    ]
  }
}
```

---

### 8.3 Get Revenue Statistics
**Endpoint:** `GET /api/method/get_revenue_stats`

**Description:** Retrieves revenue statistics for a date range.

**Query Parameters:**
- `start_date` - Start date (YYYY-MM-DD)
- `end_date` - End date (YYYY-MM-DD)

**Example:**
```
GET /api/method/get_revenue_stats?start_date=2025-09-01&end_date=2025-09-30
```

**Response:**
```json
{
  "message": "success",
  "data": {
    "period": {
      "start_date": "2025-09-01",
      "end_date": "2025-09-30"
    },
    "total_invoiced": 450000,
    "total_collected": 380000,
    "total_pending": 70000,
    "by_payment_method": {
      "Cash": 200000,
      "UPI": 150000,
      "Card": 30000
    },
    "daily_revenue": [
      {
        "date": "2025-09-01",
        "amount": 15000
      },
      {
        "date": "2025-09-02",
        "amount": 12000
      }
    ],
    "top_treatments": [
      {
        "treatment": "Root Canal Treatment",
        "count": 12,
        "revenue": 180000
      },
      {
        "treatment": "Dental Cleaning",
        "count": 25,
        "revenue": 87500
      }
    ]
  }
}
```

---

## Error Handling

All API endpoints should return appropriate HTTP status codes and error messages:

### Success Response
```json
{
  "message": "Operation successful",
  "data": { /* Response data */ }
}
```

### Error Response
```json
{
  "exc_type": "ErrorType",
  "message": "Error description",
  "exception": "Detailed error message (only in development)",
  "_server_messages": "[\"Error details\"]"
}
```

### HTTP Status Codes
- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict (e.g., duplicate patient)
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Server error

---

## Authentication & Authorization

### Request Headers
All authenticated requests should include:
```
Authorization: token <api_key>:<api_secret>
OR
Cookie: sid=<session_id>
```

### Permissions
- Doctor role can access all endpoints related to their clinic
- Patients can only access their own data (if patient portal is implemented)
- Admin role has full access

---

## Rate Limiting

To prevent abuse, implement rate limiting:
- 100 requests per minute for authenticated users
- 20 requests per minute for unauthenticated users

---

## Pagination

For list endpoints, use standard pagination:
```
GET /api/resource/Patient?limit_start=0&limit_page_length=20
```

Response includes:
```json
{
  "data": [ /* Records */ ],
  "total_count": 100,
  "page_length": 20,
  "start": 0
}
```

---

## Webhooks (Optional)

For real-time notifications:
- Appointment created/updated/cancelled
- Payment received
- New patient registered

---

## Additional Notes

1. **Date Format**: Use ISO 8601 format (YYYY-MM-DD) for dates and (YYYY-MM-DDTHH:mm:ss) for timestamps
2. **Currency**: All amounts are in INR (Indian Rupees)
3. **File Storage**: Use Frappe's built-in file storage system
4. **Soft Deletes**: Implement soft deletes for important records (don't permanently delete data)
5. **Audit Trail**: Maintain created_at, updated_at, created_by, modified_by fields
6. **Validation**: Implement proper validation for all input fields
7. **Search**: Implement full-text search for patient names, phone numbers, etc.

---

## Implementation Priority

**Phase 1 (MVP):**
1. Authentication APIs
2. Patient Management APIs
3. Appointment Management APIs
4. Dashboard Statistics API

**Phase 2:**
5. Prescription/Medical History APIs
6. File Upload APIs

**Phase 3:**
7. Payment/Invoice Management APIs
8. Advanced Statistics & Reports

---

## Frappe-Specific Implementation Notes

### DocTypes to Create:

1. **Doctor** (extends User)
   - Fields: name, phone, email, specialization, qualification, registration_number, experience
   - Child Table: Clinic Details, Services

2. **Patient**
   - Fields: patient_id (auto-generated), name, age, gender, dob, phone, email, address
   - Child Table: Medical History

3. **Appointment**
   - Fields: appointment_id, patient (Link to Patient), appointment_date, appointment_time, type, status, notes
   - Status: Scheduled, Confirmed, Cancelled, Completed

4. **Prescription**
   - Fields: prescription_id, patient (Link to Patient), prescription_date, doctor (Link to Doctor)
   - Child Tables: Investigations, Medications
   - Text Fields: notes
   - Attach: Multiple files support

5. **Payment**
   - Fields: payment_id, invoice_number, patient (Link to Patient), payment_date, treatment, total_amount, paid_amount, pending_amount, status
   - Child Table: Payment Transactions
   - Status: Pending, Partially Paid, Paid

6. **File Attachment**
   - Use Frappe's built-in File DocType with custom categories

### Custom Methods:

Create custom Python methods in respective DocType controllers:
- `@frappe.whitelist()` decorator for API exposure
- Implement proper permission checks
- Use Frappe's query builder for complex queries
- Implement caching for frequently accessed data

### Hooks to Implement:
- Auto-generate IDs (Patient ID, Appointment ID, etc.)
- Send notifications on appointment creation/update
- Calculate pending amounts automatically
- Validate appointment time slots (prevent double booking)

---

## Testing

Use these test cases for API testing:

1. **Authentication**
   - Valid login
   - Invalid credentials
   - Token expiration

2. **Patient CRUD**
   - Create, Read, Update, Delete operations
   - Search functionality
   - Validation errors

3. **Appointment Management**
   - Create appointment for today
   - Create future appointment
   - Reschedule appointment
   - Cancel appointment
   - Conflict detection (double booking)

4. **Payment Processing**
   - Create invoice
   - Record partial payment
   - Record full payment
   - Payment history retrieval

5. **File Upload**
   - Upload prescription PDF
   - Upload X-ray image
   - Delete file

---

## Contact

For implementation questions or clarifications, please contact the development team.

---

**Last Updated:** January 25, 2025  
**Version:** 1.0
