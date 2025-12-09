# Multi-Clinic Dental API - Quick Reference

## API Endpoints Overview

All endpoints require `clinic` parameter to identify which clinic's data to retrieve/modify.

---

## Procedures API

### Base URL
`/api/method/mob_clinic.mob_clinic.api.procedures`

### 1. Get All Procedures
```http
GET /get_procedures?clinic=CLINIC-001&search=root&category=Endodontic
```

**Parameters:**
- `clinic` (required): Clinic identifier
- `search` (optional): Search in name/code
- `category` (optional): Filter by category

**Response:**
```json
{
  "message": "success",
  "procedures": [
    {
      "procedure_name": "Root Canal Treatment",
      "code": "RCT001",
      "category": "Endodontic",
      "cost": 450.00,
      "duration_minutes": 60,
      "description": "...",
      "is_custom": false,
      "source": "template_override"
    },
    {
      "procedure_name": "Custom Laser Whitening",
      "code": null,
      "category": "Other",
      "cost": 200.00,
      "duration_minutes": null,
      "description": "...",
      "is_custom": true,
      "source": "clinic_custom"
    }
  ]
}
```

**Note:** Fields like `code`, `duration_minutes` may be `null` if not provided.

**Source Types:**
- `template_default`: Global template with default pricing
- `template_override`: Global template with clinic's custom pricing
- `clinic_custom`: Custom procedure created by this clinic

---

### 2. Create Custom Procedure
```http
POST /create_custom_procedure
Content-Type: application/json

{
  "clinic": "CLINIC-001",
  "procedure_name": "Laser Whitening",
  "code": "LW001",
  "category": "Cosmetic",
  "cost": 200,
  "duration_minutes": 45,
  "description": "Advanced laser teeth whitening"
}
```

**Required Fields:**
- `clinic` (string): Clinic identifier
- `procedure_name` (string): Name of the procedure
- `cost` (number): Procedure cost

**Optional Fields:**
- `code` (string): Procedure code (e.g., "LW001")
- `category` (string): Category (default: "Other")
- `duration_minutes` (number): Estimated duration in minutes
- `description` (string): Detailed description

---

### 3. Override Template Pricing
```http
POST /override_template_procedure
Content-Type: application/json

{
  "clinic": "CLINIC-001",
  "procedure_template": "PROCT-00001",
  "cost": 450,
  "is_active": 1
}
```

**Use Cases:**
- Change pricing for your clinic
- Disable procedure: `"is_active": 0`
- Re-enable procedure: `"is_active": 1`

---

### 4. Delete Custom Procedure
```http
POST /delete_custom_procedure
Content-Type: application/json

{
  "clinic": "CLINIC-001",
  "procedure_name": "Laser Whitening"
}
```

**Note:** Only works for custom procedures (`is_custom: true`). Cannot delete global templates.

---

### 5. Get Categories
```http
GET /get_procedure_categories
```

**Response:**
```json
{
  "message": "success",
  "categories": [
    "Preventive", "Restorative", "Surgical", "Endodontic",
    "Periodontic", "Orthodontic", "Prosthodontic", "Cosmetic", "Other"
  ]
}
```

---

## Conditions API

### Base URL
`/api/method/mob_clinic.mob_clinic.api.conditions`

### 1. Get All Conditions
```http
GET /get_conditions?clinic=CLINIC-001&search=cavity&category=Decay
```

**Parameters:**
- `clinic` (required): Clinic identifier
- `search` (optional): Search in name/code/type
- `category` (optional): Filter by category

**Response:**
```json
{
  "message": "success",
  "conditions": [
    {
      "condition_name": "Dental Cavity",
      "code": "CAV001",
      "type": "cavity",
      "category": "Decay",
      "description": "...",
      "icon": "tooth-decay",
      "color": "#FF5733",
      "treatment_required": true,
      "severity_levels": ["Mild", "Moderate", "Severe"],
      "is_custom": false,
      "source": "template_default"
    },
    {
      "condition_name": "Custom Condition",
      "code": null,
      "type": null,
      "category": "Other",
      "description": null,
      "icon": null,
      "color": null,
      "treatment_required": false,
      "severity_levels": [],
      "is_custom": true,
      "source": "clinic_custom"
    }
  ]
}
```

