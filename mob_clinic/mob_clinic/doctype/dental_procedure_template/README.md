# Dental Procedure

**Dental Procedure** represents a dental treatment or service offered by the clinic.

## Features

- Track procedure names, codes, and categories
- Set cost and estimated duration for each procedure
- Support for custom procedures created by users
- Soft delete with is_active flag
- Category-based organization (Preventive, Restorative, Surgical, etc.)

## Fields

- **Procedure Name**: Unique name of the procedure
- **Code**: Unique identifier code (e.g., D0120, D1110)
- **Category**: Type of procedure (Preventive, Restorative, etc.)
- **Cost**: Procedure cost in currency
- **Duration Minutes**: Estimated time to complete
- **Description**: Detailed description of the procedure
- **Is Active**: Whether procedure is currently available
- **Is Custom**: Marks user-created custom procedures
- **Created By**: User who created the procedure
