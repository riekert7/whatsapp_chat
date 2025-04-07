from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document

class WhatsAppDialogueInputItems(Document):
    def validate(self):
        """Validate the input item"""
        if not self.send_text:
            frappe.throw(_("Text to send is required"))
        if not self.receive_text:
            frappe.throw(_("Receive Content type is required")) 