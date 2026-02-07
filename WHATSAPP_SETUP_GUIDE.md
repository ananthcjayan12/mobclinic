# WhatsApp Business API Integration - Setup Guide

This guide walks you through setting up Meta WhatsApp Business Cloud API integration for your DentCharts clinic.

---

## Prerequisites

- A Facebook Business Account
- A phone number that can receive SMS (for verification)
- Admin access to your clinic's Frappe/ERPNext installation

---

## Part 1: Meta Business Account Setup

### Step 1: Create Meta Business Account

1. Go to [business.facebook.com](https://business.facebook.com)
2. Click **Create Account** or **Log In**
3. Fill in your business details:
   - Business Name: Your clinic name
   - Your Name
   - Business Email
4. Verify your email address

### Step 2: Set Up WhatsApp Business Platform

1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Click **My Apps** → **Create App**
3. Select **Business** as the app type
4. Fill in:
   - App Name: e.g., "DentCharts WhatsApp"
   - App Contact Email
   - Business Account: Select your business
5. Click **Create App**

### Step 3: Add WhatsApp Product

1. In your app dashboard, find **Add Products to Your App**
2. Click **Set Up** under **WhatsApp**
3. Select your Meta Business Account
4. You'll see the **WhatsApp** section in the left sidebar

### Step 4: Get API Credentials

In the WhatsApp section of your app:

1. **Phone Number ID**: 
   - Go to **WhatsApp** → **API Setup**
   - Find "Phone number ID" (looks like: `123456789012345`)
   - Copy this value

2. **WhatsApp Business Account ID**:
   - Go to **WhatsApp** → **API Setup**
   - Find "WhatsApp Business Account ID" (in the "From" dropdown area)
   - Copy this value

3. **Access Token**:
   - For testing: Use the "Temporary access token" shown on the API Setup page (valid 24 hours)
   - For production: Create a permanent System User token:
     1. Go to [Business Settings](https://business.facebook.com/settings)
     2. Navigate to **Users** → **System Users**
     3. Click **Add** → Create a System User
     4. Assign the **WhatsApp Business Messaging** permission
     5. Click **Generate Token** → select your app
     6. Copy the permanent token

---

## Part 2: Create Message Templates

WhatsApp requires pre-approved message templates for business-initiated conversations.

### Step 1: Navigate to Template Manager

1. Go to [WhatsApp Manager](https://business.facebook.com/wa/manage/message-templates/)
2. Or from your app: **WhatsApp** → **Message Templates**

### Step 2: Create Required Templates

You need to create **4 templates**. For each, click **Create Template**:

---

#### Template 1: Appointment Reminder

| Field | Value |
|-------|-------|
| **Name** | `appointment_reminder` |
| **Category** | Utility |
| **Language** | English (or your preferred language) |

**Body Text:**
```
Hello {{1}},

This is a reminder for your appointment at {{2}} on {{3}} at {{4}}.

Please arrive 10 minutes early.

If you need to reschedule, please contact us.
```

**Parameters:**
- `{{1}}` = Patient Name
- `{{2}}` = Clinic Name
- `{{3}}` = Date
- `{{4}}` = Time

---

#### Template 2: Review Request

| Field | Value |
|-------|-------|
| **Name** | `review_request` |
| **Category** | Marketing |
| **Language** | English |

**Body Text:**
```
Hi {{1}},

Thank you for visiting {{2}}! We hope you had a great experience.

We'd love to hear your feedback. Please share your review:
{{3}}

Your feedback helps us serve you better!
```

**Parameters:**
- `{{1}}` = Patient Name
- `{{2}}` = Clinic Name
- `{{3}}` = Google Maps Review Link

---

#### Template 3: Prescription Shared

| Field | Value |
|-------|-------|
| **Name** | `prescription_shared` |
| **Category** | Utility |
| **Language** | English |

**Body Text:**
```
Dear {{1}},

Your prescription from {{2}} dated {{3}} is ready.

Prescribed by: Dr. {{4}}

View/Download: {{5}}

For any queries, contact us at {{6}}.
```

**Parameters:**
- `{{1}}` = Patient Name
- `{{2}}` = Clinic Name
- `{{3}}` = Prescription Date
- `{{4}}` = Doctor Name
- `{{5}}` = Prescription Link/URL
- `{{6}}` = Clinic Phone

---

#### Template 4: Invoice Receipt

| Field | Value |
|-------|-------|
| **Name** | `invoice_receipt` |
| **Category** | Utility |
| **Language** | English |

**Body Text:**
```
Dear {{1}},

Thank you for your payment of ₹{{2}} at {{3}}.

Invoice No: {{4}}
Date: {{5}}

View Receipt: {{6}}

For queries, contact: {{7}}
```

**Parameters:**
- `{{1}}` = Patient Name
- `{{2}}` = Amount
- `{{3}}` = Clinic Name
- `{{4}}` = Invoice Number
- `{{5}}` = Date
- `{{6}}` = Invoice Link
- `{{7}}` = Phone

---

### Step 3: Submit Templates for Approval

1. After creating each template, click **Submit**
2. Templates go through Meta review (typically 24-48 hours)
3. Status will change from "Pending" to "Approved" or "Rejected"
4. If rejected, review the reason and modify accordingly

---

## Part 3: Configure in DentCharts

### Step 1: Access Clinic Settings

**Option A: Via Frappe Desk**
1. Log into your Frappe/ERPNext desk
2. Search for "Clinic Settings"
3. Open your clinic's settings document

**Option B: Direct Database (Advanced)**
```bash
bench --site your-site.localhost console
```
```python
settings = frappe.get_doc("Clinic Settings", "Your Clinic Name")
settings.whatsapp_enabled = 1
settings.whatsapp_phone_number_id = "YOUR_PHONE_NUMBER_ID"
settings.whatsapp_business_account_id = "YOUR_BUSINESS_ACCOUNT_ID"
settings.whatsapp_access_token = "YOUR_ACCESS_TOKEN"
settings.whatsapp_appointment_template = "appointment_reminder"
settings.whatsapp_review_template = "review_request"
settings.whatsapp_prescription_template = "prescription_shared"
settings.whatsapp_invoice_template = "invoice_receipt"
settings.save()
frappe.db.commit()
```

### Step 2: Enter Configuration Values

| Field | Value to Enter |
|-------|----------------|
| **Enable WhatsApp Integration** | ✓ Check this box |
| **Phone Number ID** | From Meta (Step 4 above) |
| **Business Account ID** | From Meta (Step 4 above) |
| **Access Token** | Your permanent access token |
| **Appointment Reminder Template** | `appointment_reminder` |
| **Review Request Template** | `review_request` |
| **Prescription Template** | `prescription_shared` |
| **Invoice Template** | `invoice_receipt` |

### Step 3: Save and Test

1. Save the Clinic Settings
2. Use the "Test Connection" feature (if available in UI) or test via console:

```bash
bench --site your-site.localhost console
```
```python
from mob_clinic.mob_clinic.api.whatsapp import test_connection
result = test_connection("Your Clinic Name")
print(result)
# Should show: {'success': True, 'message': 'Connection successful', ...}
```

---

## Part 4: Testing WhatsApp Messages

### Test Appointment Reminder

```python
from mob_clinic.mob_clinic.api.whatsapp import send_appointment_reminder
result = send_appointment_reminder("APPOINTMENT-ID-HERE")
print(result)
```

### Test Prescription Share

```python
from mob_clinic.mob_clinic.api.whatsapp import send_prescription
result = send_prescription("PRESCRIPTION-ID-HERE")
print(result)
```

### Important Notes for Testing

1. **Test Phone Number**: During development, you can only send messages to phone numbers added to your WhatsApp test numbers list in Meta
2. **Add Test Numbers**: Go to **WhatsApp** → **API Setup** → **To** field → **Manage phone number list**
3. **Production**: Once verified, you can message any WhatsApp number

---

## File Structure Reference

```
frappe-bench/
├── apps/mob_clinic/mob_clinic/mob_clinic/
│   ├── api/
│   │   └── whatsapp.py              # Backend API (send_template_message, etc.)
│   └── doctype/
│       ├── clinic_settings/
│       │   └── clinic_settings.json # WhatsApp config fields
│       └── whatsapp_message_log/
│           └── whatsapp_message_log.json # Message tracking
│
└── UI/dentcharts-mob/src/
    ├── api/services/
    │   └── whatsapp.ts              # Frontend service
    └── pages/
        ├── AppointmentsPage.tsx     # Reminder & Review buttons
        └── PrescriptionPage.tsx     # Share via WhatsApp button
```

---

## Troubleshooting

### Error: "WhatsApp not configured for this clinic"
- Ensure `whatsapp_enabled` is checked in Clinic Settings
- Verify the Clinic Settings document exists for your clinic

### Error: "Invalid template"
- Template name in Clinic Settings must exactly match the template name in Meta
- Template must be "Approved" status in Meta

### Error: "Invalid phone number"
- Ensure patient has a valid mobile number in their profile
- Number should be in format: 10 digits (will auto-add 91 country code for India)

### Error: "Authorization error"
- Access token may have expired (if using temporary token)
- Generate a new permanent token from System User

### Message not received
- Check if the recipient's number is on WhatsApp
- During testing, ensure number is in your approved test list
- Check WhatsApp Message Log for status and error details

---

## WhatsApp API Limits

| Limit | Value |
|-------|-------|
| Message Template Limit | 250 templates per Business Account |
| New Business Messaging Limit | 1,000 messages/24 hours (increases with quality) |
| Template Parameter Length | 1,024 characters per parameter |
| Media Size | Max 16 MB for documents |

---

## Support Resources

- [Meta WhatsApp Cloud API Documentation](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [Message Template Guidelines](https://developers.facebook.com/docs/whatsapp/message-templates)
- [WhatsApp Business Policy](https://www.whatsapp.com/legal/business-policy/)

---

*Last Updated: January 2026*
