import frappe
from frappe import _
from frappe.auth import LoginManager
from frappe.utils import cstr, get_fullname
import json

from mob_clinic.mob_clinic.api import clinic as clinic_helper
from mob_clinic.mob_clinic.api.role_access import get_practitioner_permissions

@frappe.whitelist(allow_guest=True, methods=['POST'])
def mobile_login(usr, pwd):
    """
    Custom login method for mobile app with enhanced response
    Uses Frappe's standard login mechanism to ensure proper session management
    
    Args:
        usr (str): Username (email or phone)
        pwd (str): Password
    
    Returns:
        dict: Enhanced login response with user profile and clinic details
    """
    # Explicitly ignore CSRF for mobile login
    frappe.flags.ignore_csrf = True
    
    try:
        # Check if we're in test context (no HTTP request)
        in_test_context = not hasattr(frappe.local, 'request')
        
        if in_test_context:
            # For tests: use direct password check and set user
            frappe.auth.check_password(usr, pwd)
            frappe.set_user(usr)
            logged_in = True
        else:
            # For HTTP requests: use LoginManager with proper initialization
            login_manager = LoginManager()
            login_manager.authenticate(user=usr, pwd=pwd)
            login_manager.post_login()
            
            # IMPORTANT: Check if login was successful by verifying the session user
            logged_in = frappe.session.user != "Guest"
        
        if logged_in:
            # Get user details
            user = frappe.get_doc("User", frappe.session.user)
            
            # Get healthcare practitioner details if exists
            practitioner = None
            try:
                practitioner = frappe.get_doc("Healthcare Practitioner", {"user_id": user.name})
            except (frappe.DoesNotExistError, Exception):
                # No practitioner profile - user might be admin or non-healthcare user
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
                permissions = get_practitioner_permissions(practitioner)

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

                # Provide list of accessible clinics and resolved active clinic
                try:
                    clinics = clinic_helper.get_accessible_companies_for_practitioner(practitioner.name)
                    # IMPORTANT: Ignore old session value during login to get fresh clinic for this practitioner
                    active_clinic = clinic_helper.resolve_active_clinic(
                        practitioner_name=practitioner.name, 
                        clinic_param=None,
                        ignore_session=True  # Don't use old session's active_clinic during login
                    )
                except Exception:
                    clinics = []
                    active_clinic = None

                response_data["user"]["clinics"] = clinics
                response_data["user"]["active_clinic"] = active_clinic
                response_data["user"]["is_clinic_admin"] = permissions["is_clinic_admin"]
                response_data["user"]["allowed_pages"] = permissions["allowed_pages"]
                response_data["user"]["permissions"] = permissions

                # Persist active clinic to session if resolved (force reset for new login)
                if active_clinic:
                    clinic_helper.set_active_clinic_session(active_clinic)
                
                # Update app_user_id and last login
                if not getattr(practitioner, 'app_user_id', None):
                    frappe.db.set_value("Healthcare Practitioner", practitioner.name, 
                                      "app_user_id", user.name, update_modified=False)
                    
            # --- Ensure persistent helper cookies ---
            try:
                # Read cookie_max_age from site config (seconds). Default to 7 days.
                cookie_max_age = frappe.conf.get("cookie_max_age", 604800)
                try:
                    cookie_max_age = int(cookie_max_age)
                except Exception:
                    cookie_max_age = 604800

                cm = frappe.local.cookie_manager
                cm.set_cookie("full_name", cstr(get_fullname(user.name) or ""), max_age=cookie_max_age, samesite='Lax')
                cm.set_cookie("user_id", user.name, max_age=cookie_max_age, samesite='Lax')
                cm.set_cookie("system_user", "yes", max_age=cookie_max_age, samesite='Lax')
                cm.set_cookie("user_image", getattr(user, 'user_image', '') or "", max_age=cookie_max_age, samesite='Lax')
            except Exception:
                print(frappe.get_traceback())
                # Do not break login flow if cookie setting fails
                frappe.log_error(frappe.get_traceback(), "mobile_login_cookie_set")

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
        }


