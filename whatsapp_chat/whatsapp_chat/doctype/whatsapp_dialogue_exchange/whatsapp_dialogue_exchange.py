import frappe
from frappe import _
from frappe.model.document import Document

class WhatsAppDialogueExchange(Document):
    def validate(self):
        """Validate the exchange"""
        if self.active:
            # Check if there's already an active exchange for this WhatsApp Contact
            existing = frappe.get_all(
                'WhatsApp Dialogue Exchange',
                filters={
                    'whatsapp_contact': self.whatsapp_contact,
                    'active': 1,
                    'name': ['!=', self.name]
                }
            )
            if existing:
                frappe.throw(_("WhatsApp Contact already has an active chat flow")) 