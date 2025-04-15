import frappe
from frappe import _

def get_whatsapp_contact(mobile_no):
    """Get WhatsApp Contact by mobile number"""
    try:
        return frappe.get_doc('WhatsApp Contact', {'mobile_no': mobile_no}, ignore_permissions=True)
    except:
        return None

def get_customer(whatsapp_contact_name):
    """Get customer linked to WhatsApp Contact"""
    existing_links = frappe.get_all("Dynamic Link", filters={
        'link_doctype': 'Customer',
        'parent': whatsapp_contact_name
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
            send_whatsapp_message(exchange.whatsapp_contact, error_msg)

def get_active_exchange(whatsapp_contact):
    """Get the active exchange for a WhatsApp Contact"""
    wdes = frappe.get_list('WhatsApp Dialogue Exchange', filters={
        'whatsapp_contact': whatsapp_contact.name,
        'active': 1
    }, order_by='creation desc', limit=1, ignore_permissions=True)
    
    if wdes:
        return frappe.get_doc('WhatsApp Dialogue Exchange', wdes[0].name)
    return None

def create_target_doc(dialogue, exchange):
    """Create target DocType based on system items mappings"""
    target_doc = frappe.new_doc(dialogue.target_doctype)
    
    # Prepare input items context
    input_items = []
    for item in exchange.wde_table:
        input_items.append({
            'content': item.content,
            'type': item.content_type_received,
            'from': exchange.whatsapp_contact
        })
    
    # Apply system items mappings
    for item in dialogue.system_items:
        value = None
        
        if item.field_type == "Direct Map":
            # Direct mapping from input items
            try:
                idx = int(item.default_value) - 1  # Convert to 0-based index
                if 0 <= idx < len(input_items):
                    value = input_items[idx]['content']
            except:
                frappe.log_error(f"Invalid direct map index: {item.default_value}")
                continue
                
        elif item.field_type == "Default":
            value = item.default_value
            
        elif item.field_type == "Function":
            # Execute function with context
            context = {
                'input_items': input_items,
                'doc': target_doc,
                'command': dialogue.command
            }
            try:
                value = execute_custom_function(exchange, dialogue, context, item.function_script)
            except Exception as e:
                frappe.log_error(f"Error executing function for {item.target_field}: {str(e)}")
                continue
        
        if value is not None:
            target_doc.set(item.target_field, value)
    
    # Insert the document
    target_doc.insert(ignore_permissions=True)
    
    # Update WhatsApp Contact with reference to the newly created document
    whatsapp_contact = frappe.get_doc('WhatsApp Contact', exchange.whatsapp_contact)
    whatsapp_contact.reference_doctype = dialogue.target_doctype
    whatsapp_contact.reference_name = target_doc.name
    whatsapp_contact.save(ignore_permissions=True)
    
    return target_doc

def continue_chat_flow(dialogue, exchange, doc):
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
        
        # Prepare messages context
        messages = []
        for item in wde_table:
            messages.append({
                'content': item.content,
                'type': item.content_type_received,
                'from': doc.get("from")
            })
        
        # Execute custom script
        context = {
            'messages': messages,
            'command': dialogue.command
        }
        dialogue.execute_custom_script(context)
        
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

def handle_command(message, whatsapp_contact, doc):
    """Handle chat commands"""
    if message.startswith('/'):
        # Find matching dialogue
        dialogues = frappe.get_list('WhatsApp Dialogue', filters={'command': message.split()[0]}, ignore_permissions=True)
            
        if dialogues:
            dialogue = frappe.get_doc('WhatsApp Dialogue', dialogues[0].name)
            
            if dialogue.collect_input_items:
                # Start new chat flow
                exchange = frappe.get_doc({
                    'doctype': 'WhatsApp Dialogue Exchange',
                    'whatsapp_contact': whatsapp_contact.name,
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
            else:
                # Execute script directly
                context = {
                    'messages': [{
                        'content': doc.message,
                        'type': doc.content_type,
                        'from': doc.get("from")
                    }],
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

def send_help_message(whatsapp_contact):
    """Send help message with available commands"""
    # Get all available dialogues
    dialogues = frappe.get_all(
        'WhatsApp Dialogue',
        fields=['command', 'title'],
        ignore_permissions=True
    )
    
    message = f"Hello {whatsapp_contact.contact_name}! Here are the available commands:\n\n"
    
    for dialogue in dialogues:
        message += f"*{dialogue.command}*:\n{dialogue.title}\n\n"
    
    message += "Type any command to start a chat flow."
    
    send_whatsapp_message(whatsapp_contact.mobile_no, message)

def link_message_to_reference(whatsapp_contact, doc):
    """Link message to reference document if conditions are met"""
    # Only link if reference fields are filled
    if whatsapp_contact.reference_doctype and whatsapp_contact.reference_name:
        # Update the message with reference fields
        doc.reference_doctype = whatsapp_contact.reference_doctype
        doc.reference_name = whatsapp_contact.reference_name
        doc.save(ignore_permissions=True)
        return True
    return False

def handle_chat_message(doc, method):
    """Handle incoming WhatsApp messages and manage chat flows"""
    if doc.type != 'Incoming':
        return

    whatsapp_contact = get_whatsapp_contact(doc.get("from"))
    if not whatsapp_contact:
        # Only log critical errors
        frappe.log_error('WhatsApp Contact not found', f'No WhatsApp Contact found for {doc.get("from")}')
        return
        
    # Check for active chat flow
    active_exchange = get_active_exchange(whatsapp_contact)

    if active_exchange:
        # If there's an active exchange, continue the flow
        dialogue = frappe.get_doc('WhatsApp Dialogue', active_exchange.whatsapp_dialogue)
        continue_chat_flow(dialogue, active_exchange, doc)
    else:
        # Check if message is a command (for both text and media messages)
        message_content = doc.message if doc.content_type == 'text' else doc.attach
        if message_content and message_content.startswith('/') and doc.content_type == 'text':
            # If it's a command, handle it
            handle_command(message_content, whatsapp_contact, doc)
        else:
            # If not a command and no active exchange, link to reference document if available
            linked = link_message_to_reference(whatsapp_contact, doc)
            if not linked:
                # If not a command and no active exchange, show help
                send_help_message(whatsapp_contact) 