**Note:** Fields like `code`, `type`, `icon`, `color`, `severity_levels` may be `null` or empty if not provided.

---

### 2. Create Custom Condition
```http
POST /create_custom_condition
Content-Type: application/json

{
  "clinic": "CLINIC-001",
  "condition_name": "Advanced Decay",
  "code": "ADEC001",
  "type": "cavity",
  "category": "Decay",
  "severity_levels": ["Stage 1", "Stage 2", "Stage 3"],
  "description": "Advanced cavity condition",
  "icon": "warning",
  "color": "#FF0000",
  "treatment_required": 1
}
```

**Required Fields:**
- `clinic` (string): Clinic identifier
- `condition_name` (string): Name of the condition

**Optional Fields:**
- `code` (string): Condition code (e.g., "ADEC001")
- `type` (string): Type (cavity, crown, bridge, etc.)
- `category` (string): Category (default: "Other")
- `severity_levels` (array): Array of severity level strings (e.g., ["Mild", "Moderate", "Severe"])
- `description` (string): Detailed description
- `icon` (string): Icon identifier for UI
- `color` (string): Color code (e.g., "#FF0000")
- `treatment_required` (number): 0 or 1 (default: 0)

---

### 3. Override Template Condition
```http
POST /override_template_condition
Content-Type: application/json

{
  "clinic": "CLINIC-001",
  "condition_template": "CONDT-00001",
  "is_active": 0
}
```

**Use Cases:**
- Disable condition for clinic: `"is_active": 0`
- Enable condition for clinic: `"is_active": 1`

**Note:** Unlike procedures, conditions only support enable/disable overrides (no pricing to override).

---

### 4. Delete Custom Condition
```http
POST /delete_custom_condition
Content-Type: application/json

{
  "clinic": "CLINIC-001",
  "condition_name": "Advanced Decay"
}
```

**Note:** Only works for custom conditions. Cannot delete global templates.

---

### 5. Get Categories
```http
GET /get_condition_categories
```

**Response:**
```json
{
  "message": "success",
  "categories": [
    "Decay", "Gum Disease", "Structural", "Trauma",
    "Infection", "Congenital", "Cosmetic", "Other"
  ]
}
```

---

### 6. Get Types
```http
GET /get_condition_types
```

**Response:**
```json
{
  "message": "success",
  "types": [
    "cavity", "crown", "bridge", "implant", "root-canal",
    "filling", "extraction", "fracture", "abscess",
    "gingivitis", "periodontitis", "other"
  ]
}
```

---

## Common Patterns

### 1. Initialize Procedure List for Clinic
```javascript
const clinic = getCurrentClinic(); // Your function to get current clinic

// Fetch all procedures
const response = await fetch(
  `/api/method/mob_clinic.mob_clinic.api.procedures.get_procedures?clinic=${clinic}`
);
const data = await response.json();
const procedures = data.message.procedures;

// Separate by source
const customProcedures = procedures.filter(p => p.is_custom);
const templateProcedures = procedures.filter(p => !p.is_custom);
```

### 2. Override Template Pricing
```javascript
// User clicks "Edit Pricing" on a template procedure
async function overridePricing(templateId, newCost) {
  const response = await fetch(
    '/api/method/mob_clinic.mob_clinic.api.procedures.override_template_procedure',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        clinic: getCurrentClinic(),
        procedure_template: templateId,
        cost: newCost,
        is_active: 1
      })
    }
  );
  return response.json();
}
```

### 3. Create Custom Procedure with Validation
```javascript
async function createCustomProcedure(formData) {
  try {
    const response = await fetch(
      '/api/method/mob_clinic.mob_clinic.api.procedures.create_custom_procedure',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          clinic: getCurrentClinic(),
          procedure_name: formData.name, // Required
          cost: parseFloat(formData.cost), // Required
          code: formData.code || null, // Optional
          category: formData.category || 'Other', // Optional (default: "Other")
          duration_minutes: formData.duration ? parseInt(formData.duration) : null, // Optional
          description: formData.description || null // Optional
        })
      }
    );
    
    const result = await response.json();
    
    if (response.status === 400) {
      alert(result.message); // Show duplicate error
      return null;
    }
    
    return result.message.procedure;
  } catch (error) {
    console.error('Failed to create procedure:', error);
    return null;
  }
}
```

