# WhatsApp Chat

Chat-like Frappe app for sending and receiving WhatsApp messages via the WhatsApp Cloud API. Works as a companion to [frappe_whatsapp](https://github.com/riekert7/frappe_whatsapp/tree/develop).

![whatsapp chat](https://github.com/shridarpatil/whatsapp_chat/assets/11792643/197d1d68-7ff7-48f5-a96c-221d1c6cb8db)

> **Note:** You can only send a direct WhatsApp message after you first receive a message from the client — this is a Meta policy.
> **Requires:** `frappe_whatsapp` to be installed on the same site.

## Installation

```bash
bench get-app https://github.com/riekert7/whatsapp_chat
bench --site [sitename] install-app whatsapp_chat
```

## My Changes (fork of [shridarpatil/whatsapp_chat](https://github.com/shridarpatil/whatsapp_chat))

Extended the app to support server-side custom script execution triggered from WhatsApp dialogues:

- **Custom script execution on WhatsApp Dialogue** — ability to trigger a configurable server script when a specific command is received in a chat dialogue
- **`chat_flow.py` refactor** — updated the chat flow handler to support the custom script integration
- **Reply-to functionality** — messages can now be sent as replies to a specific previous message
- **Improved help message** — clearer help text shown to users in the chat

