"""
Patch to populate Medicine Templates with common dental medicines
"""

import frappe
from frappe import _

def execute():
    """Execute the patch to create initial medicine templates"""
    
    create_medicine_templates()
    
    frappe.db.commit()
    print("✅ Successfully created medicine templates")


def create_medicine_templates():
    """Create common dental medicine templates"""
    
    medicines = [
        # Antibiotics
        {"name": "Amoxicillin 500mg", "generic": "Amoxicillin", "form": "Capsule", "strength": "500mg", "category": "Antibiotic", "morning": 1, "lunch": 1, "evening": 0, "night": 1, "days": 5, "condition": "After Food"},
        {"name": "Amoxicillin 250mg", "generic": "Amoxicillin", "form": "Capsule", "strength": "250mg", "category": "Antibiotic", "morning": 1, "lunch": 1, "evening": 0, "night": 1, "days": 5, "condition": "After Food"},
        {"name": "Augmentin 625mg", "generic": "Amoxicillin + Clavulanic Acid", "form": "Tablet", "strength": "625mg", "category": "Antibiotic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 5, "condition": "After Food"},
        {"name": "Azithromycin 500mg", "generic": "Azithromycin", "form": "Tablet", "strength": "500mg", "category": "Antibiotic", "morning": 1, "lunch": 0, "evening": 0, "night": 0, "days": 3, "condition": "After Food"},
        {"name": "Metronidazole 400mg", "generic": "Metronidazole", "form": "Tablet", "strength": "400mg", "category": "Antibiotic", "morning": 1, "lunch": 1, "evening": 0, "night": 1, "days": 5, "condition": "After Food"},
        {"name": "Clindamycin 300mg", "generic": "Clindamycin", "form": "Capsule", "strength": "300mg", "category": "Antibiotic", "morning": 1, "lunch": 1, "evening": 0, "night": 1, "days": 5, "condition": "After Food"},
        
        # Analgesics / Pain Relievers
        {"name": "Ibuprofen 400mg", "generic": "Ibuprofen", "form": "Tablet", "strength": "400mg", "category": "Analgesic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Paracetamol 500mg", "generic": "Paracetamol", "form": "Tablet", "strength": "500mg", "category": "Analgesic", "morning": 1, "lunch": 0, "evening": 1, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Paracetamol 650mg", "generic": "Paracetamol", "form": "Tablet", "strength": "650mg", "category": "Analgesic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Combiflam", "generic": "Ibuprofen + Paracetamol", "form": "Tablet", "strength": "400mg+325mg", "category": "Analgesic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Zerodol-P", "generic": "Aceclofenac + Paracetamol", "form": "Tablet", "strength": "100mg+325mg", "category": "Analgesic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Zerodol-SP", "generic": "Aceclofenac + Paracetamol + Serratiopeptidase", "form": "Tablet", "strength": "100mg+325mg+15mg", "category": "Analgesic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Ketorol DT", "generic": "Ketorolac", "form": "Tablet", "strength": "10mg", "category": "Analgesic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        
        # Anti-inflammatory
        {"name": "Diclofenac 50mg", "generic": "Diclofenac", "form": "Tablet", "strength": "50mg", "category": "Anti-inflammatory", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Nimesulide 100mg", "generic": "Nimesulide", "form": "Tablet", "strength": "100mg", "category": "Anti-inflammatory", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Chymoral Forte", "generic": "Trypsin + Chymotrypsin", "form": "Tablet", "strength": "100000 AU", "category": "Anti-inflammatory", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 5, "condition": "Before Food"},
        
        # Antacids (for gastric protection)
        {"name": "Pantoprazole 40mg", "generic": "Pantoprazole", "form": "Tablet", "strength": "40mg", "category": "Antacid", "morning": 1, "lunch": 0, "evening": 0, "night": 0, "days": 5, "condition": "Before Food"},
        {"name": "Omeprazole 20mg", "generic": "Omeprazole", "form": "Capsule", "strength": "20mg", "category": "Antacid", "morning": 1, "lunch": 0, "evening": 0, "night": 0, "days": 5, "condition": "Before Food"},
        {"name": "Ranitidine 150mg", "generic": "Ranitidine", "form": "Tablet", "strength": "150mg", "category": "Antacid", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 5, "condition": "Before Food"},
        
        # Antifungal
        {"name": "Fluconazole 150mg", "generic": "Fluconazole", "form": "Tablet", "strength": "150mg", "category": "Antifungal", "morning": 1, "lunch": 0, "evening": 0, "night": 0, "days": 1, "condition": "After Food"},
        {"name": "Candid Mouth Paint", "generic": "Clotrimazole", "form": "Other", "strength": "1%", "category": "Antifungal", "morning": 1, "lunch": 1, "evening": 1, "night": 1, "days": 7, "condition": "After Food", "instructions": "Apply on affected area with cotton bud"},
        
        # Mouthwash / Oral Care
        {"name": "Hexidine Mouthwash", "generic": "Chlorhexidine", "form": "Mouthwash", "strength": "0.2%", "category": "Antiseptic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 7, "condition": "After Food", "instructions": "Rinse for 30 seconds, do not swallow"},
        {"name": "Betadine Gargle", "generic": "Povidone Iodine", "form": "Mouthwash", "strength": "1%", "category": "Antiseptic", "morning": 1, "lunch": 1, "evening": 0, "night": 1, "days": 5, "condition": "After Food", "instructions": "Gargle for 30 seconds"},
        {"name": "Listerine", "generic": "Essential Oils", "form": "Mouthwash", "strength": "", "category": "Antiseptic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 14, "condition": "After Food"},
        
        # Vitamins
        {"name": "Vitamin C 500mg", "generic": "Ascorbic Acid", "form": "Tablet", "strength": "500mg", "category": "Vitamin", "morning": 1, "lunch": 0, "evening": 0, "night": 0, "days": 15, "condition": "After Food"},
        {"name": "Calcium + Vitamin D3", "generic": "Calcium Carbonate + Vitamin D3", "form": "Tablet", "strength": "500mg+250IU", "category": "Mineral", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food"},
        {"name": "B-Complex", "generic": "Vitamin B Complex", "form": "Tablet", "strength": "", "category": "Vitamin", "morning": 1, "lunch": 0, "evening": 0, "night": 0, "days": 15, "condition": "After Food"},
        
        # Steroids
        {"name": "Prednisolone 10mg", "generic": "Prednisolone", "form": "Tablet", "strength": "10mg", "category": "Steroid", "morning": 1, "lunch": 0, "evening": 0, "night": 0, "days": 5, "condition": "After Food"},
        {"name": "Dexamethasone 0.5mg", "generic": "Dexamethasone", "form": "Tablet", "strength": "0.5mg", "category": "Steroid", "morning": 1, "lunch": 0, "evening": 0, "night": 0, "days": 3, "condition": "After Food"},
        
        # Muscle Relaxants  
        {"name": "Flexon MR", "generic": "Ibuprofen + Paracetamol + Chlorzoxazone", "form": "Tablet", "strength": "400mg+500mg+250mg", "category": "Muscle Relaxant", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Myospaz", "generic": "Chlorzoxazone + Paracetamol", "form": "Tablet", "strength": "250mg+500mg", "category": "Muscle Relaxant", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        
        # Antihistamines
        {"name": "Cetirizine 10mg", "generic": "Cetirizine", "form": "Tablet", "strength": "10mg", "category": "Antihistamine", "morning": 0, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Levocetirizine 5mg", "generic": "Levocetirizine", "form": "Tablet", "strength": "5mg", "category": "Antihistamine", "morning": 0, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        
        # Topical
        {"name": "Lignocaine Gel 2%", "generic": "Lidocaine", "form": "Gel", "strength": "2%", "category": "Anesthetic", "morning": 1, "lunch": 1, "evening": 1, "night": 1, "days": 5, "condition": "As Needed", "instructions": "Apply on affected area before meals"},
    ]

    medicines.extend([
        # Additional oral care products
        {"name": "Clohex ADS", "generic": "Chlorhexidine", "form": "Mouthwash", "strength": "", "category": "Antiseptic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 7, "condition": "After Food", "instructions": "Rinse for 30 seconds, do not swallow"},
        {"name": "Vantej Fort", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Use twice daily as directed"},
        {"name": "Clohex Heal", "generic": "", "form": "Gel", "strength": "", "category": "Antiseptic", "morning": 1, "lunch": 1, "evening": 1, "night": 1, "days": 7, "condition": "After Food", "instructions": "Apply on affected gums or oral mucosa as directed"},
        {"name": "Vantej Aqua", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Use twice daily as directed"},
        {"name": "Toothmin", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Use twice daily as directed"},
        {"name": "Kidodent Mouthwash", "generic": "", "form": "Mouthwash", "strength": "", "category": "Antiseptic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 7, "condition": "After Food", "instructions": "Rinse for 30 seconds, do not swallow"},
        {"name": "Kidodent Paste", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Brush twice daily"},
        {"name": "Metrogyl DG fort", "generic": "Metronidazole", "form": "Gel", "strength": "", "category": "Antibiotic", "morning": 1, "lunch": 1, "evening": 1, "night": 1, "days": 5, "condition": "After Food", "instructions": "Apply on affected gums as directed"},
        {"name": "Metrogyl DG LA", "generic": "Metronidazole", "form": "Gel", "strength": "", "category": "Antibiotic", "morning": 1, "lunch": 1, "evening": 1, "night": 1, "days": 5, "condition": "After Food", "instructions": "Apply on affected gums as directed"},
        {"name": "Metrogreen", "generic": "", "form": "Gel", "strength": "", "category": "Other", "morning": 1, "lunch": 1, "evening": 1, "night": 1, "days": 5, "condition": "After Food", "instructions": "Apply on affected area as directed"},
        {"name": "Kera Cort", "generic": "", "form": "Gel", "strength": "", "category": "Steroid", "morning": 1, "lunch": 1, "evening": 1, "night": 1, "days": 5, "condition": "After Food", "instructions": "Apply on affected oral lesion as directed"},
        {"name": "Perio Guard", "generic": "", "form": "Mouthwash", "strength": "", "category": "Antiseptic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 7, "condition": "After Food", "instructions": "Rinse for 30 seconds, do not swallow"},
        {"name": "Rexidin M Fort", "generic": "", "form": "Mouthwash", "strength": "", "category": "Antiseptic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 7, "condition": "After Food", "instructions": "Rinse for 30 seconds, do not swallow"},
        {"name": "Odin Gel", "generic": "", "form": "Gel", "strength": "", "category": "Other", "morning": 1, "lunch": 1, "evening": 1, "night": 1, "days": 5, "condition": "After Food", "instructions": "Apply on affected area as directed"},
        {"name": "Visible White", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Brush twice daily"},
        {"name": "Sensodent Acipro", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Brush twice daily"},
        {"name": "Dental Floss", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 0, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Use once daily after brushing"},
        {"name": "Stim Flosser", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 0, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Use once daily after brushing"},
        {"name": "Ortho Brush", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Brush twice daily"},
        {"name": "Soft Brush", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Brush twice daily"},
        {"name": "Electric Brush", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Brush twice daily"},

        # Additional medicines
        {"name": "Addclav 625", "generic": "Amoxicillin + Clavulanic Acid", "form": "Tablet", "strength": "625mg", "category": "Antibiotic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 5, "condition": "After Food"},
        {"name": "Augmentin 625", "generic": "Amoxicillin + Clavulanic Acid", "form": "Tablet", "strength": "625mg", "category": "Antibiotic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 5, "condition": "After Food"},
        {"name": "Mox 500", "generic": "Amoxicillin", "form": "Capsule", "strength": "500mg", "category": "Antibiotic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 5, "condition": "After Food"},
        {"name": "Fenpil S", "generic": "", "form": "Tablet", "strength": "", "category": "Other", "morning": 1, "lunch": 1, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Metrogyl 400", "generic": "Metronidazole", "form": "Tablet", "strength": "400mg", "category": "Antibiotic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 5, "condition": "After Food"},
        {"name": "Metrogyl 200", "generic": "Metronidazole", "form": "Tablet", "strength": "200mg", "category": "Antibiotic", "morning": 1, "lunch": 1, "evening": 0, "night": 1, "days": 5, "condition": "After Food"},
        {"name": "Metrogyl ER", "generic": "Metronidazole", "form": "Tablet", "strength": "", "category": "Antibiotic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 5, "condition": "After Food"},
        {"name": "H-pan 40", "generic": "Pantoprazole", "form": "Tablet", "strength": "40mg", "category": "Antacid", "morning": 1, "lunch": 0, "evening": 0, "night": 0, "days": 5, "condition": "Before Food"},
        {"name": "Wyslone", "generic": "Prednisolone", "form": "Tablet", "strength": "", "category": "Steroid", "morning": 1, "lunch": 1, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Aux Keto", "generic": "", "form": "Tablet", "strength": "", "category": "Analgesic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Nace-P", "generic": "", "form": "Tablet", "strength": "", "category": "Analgesic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Zoyas-P", "generic": "", "form": "Tablet", "strength": "", "category": "Analgesic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Calpol 650", "generic": "Paracetamol", "form": "Tablet", "strength": "650mg", "category": "Analgesic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Mox 250", "generic": "Amoxicillin", "form": "Capsule", "strength": "250mg", "category": "Antibiotic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 5, "condition": "After Food"},
        {"name": "Augmentine 375", "generic": "Amoxicillin + Clavulanic Acid", "form": "Tablet", "strength": "375mg", "category": "Antibiotic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 5, "condition": "After Food"},
        {"name": "P-250", "generic": "Paracetamol", "form": "Tablet", "strength": "250mg", "category": "Analgesic", "morning": 1, "lunch": 1, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Meflan 500", "generic": "Mefenamic Acid", "form": "Tablet", "strength": "500mg", "category": "Analgesic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 3, "condition": "After Food"},
        {"name": "Augmentin 228 (Syrup)", "generic": "Amoxicillin + Clavulanic Acid", "form": "Syrup", "strength": "228mg", "category": "Antibiotic", "morning": 1, "lunch": 1, "evening": 0, "night": 1, "days": 5, "condition": "After Food", "instructions": "Specify ml dose per administration"},
        {"name": "Cefiges-200", "generic": "Cefixime", "form": "Tablet", "strength": "200mg", "category": "Antibiotic", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 5, "condition": "After Food"},
        {"name": "Calpol 120 (Syrup)", "generic": "Paracetamol", "form": "Syrup", "strength": "120mg", "category": "Analgesic", "morning": 1, "lunch": 1, "evening": 0, "night": 1, "days": 3, "condition": "After Food", "instructions": "Specify ml dose per administration"},
        {"name": "Calpol 250 (Syrup)", "generic": "Paracetamol", "form": "Syrup", "strength": "250mg", "category": "Analgesic", "morning": 1, "lunch": 1, "evening": 0, "night": 1, "days": 3, "condition": "After Food", "instructions": "Specify ml dose per administration"},
        {"name": "Metrogyl 200 (Syrup)", "generic": "Metronidazole", "form": "Syrup", "strength": "200mg", "category": "Antibiotic", "morning": 1, "lunch": 1, "evening": 0, "night": 1, "days": 5, "condition": "After Food", "instructions": "Specify ml dose per administration"},
        {"name": "Augmentine 457 (Syrup)", "generic": "Amoxicillin + Clavulanic Acid", "form": "Syrup", "strength": "457mg", "category": "Antibiotic", "morning": 1, "lunch": 1, "evening": 0, "night": 1, "days": 5, "condition": "After Food", "instructions": "Specify ml dose per administration"},

        # Additional pediatric and hygiene products
        {"name": "Cheerio Paste Blue", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Brush twice daily"},
        {"name": "Cheerio Paste Pink", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Brush twice daily"},
        {"name": "Metrohex Plus Gel", "generic": "", "form": "Gel", "strength": "", "category": "Antibiotic", "morning": 1, "lunch": 1, "evening": 1, "night": 1, "days": 5, "condition": "After Food", "instructions": "Apply on affected gums as directed"},
        {"name": "Colgate 0-2", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Brush twice daily"},
        {"name": "Colgate 3-5", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Brush twice daily"},
        {"name": "Colgate 6-9", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Brush twice daily"},
        {"name": "Why-t", "generic": "", "form": "Other", "strength": "", "category": "Other", "morning": 1, "lunch": 0, "evening": 0, "night": 1, "days": 30, "condition": "After Food", "instructions": "Use twice daily as directed"},
    ])
    
    created_count = 0
    skipped_count = 0
    
    for med in medicines:
        # Check if already exists
        existing = frappe.db.exists("Medicine Template", {"medicine_name": med["name"]})
        
        if existing:
            print(f"⏭️  Skipping '{med['name']}' - already exists")
            skipped_count += 1
            continue
        
        try:
            doc = frappe.get_doc({
                "doctype": "Medicine Template",
                "medicine_name": med["name"],
                "generic_name": med.get("generic"),
                "dosage_form": med.get("form", "Tablet"),
                "strength": med.get("strength"),
                "category": med.get("category", "Other"),
                "default_morning": med.get("morning", 0),
                "default_lunch": med.get("lunch", 0),
                "default_evening": med.get("evening", 0),
                "default_night": med.get("night", 0),
                "default_days": med.get("days", 5),
                "default_condition": med.get("condition", "After Food"),
                "instructions": med.get("instructions"),
                "is_active": 1
            })
            doc.insert(ignore_permissions=True)
            created_count += 1
            print(f"✅ Created medicine template: {med['name']}")
        except Exception as e:
            print(f"❌ Failed to create '{med['name']}': {str(e)}")
            frappe.log_error(frappe.get_traceback(), f"Medicine Template Creation Failed: {med['name']}")
    
    print(f"\n📊 Medicine Templates: {created_count} created, {skipped_count} skipped")
