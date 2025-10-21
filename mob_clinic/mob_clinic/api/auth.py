import frappe
from frappe import _
from frappe.auth import LoginManager
from frappe.utils import cstr, get_fullname
import json

@frappe.whitelist(allow_guest=True)
def mobile_login(usr, pwd):
    """
    Custom login method for mobile app with enhanced response
    
    Args:
        usr (str): Username (email or phone)
        pwd (str): Password
    
    Returns:
        dict: Enhanced login response with user profile and clinic details
    """
    try:
        # Attempt to login using Frappe's built-in method
        login_manager = LoginManager()
        login_manager.authenticate(user=usr, pwd=pwd)
        login_manager.post_login()
        
        if frappe.response.get("message") == "Logged In":
            # Get user details
            user = frappe.get_doc("User", frappe.session.user)
            
            # Get healthcare practitioner details if exists
            practitioner = None
            try:
                practitioner = frappe.get_doc("Healthcare Practitioner", {"user_id": user.name})
            except frappe.DoesNotExistError:
                pass
            
            # Prepare enhanced response
            response_data = {
                "message": "Logged In",
                "home_page": "/app",
                "full_name": get_fullname(user.name),
                "user": {
                    "id": user.name,
                    "name": get_fullname(user.name),
                    "email": user.email,
                    "phone": user.mobile_no or user.phone,
                    "role": "doctor" if practitioner else "user",
                    "avatar": user.user_image,
                    "first_login": user.last_login is None
                }
            }
            
            # Add practitioner/clinic details if exists
            if practitioner:
                clinic_data = {
                    "practitioner_id": practitioner.name,
                    "name": practitioner.practitioner_name,
                    "department": practitioner.department,
                    "mobile_app_enabled": getattr(practitioner, 'mobile_app_enabled', 0),
                    "phone": practitioner.mobile_phone,
                    "consultation_fee": getattr(practitioner, 'consultation_fee', 0),
                    "clinic_logo": getattr(practitioner, 'clinic_logo', None),
                    "clinic_description": getattr(practitioner, 'clinic_description', ''),
                    "online_consultation": getattr(practitioner, 'online_consultation', 0)
                }
                
                # Get working hours if exists
                working_hours = []
                if hasattr(practitioner, 'clinic_working_hours'):
                    for row in practitioner.clinic_working_hours:
                        working_hours.append({
                            "day": row.day,
                            "is_working_day": row.is_working_day,
                            "start_time": cstr(row.start_time),
                            "end_time": cstr(row.end_time)
                        })
                
                clinic_data["working_hours"] = working_hours
                response_data["user"]["clinic"] = clinic_data
                
                # Update app_user_id and last login
                if not getattr(practitioner, 'app_user_id', None):
                    frappe.db.set_value("Healthcare Practitioner", practitioner.name, 
                                      "app_user_id", user.name, update_modified=False)
                    
            return response_data
            
        else:
            frappe.local.response["http_status_code"] = 401
            return {
                "exc_type": "AuthenticationError",
                "message": "Invalid credentials"
            }
            
    except frappe.AuthenticationError:
        frappe.local.response["http_status_code"] = 401
        return {
            "exc_type": "AuthenticationError", 
            "message": "Invalid credentials"
        }
    except Exception as e:
        frappe.log_error(f"Mobile login error: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Internal server error during login"
        }

