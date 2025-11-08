"""
File Upload APIs for Mobile Clinic Management System

This module handles file uploads for:
- Prescription documents/images
- X-ray images
- Medical reports (PDF)
- Profile pictures
- Treatment photos

Uses Frappe's built-in File DocType for secure file handling.
"""

import frappe
import os
import json
import base64
import re
from frappe import _
from frappe.utils import get_files_path, get_url, cstr, now_datetime
from frappe.core.api.file import create_new_folder


def secure_filename(filename):
    """
    Simple secure filename function - removes/replaces unsafe characters
    """
    if not filename:
        return filename
    # Remove or replace unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = re.sub(r'\s+', '_', filename)
    return filename.strip('.')



@frappe.whitelist(methods=['POST'])
def upload_file(file_name=None, content=None, decode_base64=False, folder="Home", 
                is_private=0, file_url=None, reference_doctype=None, reference_name=None,
                file_category=None, description=None):
    """
    Upload file for mobile clinic management
    
    Args:
        file_name (str): Name of the file
        content (str): Base64 encoded file content or binary content
        decode_base64 (bool): Whether to decode base64 content
        folder (str): Folder to store the file (default: Home)
        is_private (int): Whether file is private (1) or public (0)
        file_url (str): URL of external file
        reference_doctype (str): DocType this file is attached to
        reference_name (str): Document name this file is attached to
        file_category (str): Category (prescription, xray, report, profile)
        description (str): File description
        
    Returns:
        dict: File information with download URL
    """
    try:
        # Validate inputs
        if not file_name and not file_url:
            return {
                "exc_type": "ValidationError",
                "message": "Either file_name or file_url is required"
            }
            
        # Validate file category
        valid_categories = ["prescription", "xray", "report", "profile", "treatment", "document"]
        if file_category and file_category not in valid_categories:
            return {
                "exc_type": "ValidationError", 
                "message": f"Invalid file category. Must be one of: {', '.join(valid_categories)}"
            }
            
        # Validate reference document if provided
        if reference_doctype and reference_name:
            if not frappe.db.exists(reference_doctype, reference_name):
                return {
                    "exc_type": "ValidationError",
                    "message": f"{reference_doctype} {reference_name} does not exist"
                }
                
        # Create folder structure using Frappe's pattern
        clinic_folder_name = "Clinic Files"
        
        # Create main clinic folder if it doesn't exist
        if not frappe.db.exists("File", {"file_name": clinic_folder_name, "is_folder": 1, "folder": "Home"}):
            clinic_folder = create_new_folder(clinic_folder_name, "Home")
        else:
            clinic_folder = frappe.get_doc("File", {"file_name": clinic_folder_name, "is_folder": 1, "folder": "Home"})
        
        target_folder = clinic_folder.name  # This will be "Home/Clinic Files"
        
        # Create category subfolder if specified
        if file_category:
            category_folder_name = f"{file_category.title()} Files"
            category_folder_path = f"{clinic_folder.name}/{category_folder_name}"
            
            if not frappe.db.exists("File", {"file_name": category_folder_name, "is_folder": 1, "folder": clinic_folder.name}):
                category_folder = create_new_folder(category_folder_name, clinic_folder.name)
                target_folder = category_folder.name
            else:
                target_folder = category_folder_path
            
        # Secure filename
        if file_name:
            file_name = secure_filename(file_name)
            
        # Handle base64 content
        if content and decode_base64:
            try:
                content = base64.b64decode(content)
            except Exception as e:
                return {
                    "exc_type": "ValidationError",
                    "message": f"Invalid base64 content: {str(e)}"
                }
                
        # Create file document
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "folder": target_folder,
            "is_private": is_private,
            "attached_to_doctype": reference_doctype,
            "attached_to_name": reference_name,
        })
        
        # Add content if provided (this will trigger save_file)
        if content:
            file_doc.content = content
        elif file_url:
            file_doc.file_url = file_url
            
        # Insert the file (this will call save_file and handle content)
        file_doc.insert(ignore_permissions=True)
        
        # Store custom metadata in comment
        if file_category or description:
            try:
                # Add metadata as comment
                file_doc.add_comment("Info", f"Category: {file_category or 'None'}, Description: {description or 'N/A'}")
            except Exception as e:
                # Don't fail upload if comment fails
                frappe.logger().warning(f"Could not add metadata comment to {file_doc.name}: {str(e)}")
        
        # Optimize image files automatically based on category configuration
        if content and file_category:
            category_config = get_file_category_config().get(file_category, {})
            if category_config.get("optimize_images", False):
                try:
                    optimized = optimize_uploaded_image(file_doc)
                    if optimized:
                        frappe.logger().info(f"Optimized image file: {file_doc.name} (category: {file_category})")
                except Exception as e:
                    # Don't fail upload if optimization fails, just log it
                    frappe.logger().warning(f"Image optimization failed for {file_doc.name}: {str(e)}")
        
        # Get file information
        file_info = {
            "file_id": file_doc.name,
            "file_name": file_doc.file_name,
            "file_url": file_doc.file_url,
            "file_size": file_doc.file_size or 0,
            "is_private": file_doc.is_private,
            "folder": file_doc.folder,
            "creation": file_doc.creation,
            "owner": file_doc.owner,
            "file_category": file_category,
            "description": description,
            "reference_doctype": reference_doctype,
            "reference_name": reference_name
        }
        
        # Add download URL
        if file_doc.file_url:
            if file_doc.is_private:
                file_info["download_url"] = f"/api/method/frappe.core.doctype.file.file.download_file?file_url={file_doc.file_url}"
            else:
                file_info["download_url"] = get_url(file_doc.file_url)
                
        return {
            "message": "File uploaded successfully",
            "data": file_info
        }
        
    except frappe.DuplicateEntryError:
        return {
            "exc_type": "DuplicateEntryError",
            "message": "File with this name already exists"
        }
    except Exception as e:
        frappe.log_error(f"File upload error: {str(e)}")
        return {
            "exc_type": "FileUploadError",
            "message": f"File upload failed: {str(e)}"
        }


