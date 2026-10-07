frappe.ui.form.on("HR Doc Post", {
	refresh(frm) {
		if (!frm.is_new() && frm.doc.status === "Published") {
			frm.add_custom_button(__("View on Portal"), () => {
				window.open(`/hr-docs/post?name=${encodeURIComponent(frm.doc.name)}`);
			});
		}
		if (!frm.is_new() && frm.doc.is_required) {
			frm.add_custom_button(__("Read Log"), () => {
				frappe.set_route("List", "HR Doc Acknowledgement", { post: frm.doc.name });
			});
			frm.add_custom_button(__("Compliance"), () => {
				frappe.set_route("query-report", "HR Doc Compliance", { post: frm.doc.name });
			});
		}
	},
});
