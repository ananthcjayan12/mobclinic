import frappe


def _create_index(table, columns, index_name):
    try:
        frappe.db.sql(
            f"ALTER TABLE `{table}` ADD INDEX `{index_name}` ({columns})"
        )
    except Exception:
        pass


def execute():
    _create_index("tabWhatsApp Message Log", "clinic, sent_at", "idx_wa_log_clinic_sent")
    _create_index("tabWhatsApp Message Log", "message_id", "idx_wa_log_msg_id")
    _create_index("tabWhatsApp Conversation", "clinic, last_message_at", "idx_wa_conv_clinic_last")
    _create_index("tabWhatsApp Conversation", "clinic, wa_id", "idx_wa_conv_clinic_waid")
    _create_index("tabWhatsApp Conversation Message", "conversation, message_timestamp", "idx_wa_msg_conv_time")
    _create_index("tabWhatsApp Conversation Message", "wa_message_id", "idx_wa_msg_id")
    frappe.db.commit()
