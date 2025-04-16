import frappe

MAX_MESSAGE_LENGTH = 4096  # or whatever limit you want

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

def send_whatsapp_message(to, message, ref_doctype=None, ref_name=None):
    """Send WhatsApp message"""
    wa_doc = frappe.get_doc({
        'doctype': 'WhatsApp Message',
        'to': to,
        'content_type': 'text',
        'type': 'Outgoing',
        'message': message,
        'reference_doctype': ref_doctype,
        'reference_name': ref_name
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
    """Send help message explaining command-based interaction and available commands"""
    # Get all available dialogues
    dialogues = frappe.get_all(
        'WhatsApp Dialogue',
        fields=['command', 'title'],
        ignore_permissions=True
    )
    
    # Create a clear, structured help message
    message = (
        f"Hello {whatsapp_contact.contact_name}! 👋\n\n"
        "*How to use WhatsApp Chat:*\n"
        "1. Use commands to start specific actions (e.g., logging tickets)\n"
        "2. When you start a command that needs information, you must complete all steps\n"
        "3. You cannot use other commands or switch documents during an active chat flow\n"
        "4. Reply to existing messages to continue conversations on specific tickets\n\n"
        "*Available Commands:*\n"
    )
    
    # Add each command with its description
    for dialogue in dialogues:
        message += f"• *{dialogue.command}*\n  {dialogue.title}\n\n"
    
    # Add footer with quick help
    message += (
        "*Tips:*\n"
        "• Commands always start with /\n"
        "• Complete all steps when prompted\n"
        "• Type any command to begin"
    )
    
    send_whatsapp_message(whatsapp_contact.mobile_no, message)

def link_message_to_reference(whatsapp_contact, doc):
    """Link message to reference document if conditions are met."""
    
    # Check if reply-to-message and link to reference document if available
    if doc.is_reply == 1:
        try:
            replied_messages = frappe.get_list(
                doctype='WhatsApp Message',
                fields=['reference_doctype', 'reference_name'],
                filters={'message_id': doc.reply_to_message_id},
                ignore_permissions=True
            )
            
            if replied_messages:
                replied_to_message = replied_messages[0]
                replied_refdoc = replied_to_message.get('reference_doctype')
                replied_refname = replied_to_message.get('reference_name')

                if replied_refdoc and replied_refname:
                    # Check if already interacting with the same ticket
                    if (whatsapp_contact.reference_doctype == replied_refdoc and 
                        whatsapp_contact.reference_name == replied_refname):
                        send_whatsapp_message(whatsapp_contact.mobile_no, 
                            f'You are already interacting with {replied_refdoc}: {replied_refname}')
                        doc.reference_doctype = replied_refdoc
                        doc.reference_name = replied_refname
                        doc.save(ignore_permissions=True)
                        return True

                    # Update references and notify
                    whatsapp_contact.reference_doctype = replied_refdoc
                    whatsapp_contact.reference_name = replied_refname
                    whatsapp_contact.save(ignore_permissions=True)
                    
                    doc.reference_doctype = replied_refdoc
                    doc.reference_name = replied_refname
                    doc.save(ignore_permissions=True)
                    
                    send_whatsapp_message(whatsapp_contact.mobile_no, 
                        f'You are now interacting with {replied_refdoc}: {replied_refname}')
                    return True
                
                # Handle case where replied message has no reference
                if not replied_refdoc and not replied_refname:
                    if whatsapp_contact.reference_doctype and whatsapp_contact.reference_name:
                        send_whatsapp_message(whatsapp_contact.mobile_no, 
                            f'The message you replied to is not associated with any document. Your reply will be linked to your current {whatsapp_contact.reference_doctype}: {whatsapp_contact.reference_name}.')
                        doc.reference_doctype = whatsapp_contact.reference_doctype
                        doc.reference_name = whatsapp_contact.reference_name
                        doc.save(ignore_permissions=True)
                        return True
                    else:
                        send_whatsapp_message(whatsapp_contact.mobile_no, 
                            'The message you replied to is not associated with any document and you also do not have a current document. Your reply will not be linked to any document.')
                        return False

        except Exception as e:
            frappe.log_error("Error linking message to reference", str(e))
            return False

    # Fallback to link to reference document on WhatsApp contact if available
    if whatsapp_contact.reference_doctype and whatsapp_contact.reference_name:
        doc.reference_doctype = whatsapp_contact.reference_doctype
        doc.reference_name = whatsapp_contact.reference_name
        doc.save(ignore_permissions=True)
        return True
        
    return False

def handle_chat_message(doc, method):
    """Handle incoming WhatsApp messages and manage chat flows"""

    # Order of Operations:
    # 1. Get WhatsApp Contact
    # 2. Check for active chat flow
    # 3. If there's an active exchange, continue the flow (disreagard command and reply-to-message when exchange is acive)
    # 4. If there's no active exchange, check if message is a command (disregard reply to-to-message if message content is command)
    # 5. If no active exchange and not a command but is reply-to-message, get reference document and link to reference document if available 
    # 6. If not a command and no active exchange and not reply-to-message, link to reference document if available 
    # 7. If not a command and no active exchange and not reply-to-message or no reference document available for linking, show help

    if doc.type != 'Incoming':
        return

    whatsapp_contact = get_whatsapp_contact(doc.get("from"))
    if not whatsapp_contact:
        # Only log critical errors
        frappe.log_error('WhatsApp Contact not found', f'No WhatsApp Contact found for {doc.get("from")}')
        return
        
    # Check for active chat flow
    active_exchange = get_active_exchange(whatsapp_contact)
    message_content = doc.message if doc.content_type == 'text' else doc.attach

    # Check if message is too long
    if len(message_content) > MAX_MESSAGE_LENGTH:
        send_whatsapp_message(doc.get("from"), "Your message is too long. Please send a shorter message.")
        return
    
    if active_exchange:
        # Disregard reply-to-message and command when chat flow is active
        if doc.is_reply == 1:
            send_whatsapp_message(doc.get("from"), "You cannot reply to a message when a chat flow is active. Please finish chat flow first.")
            return
        elif message_content and message_content.startswith('/') and doc.content_type == 'text':
            send_whatsapp_message(doc.get("from"), "You cannot send a command when a chat flow is active. Please finish chat flow first.")
            return
        
        # If there's an active exchange, continue the flow
        dialogue = frappe.get_doc('WhatsApp Dialogue', active_exchange.whatsapp_dialogue)
        continue_chat_flow(dialogue, active_exchange, doc)
    else:
        # Check if message is a command (for both text and media messages)
        if message_content and message_content.startswith('/') and doc.content_type == 'text':
            # Disregard reply-to-message when command is sent
            if doc.is_reply == 1:
                send_whatsapp_message(doc.get("from"), "You cannot reply to a message with a command. Please use command without replying to a message.")
                return
            
            # If it's a command, handle it
            handle_command(message_content, whatsapp_contact, doc)
        else:            
            # If not a command and no active exchange, link to reference document if available (link to reference document on replied-to-message for reply-to-message)
            linked = link_message_to_reference(whatsapp_contact, doc)
            if not linked:
                # If not a command and no active exchange, show help
                send_help_message(whatsapp_contact) 