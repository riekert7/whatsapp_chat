from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document

class WhatsAppDialogueSystemItems(Document):
    def validate(self):
        """Validate the system item"""
        if self.field_type == "Default" and not self.default_value:
            frappe.throw(_("Default Value is required when Field Type is Default"))
        elif self.field_type == "Function" and not self.function_script:
            frappe.throw(_("Function Script is required when Field Type is Function")) 