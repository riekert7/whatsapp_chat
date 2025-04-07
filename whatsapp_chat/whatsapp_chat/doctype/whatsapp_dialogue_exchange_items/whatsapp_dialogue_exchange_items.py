import frappe
from frappe.model.document import Document

class WhatsAppDialogueExchangeItems(Document):
    def validate(self):
        """Validate the exchange item"""
        if not self.content:
            frappe.throw(_("Response content is required")) 