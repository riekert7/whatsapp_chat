import frappe
import unittest

class TestWhatsAppDialogue(unittest.TestCase):
    def setUp(self):
        # Create test data
        self.dialogue = frappe.get_doc({
            'doctype': 'WhatsApp Dialogue',
            'title': 'Test Dialogue',
            'command': '/test_command',
            'target_doctype': 'Issue'
        })
        
    def test_validation(self):
        # Test command validation
        self.dialogue.command = 'invalid_command'
        self.assertRaises(frappe.ValidationError, self.dialogue.validate)
        
        # Test valid command
        self.dialogue.command = '/valid_command'
        self.dialogue.validate()
        
    def tearDown(self):
        # Clean up test data
        if self.dialogue.name:
            frappe.delete_doc('WhatsApp Dialogue', self.dialogue.name, force=1) 