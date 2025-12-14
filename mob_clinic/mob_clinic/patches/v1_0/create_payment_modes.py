import frappe


def execute():
    """Install default payment modes for mobile clinic app"""
    
    print("=" * 50)
    print("INSTALLING PAYMENT MODES FOR MOBILE CLINIC")
    print("=" * 50)
    
    try:
        create_payment_modes()
        frappe.db.commit()
        
        print("=" * 50)
        print("PAYMENT MODES INSTALLATION COMPLETED SUCCESSFULLY!")
        print("=" * 50)
        
    except Exception as e:
        print(f"ERROR: Failed to install payment modes: {str(e)}")
        frappe.log_error(f"Error installing payment modes: {str(e)}", "Payment Modes Installation Error")
        raise


def create_payment_modes():
    """Create default payment modes for the clinic"""
    
    payment_modes = [
        {
            "mode_of_payment": "UPI",
            "type": "Bank",
            "enabled": 1
        },
        {
            "mode_of_payment": "Card",
            "type": "Bank",
            "enabled": 1
        },
        {
            "mode_of_payment": "Bank Transfer",
            "type": "Bank",
            "enabled": 1
        },
        {
            "mode_of_payment": "Online",
            "type": "Bank",
            "enabled": 1
        },
        {
            "mode_of_payment": "UPI/Online",
            "type": "Bank",
            "enabled": 1
        },
        {
            "mode_of_payment": "Net Banking",
            "type": "Bank",
            "enabled": 1
        },
        {
            "mode_of_payment": "Debit Card",
            "type": "Bank",
            "enabled": 1
        },
        {
            "mode_of_payment": "Credit Card",
            "type": "Bank",
            "enabled": 1
        },
        {
            "mode_of_payment": "Google Pay",
            "type": "Bank",
            "enabled": 1
        },
        {
            "mode_of_payment": "PhonePe",
            "type": "Bank",
            "enabled": 1
        },
        {
            "mode_of_payment": "Paytm",
            "type": "Bank",
            "enabled": 1
        },
        {
            "mode_of_payment": "Cash",
            "type": "Cash",
            "enabled": 1
        }
    ]
    
    for mode in payment_modes:
        mode_name = mode["mode_of_payment"]
        
        if not frappe.db.exists("Mode of Payment", mode_name):
            try:
                doc = frappe.get_doc({
                    "doctype": "Mode of Payment",
                    **mode
                })
                doc.insert(ignore_permissions=True)
                print(f"Created Mode of Payment: {mode_name}")
            except Exception as e:
                print(f"Error creating {mode_name}: {str(e)}")
                frappe.log_error(f"Error creating Mode of Payment {mode_name}: {str(e)}")
        else:
            print(f"Mode of Payment already exists: {mode_name}")


def setup_mode_of_payment_accounts(company=None):
    """
    Optional: Set up default accounts for payment modes.
    This should be called after company setup to link payment modes to bank/cash accounts.
    
    Args:
        company (str): Company name to set up accounts for
    """
    if not company:
        # Get default company
        company = frappe.db.get_single_value("Global Defaults", "default_company")
    
    if not company:
        print("No company found, skipping account setup for payment modes")
        return
    
    try:
        # Get default accounts
        default_bank = frappe.db.get_value("Company", company, "default_bank_account")
        default_cash = frappe.db.get_value("Company", company, "default_cash_account")
        
        if not default_bank and not default_cash:
            print(f"No default accounts found for company {company}")
            return
        
        # Payment modes that should use bank account
        bank_modes = ["UPI", "Card", "Bank Transfer", "Online", "UPI/Online", 
                      "Net Banking", "Debit Card", "Credit Card", "Google Pay", 
                      "PhonePe", "Paytm", "Wire Transfer", "Cheque"]
        
        # Payment modes that should use cash account
        cash_modes = ["Cash"]
        
        for mode_name in bank_modes:
            if frappe.db.exists("Mode of Payment", mode_name) and default_bank:
                _add_mode_account(mode_name, company, default_bank)
        
        for mode_name in cash_modes:
            if frappe.db.exists("Mode of Payment", mode_name) and default_cash:
                _add_mode_account(mode_name, company, default_cash)
        
        frappe.db.commit()
        print(f"Payment mode accounts configured for company: {company}")
        
    except Exception as e:
        print(f"Error setting up payment mode accounts: {str(e)}")
        frappe.log_error(f"Error setting up payment mode accounts: {str(e)}")


def _add_mode_account(mode_name, company, account):
    """Add account to mode of payment for a specific company"""
    try:
        mode = frappe.get_doc("Mode of Payment", mode_name)
        
        # Check if account already exists for this company
        existing = [a for a in mode.accounts if a.company == company]
        
        if not existing:
            mode.append("accounts", {
                "company": company,
                "default_account": account
            })
            mode.save(ignore_permissions=True)
            print(f"Added account {account} for {mode_name} in {company}")
        else:
            print(f"Account already configured for {mode_name} in {company}")
            
    except Exception as e:
        print(f"Error adding account for {mode_name}: {str(e)}")