@frappe.whitelist(methods=['GET'])
def get_file(file_id):
    """
    Get file information by file ID
    
    Args:
        file_id (str): File document ID
        
    Returns:
        dict: File information
    """
    try:
        # Get file document
        file_doc = frappe.get_doc("File", file_id)
        
        # Check permissions
        if file_doc.is_private and not frappe.has_permission("File", "read", file_doc):
            return {
                "exc_type": "PermissionError",
                "message": "You don't have permission to access this file"
            }
            
        # Build file information
        file_info = {
            "file_id": file_doc.name,
            "file_name": file_doc.file_name,
            "file_url": file_doc.file_url,
            "file_size": file_doc.file_size or 0,
            "is_private": file_doc.is_private,
            "folder": file_doc.folder,
            "creation": file_doc.creation,
            "modified": file_doc.modified,
            "owner": file_doc.owner,
            "reference_doctype": file_doc.attached_to_doctype,
            "reference_name": file_doc.attached_to_name,
        }
        
        # Extract custom metadata from comments
        comments = frappe.get_all("Comment", 
            filters={"reference_doctype": "File", "reference_name": file_doc.name, "comment_type": "Info"},
            fields=["content"], 
            order_by="creation desc", 
            limit=1
        )
        
        file_category = None
        description = None
        
        if comments:
            comment_content = comments[0].content
            # Parse category and description from comment
            if "Category:" in comment_content:
                try:
                    parts = comment_content.split(", ")
                    if len(parts) >= 1:
                        category_part = parts[0].replace("Category: ", "")
                        file_category = category_part if category_part != "None" else None
                    if len(parts) >= 2:
                        desc_part = parts[1].replace("Description: ", "")
                        description = desc_part if desc_part != "N/A" else None
                except:
                    pass
        
        # Add parsed metadata
        file_info["file_category"] = file_category
        file_info["description"] = description
            
        # Add download URL
        if file_doc.file_url:
            if file_doc.is_private:
                file_info["download_url"] = f"/api/method/frappe.core.doctype.file.file.download_file?file_url={file_doc.file_url}"
            else:
                file_info["download_url"] = get_url(file_doc.file_url)
                
        return {
            "message": "success",
            "data": file_info
        }
        
    except frappe.DoesNotExistError:
        return {
            "exc_type": "DoesNotExistError",
            "message": "File not found"
        }
    except Exception as e:
        frappe.log_error(f"Get file error: {str(e)}")
        return {
            "exc_type": "FileAccessError",
            "message": f"Could not access file: {str(e)}"
        }


