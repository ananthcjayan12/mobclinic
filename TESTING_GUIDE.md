# Mob Clinic API Testing Guide

## 📋 Overview

This document explains how to run unit tests for the Mob Clinic APIs to ensure everything is working correctly.

## 🧪 Test Coverage

### 1. **Authentication API Tests** (`test_auth.py`)
- ✅ Doctor registration
- ✅ Duplicate email validation
- ✅ Login with valid credentials
- ✅ Login with invalid credentials
- ✅ Get practitioner profile
- ✅ Update practitioner profile
- ✅ Logout functionality

### 2. **Patient Management API Tests** (`test_patient.py`)
- ✅ Create new patient
- ✅ Duplicate mobile validation
- ✅ Get single patient
- ✅ Get patients list with pagination
- ✅ Search patients
- ✅ Update patient information
- ✅ Filter patients
- ✅ Error handling for non-existent patients

## 🚀 Running Tests

### Method 1: Run All Tests (Recommended)
```bash
# Run all tests in the app
bench --site your-site run-tests --app mob_clinic

# Run with verbose output
bench --site your-site run-tests --app mob_clinic --verbose
```

### Method 2: Run Specific Test Module
```bash
# Run authentication tests only
bench --site your-site run-tests --module mob_clinic.mob_clinic.tests.test_auth

# Run patient tests only
bench --site your-site run-tests --module mob_clinic.mob_clinic.tests.test_patient
```

### Method 3: Run Specific Test Class
```bash
# Run authentication test class
bench --site your-site run-tests --module mob_clinic.mob_clinic.tests.test_auth --test TestAuthenticationAPI

# Run patient test class
bench --site your-site run-tests --module mob_clinic.mob_clinic.tests.test_patient --test TestPatientAPI
```

### Method 4: Run Specific Test Method
```bash
# Run specific test method
bench --site your-site run-tests --module mob_clinic.mob_clinic.tests.test_auth --test TestAuthenticationAPI.test_01_mobile_register
```

### Method 5: Using Python Console
```bash
# Enter Frappe console
bench --site your-site console

# In console, run:
from mob_clinic.mob_clinic.tests.test_auth import run_tests as run_auth_tests
from mob_clinic.mob_clinic.tests.test_patient import run_tests as run_patient_tests

# Run tests
run_auth_tests()
run_patient_tests()
```

## 📊 Understanding Test Output

### Successful Test Output:
```
test_01_mobile_register (mob_clinic.mob_clinic.tests.test_auth.TestAuthenticationAPI) ... ✓ Doctor registration test passed
ok
test_02_mobile_register_duplicate_email (mob_clinic.mob_clinic.tests.test_auth.TestAuthenticationAPI) ... ✓ Duplicate email validation test passed
ok

----------------------------------------------------------------------
Ran 7 tests in 5.234s

OK
```

### Failed Test Output:
```
test_01_create_patient (mob_clinic.mob_clinic.tests.test_patient.TestPatientAPI) ... FAIL

======================================================================
FAIL: test_01_create_patient (mob_clinic.mob_clinic.tests.test_patient.TestPatientAPI)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "...", line XX, in test_01_create_patient
    self.assertEqual(result.get("message"), "Patient created successfully")
AssertionError: 'Error' != 'Patient created successfully'
```

## 🔍 Test Details

### Authentication Tests

#### Test 1: Doctor Registration
- **Purpose:** Verify new doctor can register
- **Validates:** User creation, Healthcare Practitioner linking, mobile app enablement
- **Expected:** Success response with user_id and practitioner_id

#### Test 2: Duplicate Email Validation
- **Purpose:** Ensure duplicate emails are rejected
- **Validates:** Email uniqueness constraint
- **Expected:** ValidationError with "already exists" message

#### Test 3: Valid Login
- **Purpose:** Verify login with correct credentials
- **Validates:** Authentication, session creation, profile data return
- **Expected:** Login success with clinic details

#### Test 4: Invalid Login
- **Purpose:** Verify login fails with wrong password
- **Validates:** Security, error handling
- **Expected:** AuthenticationError

#### Test 5: Get Profile
- **Purpose:** Retrieve practitioner profile data
- **Validates:** Profile retrieval, data completeness
- **Expected:** Complete profile with clinic info

#### Test 6: Update Profile
- **Purpose:** Update practitioner information
- **Validates:** Data modification, persistence
- **Expected:** Success with updated fields list

#### Test 7: Logout
- **Purpose:** End user session
- **Validates:** Session termination
- **Expected:** Logout success message

### Patient Management Tests

#### Test 1: Create Patient
- **Purpose:** Create new patient record
- **Validates:** Patient creation, data storage
- **Expected:** Success with patient ID

#### Test 2: Duplicate Mobile Validation
- **Purpose:** Prevent duplicate mobile numbers
- **Validates:** Mobile uniqueness
- **Expected:** ValidationError

