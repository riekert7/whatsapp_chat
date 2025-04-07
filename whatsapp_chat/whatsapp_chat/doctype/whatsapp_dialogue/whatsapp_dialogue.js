frappe.ui.form.on('WhatsApp Dialogue', {
    refresh: function(frm) {
        // Add custom buttons or actions
    },
    
    target_doctype: function(frm) {
        // Update field mappings when target doctype changes
        if (frm.doc.target_doctype) {
            frappe.model.with_doctype(frm.doc.target_doctype, function() {
                let fields = frappe.get_meta(frm.doc.target_doctype).get_fieldnames();
                frm.set_query('target_field', 'field_mappings', function() {
                    return {
                        filters: {
                            fieldname: ['in', fields]
                        }
                    };
                });
            });
        }
    }
}); 