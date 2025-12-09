# Clinic Profile Management API - Quick Reference

## Overview
Complete API for managing clinic information, branding, invoice settings, and customization in a multi-tenant environment.

---

## Base URL
`/api/method/mob_clinic.mob_clinic.api.clinic_profile`

---

## API Endpoints

### 1. Get Complete Clinic Profile
```http
GET /get_clinic_profile?clinic=CLINIC-001
```

**Parameters:**
- `clinic` (required): Company/Clinic identifier

**Response:**
```json
{
  "message": "success",
  "profile": {
    "basic_info": {
      "clinic_name": "Dr. Smith Dental Clinic",
      "abbr": "DSC",
      "logo_url": "/files/logo.png",
      "phone": "+1-555-1234",
      "email": "info@drsmith.com",
      "website": "www.drsmith.com",
      "registration_number": "REG-12345",
      "tax_id": "TAX-67890"
    },
    "address": {
      "address_line1": "123 Main Street",
      "address_line2": "Suite 400",
      "city": "New York",
      "state": "NY",
      "country": "USA",
      "pincode": "10001",
      "phone": "+1-555-1234",
      "email": "info@drsmith.com"
    },
    "branding": {
      "primary_color": "#2563EB",
      "secondary_color": "#10B981",
      "text_color": "#1F2937",
      "background_color": "#F9FAFB",
      "font_family": "Inter"
    },
    "invoice_settings": {
      "header_text": "Dr. Smith Dental Clinic",
      "footer_text": "Thank you for choosing our services",
      "terms_conditions": "Payment due within 30 days",
      "signature_url": "/files/signature.png",
      "seal_url": "/files/seal.png",
      "show_logo": true,
      "show_seal": true
    },
    "notifications": {
      "appointment_reminder": "Your appointment is on {date} at {time}",
      "payment_receipt": "Payment of {amount} received",
      "prescription_message": "Follow prescription carefully",
      "sms_sender": "DRSMTH"
    },
    "social_media": {
      "facebook": "https://facebook.com/drsmith",
      "instagram": "https://instagram.com/drsmith",
      "twitter": null,
      "google_maps": "https://maps.google.com/?q=..."
    },
    "additional": {
      "appointment_slot_duration": 30,
      "allow_online_booking": true,
      "timezone": "America/New_York",
      "currency": "USD"
    }
  }
}
```

---

### 2. Update Basic Info
```http
POST /update_basic_info
Content-Type: application/json

{
  "clinic": "CLINIC-001",
  "phone": "+1-555-9999",
  "email": "contact@drsmith.com",
  "website": "www.drsmithdental.com",
  "registration_number": "REG-12345",
  "tax_id": "TAX-67890"
}
```

**Required:** `clinic`  
**Optional:** All other fields

---

### 3. Update Address
```http
POST /update_address
Content-Type: application/json

{
  "clinic": "CLINIC-001",
  "address_line1": "456 Oak Avenue",
  "address_line2": "Floor 2",
  "city": "Brooklyn",
  "state": "NY",
  "country": "USA",
  "pincode": "11201",
  "phone": "+1-555-8888",
  "email": "info@drsmith.com"
}
```

**Required:** `clinic`, `address_line1`, `city`, `state`, `country`, `pincode`  
**Optional:** `address_line2`, `phone`, `email`

---

### 4. Update Branding
```http
POST /update_branding
Content-Type: application/json

{
  "clinic": "CLINIC-001",
  "primary_color": "#2563EB",
  "secondary_color": "#10B981",
  "text_color": "#1F2937",
  "background_color": "#F9FAFB",
  "font_family": "Inter"
}
```

**Font Options:** Inter, Roboto, Open Sans, Lato, Montserrat, Poppins, Arial, Helvetica

---

### 5. Update Invoice Settings
```http
POST /update_invoice_settings
Content-Type: application/json

{
  "clinic": "CLINIC-001",
  "header_text": "Premium Dental Care",
  "footer_text": "Thank you for your trust",
  "terms_conditions": "Payment terms: Net 30 days",
  "show_logo": 1,
  "show_seal": 1
}
```

---

### 6. Upload Logo
```http
POST /upload_logo
Content-Type: multipart/form-data

clinic: CLINIC-001
file: [binary image data]
```

**Supported formats:** PNG, JPG, JPEG, SVG  
**Recommended size:** 200x200px

**Response:**
```json
{
  "message": "Logo uploaded successfully",
  "logo_url": "/files/clinic-logo.png"
}
```

---

### 7. Upload Signature/Seal
```http
POST /upload_document
Content-Type: multipart/form-data

clinic: CLINIC-001
document_type: signature  // or "seal"
file: [binary image data]
```

**Document Types:** `signature`, `seal`

**Response:**
```json
{
  "message": "Signature uploaded successfully",
  "file_url": "/files/signature.png"
}
```

---

### 8. Update Notification Templates
```http
POST /update_notification_templates
Content-Type: application/json

{
  "clinic": "CLINIC-001",
  "appointment_reminder": "Hi {patient_name}, appointment on {date} at {time}",
  "payment_receipt": "Receipt for {amount}. Invoice: {invoice_number}",
  "prescription_message": "Follow prescription carefully",
  "sms_sender": "DRSMTH"
}
```

**Placeholders:**
- Appointment: `{patient_name}`, `{date}`, `{time}`
- Payment: `{patient_name}`, `{amount}`, `{invoice_number}`
- SMS Sender: Max 6 characters

---

