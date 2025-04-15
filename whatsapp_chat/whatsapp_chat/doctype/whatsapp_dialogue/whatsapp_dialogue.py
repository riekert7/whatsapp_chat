from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.integrations.utils import make_post_request
import re

class WhatsAppDialogue(Document):
    def validate(self):
        """Validate the dialogue"""
        if not self.title:
            frappe.throw(_("Title is required"))
        if not self.command:
            frappe.throw(_("Command is required"))
            
        # Validate command starts with forward slash
        if not self.command.startswith('/'):
            frappe.throw(_("Command must start with a forward slash (/)"))
            
        # Validate command format
        formatted_command = self.format_command_name(self.command)
        if self.command.lstrip('/') != formatted_command:
            frappe.throw(_("Command must only contain lowercase letters, numbers, and underscores. Example: /issue_integration_failure"))
            
        # Validate custom script
        if not self.custom_script:
            frappe.throw(_("Custom Script is required"))
        try:
            # Try to compile the script to check for syntax errors
            compile(self.custom_script, '<string>', 'exec')
        except Exception as e:
            frappe.throw(_("Invalid Python syntax in custom script: {0}").format(str(e)))
            
        # Validate input items if collect_input_items is checked
        if self.collect_input_items:
            if not self.input_items:
                frappe.throw(_("Input Items are required when Collect Input Items is checked"))
            for item in self.input_items:
                if not item.send_text:
                    frappe.throw(_("Text to send is required for all input items"))
                if not item.receive_text:
                    frappe.throw(_("Receive Content type is required for all input items"))

    def format_command_name(self, command):
        """Format command to only contain lowercase letters and underscores"""
        # Remove leading slash if present
        command = command.lstrip('/')
        # Replace any non-alphanumeric characters with underscores
        command = re.sub(r'[^a-zA-Z0-9]', '_', command)
        # Convert to lowercase
        command = command.lower()
        # Replace multiple consecutive underscores with a single one
        command = re.sub(r'_+', '_', command)
        # Remove leading and trailing underscores
        command = command.strip('_')
        return command

    def execute_custom_script(self, context):
        """Execute the custom script with the given context"""
        # Create a safe namespace for the script
        namespace = {
            'frappe': frappe,
            'context': context
        }
        
        try:
            # Execute the script
            exec(self.custom_script, namespace)
            
            # The script should define an execute() function
            if 'execute' not in namespace:
                frappe.throw(_("Custom script must define an execute(context) function"))
                
            # Call the execute function with context
            namespace['execute'](context)
            
        except Exception as e:
            frappe.log_error(
                title="Custom Script Error",
                message=f"Error executing custom script: {str(e)}\nScript: {self.custom_script}"
            )
            frappe.throw(_("Error executing custom script: {0}").format(str(e)))

    def on_update(self):
        """Sync commands with WhatsApp Business API after save"""
        # Only proceed if this is a new document or if title/command has changed
        if not (self.is_new() or self.has_value_changed('title') or self.has_value_changed('command')):
            return
            
        # Get all active WhatsApp Dialogues
        dialogues = frappe.get_all(
            'WhatsApp Dialogue',
            fields=['title', 'command'],
            limit=10
        )
        
        # Prepare commands list
        commands = []
        for dialogue in dialogues:
            command_name = self.format_command_name(dialogue.command)
            commands.append({
                "command_name": command_name,
                "command_description": dialogue.title
            })
        
        # Get WhatsApp Settings
        settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
        token = settings.get_password("token")
        
        # Prepare headers and URL
        headers = {
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
        }
        url = f"{settings.url}/{settings.version}/{settings.phone_id}/conversational_automation"
        
        # Make API request
        try:
            response = make_post_request(url, headers=headers, json={"commands": commands})
        except Exception as e:
            frappe.log_error(
                title="WhatsApp API Error",
                message=f"Failed to sync commands: {str(e)}",
                reference_doctype=self.doctype,
                reference_name=self.name
            ) 