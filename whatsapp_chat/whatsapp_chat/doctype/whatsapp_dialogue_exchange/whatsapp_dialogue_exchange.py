import frappe
from frappe.model.document import Document

class WhatsAppDialogueExchange(Document):
    def validate(self):
        """Validate the exchange"""
        if self.active:
            # Check if there's already an active exchange for this contact
            existing = frappe.get_all(
                'WhatsApp Dialogue Exchange',
                filters={
                    'contact': self.contact,
                    'active': 1,
                    'name': ['!=', self.name]
                }
            )
            if existing:
                frappe.throw(_("Contact already has an active chat flow")) 