### 4. Disable/Enable Template for Clinic
```javascript
async function toggleProcedure(templateId, isActive) {
  const response = await fetch(
    '/api/method/mob_clinic.mob_clinic.api.procedures.override_template_procedure',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        clinic: getCurrentClinic(),
        procedure_template: templateId,
        cost: 0, // Will be ignored for disable action
        is_active: isActive ? 1 : 0
      })
    }
  );
  return response.json();
}
```

### 5. Search with Debouncing
```javascript
let searchTimeout;

function searchProcedures(searchTerm, category = null) {
  clearTimeout(searchTimeout);
  
  searchTimeout = setTimeout(async () => {
    const params = new URLSearchParams({
      clinic: getCurrentClinic(),
      search: searchTerm
    });
    
    if (category) {
      params.append('category', category);
    }
    
    const response = await fetch(
      `/api/method/mob_clinic.mob_clinic.api.procedures.get_procedures?${params}`
    );
    const data = await response.json();
    
    // Update UI with filtered results
    updateProcedureList(data.message.procedures);
  }, 300); // 300ms debounce
}
```

---

## Error Handling

All endpoints return consistent error formats:

**Success (200):**
```json
{
  "message": "success",
  "procedures": [...],
  "conditions": [...]
}
```

**Client Error (400):**
```json
{
  "message": "Custom procedure 'Laser Whitening' already exists for this clinic"
}
```

**Not Found (404):**
```json
{
  "message": "Invalid clinic"
}
```

**Server Error (500):**
```json
{
  "message": "Internal server error details"
}
```

---

## Best Practices

1. **Always pass clinic parameter** - Required for all operations
2. **Cache template lists** - Templates change rarely, cache aggressively
3. **Validate before create** - Check for duplicates in UI before API call
4. **Use search/filter** - Don't load all data if user needs specific items
5. **Show source indicator** - Display badges showing custom vs template items
6. **Confirm destructive actions** - Confirm before deleting custom procedures
7. **Handle async properly** - Use async/await or promises correctly
8. **Show loading states** - Indicate when fetching/creating/deleting
9. **Optional fields flexibility** - Code, category, duration, type, and severity_levels are optional
10. **Default values** - Category defaults to "Other" if not provided

---

## Field Requirements Summary

### Procedures
**Mandatory:**
- ✅ `procedure_name` - Procedure name
- ✅ `default_cost` - Default cost (for templates) or `cost` (for overrides)

**Optional:**
- ❌ `code` - Procedure code
- ❌ `category` - Defaults to "Other"
- ❌ `duration_minutes` - Estimated duration
- ❌ `description` - Detailed description

### Conditions
**Mandatory:**
- ✅ `condition_name` - Condition name

**Optional:**
- ❌ `code` - Condition code
- ❌ `type` - Condition type (cavity, crown, etc.)
- ❌ `category` - Defaults to "Other"
- ❌ `severity_levels` - Array of severity levels
- ❌ `description` - Detailed description
- ❌ `icon` - Icon identifier
- ❌ `color` - Color code
- ❌ `treatment_required` - Boolean flag (default: 0)

---

## Security Notes

- All endpoints require authentication (Frappe session)
- Clinic parameter is validated - can't access other clinic's data
- Role-based permissions apply (Healthcare Administrator, System Manager)
- Custom procedures are clinic-scoped (automatically isolated)
- Template modifications require appropriate role permissions

---

## Performance Tips

1. **Pagination** - For large datasets, consider adding pagination
2. **Caching** - Cache template data on frontend (expires hourly)
3. **Batch operations** - If creating multiple items, consider batch endpoint
4. **Index usage** - Database indexes on clinic + template fields
5. **Lazy loading** - Load custom procedures first, templates on demand
