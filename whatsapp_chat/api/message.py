import frappe
import mimetypes



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
        WHERE (`to` = %(user_no)s OR `from` = %(user_no)s)
        ORDER BY creation ASC
    """, {"user_no": user_no}, as_dict=True)
    
    return messages


@frappe.whitelist()
def mark_as_read(room):
    try:
        doc = frappe.get_doc("WhatsApp Contact", room)
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



@frappe.whitelist()
def send(content, user, room, user_no, attachment=None):
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
            "content_type": content_type
        }).save()
    else:
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "to": user_no,
            "type": "Outgoing",
            "message": content,
            "content_type": content_type
        }).save()
    
    # Prepare socket data for all users - ensure consistent data across all events
    socket_data = {
        "content": content,
        "sender": user,
        "sender_user_no": user,
        "creation": doc.creation,
        "type": doc.type,  # Use the type from the document
        "content_type": content_type,
        "room": room,  # Add room info to help with message routing
        "message_id": doc.name,  # Use doc.name as unique message ID
        "message_type": doc.type.lower()  # Add message_type for backward compatibility
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
        "message_id": doc.name,  # Use doc.name as unique message ID
        "message_type": doc.type.lower()  # Add message_type for backward compatibility
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
        chat_doc.is_read = 0
        chat_doc.save(ignore_version=True)
        
        # Emit socket event for real-time updates with consistent data
        socket_data = {
            "content": doc.message or doc.attach,
            "sender": doc.get("from"),
            "sender_user_no": doc.get("from"),
            "creation": doc.creation,
            "type": doc.type,  # Use the type from the document
            "content_type": doc.content_type,
            "room": contact_name,  # Add room info to help with message routing
            "message_id": doc.name,  # Use doc.name as unique message ID
            "message_type": doc.type.lower()  # Add message_type for backward compatibility
        }
        
        frappe.publish_realtime(contact_name, socket_data)
        
        # Also emit a broadcast for chat list updates with consistent data
        broadcast_data = {
            "room": contact_name,
            "content": doc.message or doc.attach,
            "creation": doc.creation,
            "sender": doc.get("from"),
            "sender_user_no": doc.get("from"),
            "type": doc.type,  # Use the type from the document
            "message_id": doc.name,  # Use doc.name as unique message ID
            "message_type": doc.type.lower()  # Add message_type for backward compatibility
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
                "new_room_creation",  # Broadcast channel
                {
                    "room": new_contact.name,
                    "room_name": mobile_no,
                    "room_type": "Direct",
                    "members": [frappe.session.user],
                    "member_names": [
                        {"name": frappe.session.user_fullname, "email": frappe.session.user}
                    ]
                }
            )

    return "ok"