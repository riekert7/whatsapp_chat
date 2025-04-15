import frappe
from frappe.utils import add_days, now, get_datetime
import mimetypes
import time



@frappe.whitelist()
def get_all(room: str, user_no: str):
    """Get all the messages of a particular room

    Args:
        room (str): Room's name.
        user_no (str): User's mobile number or email

    """
    # First try to get the contact's mobile number if user_no is an email
    if '@' in user_no:
        contact = frappe.get_doc("WhatsApp Contact", room)
        user_no = contact.mobile_no
    
    # Get messages where the user is either sender or receiver
    messages = frappe.db.sql("""
        SELECT 
            creation,
            CASE
                WHEN type = 'Outgoing' THEN 'Administrator'
                ELSE `from`
            END as sender_user_no,
            CASE
                WHEN content_type = 'text' THEN message
                ELSE attach
            END as content,
            `from` as original_from,
            `to` as original_to,
            CASE
                WHEN type = 'Outgoing' THEN 'Administrator'
                ELSE `from`
            END as sender,
            type
        FROM `tabWhatsApp Message` 
        WHERE (`to` = %(user_no)s OR `from` = %(user_no)s) AND `template` IS NULL
        ORDER BY creation ASC
    """, {"user_no": user_no}, as_dict=True)
    
    return messages


@frappe.whitelist()
def mark_as_read(room):
    try:
        # Get the document with current values
        doc = frappe.get_doc("WhatsApp Contact", room)
        
        # Only update if not already read
        if doc.is_read == 0:
            doc.is_read = 1
            # Use ignore_version=True to handle concurrent updates
            doc.save(ignore_version=True)
        return "ok"
    except Exception as e:
        frappe.log_error(
            title="WhatsApp Chat Error",
            message=f"Error marking room {room} as read: {str(e)}"
        )
        return "error"

def waba_conversation_passed(wa_contact):
    """Check if the last message in the conversation is older than 24 hours"""
    docs = frappe.get_all(
        "WhatsApp Message", 
        filters={"from": wa_contact.mobile_no},
        fields=["creation"],
        order_by="creation desc",
        limit=1
    )
    
    if not docs:
        return True
        
    last_message_time = docs[0].creation
    if not last_message_time:
        return False
        
    # Convert to datetime if it's a string
    if isinstance(last_message_time, str):
        last_message_time = get_datetime(last_message_time)
        
    # Get current time as datetime
    current_time = get_datetime(now)
    one_day_ago = add_days(current_time, -1)
    
    # Check if the last message is older than 24 hours
    return last_message_time < one_day_ago

def reinitialize_waba_conversation(wa_contact):
    if wa_contact.get('reference_doctype') and wa_contact.get('reference_name'):
        template = 'reinitialize_convo_with_doc-en'
        frappe.call(
            'frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.send_template',
            to=wa_contact.mobile_no,
            reference_doctype='WhatsApp Contact',
            reference_name=wa_contact.name,
            template=template
        )
        frappe.db.set_value('WhatsApp Contact', wa_contact.name, 'last_message', f'{template} sent. Awaiting Customer Response')
        frappe.throw(f'No active conversation, {template} sent. Please wait for customer response to open a new 24 hour conversation.')
    else:
        template = 'reinitialize_convo_without_doc-en'
        frappe.call(
            'frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.send_template',
            to=wa_contact.mobile_no,
            reference_doctype='WhatsApp Contact',
            reference_name=wa_contact.name,
            template=template
        )
        frappe.db.set_value('WhatsApp Contact', wa_contact.name, 'last_message', f'{template} sent. Awaiting Customer Response')
        frappe.throw(f'No active conversation, {template} sent. Please wait for customer response to open a new 24 hour conversation.')
    
    # settings = frappe.get_doc('WhatsApp Settings')
    # url = settings.get('url')
    # version = settings.get('version')
    # access_token = settings.get_password('token')
    # phone_number_id = settings.get('phone_number_id')
    # template = frappe.get_doc('WhatsApp Template', 'init_convo_again-')
    # frappe.make_post_request(
    #     url=f'{url}/{version}/{phone_number_id}/messages',
    #     headers={
    #         'Authorization': f'Bearer {access_token}',
    #         'Content-Type': 'application/json'
    #     },
    #     data={
    #         "messaging_product": "whatsapp",
    #         "to": wa_contact.mobile,
    #         "type": "template",
    #         "template": {
    #             "name": template.name,
    #             "language": { "code": template.language_code },
    #             "components": [
    #                 {
    #                     "type": "body",
    #                     "parameters": [
    #                         {
    #                             "type": "text",
    #                             "text": text_message
    #                         }
    #                     ]
    #                 }
    #             ]
    #         }
    #     }
    # )

    #time.sleep(2)