@frappe.whitelist(allow_guest=True, methods=['POST'])
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
            "send_welcome_email": 0
        })
        user.flags.ignore_permissions = True
        user.flags.ignore_password_policy = True
        user.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Create Healthcare Practitioner
        practitioner = frappe.get_doc({
            "doctype": "Healthcare Practitioner",
            "first_name": first_name,
            "last_name": last_name,
            "status": "Active",
            "user_id": user.name,
            "mobile_phone": phone,
            "mobile_app_enabled": 1,
            "app_user_id": user.name,
            "clinic_description": clinic_name,
            # If admin passed a clinic/company name treat it as primary_company when valid
            **({"primary_company": clinic_name} if clinic_name else {}),
            **kwargs  # Additional fields like specialization, qualification, etc.
        })
        practitioner.flags.ignore_permissions = True
        practitioner.flags.ignore_mandatory = True
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
    except frappe.exceptions.ValidationError as e:
        frappe.local.response["http_status_code"] = 400
        return {
            "exc_type": "ValidationError",
            "message": str(e)
        }
    except Exception as e:
        error_msg = str(e)
        # Log with shorter title
        frappe.log_error(error_msg, "Registration Error")
        frappe.local.response["http_status_code"] = 500
        return {
            "exc_type": "ServerError",
            "message": f"Internal server error during registration: {error_msg[:100]}"
        }


@frappe.whitelist(methods=['POST'])
def switch_clinic(clinic: str = None):
    """Switch the active clinic for the current session after validating access.

    Request body: { "clinic": "Clinic Name" }
    """
    try:
        user = frappe.session.user
        # find linked practitioner
        try:
            practitioner = frappe.get_doc("Healthcare Practitioner", {"user_id": user})
            practitioner_name = practitioner.name
        except Exception:
            practitioner_name = None

        # Validate access
        if clinic and not clinic_helper.validate_practitioner_access(practitioner_name, clinic):
            frappe.local.response["http_status_code"] = 403
            return {"exc_type": "PermissionError", "message": "Practitioner does not have access to the requested clinic"}

        # set session
        clinic_helper.set_active_clinic_session(clinic)
        return {"message": "active_clinic_set", "active_clinic": clinic}

    except Exception as e:
        frappe.log_error(f"Switch clinic error: {str(e)}")
        frappe.local.response["http_status_code"] = 500
        return {"exc_type": "ServerError", "message": "Error switching clinic"}

@frappe.whitelist(methods=['POST'])
def mobile_logout():
    """
    Custom logout method for mobile app
    
    Returns:
        dict: Logout response
    """
    try:
        # Check if we're in test context
        if hasattr(frappe.local, 'login_manager'):
            frappe.local.login_manager.logout()
        else:
            # For tests: just clear the user
            frappe.set_user("Guest")
        # Clear helper cookies on logout so clients don't keep stale values
        try:
            cm = frappe.local.cookie_manager
            for _c in ("full_name", "user_id", "system_user", "user_image", "sid"):
                try:
                    cm.set_cookie(_c, "", max_age=0, samesite='Lax')
                except Exception:
                    # ignore per-cookie failures
                    pass
        except Exception:
            frappe.log_error(frappe.get_traceback(), "mobile_logout_cookie_clear")

        return {
            "message": "Logged Out"
        }
    except Exception as e:
        frappe.log_error(f"Mobile logout error: {str(e)}")
        return {
            "exc_type": "ServerError", 
            "message": "Error during logout"
        }

@frappe.whitelist(methods=['GET'])
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

        permissions = get_practitioner_permissions(practitioner)
        profile_data["is_clinic_admin"] = permissions["is_clinic_admin"]
        profile_data["allowed_pages"] = permissions["allowed_pages"]
        profile_data["permissions"] = permissions
        
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
        
        # Add clinic data for frontend
        try:
            clinics = clinic_helper.get_accessible_companies_for_practitioner(practitioner.name)
            active_clinic = clinic_helper.resolve_active_clinic(
                practitioner_name=practitioner.name,
                clinic_param=None
            )
            profile_data["clinics"] = clinics
            profile_data["active_clinic"] = active_clinic
        except Exception:
            profile_data["clinics"] = []
            profile_data["active_clinic"] = None
        
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

@frappe.whitelist(methods=['POST', 'PUT'])
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
            practitioner.flags.ignore_permissions = True
            practitioner.save(ignore_permissions=True)
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