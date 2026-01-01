import frappe
import json
from mob_clinic.mob_clinic.api.clinic_profile import get_clinic_profile

@frappe.whitelist(allow_guest=True)
def get_public_landing_data(clinic):
    """
    Composite endpoint to fetch all data needed for the public landing page.
    Reads from Clinic Settings with fallback to defaults.
    """
    try:
        # 1. Get Base Profile
        profile_response = get_clinic_profile(clinic)
        profile = profile_response.get("profile", {})
        
        # 2. Get Clinic Settings (for landing page customization)
        settings = None
        if frappe.db.exists("Clinic Settings", clinic):
            settings = frappe.get_doc("Clinic Settings", clinic)
        
        # 3. Get Doctors
        practitioners = frappe.get_all(
            "Healthcare Practitioner",
            fields=["name", "practitioner_name", "department", "image"],
            filters={"status": "Active", "primary_company": clinic},
            limit=6
        )
        
        formatted_doctors = []
        for doc in practitioners:
            formatted_doctors.append({
                "id": doc.name,
                "name": doc.practitioner_name,
                "specialization": doc.department or "General Dentistry",
                "image": doc.image or "",
                "bio": f"Experienced {doc.department or 'Dentist'} dedicated to your smile."
            })

        # 4. Get Treatments
        treatments = frappe.get_all(
            "Item",
            fields=["item_code", "item_name", "description", "standard_rate", "image"],
            filters={"is_sales_item": 1, "disabled": 0},
            limit=6
        )
        
        formatted_treatments = []
        for t in treatments:
            formatted_treatments.append({
                "id": t.item_code,
                "title": t.item_name,
                "description": t.description or "Professional dental care procedure.",
                "price": t.standard_rate,
                "image": t.image
            })

        # 5. Load from Clinic Settings OR use fallback defaults
        # Stats
        default_stats = {
            "patients": "5,000+",
            "years_experience": "12+",
            "reviews": "4.9/5",
            "surgeries": "1,200+"
        }
        stats = default_stats
        if settings and settings.get("landing_page_stats_json"):
            try:
                stats = json.loads(settings.landing_page_stats_json)
            except:
                pass

        # Testimonials
        default_testimonials = [
            {"id": 1, "name": "Sarah Johnson", "role": "Patient", "content": "The best dental experience I've ever had. The team is incredibly professional!", "rating": 5, "image": ""},
            {"id": 2, "name": "Michael Chen", "role": "Patient", "content": "Pain-free root canal treatment. I can't believe I'm saying this, but I enjoyed my visit.", "rating": 5, "image": ""},
            {"id": 3, "name": "Emma Wilson", "role": "Patient", "content": "State of the art facilities and such a warm, welcoming staff. Highly recommended!", "rating": 5, "image": ""}
        ]
        testimonials = default_testimonials
        if settings and settings.get("landing_page_testimonials_json"):
            try:
                testimonials = json.loads(settings.landing_page_testimonials_json)
            except:
                pass

        # Gallery
        default_gallery = [
            {"id": 1, "type": "image", "url": "https://images.unsplash.com/photo-1629909613654-28e377c37b09?q=80&w=2068&auto=format&fit=crop", "caption": "Modern Operatory"},
            {"id": 2, "type": "image", "url": "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?q=80&w=2053&auto=format&fit=crop", "caption": "Waiting Lounge"},
            {"id": 3, "type": "image", "url": "https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?q=80&w=2070&auto=format&fit=crop", "caption": "Advanced Equipment"}
        ]
        gallery = default_gallery
        if settings and settings.get("landing_page_gallery_json"):
            try:
                gallery = json.loads(settings.landing_page_gallery_json)
            except:
                pass

        # Tagline
        tagline = "Experience world-class dental care with cutting-edge technology."
        if settings and settings.get("landing_page_tagline"):
            tagline = settings.landing_page_tagline

        return {
            "message": "success",
            "data": {
                "profile": profile,
                "tagline": tagline,
                "doctors": formatted_doctors,
                "treatments": formatted_treatments,
                "testimonials": testimonials,
                "gallery": gallery,
                "stats": stats
            }
        }

    except Exception as e:
        frappe.log_error(str(e), "Public Landing Data Error")
        return {"message": "error", "error": str(e)}
