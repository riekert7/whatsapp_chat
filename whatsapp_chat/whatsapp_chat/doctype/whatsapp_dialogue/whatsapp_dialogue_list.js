// Add button to list view
frappe.listview_settings['WhatsApp Dialogue'] = {
    onload: function(listview) {
        listview.page.add_menu_item(__('Sync Commands to WhatsApp Business API'), function() {
            frappe.call({
                method: 'whatsapp_chat.whatsapp_chat.doctype.whatsapp_dialogue.whatsapp_dialogue.sync_commands',
                callback: function(r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __('Commands synced successfully'),
                            indicator: 'green'
                        });
                    }
                }
            });
        });
    }
}; 