@frappe.whitelist(allow_guest=True)
def mobile_register(full_name, email, phone, password, clinic_name, **kwargs):
    """
    Register a new doctor/healthcare practitioner
    
    Args:
        full_name (str): Full name of the doctor
        email (str): Email address
        phone (str): Phone number
        password (str): Password
        clinic_name (str): Clinic name
        **kwargs: Additional optional fields
    
    Returns:
        dict: Registration response
    """
    try:
        # Validate required fields
        if not all([full_name, email, password, clinic_name]):
            frappe.local.response["http_status_code"] = 400
            return {
                "exc_type": "ValidationError",
                "message": "Missing required fields: full_name, email, password, clinic_name"
            }
        
        # Check if user already exists
        if frappe.db.exists("User", email):
            frappe.local.response["http_status_code"] = 409
            return {
                "exc_type": "ValidationError", 
                "message": "User with this email already exists"
            }
        
        # Split full name
        name_parts = full_name.split()
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        
        # Create user
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "new_password": password,
            "mobile_no": phone,
            "user_type": "System User",
            "role_profile_name": "Healthcare Practitioner"
        })
        user.insert(ignore_permissions=True)
        
        # Create Healthcare Practitioner
        practitioner = frappe.get_doc({
            "doctype": "Healthcare Practitioner",
            "first_name": first_name,
            "last_name": last_name,
            "user_id": user.name,
            "mobile_phone": phone,
            "mobile_app_enabled": 1,
            "app_user_id": user.name,
            "clinic_description": clinic_name,
            **kwargs  # Additional fields like specialization, qualification, etc.
        })
        practitioner.insert(ignore_permissions=True)
        
        frappe.db.commit()
        
        return {
            "message": "Registration successful",
            "user_id": user.name,
            "practitioner_id": practitioner.name
        }
        
    except frappe.DuplicateEntryError:
        frappe.local.response["http_status_code"] = 409
        return {
            "exc_type": "ValidationError",
            "message": "User with this email already exists"
        }
    except Exception as e:
        frappe.log_error(f"Mobile registration error: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Internal server error during registration"
        }

@frappe.whitelist()
def mobile_logout():
    """
    Custom logout method for mobile app
    
    Returns:
        dict: Logout response
    """
    try:
        frappe.local.login_manager.logout()
        return {
            "message": "Logged Out"
        }
    except Exception as e:
        frappe.log_error(f"Mobile logout error: {str(e)}")
        return {
            "exc_type": "ServerError", 
            "message": "Error during logout"
        }

@frappe.whitelist()
def get_practitioner_profile():
    """
    Get current healthcare practitioner's profile
    
    Returns:
        dict: Practitioner profile data
    """
    try:
        user = frappe.session.user
        practitioner = frappe.get_doc("Healthcare Practitioner", {"user_id": user})
        
        profile_data = {
            "id": practitioner.name,
            "name": practitioner.practitioner_name,
            "first_name": practitioner.first_name,
            "last_name": practitioner.last_name,
            "phone": practitioner.mobile_phone,
            "email": frappe.get_value("User", user, "email"),
            "department": practitioner.department,
            "designation": practitioner.designation,
            "employee": practitioner.employee,
            "mobile_app_enabled": getattr(practitioner, 'mobile_app_enabled', 0),
            "consultation_fee": getattr(practitioner, 'consultation_fee', 0),
            "online_consultation": getattr(practitioner, 'online_consultation', 0),
            "clinic_logo": getattr(practitioner, 'clinic_logo', None),
            "clinic_description": getattr(practitioner, 'clinic_description', ''),
            "avatar": practitioner.image
        }
        
        # Get working hours
        working_hours = []
        if hasattr(practitioner, 'clinic_working_hours'):
            for row in practitioner.clinic_working_hours:
                working_hours.append({
                    "day": row.day,
                    "is_working_day": row.is_working_day,
                    "start_time": cstr(row.start_time),
                    "end_time": cstr(row.end_time)
                })
        
        profile_data["working_hours"] = working_hours
        
        return {
            "message": "success",
            "data": profile_data
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": "Healthcare Practitioner profile not found"
        }
    except Exception as e:
        frappe.log_error(f"Get practitioner profile error: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error retrieving practitioner profile"
        }

@frappe.whitelist()
def update_practitioner_profile(**kwargs):
    """
    Update healthcare practitioner profile
    
    Args:
        **kwargs: Fields to update
        
    Returns:
        dict: Update response
    """
    try:
        user = frappe.session.user
        practitioner = frappe.get_doc("Healthcare Practitioner", {"user_id": user})
        
        # Update allowed fields
        allowed_fields = [
            'mobile_phone', 'consultation_fee', 'online_consultation',
            'clinic_logo', 'clinic_description', 'department', 'designation'
        ]
        
        updated_fields = []
        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(practitioner, field):
                setattr(practitioner, field, value)
                updated_fields.append(field)
        
        if updated_fields:
            practitioner.save()
            frappe.db.commit()
            
        return {
            "message": "Profile updated successfully",
            "updated_fields": updated_fields
        }
        
    except frappe.DoesNotExistError:
        frappe.local.response["http_status_code"] = 404
        return {
            "exc_type": "NotFound",
            "message": "Healthcare Practitioner profile not found"
        }
    except Exception as e:
        frappe.log_error(f"Update practitioner profile error: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": "Error updating practitioner profile"
        }