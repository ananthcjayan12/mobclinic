# Copyright (c) 2025, CJ and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ClinicWorkingHours(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		day: DF.Literal["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
		end_time: DF.Time | None
		is_working_day: DF.Check
		start_time: DF.Time | None
	# end: auto-generated types

	pass