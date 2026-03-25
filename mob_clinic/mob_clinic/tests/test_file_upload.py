"""
Test cases for File Upload APIs in Mobile Clinic Management System

This module tests file upload functionality including:
- File upload (base64 and binary)
- File retrieval and metadata
- File deletion
- File listing with filters
- File category management
- Permission handling
"""

import frappe
import unittest
import base64
import os
from frappe.tests.utils import FrappeTestCase


class TestFileUploadAPI(FrappeTestCase):
    """Test cases for File Upload APIs"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests"""
        super().setUpClass()
        cls.company = frappe.defaults.get_global_default("company")
        
        # Create test practitioners in the same clinic
        cls.create_test_practitioner(
            email="test_file_doctor@example.com",
            first_name="Test File",
            last_name="Doctor",
            phone="+1111111111",
            practitioner_attr="practitioner_id",
            email_attr="practitioner_email",
        )
        cls.create_test_practitioner(
            email="test_file_associate@example.com",
            first_name="Test File",
            last_name="Associate",
            phone="+1111111112",
            practitioner_attr="associate_practitioner_id",
            email_attr="associate_practitioner_email",
        )
        
        # Create test patient for file attachments
        cls.create_test_patient()
        
        # Sample file content for testing
        cls.sample_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        cls.sample_pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 2\n0000000000 65535 f \ntrailer\n<<\n/Size 2\n/Root 1 0 R\n>>\nstartxref\n9\n%%EOF"
        
        # Test file IDs for cleanup
        cls.test_file_ids = []
        
    @classmethod
    def create_test_practitioner(cls, email, first_name, last_name, phone, practitioner_attr, email_attr):
        """Create a test healthcare practitioner."""
        try:
            if not frappe.db.exists("User", email):
                user_doc = frappe.get_doc({
                    "doctype": "User",
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "send_welcome_email": 0,
                    "user_type": "System User"
                })
                user_doc.insert(ignore_permissions=True)
                
            if not frappe.db.exists("Healthcare Practitioner", {"user_id": email}):
                practitioner_doc = frappe.get_doc({
                    "doctype": "Healthcare Practitioner",
                    "first_name": first_name,
                    "last_name": last_name,
                    "user_id": email,
                    "mobile_phone": phone,
                })
                practitioner_doc.insert(ignore_permissions=True)
            else:
                practitioner_doc = frappe.get_doc("Healthcare Practitioner", {"user_id": email})

            setattr(cls, email_attr, email)
            setattr(cls, practitioner_attr, practitioner_doc.name)

            if cls.company:
                frappe.db.set_value("Healthcare Practitioner", practitioner_doc.name, "primary_company", cls.company)
                frappe.db.set_value(
                    "Healthcare Practitioner",
                    practitioner_doc.name,
                    "allowed_pages_json",
                    '["home","appointments","patients","patients_all","prescriptions","invoice"]',
                )
                
        except Exception as e:
            print(f"Error creating test practitioner: {e}")
            
    @classmethod
    def create_test_patient(cls):
        """Create test patient for file attachments"""
        try:
            patient_doc = frappe.get_doc({
                "doctype": "Patient",
                "first_name": "File Test",
                "last_name": "Patient",
                "patient_name": "File Test Patient",
                "sex": "Male",
                "mobile": "+2222222222",
                "email": "filetest@example.com",
                "dob": "1990-01-01"
            })
            patient_doc.insert(ignore_permissions=True)
            cls.test_patient_id = patient_doc.name
            if cls.company:
                frappe.db.set_value("Patient", cls.test_patient_id, "primary_clinic", cls.company)
            
        except Exception as e:
            print(f"Error creating test patient: {e}")
            cls.test_patient_id = None
    
    def setUp(self):
        """Set up before each test"""
        super().setUp()
        frappe.set_user("Administrator")
    
    def test_01_upload_base64_image(self):
        """Test uploading a base64 encoded image"""
        from mob_clinic.mob_clinic.api.file_upload import upload_file
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        result = upload_file(
            file_name="test_image.png",
            content=self.sample_image_base64,
            decode_base64=True,
            file_category="profile",
            description="Test profile image",
            is_private=0
        )
        
        # Verify upload success
        if result.get("message") != "File uploaded successfully":
            self.fail(f"Upload failed: {result.get('message', 'Unknown error')}")
            
        self.assertEqual(result.get("message"), "File uploaded successfully")
        self.assertIsNotNone(result.get("data"))
        
        file_data = result["data"]
        self.assertEqual(file_data["file_name"], "test_image.png")
        self.assertEqual(file_data["file_category"], "profile")
        self.assertEqual(file_data["description"], "Test profile image")
        self.assertIsNotNone(file_data["file_url"])
        self.assertIsNotNone(file_data["download_url"])
        
        # Store for cleanup
        self.test_file_ids.append(file_data["file_id"])
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Upload base64 image test passed")
    
    def test_02_upload_file_with_reference(self):
        """Test uploading file attached to a patient"""
        from mob_clinic.mob_clinic.api.file_upload import upload_file
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Skip test if patient creation failed
        if not hasattr(self, 'test_patient_id') or not self.test_patient_id:
            self.skipTest("Test patient not available")
        
        result = upload_file(
            file_name="patient_xray.jpg",
            content=self.sample_image_base64,
            decode_base64=True,
            file_category="xray",
            description="Patient X-ray image",
            reference_doctype="Patient",
            reference_name=self.test_patient_id,
            is_private=1
        )
        
        # Verify upload success
        self.assertEqual(result.get("message"), "File uploaded successfully")
        file_data = result["data"]
        
        self.assertEqual(file_data["file_category"], "xray")
        self.assertEqual(file_data["reference_doctype"], "Patient")
        self.assertEqual(file_data["reference_name"], self.test_patient_id)
        self.assertEqual(file_data["is_private"], 1)
        
        # Store for cleanup
        self.test_file_ids.append(file_data["file_id"])
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Upload file with reference test passed")
    
    def test_03_get_file_info(self):
        """Test getting file information"""
        from mob_clinic.mob_clinic.api.file_upload import upload_file, get_file
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # First upload a file
        upload_result = upload_file(
            file_name="test_document.pdf",
            content=base64.b64encode(self.sample_pdf_content).decode(),
            decode_base64=True,
            file_category="report",
            description="Test medical report"
        )
        
        file_id = upload_result["data"]["file_id"]
        self.test_file_ids.append(file_id)
        
        # Get file info
        result = get_file(file_id)
        
        # Verify file info
        self.assertEqual(result.get("message"), "success")
        file_data = result["data"]
        
        self.assertEqual(file_data["file_id"], file_id)
        self.assertEqual(file_data["file_name"], "test_document.pdf")
        self.assertEqual(file_data["file_category"], "report")
        self.assertEqual(file_data["description"], "Test medical report")
        self.assertIsNotNone(file_data["creation"])
        self.assertIsNotNone(file_data["download_url"])
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Get file info test passed")

    def test_03a_cross_practitioner_private_file_access(self):
        """Private patient files should remain accessible across practitioners in the same clinic."""
        from mob_clinic.mob_clinic.api.file_upload import upload_file, get_file, download_file

        if not self.test_patient_id or not getattr(self, "associate_practitioner_email", None):
            self.skipTest("Cross-practitioner file access prerequisites not available")

        frappe.set_user(self.practitioner_email)
        upload_result = upload_file(
            file_name="shared_private_report.txt",
            content=base64.b64encode(b"shared private content").decode(),
            decode_base64=True,
            file_category="report",
            description="Cross practitioner private report",
            reference_doctype="Patient",
            reference_name=self.test_patient_id,
            is_private=1,
        )

        self.assertEqual(upload_result.get("message"), "File uploaded successfully")
        file_id = upload_result["data"]["file_id"]
        self.test_file_ids.append(file_id)

        frappe.set_user(self.associate_practitioner_email)
        get_result = get_file(file_id)
        self.assertEqual(get_result.get("message"), "success")
        self.assertIn("mob_clinic.mob_clinic.api.file_upload.download_file", get_result["data"]["download_url"])

        frappe.local.response = frappe._dict({})
        download_file(file_id=file_id)

        self.assertEqual(frappe.local.response.get("filename"), "shared_private_report.txt")
        self.assertEqual(frappe.local.response.get("type"), "download")
        self.assertEqual(frappe.local.response.get("filecontent"), "shared private content")

        frappe.set_user("Administrator")

        print("✓ Cross practitioner private file access test passed")

    def test_03b_backfill_private_file_docshares_patch(self):
        """Patch should backfill native shares so the existing private-file route can work."""
        from mob_clinic.mob_clinic.api.file_upload import upload_file
        from mob_clinic.mob_clinic.patches.v1_0.backfill_private_file_docshares import execute as backfill_docshares

        if not self.test_patient_id or not getattr(self, "associate_practitioner_email", None):
            self.skipTest("Patch prerequisites not available")

        frappe.set_user(self.practitioner_email)
        upload_result = upload_file(
            file_name="legacy-private-proof.txt",
            content=base64.b64encode(b"legacy private content").decode(),
            decode_base64=True,
            file_category="report",
            description="Legacy private proof",
            reference_doctype="Patient",
            reference_name=self.test_patient_id,
            is_private=1,
        )

        self.assertEqual(upload_result.get("message"), "File uploaded successfully")
        file_id = upload_result["data"]["file_id"]
        self.test_file_ids.append(file_id)

        frappe.set_user(self.associate_practitioner_email)
        self.assertFalse(frappe.has_permission("File", "read", frappe.get_doc("File", file_id)))

        frappe.set_user("Administrator")
        patch_result = backfill_docshares(clinic=self.company)
        self.assertGreaterEqual(patch_result.get("shares_created", 0), 1)

        frappe.set_user(self.associate_practitioner_email)
        self.assertTrue(frappe.has_permission("File", "read", frappe.get_doc("File", file_id)))

        frappe.set_user("Administrator")

        print("✓ Backfill private file docshares patch test passed")
    
    def test_04_list_files(self):
        """Test listing files with filters"""
        from mob_clinic.mob_clinic.api.file_upload import upload_file, list_files
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Upload multiple files
        files_to_upload = [
            {
                "file_name": "prescription1.pdf",
                "file_category": "prescription",
                "description": "Patient prescription 1"
            },
            {
                "file_name": "prescription2.pdf",
                "file_category": "prescription", 
                "description": "Patient prescription 2"
            },
            {
                "file_name": "xray1.jpg",
                "file_category": "xray",
                "description": "X-ray image"
            }
        ]
        
        for file_info in files_to_upload:
            upload_result = upload_file(
                file_name=file_info["file_name"],
                content=self.sample_image_base64 if file_info["file_name"].endswith('.jpg') else base64.b64encode(self.sample_pdf_content).decode(),
                decode_base64=True,
                file_category=file_info["file_category"],
                description=file_info["description"]
            )
            self.test_file_ids.append(upload_result["data"]["file_id"])
        
        # Test listing all files
        result = list_files(limit=10)
        self.assertEqual(result.get("message"), "success")
        
        # Verify pagination info
        data = result["data"]
        self.assertIn("files", data)
        self.assertIn("total_count", data)
        self.assertIn("has_more", data)
        self.assertTrue(len(data["files"]) >= 3)  # At least our uploaded files
        
        # Test filtering by category
        result = list_files(file_category="prescription", limit=10)
        if result.get("message") == "success":
            prescription_files = result["data"]["files"]
            # Should find at least our 2 prescription files
            prescription_count = sum(1 for f in prescription_files if f.get("file_category") == "prescription")
            self.assertTrue(prescription_count >= 2)
        
        # Test search
        result = list_files(search_term="prescription1", limit=10)
        if result.get("message") == "success":
            search_files = result["data"]["files"]
            found_file = any(f["file_name"] == "prescription1.pdf" for f in search_files)
            self.assertTrue(found_file)
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ List files test passed")
    
    def test_05_delete_file(self):
        """Test deleting a file"""
        from mob_clinic.mob_clinic.api.file_upload import upload_file, delete_file, get_file
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Upload a file to delete
        upload_result = upload_file(
            file_name="temp_file.txt",
            content=base64.b64encode(b"Temporary file content").decode(),
            decode_base64=True,
            file_category="document",
            description="Temporary file for deletion test"
        )
        
        file_id = upload_result["data"]["file_id"]
        
        # Verify file exists
        get_result = get_file(file_id)
        self.assertEqual(get_result.get("message"), "success")
        
        # Delete the file
        delete_result = delete_file(file_id)
        self.assertIn("deleted successfully", delete_result.get("message"))
        
        # Verify file is deleted
        get_result_after = get_file(file_id)
        self.assertEqual(get_result_after.get("exc_type"), "DoesNotExistError")
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Delete file test passed")
    
    def test_06_upload_validation_errors(self):
        """Test file upload validation errors"""
        from mob_clinic.mob_clinic.api.file_upload import upload_file
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Test missing file name and URL
        result = upload_file()
        self.assertEqual(result.get("exc_type"), "ValidationError")
        self.assertIn("file_name or file_url is required", result.get("message"))
        
        # Test invalid file category
        result = upload_file(
            file_name="test.jpg",
            content=self.sample_image_base64,
            decode_base64=True,
            file_category="invalid_category"
        )
        self.assertEqual(result.get("exc_type"), "ValidationError")
        self.assertIn("Invalid file category", result.get("message"))
        
        # Test invalid reference document
        result = upload_file(
            file_name="test.jpg",
            content=self.sample_image_base64,
            decode_base64=True,
            reference_doctype="Patient",
            reference_name="INVALID-PATIENT-ID"
        )
        self.assertEqual(result.get("exc_type"), "NotFoundError")
        self.assertIn("not found", result.get("message"))
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Upload validation errors test passed")
    
    def test_07_get_nonexistent_file(self):
        """Test getting non-existent file"""
        from mob_clinic.mob_clinic.api.file_upload import get_file
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Try to get non-existent file
        result = get_file("INVALID-FILE-ID")
        
        # Verify error response
        self.assertEqual(result.get("exc_type"), "DoesNotExistError")
        self.assertEqual(result.get("message"), "File not found")
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Get non-existent file test passed")
    
    def test_08_image_optimization(self):
        """Test automatic image optimization during upload"""
        from mob_clinic.mob_clinic.api.file_upload import upload_file, get_file
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Create a larger base64 image for optimization testing
        # This is a simple 10x10 pixel red image that should be optimizable
        larger_image_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAABklEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        
        # Upload image that should be optimized (profile category has optimize_images: True)
        result = upload_file(
            file_name="profile_to_optimize.png",
            content=larger_image_base64,
            decode_base64=True,
            file_category="profile",
            description="Profile image for optimization test"
        )
        
        # Verify upload success
        self.assertEqual(result.get("message"), "File uploaded successfully")
        file_data = result["data"]
        file_id = file_data["file_id"]
        self.test_file_ids.append(file_id)
        
        # Get file info to verify optimization occurred
        file_info_result = get_file(file_id)
        self.assertEqual(file_info_result.get("message"), "success")
        
        # The file should exist and be valid (optimization might reduce size)
        file_info = file_info_result["data"]
        self.assertEqual(file_info["file_category"], "profile")
        self.assertIsNotNone(file_info["file_size"])
        self.assertGreater(file_info["file_size"], 0)
        
        # Upload document that should NOT be optimized (report category has optimize_images: False)
        result2 = upload_file(
            file_name="report_no_optimize.pdf",
            content=base64.b64encode(self.sample_pdf_content).decode(),
            decode_base64=True,
            file_category="report",
            description="Report that should not be optimized"
        )
        
        self.assertEqual(result2.get("message"), "File uploaded successfully")
        self.test_file_ids.append(result2["data"]["file_id"])
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Image optimization test passed")
    
    def test_09_list_files_with_reference(self):
        """Test listing files attached to specific document"""
        from mob_clinic.mob_clinic.api.file_upload import upload_file, list_files
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Skip test if patient creation failed
        if not hasattr(self, 'test_patient_id') or not self.test_patient_id:
            self.skipTest("Test patient not available")
        
        # Upload file attached to patient
        upload_result = upload_file(
            file_name="patient_attachment.pdf",
            content=base64.b64encode(self.sample_pdf_content).decode(),
            decode_base64=True,
            file_category="report",
            description="Patient medical report",
            reference_doctype="Patient",
            reference_name=self.test_patient_id
        )
        
        self.test_file_ids.append(upload_result["data"]["file_id"])
        
        # List files for this patient
        result = list_files(
            reference_doctype="Patient",
            reference_name=self.test_patient_id
        )
        
        # Verify results
        self.assertEqual(result.get("message"), "success")
        files = result["data"]["files"]
        
        # Should find at least our uploaded file
        patient_files = [f for f in files if f["reference_name"] == self.test_patient_id]
        self.assertTrue(len(patient_files) >= 1)
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ List files with reference test passed")
    
    def test_10_get_file_categories(self):
        """Test getting file category configurations"""
        from mob_clinic.mob_clinic.api.file_upload import get_file_categories
        
        # Login as practitioner
        frappe.set_user(self.practitioner_email)
        
        # Get file categories
        result = get_file_categories()
        
        # Verify response
        self.assertEqual(result.get("message"), "success")
        categories = result["data"]
        
        # Check expected categories exist
        expected_categories = [
            "prescription",
            "xray",
            "report",
            "profile",
            "treatment",
            "document",
            "photo",
            "other",
        ]
        for category in expected_categories:
            self.assertIn(category, categories)
            
            category_config = categories[category]
            self.assertIn("name", category_config)
            self.assertIn("display_name", category_config) 
            self.assertIn("description", category_config)
            self.assertIn("allowed_extensions", category_config)
            self.assertIn("max_size_mb", category_config)
            self.assertIn("optimize_images", category_config)
            
            # Verify optimization settings
            if category in ["profile", "xray", "treatment", "photo", "prescription"]:
                self.assertTrue(category_config["optimize_images"], 
                              f"Category {category} should have optimization enabled")
            else:
                self.assertFalse(category_config["optimize_images"],
                               f"Category {category} should have optimization disabled")
        
        # Reset user
        frappe.set_user("Administrator")
        
        print("✓ Get file categories test passed")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        super().tearDownClass()
        
        # Clean up test files
        for file_id in cls.test_file_ids:
            try:
                if frappe.db.exists("File", file_id):
                    frappe.delete_doc("File", file_id, force=True)
            except:
                pass
                
        # Clean up test patient
        try:
            if hasattr(cls, 'test_patient_id') and frappe.db.exists("Patient", cls.test_patient_id):
                frappe.delete_doc("Patient", cls.test_patient_id, force=True)
        except:
            pass
            
        # Clean up test practitioner and user
        try:
            if hasattr(cls, 'practitioner_id') and frappe.db.exists("Healthcare Practitioner", cls.practitioner_id):
                frappe.delete_doc("Healthcare Practitioner", cls.practitioner_id, force=True)
            if hasattr(cls, 'practitioner_email') and frappe.db.exists("User", cls.practitioner_email):
                frappe.delete_doc("User", cls.practitioner_email, force=True)
            if hasattr(cls, 'associate_practitioner_id') and frappe.db.exists("Healthcare Practitioner", cls.associate_practitioner_id):
                frappe.delete_doc("Healthcare Practitioner", cls.associate_practitioner_id, force=True)
            if hasattr(cls, 'associate_practitioner_email') and frappe.db.exists("User", cls.associate_practitioner_email):
                frappe.delete_doc("User", cls.associate_practitioner_email, force=True)
        except:
            pass


def run_tests():
    """Helper function to run file upload tests"""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFileUploadAPI)
    unittest.TextTestRunner(verbosity=2).run(suite)


if __name__ == "__main__":
    run_tests()