@frappe.whitelist(methods=['POST', 'DELETE'])
def delete_file(file_id):
    """
    Delete a file
    
    Args:
        file_id (str): File document ID
        
    Returns:
        dict: Success message
    """
    try:
        # Get file document
        file_doc = frappe.get_doc("File", file_id)
        
        # Check permissions
        if not frappe.has_permission("File", "delete", file_doc):
            return {
                "exc_type": "PermissionError",
                "message": "You don't have permission to delete this file"
            }
            
        # Store file info before deletion
        file_name = file_doc.file_name
        
        # Delete the file
        file_doc.delete()
        
        return {
            "message": f"File '{file_name}' deleted successfully"
        }
        
    except frappe.DoesNotExistError:
        return {
            "exc_type": "DoesNotExistError",
            "message": "File not found"
        }
    except Exception as e:
        frappe.log_error(f"Delete file error: {str(e)}")
        return {
            "exc_type": "FileDeletionError",
            "message": f"Could not delete file: {str(e)}"
        }


@frappe.whitelist(methods=['GET'])
def list_files(reference_doctype=None, reference_name=None, file_category=None, 
               folder=None, limit=20, offset=0, search_term=None):
    """
    List files with filtering options
    
    Args:
        reference_doctype (str): Filter by attached DocType
        reference_name (str): Filter by attached document
        file_category (str): Filter by file category
        folder (str): Filter by folder
        limit (int): Number of files to return
        offset (int): Pagination offset
        search_term (str): Search in file names
        
    Returns:
        dict: List of files with pagination
    """
    try:
        # Build filters
        filters = {}
        
        if reference_doctype:
            filters["attached_to_doctype"] = reference_doctype
        if reference_name:
            filters["attached_to_name"] = reference_name
        if folder:
            filters["folder"] = folder
            
        # Add file category filter if available as custom field
        if file_category and frappe.db.has_column("File", "file_category"):
            filters["file_category"] = file_category
            
        # Search filters
        or_filters = []
        if search_term:
            or_filters = [
                ["file_name", "like", f"%{search_term}%"],
                ["description", "like", f"%{search_term}%"] if frappe.db.has_column("File", "description") else None
            ]
            or_filters = [f for f in or_filters if f]  # Remove None filters
            
        # Get files
        files = frappe.get_all(
            "File",
            fields=[
                "name as file_id",
                "file_name", 
                "file_url",
                "file_size",
                "is_private",
                "folder",
                "creation",
                "modified",
                "owner",
                "attached_to_doctype as reference_doctype",
                "attached_to_name as reference_name"
            ],
            filters=filters,
            or_filters=or_filters if or_filters else None,
            order_by="creation desc",
            limit_start=offset,
            limit_page_length=limit
        )
        
        # Enhance file information and apply category filter if needed
        filtered_files = []
        for file_info in files:
            # Extract category and description from comments
            comments = frappe.get_all("Comment", 
                filters={"reference_doctype": "File", "reference_name": file_info["file_id"], "comment_type": "Info"},
                fields=["content"], 
                order_by="creation desc", 
                limit=1
            )
            
            file_category_found = None
            description_found = None
            
            if comments:
                comment_content = comments[0].content
                if "Category:" in comment_content:
                    try:
                        parts = comment_content.split(", ")
                        if len(parts) >= 1:
                            category_part = parts[0].replace("Category: ", "")
                            file_category_found = category_part if category_part != "None" else None
                        if len(parts) >= 2:
                            desc_part = parts[1].replace("Description: ", "")
                            description_found = desc_part if desc_part != "N/A" else None
                    except:
                        pass
            
            # Apply category filter
            if file_category and file_category_found != file_category:
                continue
                
            # Add metadata to file info
            file_info["file_category"] = file_category_found
            file_info["description"] = description_found
                
            # Add download URL
            if file_info["file_url"]:
                if file_info["is_private"]:
                    file_info["download_url"] = f"/api/method/frappe.core.doctype.file.file.download_file?file_url={file_info['file_url']}"
                else:
                    file_info["download_url"] = get_url(file_info["file_url"])
                    
            # Format file size
            if file_info["file_size"]:
                file_info["file_size_formatted"] = format_file_size(file_info["file_size"])
                
            filtered_files.append(file_info)
                
        # Get total count for pagination (approximate since we're filtering)
        total_count = len(filtered_files) if file_category else frappe.db.count("File", filters=filters)
        
        return {
            "message": "success",
            "data": {
                "files": filtered_files,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + limit) < total_count
            }
        }
        
    except Exception as e:
        frappe.log_error(f"List files error: {str(e)}")
        return {
            "exc_type": "FileListError",
            "message": f"Could not list files: {str(e)}"
        }


