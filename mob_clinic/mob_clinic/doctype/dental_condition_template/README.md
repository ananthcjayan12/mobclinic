# Dental Condition

**Dental Condition** represents a dental health issue or diagnosis.

## Features

- Track dental conditions, diagnoses, and health issues
- Support multiple severity levels per condition
- Category and type-based organization
- Visual indicators with icon and color support
- Treatment requirement tracking
- Soft delete with is_active flag
- Support for custom conditions created by users

## Fields

- **Condition Name**: Unique name of the condition
- **Code**: Unique identifier code
- **Type**: Specific type (cavity, crown, implant, etc.)
- **Category**: Category classification (Decay, Gum Disease, etc.)
- **Icon**: Icon identifier for UI display
- **Color**: Color code for visual representation
- **Treatment Required**: Whether treatment is needed
- **Is Active**: Whether condition is currently available
- **Is Custom**: Marks user-created custom conditions
- **Created By**: User who created the condition
- **Description**: Detailed description of the condition
- **Severity Levels**: Child table with multiple severity levels

## Child Table: Severity Levels

Each condition can have multiple severity levels (e.g., Mild, Moderate, Severe) defined in the child table.
