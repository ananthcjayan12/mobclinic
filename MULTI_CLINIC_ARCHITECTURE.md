# Multi-Clinic Dental Procedures & Conditions Architecture

## Overview

This architecture allows each clinic to have their own customized procedures and conditions while maintaining efficiency through shared global templates.

## Database Design

### 1. **Global Templates** (Shared Master Data)
- **Dental Procedure Template**: Global procedure definitions
- **Dental Condition Template**: Global condition definitions

These templates are created by system administrators and shared across ALL clinics. They serve as:
- Standard procedure/condition library
- Default pricing and details
- Best practices from dental industry

### 2. **Clinic-Specific Overrides**
- **Dental Procedure Clinic Override**: Clinic-specific customizations for procedures
- **Dental Condition Clinic Override**: Clinic-specific customizations for conditions

Each clinic can:
- Override pricing for global templates
- Enable/disable global templates
- Create completely custom procedures/conditions

## How It Works

### Resolution Order (Priority)

When fetching procedures/conditions for a clinic:

1. **Clinic Overrides First** (Highest Priority)
   - Custom procedures/conditions created by the clinic
   - Template overrides (modified pricing, enabled/disabled)

2. **Global Templates** (Fallback)
   - Templates that haven't been overridden by the clinic
   - Use default pricing from template

### Example Scenarios

#### Scenario 1: Clinic Uses Default Template
```
Template: Root Canal | Default Cost: $500
Clinic A: No override → Shows $500
Clinic B: No override → Shows $500
```

#### Scenario 2: Clinic Overrides Pricing
```
Template: Root Canal | Default Cost: $500
Clinic A: Override → Cost: $450 (price competition)
Clinic B: Override → Cost: $600 (premium service)
```

#### Scenario 3: Clinic Creates Custom Procedure
```
Template: (none)
Clinic A: Custom "Laser Teeth Whitening" → $200 (only visible to Clinic A)
Clinic B: Does not have this procedure
```

#### Scenario 4: Clinic Disables Template
```
Template: Tooth Extraction | Default Cost: $150
Clinic A: Override → is_active: 0 (doesn't offer extractions)
Clinic B: No override → Shows $150 (offers extractions)
```

## Database Schema

### Dental Procedure Template
```
- procedure_name (unique)
- code (unique)
- category (Select)
- default_cost (Currency)
- duration_minutes (Int)
- description (Text)
- is_active (Check)
- created_by (Link: User)
```

### Dental Procedure Clinic Override
```
- clinic (Link: Clinic) [Required]
- procedure_template (Link: Dental Procedure Template) [For overrides]
- is_custom_procedure (Check) [For custom procedures]
- procedure_name (Data) [Required for custom]
- code (Data) [Required for custom]
- category (Select) [Required for custom]
- cost (Currency) [Required - clinic's price]
- duration_minutes (Int) [Required for custom]
- description (Text) [For custom]
- is_active (Check) [Enable/disable for this clinic]

Constraint: Unique (clinic, procedure_template)
```

### Dental Condition Template
```
- condition_name (unique)
- code (unique)
- type (Select: cavity, crown, etc.)
- category (Select: Decay, Gum Disease, etc.)
- description (Text)
- icon (Data)
- color (Data)
- treatment_required (Check)
- is_active (Check)
- created_by (Link: User)
- severity_levels (Table: Dental Condition Severity Level)
```

### Dental Condition Clinic Override
```
- clinic (Link: Clinic) [Required]
- condition_template (Link: Dental Condition Template) [For overrides]
- is_custom_condition (Check) [For custom conditions]
- condition_name (Data) [Required for custom]
- code (Data) [Required for custom]
- type (Select) [Required for custom]
- category (Select) [Required for custom]
- description (Text) [For custom]
- icon (Data) [For custom]
- color (Data) [For custom]
- treatment_required (Check) [For custom]
- is_active (Check) [Enable/disable for this clinic]
- severity_levels (Table) [For custom]

Constraint: Unique (clinic, condition_template)
```

## API Endpoints

### Procedures API (`/api/method/mob_clinic.mob_clinic.api.procedures.*`)

#### 1. Get Procedures
```
GET /get_procedures
Parameters:
  - clinic (required): Clinic name/ID
  - search (optional): Search term
  - category (optional): Filter by category

Returns merged list of:
  - Custom procedures for this clinic
  - Template overrides for this clinic
  - Global templates (not overridden)
```

#### 2. Create Custom Procedure
```
POST /create_custom_procedure
Body:
  - clinic (required)
  - procedure_name (required)
  - code (required)
  - category (required)
  - cost (required)
  - duration_minutes (required)
  - description (optional)

Creates a clinic-specific custom procedure
```

#### 3. Override Template Procedure
```
POST /override_template_procedure
Body:
  - clinic (required)
  - procedure_template (required): Template name to override
  - cost (required): Clinic's custom price
  - is_active (optional): Enable/disable (default: 1)

Overrides pricing or availability of a global template
```

#### 4. Delete Custom Procedure
```
POST /delete_custom_procedure
Body:
  - clinic (required)
  - procedure_name (required)

Deletes a custom procedure (only works for clinic's custom procedures)
```

#### 5. Get Categories
```
GET /get_procedure_categories

Returns list of all procedure categories
```

### Conditions API (`/api/method/mob_clinic.mob_clinic.api.conditions.*`)

