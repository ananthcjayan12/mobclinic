# Mob Clinic - Installation & Migration Guide

## 📋 Prerequisites

1. **Frappe/ERPNext Environment** 
   - Frappe Framework v14+
   - ERPNext installed (optional but recommended)
   - Healthcare app installed

2. **Install Healthcare App** (if not already installed)
   ```bash
   bench get-app healthcare
   bench --site your-site install-app healthcare
   ```

## 🚀 Installation

### Step 1: Install the App
```bash
# Get the app (from your repository)
cd /path/to/your/bench
bench get-app /path/to/mobclinic

# Install on your site
bench --site your-site install-app mob_clinic
```

### Step 2: Run Migration
```bash
# This will create custom fields automatically via patch
bench --site your-site migrate
```

### Step 3: Verify Installation
```bash
# Check if custom fields are created
bench --site your-site console

# In console:
import frappe
frappe.get_meta("Healthcare Practitioner").get_field("mobile_app_enabled")
# Should return the field definition
```

## 🔧 What Gets Installed

### 1. **Custom Fields Added To:**
- **Healthcare Practitioner**: Mobile app settings, clinic details, working hours
- **Patient**: App profile, preferences, insurance details
- **Patient Appointment**: Mobile booking details, treatment info
- **Patient Medical Record**: App sharing, treatment plans, follow-up
- **Sales Invoice**: Medical details, payment tracking

### 2. **Child Table Created:**
- **Clinic Working Hours**: For practitioner schedules

### 3. **Default Data Created:**
- Default appointment types (General, Follow-up, Emergency, etc.)
- Healthcare settings updated for mobile clinic
- Basic permissions configured

### 4. **API Endpoints Available:**
```
Authentication:
- POST /api/method/mob_clinic.api.auth.mobile_login
- POST /api/method/mob_clinic.api.auth.mobile_register
- POST /api/method/mob_clinic.api.auth.mobile_logout
- GET /api/method/mob_clinic.api.auth.get_practitioner_profile
- PUT /api/method/mob_clinic.api.auth.update_practitioner_profile

Patient Management:
- GET /api/method/mob_clinic.api.patient.get_patients
- GET /api/method/mob_clinic.api.patient.get_patient
- POST /api/method/mob_clinic.api.patient.create_patient
- PUT /api/method/mob_clinic.api.patient.update_patient
- GET /api/method/mob_clinic.api.patient.search_patients
```

## 🧪 Testing Installation

### 1. **Test Custom Fields**
```bash
# Check Healthcare Practitioner form
# Go to: Healthcare > Healthcare Practitioner > New
# You should see "Mobile Clinic Settings" section
```

### 2. **Test API Endpoints**
```bash
# Test login endpoint
curl -X POST "http://your-site/api/method/mob_clinic.api.auth.mobile_login" \
  -H "Content-Type: application/json" \
  -d '{"usr": "your-email", "pwd": "your-password"}'
```

### 3. **Verify Patch Execution**
```bash
bench --site your-site console

# Check if patch was executed
import frappe
frappe.db.get_value("Patch Log", {"patch": "mob_clinic.patches.v1_0.install_custom_fields"})
# Should return the patch log name if executed
```

## 🔄 Update/Reinstall

### Update App
```bash
# Pull latest changes
cd apps/mob_clinic
git pull origin develop

# Update on site
bench --site your-site migrate
```

### Force Reinstall Custom Fields
```bash
# If you need to reinstall custom fields
bench --site your-site console

# In console:
from mob_clinic.mob_clinic.patches.v1_0.install_custom_fields import execute
execute()
```

## 🚨 Troubleshooting

### Common Issues

1. **Healthcare App Not Found**
   ```bash
   # Install healthcare first
   bench get-app healthcare
   bench --site your-site install-app healthcare
   ```

2. **Custom Fields Not Created**
   ```bash
   # Check patch execution
   bench --site your-site console
   
   # Re-run patch manually
   from mob_clinic.mob_clinic.patches.v1_0.install_custom_fields import execute
   execute()
   ```

3. **API Endpoints Not Working**
   ```bash
   # Check if app is installed
   bench --site your-site list-apps
   
   # Restart bench
   bench restart
   ```

4. **Permission Errors**
   ```bash
   # Set up proper permissions
   bench --site your-site add-to-role "Healthcare Practitioner" "Patient"
   bench --site your-site add-to-role "Healthcare Practitioner" "Patient Appointment"
   ```

## 📚 Next Steps

After successful installation:

1. **Create Healthcare Practitioner** with mobile app enabled
2. **Test patient creation and management**
3. **Configure appointment types** as needed
4. **Set up working hours** for practitioners
5. **Test mobile app integration**

## 🔒 Security Notes

- All API endpoints require proper authentication
- Patient data is filtered by practitioner access
- Custom fields follow Frappe permission system
- Use HTTPS in production
- Configure proper role-based access

## 📞 Support

For installation issues:
1. Check Frappe logs: `bench logs`
2. Check site logs: `bench --site your-site console` 
3. Review error logs in ERPNext Error Log
4. Ensure all dependencies are met

---

**Installation completed successfully!** 🎉

Your mobile clinic management system is ready for use.