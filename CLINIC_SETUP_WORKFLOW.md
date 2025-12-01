# Clinic Setup Workflow Guide

**Version:** 1.0  
**Date:** December 1, 2025  
**Purpose:** Complete workflow for creating a new clinic and setting up practitioners

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Workflow Steps](#workflow-steps)
4. [Step-by-Step Guide](#step-by-step-guide)
5. [Via ERPNext UI](#via-erpnext-ui)
6. [Via API](#via-api)
7. [Via Bench Console](#via-bench-console)
8. [Verification](#verification)
9. [Troubleshooting](#troubleshooting)

---

## Overview

### What You'll Create

1. **Company (Clinic)** - The clinic entity in ERPNext
2. **User Account** - Login credentials for the practitioner
3. **Healthcare Practitioner** - The practitioner profile linked to the user
4. **Mobile App Access** - Enable mobile app login

### Timeline

- **Estimated Time:** 10-15 minutes per clinic setup
- **Complexity:** Beginner to Intermediate

---

## Prerequisites

### Required Access

- Administrator account or user with permissions:
  - Create Company
  - Create User
  - Create Healthcare Practitioner

### Required Information

Before starting, gather:

- ✅ Clinic name (e.g., "Downtown Dental Clinic")
- ✅ Practitioner full name
- ✅ Practitioner email (will be used as login ID)
- ✅ Practitioner phone number
- ✅ Initial password
- ✅ Practitioner specialization (optional)
- ✅ Department (optional, e.g., "Dentistry", "General Practice")

---

## Workflow Steps

### High-Level Process

```
1. Create Company (Clinic)
   ↓
2. Create User Account
   ↓
3. Create Healthcare Practitioner
   ↓
4. Link User to Practitioner
   ↓
5. Set Primary Company
   ↓
6. Enable Mobile App Access
   ↓
7. Test Login
```

---

## Step-by-Step Guide

## Via ERPNext UI

### Step 1: Create Company (Clinic)

1. **Navigate to Company List**
   - Go to: `Home > Accounting > Company`
   - Or search: Press `Ctrl + K` and type "Company"

2. **Create New Company**
   - Click **"New"** button
   - Fill in the form:

   | Field | Value | Required |
   |-------|-------|----------|
   | Company Name | Downtown Dental Clinic | ✅ Yes |
   | Abbr | DDC | ✅ Yes (3-5 chars) |
   | Default Currency | INR / USD | ✅ Yes |
   | Country | India / USA | ✅ Yes |
   | Domain | Healthcare | Recommended |

3. **Chart of Accounts**
   - If prompted, select: **"Create New Chart of Accounts"**
   - Or use: **"Existing Company"** as template
   - **Important:** Choose a chart template that matches your country

4. **Save**
   - Click **"Save"**
   - Wait for chart of accounts setup to complete (may take 10-30 seconds)
   - ⚠️ **Common Error:** If you get "LinkValidationError", see [Troubleshooting Issue 6](#issue-6-linkvalidationerror-when-creating-company)

**✅ Result:** Company "Downtown Dental Clinic" created

---

### Step 2: Create User Account

1. **Navigate to User List**
   - Go to: `Home > Settings > User`
   - Or search: `Ctrl + K` → "User"

2. **Create New User**
   - Click **"New"** button
   - Fill in the form:

   | Field | Value | Required |
   |-------|-------|----------|
   | Email | dr.john@downtowndental.com | ✅ Yes (Login ID) |
   | First Name | John | ✅ Yes |
   | Last Name | Doe | ✅ Yes |
   | Send Welcome Email | ☑️ Check (optional) | No |
   | Language | English | No |
   | Time Zone | Asia/Kolkata | No |

3. **Set Password**
   - Scroll to **"Set New Password"** section
   - Enter temporary password (e.g., `Welcome@123`)
   - Check: **"Send Password Update Notification"** (if email configured)

4. **Assign Roles**
   - Scroll to **"Roles"** section
   - Add the following roles:
     - ☑️ **Physician** (Primary role for practitioners)
     - ☑️ **Healthcare User** (Access to healthcare modules)
     - ☑️ **System Manager** (Optional - for admin access)

5. **Set User Type**
   - User Type: **"System User"** (default)

6. **Save**
   - Click **"Save"**

**✅ Result:** User account created with email as login ID

---

### Step 3: Create Healthcare Practitioner

1. **Navigate to Healthcare Practitioner List**
   - Go to: `Home > Healthcare > Masters > Healthcare Practitioner`
   - Or search: `Ctrl + K` → "Healthcare Practitioner"

2. **Create New Practitioner**
   - Click **"New"** button
   - Fill in the form:

   | Field | Value | Required | Description |
   |-------|-------|----------|-------------|
   | First Name | John | ✅ Yes | Must match user |
   | Last Name | Doe | ✅ Yes | Must match user |
   | Practitioner Name | Dr. John Doe | Auto-filled | Full name |
   | Gender | Male | ✅ Yes | - |
   | Mobile | +1234567890 | Recommended | Contact number |
   | Email | dr.john@downtowndental.com | Recommended | Match user email |

3. **Link to User Account**
   - Scroll to **"User ID"** field
   - Select: **"dr.john@downtowndental.com"**
   - This links the practitioner to the user account

4. **Set Department (Optional)**
   - Field: **"Department"**
   - Value: Create/Select (e.g., "Dentistry", "General Practice")

5. **Set Specialization (Optional)**
   - Field: **"Specialization"**
   - Value: Add specializations (e.g., "Orthodontics", "Pediatric Dentistry")

6. **Mobile Clinic Settings** (Custom Section)
   - Scroll to **"Mobile Clinic Settings"** section
   - Check: ☑️ **"Enable Mobile App Access"**
   - **Primary Company**: Select **"Downtown Dental Clinic"**
   - **Clinic Logo**: Upload image (optional)
   - **Clinic Description**: Enter description (optional)

7. **Working Hours** (Optional)
   - Scroll to **"Clinic Working Hours"** table
   - Add rows for each working day:

   | Day | From Time | To Time |
   |-----|-----------|---------|
   | Monday | 09:00 | 17:00 |
   | Tuesday | 09:00 | 17:00 |
   | ... | ... | ... |

8. **Save**
   - Click **"Save"**

**✅ Result:** Healthcare Practitioner created and linked to user

---

### Step 4: Verify Setup

1. **Check Practitioner Fields**
   - Open the saved practitioner
   - Verify:
     - ✅ `user_id` = dr.john@downtowndental.com
     - ✅ `primary_company` = Downtown Dental Clinic
     - ✅ `mobile_app_enabled` = Checked

2. **Test Login**
   - Open incognito/private browser window
   - Go to: `https://your-site.com/app/login`
   - Enter:
     - Email: `dr.john@downtowndental.com`
     - Password: `Welcome@123`
   - Click **"Login"**

**✅ Result:** Practitioner can log in to ERPNext

---

### Step 5: Test Mobile App Login

Use the mobile app login API to verify:

**API Request:**
```bash
curl -X POST https://your-site.com/api/method/mob_clinic.mob_clinic.api.auth.mobile_login \
  -H "Content-Type: application/json" \
  -d '{
    "usr": "dr.john@downtowndental.com",
    "pwd": "Welcome@123"
  }'
```

**Expected Response:**
```json
{
  "message": {
    "status": "success",
    "user": {
      "user_id": "dr.john@downtowndental.com",
      "full_name": "Dr. John Doe",
      "practitioner_id": "PRAC-00001",
      "clinics": ["Downtown Dental Clinic"],
      "active_clinic": "Downtown Dental Clinic",
      "clinic": {
        "name": "Dr. John Doe Clinic",
        "working_hours": [...]
      }
    },
    "token": {
      "api_key": "abc123...",
      "api_secret": "xyz789..."
    }
  }
}
```

**✅ Result:** Mobile app login successful

---

## Via API

### Complete API Workflow

**Note:** This requires Administrator API credentials.

#### 1. Create Company

```bash
curl -X POST https://your-site.com/api/resource/Company \
  -H "Authorization: token {api_key}:{api_secret}" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Downtown Dental Clinic",
    "abbr": "DDC",
    "default_currency": "INR",
    "country": "India",
    "domain": "Healthcare"
  }'
```

#### 2. Create User

```bash
curl -X POST https://your-site.com/api/resource/User \
  -H "Authorization: token {api_key}:{api_secret}" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dr.john@downtowndental.com",
    "first_name": "John",
    "last_name": "Doe",
    "new_password": "Welcome@123",
    "roles": [
      {"role": "Physician"},
      {"role": "Healthcare User"}
    ]
  }'
```

#### 3. Create Healthcare Practitioner

```bash
curl -X POST https://your-site.com/api/resource/Healthcare%20Practitioner \
  -H "Authorization: token {api_key}:{api_secret}" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "practitioner_name": "Dr. John Doe",
    "gender": "Male",
    "mobile": "+1234567890",
    "email": "dr.john@downtowndental.com",
    "user_id": "dr.john@downtowndental.com",
    "primary_company": "Downtown Dental Clinic",
    "mobile_app_enabled": 1,
    "department": "Dentistry"
  }'
```

---

## Via Bench Console

### Using Python Console

```bash
# Navigate to frappe-bench
cd /workspace/development/frappe-bench

# Open console
bench --site [your-site] console
```

**In Console:**

```python
import frappe
from frappe.utils import random_string

# Set user to Administrator
frappe.set_user("Administrator")

# === Step 1: Create Company ===
company = frappe.get_doc({
    "doctype": "Company",
    "company_name": "Downtown Dental Clinic",
    "abbr": "DDC",
    "default_currency": "INR",
    "country": "India",
    "domain": "Healthcare"
})

# Use flags to avoid validation errors during setup
company.flags.ignore_links = True
company.flags.ignore_validate_update_after_submit = True

try:
    company.insert(ignore_permissions=True)
    print(f"✅ Company created: {company.name}")
except frappe.LinkValidationError:
    # If link validation fails, use more permissive flags
    frappe.db.rollback()
    company.flags.ignore_mandatory = True
    company.insert(ignore_permissions=True, ignore_mandatory=True)
    print(f"✅ Company created (relaxed validation): {company.name}")

# === Step 2: Create User ===
user = frappe.get_doc({
    "doctype": "User",
    "email": "dr.john@downtowndental.com",
    "first_name": "John",
    "last_name": "Doe",
    "send_welcome_email": 0,
    "roles": [
        {"role": "Physician"},
        {"role": "Healthcare User"}
    ]
})
user.insert()

# Set password
user.new_password = "Welcome@123"
user.save()
print(f"✅ User created: {user.name}")

# === Step 3: Create Healthcare Practitioner ===
practitioner = frappe.get_doc({
    "doctype": "Healthcare Practitioner",
    "first_name": "John",
    "last_name": "Doe",
    "practitioner_name": "Dr. John Doe",
    "gender": "Male",
    "mobile": "+1234567890",
    "email": "dr.john@downtowndental.com",
    "user_id": "dr.john@downtowndental.com",
    "primary_company": "Downtown Dental Clinic",
    "mobile_app_enabled": 1,
    "department": "Dentistry"
})
practitioner.insert()
print(f"✅ Practitioner created: {practitioner.name}")

# Commit changes
frappe.db.commit()

print("\n" + "="*50)
print("✅ Clinic Setup Complete!")
print("="*50)
print(f"Clinic: Downtown Dental Clinic")
print(f"Login ID: dr.john@downtowndental.com")
print(f"Password: Welcome@123")
print(f"Practitioner ID: {practitioner.name}")
print("="*50)
```

**Output:**
```
✅ Company created: Downtown Dental Clinic
✅ User created: dr.john@downtowndental.com
✅ Practitioner created: PRAC-00001

==================================================
✅ Clinic Setup Complete!
==================================================
Clinic: Downtown Dental Clinic
Login ID: dr.john@downtowndental.com
Password: Welcome@123
Practitioner ID: PRAC-00001
==================================================
```

---

## Bulk Clinic Setup Script

### For Multiple Clinics/Practitioners

Create a Python script for automated setup:

```python
# File: setup_clinics.py

import frappe
from frappe.utils import random_string

def setup_clinic_and_practitioner(clinic_data):
    """
    Setup a new clinic with practitioner
    
    Args:
        clinic_data (dict): {
            "clinic_name": "Downtown Dental Clinic",
            "clinic_abbr": "DDC",
            "practitioner_first": "John",
            "practitioner_last": "Doe",
            "email": "dr.john@downtowndental.com",
            "mobile": "+1234567890",
            "password": "Welcome@123",
            "department": "Dentistry",
            "country": "India"  # Optional, defaults to India
        }
    """
    frappe.set_user("Administrator")
    
    # 1. Create Company
    if not frappe.db.exists("Company", clinic_data["clinic_name"]):
        company = frappe.get_doc({
            "doctype": "Company",
            "company_name": clinic_data["clinic_name"],
            "abbr": clinic_data["clinic_abbr"],
            "default_currency": clinic_data.get("currency", "INR"),
            "country": clinic_data.get("country", "India"),
            "domain": "Healthcare"
        })
        
        # Use flags to avoid validation errors during initial setup
        company.flags.ignore_links = True
        company.flags.ignore_validate_update_after_submit = True
        
        try:
            company.insert(ignore_permissions=True)
            print(f"✅ Company created: {company.name}")
        except frappe.LinkValidationError as e:
            # If link validation fails, try with more permissive flags
            frappe.db.rollback()
            company.flags.ignore_mandatory = True
            company.insert(ignore_permissions=True, ignore_mandatory=True)
            print(f"✅ Company created (with relaxed validation): {company.name}")
    else:
        print(f"⚠️  Company exists: {clinic_data['clinic_name']}")
    
    # 2. Create User
    if not frappe.db.exists("User", clinic_data["email"]):
        user = frappe.get_doc({
            "doctype": "User",
            "email": clinic_data["email"],
            "first_name": clinic_data["practitioner_first"],
            "last_name": clinic_data["practitioner_last"],
            "send_welcome_email": 0,
            "roles": [
                {"role": "Physician"},
                {"role": "Healthcare User"}
            ]
        })
        user.insert()
        user.new_password = clinic_data.get("password", "Welcome@123")
        user.save()
        print(f"✅ User created: {user.name}")
    else:
        print(f"⚠️  User exists: {clinic_data['email']}")
    
    # 3. Create Healthcare Practitioner
    practitioner_name = f"Dr. {clinic_data['practitioner_first']} {clinic_data['practitioner_last']}"
    
    if not frappe.db.exists("Healthcare Practitioner", {"user_id": clinic_data["email"]}):
        practitioner = frappe.get_doc({
            "doctype": "Healthcare Practitioner",
            "first_name": clinic_data["practitioner_first"],
            "last_name": clinic_data["practitioner_last"],
            "practitioner_name": practitioner_name,
            "gender": clinic_data.get("gender", "Male"),
            "mobile": clinic_data.get("mobile", ""),
            "email": clinic_data["email"],
            "user_id": clinic_data["email"],
            "primary_company": clinic_data["clinic_name"],
            "mobile_app_enabled": 1,
            "department": clinic_data.get("department", "General Practice")
        })
        practitioner.insert()
        print(f"✅ Practitioner created: {practitioner.name}")
    else:
        print(f"⚠️  Practitioner exists for: {clinic_data['email']}")
    
    frappe.db.commit()
    
    return {
        "clinic": clinic_data["clinic_name"],
        "login_id": clinic_data["email"],
        "password": clinic_data.get("password", "Welcome@123"),
        "practitioner_name": practitioner_name
    }

# === Usage ===
def setup_multiple_clinics():
    """Setup multiple clinics at once"""
    
    clinics = [
        {
            "clinic_name": "Downtown Dental Clinic",
            "clinic_abbr": "DDC",
            "practitioner_first": "John",
            "practitioner_last": "Doe",
            "email": "dr.john@downtowndental.com",
            "mobile": "+1234567890",
            "password": "Welcome@123",
            "department": "Dentistry"
        },
        {
            "clinic_name": "Uptown Medical Center",
            "clinic_abbr": "UMC",
            "practitioner_first": "Jane",
            "practitioner_last": "Smith",
            "email": "dr.jane@uptownmedical.com",
            "mobile": "+0987654321",
            "password": "Welcome@123",
            "department": "General Practice"
        }
    ]
    
    results = []
    for clinic_data in clinics:
        print("\n" + "="*60)
        print(f"Setting up: {clinic_data['clinic_name']}")
        print("="*60)
        
        result = setup_clinic_and_practitioner(clinic_data)
        results.append(result)
    
    # Print summary
    print("\n" + "="*60)
    print("📋 SETUP SUMMARY")
    print("="*60)
    for r in results:
        print(f"\n🏥 {r['clinic']}")
        print(f"   👤 Practitioner: {r['practitioner_name']}")
        print(f"   📧 Login ID: {r['login_id']}")
        print(f"   🔑 Password: {r['password']}")
    print("\n" + "="*60)

# Run the script
if __name__ == "__main__":
    setup_multiple_clinics()
```

**Run Script:**
```bash
bench --site [your-site] console < setup_clinics.py
```

---

## Verification

### Checklist

After setup, verify the following:

#### 1. Company (Clinic) Verification

```sql
-- Via SQL
SELECT name, company_name, abbr, default_currency 
FROM `tabCompany` 
WHERE name = 'Downtown Dental Clinic';
```

**Expected:**
| name | company_name | abbr | default_currency |
|------|--------------|------|------------------|
| Downtown Dental Clinic | Downtown Dental Clinic | DDC | INR |

#### 2. User Verification

```sql
SELECT name, full_name, enabled 
FROM `tabUser` 
WHERE name = 'dr.john@downtowndental.com';
```

**Expected:**
| name | full_name | enabled |
|------|-----------|---------|
| dr.john@downtowndental.com | Dr. John Doe | 1 |

#### 3. Practitioner Verification

```sql
SELECT name, practitioner_name, user_id, primary_company, mobile_app_enabled 
FROM `tabHealthcare Practitioner` 
WHERE user_id = 'dr.john@downtowndental.com';
```

**Expected:**
| name | practitioner_name | user_id | primary_company | mobile_app_enabled |
|------|-------------------|---------|-----------------|-------------------|
| PRAC-00001 | Dr. John Doe | dr.john@downtowndental.com | Downtown Dental Clinic | 1 |

#### 4. Login Test

**Via Web UI:**
- URL: `https://your-site.com/app/login`
- Email: `dr.john@downtowndental.com`
- Password: `Welcome@123`
- ✅ Should login successfully

**Via Mobile API:**
```bash
curl -X POST https://your-site.com/api/method/mob_clinic.mob_clinic.api.auth.mobile_login \
  -H "Content-Type: application/json" \
  -d '{"usr":"dr.john@downtowndental.com","pwd":"Welcome@123"}'
```
- ✅ Should return success with clinic data

---

## Troubleshooting

### Issue 1: Company Creation Fails

**Error:** `Duplicate entry 'DDC' for key 'abbr'`

**Cause:** Another company with same abbreviation exists.

**Solution:**
- Use unique abbreviation (e.g., "DDC1", "DDC2")
- Or use full name as abbreviation

### Issue 2: User Creation Fails

**Error:** `Email already exists`

**Cause:** Email already registered to another user.

**Solution:**
- Use different email address
- Or update existing user with new password

### Issue 3: Login Works But Mobile App Fails

**Cause:** `mobile_app_enabled` not checked or `primary_company` not set.

**Solution:**
```sql
-- Fix via SQL
UPDATE `tabHealthcare Practitioner` 
SET 
  mobile_app_enabled = 1,
  primary_company = 'Downtown Dental Clinic'
WHERE user_id = 'dr.john@downtowndental.com';
```

### Issue 4: No Clinic Returned in Login

**Cause:** `primary_company` field missing or empty.

**Solution:**
```python
# Via console
import frappe
frappe.set_user("Administrator")

prac = frappe.get_doc("Healthcare Practitioner", {"user_id": "dr.john@downtowndental.com"})
prac.primary_company = "Downtown Dental Clinic"
prac.save()
frappe.db.commit()
```

### Issue 5: Permission Error Creating Practitioner

**Cause:** User doesn't have "Create" permission on Healthcare Practitioner.

**Solution:**
- Login as Administrator
- Grant "Healthcare User" or "System Manager" role

### Issue 6: LinkValidationError When Creating Company

**Error:** `Could not find Row #2: Company: _Test Clinic A, Row #3: Company: _Test Clinic B`

**Cause:** ERPNext tries to set up Mode of Payment accounts before Chart of Accounts is fully initialized.

**Solution 1 - Via UI (Recommended):**
1. When creating company, ensure you select a valid chart of accounts template
2. Wait for the chart to be created before saving additional changes
3. If error occurs, reload the page and try saving again

**Solution 2 - Via Console (Create Company with CoA):**
```python
import frappe
from erpnext.setup.doctype.company.company import install_company

frappe.set_user("Administrator")

# Create company with chart of accounts
company = frappe.get_doc({
    "doctype": "Company",
    "company_name": "Downtown Dental Clinic",
    "abbr": "DDC",
    "default_currency": "INR",
    "country": "India",
    "domain": "Healthcare"
})

# Insert without validation first
company.insert(ignore_mandatory=True)

# Install chart of accounts
install_company(
    company.name,
    company.abbr,
    "India",
    "Standard"  # Use Standard chart template
)

frappe.db.commit()
print(f"✅ Company created with Chart of Accounts: {company.name}")
```

**Solution 3 - Disable Auto Mode of Payment Setup:**
```python
import frappe

frappe.set_user("Administrator")

# Create company with flags to skip auto-setup
company = frappe.get_doc({
    "doctype": "Company",
    "company_name": "Downtown Dental Clinic",
    "abbr": "DDC",
    "default_currency": "INR",
    "country": "India",
    "domain": "Healthcare"
})

# Skip mode of payment setup during insert
company.flags.ignore_validate_update_after_submit = True
company.flags.ignore_links = True

company.insert(ignore_permissions=True, ignore_mandatory=True)
frappe.db.commit()

print(f"✅ Company created: {company.name}")
```

---

## Post-Setup Configuration

### Optional: Add Working Hours

```python
import frappe

prac = frappe.get_doc("Healthcare Practitioner", "PRAC-00001")

# Add working hours
working_hours = [
    {"day": "Monday", "from_time": "09:00:00", "to_time": "17:00:00"},
    {"day": "Tuesday", "from_time": "09:00:00", "to_time": "17:00:00"},
    {"day": "Wednesday", "from_time": "09:00:00", "to_time": "17:00:00"},
    {"day": "Thursday", "from_time": "09:00:00", "to_time": "17:00:00"},
    {"day": "Friday", "from_time": "09:00:00", "to_time": "17:00:00"}
]

for hours in working_hours:
    prac.append("clinic_working_hours", hours)

prac.save()
frappe.db.commit()
```

### Optional: Upload Clinic Logo

```python
import frappe
import base64
import requests

# Download and attach logo
logo_url = "https://example.com/logo.png"
response = requests.get(logo_url)

file_doc = frappe.get_doc({
    "doctype": "File",
    "file_name": "clinic_logo.png",
    "is_private": 0,
    "content": response.content
})
file_doc.save()

# Attach to practitioner
prac = frappe.get_doc("Healthcare Practitioner", "PRAC-00001")
prac.clinic_logo = file_doc.file_url
prac.save()
frappe.db.commit()
```

---

## Quick Reference Card

### Credentials Template

After setup, provide practitioners with:

```
🏥 CLINIC LOGIN CREDENTIALS

Clinic Name: Downtown Dental Clinic
Web URL: https://your-site.com/app/login
Mobile App: [Your App Name]

📧 Login ID: dr.john@downtowndental.com
🔑 Password: Welcome@123

⚠️  Please change your password after first login.

📱 Mobile App Instructions:
1. Download app from [App Store/Play Store]
2. Tap "Login"
3. Enter email and password
4. Select your clinic if you have multiple
```

---

## Summary Checklist

Before considering setup complete:

- [ ] Company created with correct name and abbreviation
- [ ] User account created with email as login ID
- [ ] User has "Physician" role assigned
- [ ] Healthcare Practitioner created
- [ ] Practitioner linked to user via `user_id`
- [ ] `primary_company` set to clinic name
- [ ] `mobile_app_enabled` checked
- [ ] Web login tested and successful
- [ ] Mobile API login tested and returns clinic data
- [ ] Credentials shared with practitioner
- [ ] Practitioner instructed to change password

---

**End of Document**