@frappe.whitelist()
def send(content, user, room, user_no, attachment=None):
    # Get WhatsApp Contact and its reference info
    whatsapp_contact = frappe.get_doc('WhatsApp Contact', {'mobile_no': user_no}, ignore_permissions=True)
    if waba_conversation_passed(whatsapp_contact):
        reinitialize_waba_conversation(whatsapp_contact)
    
    content_type = "text"
    if attachment:
        file_type = mimetypes.guess_type(content)[0]
        if file_type in ["image/apng","image/avif","image/gif","image/jpeg","image/png","image/svg","image/webp"]:
            content_type = 'image'
        elif file_type in ["application/pdf", "application/vnd.ms-powerpoint", "application/msword", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
            content_type = "document"
        elif file_type in ["audio/aac", "audio/mp4", "audio/mpeg", "audio/amr", "audio/ogg"]:
            content_type = 'audio'
        elif file_type in ["video/mp4", "video/3gp"]:
            content_type = "video"
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "to": user_no,
            "type": "Outgoing",
            "attach": content,
            "content_type": content_type,
            "reference_doctype": whatsapp_contact.reference_doctype if whatsapp_contact else None,
            "reference_name": whatsapp_contact.reference_name if whatsapp_contact else None
        }).save()

    else:
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "to": user_no,
            "type": "Outgoing",
            "message": content,
            "content_type": content_type,
            "reference_doctype": whatsapp_contact.reference_doctype if whatsapp_contact else None,
            "reference_name": whatsapp_contact.reference_name if whatsapp_contact else None
        }).save()
    
    # Prepare socket data for all users - ensure consistent data across all events
    socket_data = {
        "content": content,
        "sender": user,
        "sender_user_no": user,
        "creation": doc.creation,
        "type": doc.type,
        "content_type": content_type,
        "room": room,
        "message_id": doc.name,
        "message_type": doc.type.lower(),
        "reference_doctype": doc.reference_doctype,
        "reference_name": doc.reference_name
    }
    
    # Emit room-specific event for all users in the room
    frappe.publish_realtime(room, socket_data)
    
    # Also emit broadcast for chat list updates
    broadcast_data = {
        "room": room,
        "content": content,
        "creation": doc.creation,
        "sender": user,
        "sender_user_no": user,
        "type": doc.type,
        "message_id": doc.name,
        "message_type": doc.type.lower(),
        "reference_doctype": doc.reference_doctype,
        "reference_name": doc.reference_name
    }
    frappe.publish_realtime("latest_chat_updates", broadcast_data)

    return "ok"


def last_message(doc, method):
    if doc.type == 'Outgoing':
        mobile_no = doc.to
    else:
        mobile_no = doc.get("from")

    contact_name = frappe.db.get_value("WhatsApp Contact", filters={"mobile_no": mobile_no})
    if contact_name:
        chat_doc = frappe.get_doc("WhatsApp Contact", contact_name)
        chat_doc.last_message = doc.message or doc.attach
        chat_doc.is_read = 0 if doc.get('type') == 'Incoming' else 1
        chat_doc.save(ignore_version=True)
        
        # Emit socket event for real-time updates with consistent data
        socket_data = {
            "content": doc.message or doc.attach,
            "sender": doc.get("from"),
            "sender_user_no": doc.get("from"),
            "creation": doc.creation,
            "type": doc.type,
            "content_type": doc.content_type,
            "room": contact_name,
            "message_id": doc.name,
            "message_type": doc.type.lower(),
            "reference_doctype": chat_doc.reference_doctype,
            "reference_name": chat_doc.reference_name
        }
        
        frappe.publish_realtime(contact_name, socket_data)
        
        # Also emit a broadcast for chat list updates with consistent data
        broadcast_data = {
            "room": contact_name,
            "content": doc.message or doc.attach,
            "creation": doc.creation,
            "sender": doc.get("from"),
            "sender_user_no": doc.get("from"),
            "type": doc.type,
            "message_id": doc.name,
            "message_type": doc.type.lower(),
            "reference_doctype": chat_doc.reference_doctype,
            "reference_name": chat_doc.reference_name
        }
        
        frappe.publish_realtime("latest_chat_updates", broadcast_data)
    else:
        new_contact = frappe.get_doc({
            "doctype": "WhatsApp Contact",
            "mobile_no": mobile_no,
            "last_message": doc.message or doc.attach,
            "contact_name": mobile_no,
            "is_read": 0
        }).save(ignore_version=True)
        
        # Only emit new room event for incoming messages
        if doc.type == 'Incoming':
            # Emit socket event for new contact
            frappe.publish_realtime(
                "new_room_creation",
                {
                    "room": new_contact.name,
                    "room_name": mobile_no,
                    "room_type": "Direct",
                    "members": [frappe.session.user],
                    "member_names": [
                        {"name": frappe.session.user_fullname, "email": frappe.session.user}
                    ],
                    "reference_doctype": new_contact.reference_doctype,
                    "reference_name": new_contact.reference_name
                }
            )

    return "ok"