@frappe.whitelist(methods=['GET'])
def get_file_categories():
    """
    Get available file categories and their configurations
    
    Returns:
        dict: File category configurations
    """
    try:
        categories = get_file_category_config()
        
        # Format for API response
        formatted_categories = {}
        for category, config in categories.items():
            formatted_categories[category] = {
                "name": category,
                "display_name": category.title(),
                "description": config["description"],
                "allowed_extensions": config["allowed_extensions"],
                "max_size_mb": config["max_size_mb"],
                "optimize_images": config.get("optimize_images", False)
            }
        
        return {
            "message": "success",
            "data": formatted_categories
        }
        
    except Exception as e:
        frappe.log_error(f"Get file categories error: {str(e)}")
        return {
            "exc_type": "FileCategoryError",
            "message": f"Could not get file categories: {str(e)}"
        }


# Helper Functions
def optimize_uploaded_image(file_doc):
    """
    Optimize uploaded image using Frappe's built-in optimization
    
    Args:
        file_doc: File document instance
        
    Returns:
        bool: True if optimization was successful, False otherwise
    """
    try:
        # Check if it's an image file that can be optimized
        if not file_doc.file_name:
            return False
            
        import mimetypes
        content_type = mimetypes.guess_type(file_doc.file_name)[0]
        
        if not content_type or not content_type.startswith("image/"):
            return False
            
        # Skip SVG files as they can't be optimized
        if content_type == "image/svg+xml":
            return False
            
        # Only optimize if file has content and size
        if not file_doc.file_size or file_doc.file_size == 0:
            return False
            
        # Call Frappe's built-in optimization
        file_doc.optimize_file()
        
        return True
        
    except (TypeError, NotImplementedError) as e:
        # These are expected for non-optimizable files
        frappe.logger().debug(f"File {file_doc.name} cannot be optimized: {str(e)}")
        return False
    except Exception as e:
        # Log unexpected errors but don't fail
        frappe.logger().error(f"Unexpected error optimizing {file_doc.name}: {str(e)}")
        return False


def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


def get_current_practitioner():
    """Get current user's healthcare practitioner record"""
    try:
        return frappe.get_doc("Healthcare Practitioner", {"user_id": frappe.session.user})
    except frappe.DoesNotExistError:
        return None


def validate_file_type(file_name, allowed_extensions):
    """Validate file type against allowed extensions"""
    if not file_name:
        return False
        
    file_extension = file_name.lower().split('.')[-1]
    return file_extension in allowed_extensions


def get_file_category_config():
    """Get file category configuration"""
    return {
        "prescription": {
            "allowed_extensions": ["pdf", "jpg", "jpeg", "png", "doc", "docx"],
            "max_size_mb": 10,
            "description": "Prescription documents and images",
            "optimize_images": True
        },
        "xray": {
            "allowed_extensions": ["jpg", "jpeg", "png", "dicom", "dcm"],
            "max_size_mb": 25,
            "description": "X-ray and diagnostic images",
            "optimize_images": True
        },
        "report": {
            "allowed_extensions": ["pdf", "doc", "docx"],
            "max_size_mb": 15,
            "description": "Medical reports and lab results",
            "optimize_images": False
        },
        "profile": {
            "allowed_extensions": ["jpg", "jpeg", "png"],
            "max_size_mb": 5,
            "description": "Profile pictures",
            "optimize_images": True
        },
        "treatment": {
            "allowed_extensions": ["jpg", "jpeg", "png", "mp4", "mov"],
            "max_size_mb": 50,
            "description": "Treatment progress photos and videos",
            "optimize_images": True
        },
        "document": {
            "allowed_extensions": ["pdf", "doc", "docx", "txt"],
            "max_size_mb": 10,
            "description": "General medical documents",
            "optimize_images": False
        }
    }