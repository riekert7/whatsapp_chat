import frappe
from frappe import _
from whatsapp_chat.api.sandbox import execute_custom_function

def handle_chat_message(doc, method):
    """Handle incoming WhatsApp messages and manage chat flows"""
    
    def get_contact(mobile_no):
        docs = frappe.get_list('Contact', filters={'mobile_no': mobile_no}, ignore_permissions=True)
        if docs:
            return frappe.get_doc('Contact', docs[0].get('name'))
        return None

    def get_customer(contact_name):
        existing_links = frappe.get_all("Dynamic Link", filters={
            'link_doctype': 'Customer',
            'parent': contact_name
        }, fields=['link_name'], ignore_permissions=True)
        return existing_links[0].get('link_name') if existing_links else None

    def validate_response_type(exchange, dialogue, response):
        """Validate response type matches expected type"""
        current_index = len(exchange.wde_table)
        if current_index < len(dialogue.input_items):
            expected_type = dialogue.input_items[current_index].receive_text
            if response.content_type_received != expected_type:
                handle_error_response(exchange, dialogue)
                return False
        return True

    def handle_error_response(exchange, dialogue):
        """Send error message if response type is wrong"""
        current_index = len(exchange.wde_table)
        if current_index < len(dialogue.input_items):
            error_msg = dialogue.input_items[current_index].error_message
            if error_msg:
                send_whatsapp_message(exchange.contact, error_msg)

    def get_active_exchange(contact):
        """Get the active exchange for a contact"""
        wdes = frappe.get_list('WhatsApp Dialogue Exchange', filters={
            'contact': contact.name,
            'active': 1
        }, order_by='creation desc', limit=1, ignore_permissions=True)
        
        if wdes:
            return frappe.get_doc('WhatsApp Dialogue Exchange', wdes[0].name)
        return None 

    def create_target_doc(dialogue, exchange):
        """Create target DocType based on field mappings"""
        target_doc = frappe.new_doc(dialogue.target_doctype)
        
        # Apply input items mappings
        for item in dialogue.input_items:
            if item.idx <= len(exchange.wde_table):
                value = exchange.wde_table[item.idx - 1].content
                if value is not None:
                    target_doc.set(item.target_field, value)
        
        # Apply system items mappings
        for item in dialogue.system_items:
            value = None
            if item.field_type == "Default":
                value = item.default_value
            elif item.field_type == "Function":
                value = execute_custom_function(exchange, dialogue, doc, item.function_script)
            
            if value is not None:
                target_doc.set(item.target_field, value)
        
        # Insert the document
        target_doc.insert(ignore_permissions=True)
        return target_doc

    def continue_chat_flow(dialogue, exchange):
        """Continue the chat flow by sending next message"""
        input_items = dialogue.input_items
        wde_table = exchange.wde_table
        
        if len(wde_table) < len(input_items):
            # Save current response
            if wde_table:
                wde_table[-1].content = doc.message
                wde_table[-1].content_type_received = doc.content_type
                if not validate_response_type(exchange, dialogue, wde_table[-1]):
                    return True
                exchange.save(ignore_permissions=True)
            
            # Send next message
            next_item = input_items[len(wde_table)]
            send_whatsapp_message(doc.get("from"), next_item.send_text)
            
            # Add new row for next response
            new_row = exchange.append('wde_table', {})
            new_row.content_type_received = 'text'
            exchange.save(ignore_permissions=True)
            return True
        else:
            # Chat flow complete
            wde_table[-1].content = doc.message
            wde_table[-1].content_type_received = doc.content_type
            if not validate_response_type(exchange, dialogue, wde_table[-1]):
                return True
            exchange.active = 0
            exchange.save(ignore_permissions=True)
            
            # Create target document
            target_doc = create_target_doc(dialogue, exchange)
            
            # Send completion message
            send_whatsapp_message(
                doc.get("from"),
                f"Thank you! Your {dialogue.target_doctype} has been created with reference: *{target_doc.name}*"
            )
            return False

    def send_whatsapp_message(to, message):
        """Send WhatsApp message"""
        wa_doc = frappe.get_doc({
            'doctype': 'WhatsApp Message',
            'to': to,
            'content_type': 'text',
            'type': 'Outgoing',
            'message': message,
        })
        wa_doc.insert(ignore_permissions=True)

    def handle_command(message, contact):
        """Handle chat commands"""
        if message.startswith('/'):
            # Find matching dialogue

            dialogues = frappe.get_list('WhatsApp Dialogue', filters={'command': message.split()[0]}, ignore_permissions=True)
                
            if dialogues:
                dialogue = frappe.get_doc('WhatsApp Dialogue', dialogues[0].name)
                
                if dialogue.type == 'Create Document':
                    # Start new chat flow
                    exchange = frappe.get_doc({
                        'doctype': 'WhatsApp Dialogue Exchange',
                        'contact': contact.name,
                        'whatsapp_dialogue': dialogue.name,
                        'active': 1
                    })
                    exchange.insert(ignore_permissions=True)

                    # Add new row for first response
                    new_row = exchange.append('wde_table', {})
                    new_row.content_type_received = 'text'
                    exchange.save(ignore_permissions=True)
                    
                    # Send first message
                    if dialogue.input_items:
                        send_whatsapp_message(doc.get("from"), dialogue.input_items[0].send_text)
                    return True
                elif dialogue.type == 'Execute Script':
                    # Execute custom script
                    context = {
                        'message': {
                            'content': doc.message,
                            'type': doc.content_type,
                            'from': doc.get("from")
                        },
                        'command': dialogue.command
                    }
                    dialogue.execute_custom_script(context)
                    return True
                
            else:
                send_whatsapp_message(
                    doc.get("from"),
                    f"Command *{message.split()[0]}* not found. Please try again."
                )
        return False

    def send_help_message(contact):
        """Send help message with available commands"""
        # Get all available dialogues
        dialogues = frappe.get_all(
            'WhatsApp Dialogue',
            fields=['command', 'title'],
            ignore_permissions=True
        )
        
        message = f"Hello {contact.first_name}! Here are the available commands:\n\n"
        
        for dialogue in dialogues:
            message += f"*{dialogue.command}*:\n{dialogue.title}\n\n"
        
        message += "Type any command to start a chat flow."
        
        send_whatsapp_message(contact.mobile_no, message)

    # Main flow
    if doc.type != 'Incoming':
        return

    contact = get_contact(doc.get("from"))
    if not contact:
        frappe.log_error('Number does not match any contact', f'No contact found for {doc.get("from")}')
        return

    # customer = get_customer(contact.name)
    # if not customer:
    #     frappe.log_error('No customer on contact', f'Contact Name {contact.name}')
    #     return

    # Check for active chat flow
    active_exchange = get_active_exchange(contact)

    if active_exchange:
        dialogue = frappe.get_doc('WhatsApp Dialogue', active_exchange.whatsapp_dialogue)
        continue_chat_flow(dialogue, active_exchange)
    else:
        # Handle new command or show help
        if not handle_command(doc.message, contact):
            send_help_message(contact) 