#### 1. Get Conditions
```
GET /get_conditions
Parameters:
  - clinic (required): Clinic name/ID
  - search (optional): Search term
  - category (optional): Filter by category

Returns merged list with severity_levels included
```

#### 2. Create Custom Condition
```
POST /create_custom_condition
Body:
  - clinic (required)
  - condition_name (required)
  - code (required)
  - type (required)
  - category (required)
  - severity_levels (optional): JSON array ["Mild", "Moderate", "Severe"]
  - description (optional)
  - icon (optional)
  - color (optional)
  - treatment_required (optional): 0 or 1

Creates a clinic-specific custom condition
```

#### 3. Override Template Condition
```
POST /override_template_condition
Body:
  - clinic (required)
  - condition_template (required): Template name to override
  - is_active (required): Enable/disable (1 or 0)

Enable or disable a global template for this clinic
```

#### 4. Delete Custom Condition
```
POST /delete_custom_condition
Body:
  - clinic (required)
  - condition_name (required)

Deletes a custom condition (only works for clinic's custom conditions)
```

#### 5. Get Categories
```
GET /get_condition_categories

Returns list of all condition categories
```

#### 6. Get Types
```
GET /get_condition_types

Returns list of all condition types
```

## Benefits of This Architecture

### 1. **Efficiency**
- No data duplication
- Global templates shared across all clinics
- Only store clinic-specific differences

### 2. **Flexibility**
- Each clinic can set their own pricing
- Clinics can create custom procedures/conditions
- Clinics can disable procedures they don't offer

### 3. **Scalability**
- Easy to add new clinics
- New global templates automatically available to all clinics
- Minimal database growth per new clinic

### 4. **Maintenance**
- Update global templates in one place
- Clinics inherit improvements unless they've overridden
- Clear separation between global and clinic-specific data

### 5. **Business Logic**
- Premium clinics can charge more
- Budget clinics can offer competitive pricing
- Specialty clinics can add unique procedures
- Small clinics can disable complex procedures

## Migration from Old System

Old files backed up as:
- `procedures_old_backup.py`
- `conditions_old_backup.py`

New multi-clinic files are now active:
- `procedures.py` (multi-clinic version)
- `conditions.py` (multi-clinic version)

## Installation Steps

1. **Run Migration**
   ```bash
   cd /workspace/development/frappe-bench
   bench --site dev.localhost migrate
   ```

2. **Create Global Templates** (System Administrator)
   - Add standard procedures to "Dental Procedure Template"
   - Add standard conditions to "Dental Condition Template"

3. **Frontend Integration**
   - Update API calls to include `clinic` parameter
   - Build UI for custom procedures/conditions management
   - Add override UI for pricing adjustments

## Frontend Implementation Guide

### Fetching Procedures for Current Clinic
```javascript
// Assume current clinic is stored in context/session
const currentClinic = "CLINIC-001";

fetch(`/api/method/mob_clinic.mob_clinic.api.procedures.get_procedures?clinic=${currentClinic}`)
  .then(res => res.json())
  .then(data => {
    // data.message.procedures contains merged list
    // Each has: procedure_name, code, category, cost, duration_minutes
    // Plus: is_custom (true/false), source (template_default/template_override/clinic_custom)
  });
```

### Creating Custom Procedure
```javascript
fetch('/api/method/mob_clinic.mob_clinic.api.procedures.create_custom_procedure', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    clinic: currentClinic,
    procedure_name: "Laser Whitening",
    code: "LW001",
    category: "Cosmetic",
    cost: 200,
    duration_minutes: 45,
    description: "Advanced laser teeth whitening"
  })
});
```

### Overriding Template Pricing
```javascript
fetch('/api/method/mob_clinic.mob_clinic.api.procedures.override_template_procedure', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    clinic: currentClinic,
    procedure_template: "PROCT-00001", // Template ID
    cost: 450, // Custom price for this clinic
    is_active: 1
  })
});
```

## Testing Checklist

- [ ] Create global procedure template
- [ ] Verify template appears for all clinics (without override)
- [ ] Create clinic override with custom pricing
- [ ] Verify overridden price shows for that clinic only
- [ ] Create custom procedure for one clinic
- [ ] Verify custom procedure only visible to that clinic
- [ ] Disable template for one clinic
- [ ] Verify template hidden for that clinic but visible to others
- [ ] Create global condition template with severity levels
- [ ] Test all condition override scenarios
- [ ] Test search and filtering across templates and overrides
- [ ] Test duplicate validation for custom procedures/conditions

## Database Indexes

Recommended indexes for performance:

```sql
-- Dental Procedure Clinic Override
CREATE INDEX idx_proc_override_clinic ON `tabDental Procedure Clinic Override` (clinic);
CREATE INDEX idx_proc_override_template ON `tabDental Procedure Clinic Override` (procedure_template);
CREATE INDEX idx_proc_override_custom ON `tabDental Procedure Clinic Override` (is_custom_procedure);

-- Dental Condition Clinic Override
CREATE INDEX idx_cond_override_clinic ON `tabDental Condition Clinic Override` (clinic);
CREATE INDEX idx_cond_override_template ON `tabDental Condition Clinic Override` (condition_template);
CREATE INDEX idx_cond_override_custom ON `tabDental Condition Clinic Override` (is_custom_condition);
```

These indexes will be created automatically by Frappe's ORM based on Link fields and filters.
