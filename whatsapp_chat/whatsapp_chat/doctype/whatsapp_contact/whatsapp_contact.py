# Copyright (c) 2024, shridhar patil and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WhatsAppContact(Document):
	def clear_reference_fields(self):
		"""Clear reference fields"""
		self.reference_doctype = None
		self.reference_name = None
		self.save()