#### Test 3: Get Single Patient
- **Purpose:** Retrieve patient details
- **Validates:** Data retrieval, completeness
- **Expected:** Full patient record

#### Test 4: Get Patients List
- **Purpose:** List all patients with pagination
- **Validates:** List retrieval, pagination
- **Expected:** List with total count

#### Test 5: Search Patients
- **Purpose:** Search by name/mobile
- **Validates:** Search functionality
- **Expected:** Matching results

#### Test 6: Update Patient
- **Purpose:** Modify patient information
- **Validates:** Data update, persistence
- **Expected:** Success with updated fields

#### Test 7: Filter Patients
- **Purpose:** Filter patients by criteria
- **Validates:** Filtering logic
- **Expected:** Filtered results

#### Test 8: Non-existent Patient
- **Purpose:** Handle invalid patient ID
- **Validates:** Error handling
- **Expected:** NotFound error

## 🛠️ Troubleshooting

### Common Issues

#### 1. **Healthcare App Not Found**
```
Error: Healthcare doctype not found
```
**Solution:**
```bash
bench get-app healthcare
bench --site your-site install-app healthcare
bench --site your-site migrate
```

#### 2. **Test User Already Exists**
```
Error: User test_doctor@mobclinic.com already exists
```
**Solution:**
```bash
# Clean up test data
bench --site your-site console

# In console:
import frappe
frappe.delete_doc("User", "test_doctor@mobclinic.com", force=True)
frappe.db.commit()
```

#### 3. **Permission Errors**
```
Error: Insufficient Permission for User
```
**Solution:**
- Tests run as Administrator by default
- Check if user has proper roles assigned
- Verify Healthcare Practitioner role permissions

#### 4. **Custom Fields Not Found**
```
Error: 'mobile_app_enabled' not found in Healthcare Practitioner
```
**Solution:**
```bash
# Run migration to install custom fields
bench --site your-site migrate

# Or manually run patch
bench --site your-site console

from mob_clinic.mob_clinic.patches.v1_0.install_custom_fields import execute
execute()
```

## 📈 Continuous Integration

### Add to CI/CD Pipeline

**GitHub Actions Example:**
```yaml
name: Run Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Frappe
        run: |
          # Setup frappe bench
          # Install dependencies
      - name: Run Tests
        run: |
          bench --site test_site run-tests --app mob_clinic --coverage
```

## 📝 Writing New Tests

### Template for New Test File:

```python
import frappe
import unittest
from frappe.tests.utils import FrappeTestCase


class TestYourFeature(FrappeTestCase):
    """Test cases for Your Feature"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data before running tests"""
        super().setUpClass()
        # Setup code here
    
    def test_01_feature_name(self):
        """Test description"""
        # Test code here
        self.assertEqual(expected, actual)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests"""
        # Cleanup code here
        super().tearDownClass()
```

### Best Practices:

1. **Naming Convention:** Use `test_XX_descriptive_name` format
2. **Cleanup:** Always clean up test data in both setUpClass and tearDownClass
3. **Independence:** Each test should be independent and not rely on test execution order
4. **Assertions:** Use appropriate assert methods (assertEqual, assertTrue, assertIn, etc.)
5. **Documentation:** Add docstrings to describe test purpose
6. **Check Before Create:** Use `frappe.db.exists()` to avoid duplicate entries
7. **Proper User Context:** Set `frappe.set_user("Administrator")` before operations
8. **Use Frappe ORM:** Prefer `frappe.delete_doc()` over raw SQL for cleanup
9. **Commit Changes:** Always call `frappe.db.commit()` after data changes
10. **Validate Field Values:** Check valid options for select fields (e.g., "O Positive" not "O+")
11. **Child Tables:** Remember child tables don't exist independently - manage through parent
12. **Unique Test Data:** Use unique identifiers (emails, phones) to avoid conflicts

### Test Cleanup Pattern:

```python
@classmethod
def cleanup_test_data(cls):
    """Clean up test data using Frappe ORM"""
    frappe.set_user("Administrator")
    
    try:
        # Check before deleting
        if frappe.db.exists("DocType", "test-record"):
            frappe.delete_doc("DocType", "test-record", 
                            force=True, ignore_permissions=True)
        
        frappe.db.commit()
    except Exception as e:
        print(f"Cleanup error: {str(e)}")
        frappe.db.rollback()
```

## 🎯 Test Coverage Goals

- **Current Coverage:** ~40% (Authentication + Patient APIs)
- **Target Coverage:** 80%+

### Pending Tests:
- [ ] Appointment Management APIs
- [ ] Prescription Management APIs
- [ ] Payment & Invoice APIs
- [ ] File Upload APIs
- [ ] Dashboard APIs

## 📞 Support

If tests fail:
1. Check error logs: `bench --site your-site logs`
2. Review test output carefully
3. Verify custom fields are installed
4. Ensure Healthcare app is installed
5. Check database for test data conflicts

---

**Happy Testing!** 🧪✅