### 9. Update Social Media
```http
POST /update_social_media
Content-Type: application/json

{
  "clinic": "CLINIC-001",
  "facebook": "https://facebook.com/drsmith",
  "instagram": "https://instagram.com/drsmith",
  "twitter": "https://twitter.com/drsmith",
  "google_maps": "https://maps.google.com/?q=..."
}
```

---

### 10. Update Additional Settings
```http
POST /update_additional_settings
Content-Type: application/json

{
  "clinic": "CLINIC-001",
  "appointment_slot_duration": 45,
  "allow_online_booking": 1,
  "timezone": "America/New_York",
  "currency": "USD"
}
```

**Timezone Options:** Asia/Kolkata, America/New_York, America/Los_Angeles, Europe/London, etc.

---

## Frontend Integration Examples

### 1. Fetch Complete Profile
```javascript
async function getClinicProfile(clinic) {
  const response = await fetch(
    `/api/method/mob_clinic.mob_clinic.api.clinic_profile.get_clinic_profile?clinic=${clinic}`
  );
  const data = await response.json();
  return data.message.profile;
}
```

### 2. Update Branding Colors
```javascript
async function updateBranding(clinic, colors) {
  const response = await fetch(
    '/api/method/mob_clinic.mob_clinic.api.clinic_profile.update_branding',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        clinic: clinic,
        primary_color: colors.primary,
        secondary_color: colors.secondary,
        text_color: colors.text,
        background_color: colors.background,
        font_family: colors.font
      })
    }
  );
  return response.json();
}
```

### 3. Upload Logo
```javascript
async function uploadLogo(clinic, file) {
  const formData = new FormData();
  formData.append('clinic', clinic);
  formData.append('file', file);
  
  const response = await fetch(
    '/api/method/mob_clinic.mob_clinic.api.clinic_profile.upload_logo',
    {
      method: 'POST',
      body: formData
    }
  );
  return response.json();
}
```

### 4. Apply Theme Colors
```javascript
function applyClinicTheme(branding) {
  document.documentElement.style.setProperty('--primary-color', branding.primary_color);
  document.documentElement.style.setProperty('--secondary-color', branding.secondary_color);
  document.documentElement.style.setProperty('--text-color', branding.text_color);
  document.documentElement.style.setProperty('--background-color', branding.background_color);
  document.body.style.fontFamily = branding.font_family;
}
```

### 5. Generate Invoice with Settings
```javascript
async function generateInvoice(clinic, invoiceData) {
  // Get clinic profile
  const profile = await getClinicProfile(clinic);
  
  const invoice = {
    header: profile.invoice_settings.header_text,
    footer: profile.invoice_settings.footer_text,
    terms: profile.invoice_settings.terms_conditions,
    logo: profile.invoice_settings.show_logo ? profile.basic_info.logo_url : null,
    signature: profile.invoice_settings.signature_url,
    seal: profile.invoice_settings.show_seal ? profile.invoice_settings.seal_url : null,
    ...invoiceData
  };
  
  return invoice;
}
```

---

## Use Cases

### 1. Settings Page
- Load complete profile on page load
- Allow editing each section independently
- Show live preview of branding changes
- Upload images with drag-and-drop

### 2. Invoice Generation
- Apply clinic logo, signature, seal
- Use custom header/footer text
- Include terms and conditions
- Apply brand colors to invoice template

### 3. Notification System
- Use templates for SMS/email
- Replace placeholders with actual values
- Use SMS sender name for branding

### 4. Theme Customization
- Apply colors to entire application
- Change font family dynamically
- Preview changes before saving
- Provide color picker interface

---

## Error Handling

**Success (200):**
```json
{
  "message": "success",
  "profile": { ... }
}
```

**Not Found (404):**
```json
{
  "message": "Invalid clinic"
}
```

**Bad Request (400):**
```json
{
  "message": "SMS sender name cannot exceed 6 characters"
}
```

**Server Error (500):**
```json
{
  "message": "Error details"
}
```

---

## Best Practices

1. **Cache profile data** - Fetch once, update on changes
2. **Validate before upload** - Check file size/format client-side
3. **Show live previews** - Preview colors/fonts before saving
4. **Graceful degradation** - Handle missing logos/images
5. **Responsive images** - Use appropriate image sizes
6. **Color accessibility** - Validate color contrast ratios
7. **Template validation** - Check placeholder syntax
8. **Progressive loading** - Load sections as needed

---

## Database Structure

### Company (Extended with Custom Fields)
- `phone_no` (Data)
- `email` (Data)
- `website` (Data)
- `registration_number` (Data)
- `tax_id` (Data)

### Clinic Settings (New DocType)
- Unique per clinic (autoname: field:clinic)
- All branding, invoice, notification settings
- Links to Company via `clinic` field

### Address (Existing DocType)
- Linked to Company via Dynamic Link
- Stores physical address information

---

## Migration & Setup

**Run migration to install:**
```bash
cd /workspace/development/frappe-bench
bench --site dev.localhost migrate
```

**Patches executed:**
1. `add_company_custom_fields` - Adds custom fields to Company
2. `initialize_clinic_settings` - Creates default settings for existing clinics

---

## Field Requirements

### Mandatory
- ✅ `clinic` - All endpoints require clinic identifier

### Optional
- ❌ All other fields are optional
- ❌ Defaults applied for colors, fonts, durations
- ❌ Notification templates can be empty

---

## Security

- ✅ All endpoints require authentication
- ✅ Clinic parameter validated
- ✅ File uploads validated for type/size
- ✅ Role-based permissions (Healthcare Administrator, System Manager)
- ✅ Each clinic can only access their own settings
