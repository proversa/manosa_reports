frappe.listview_settings["HR Doc Post"] = {
	get_indicator(doc) {
		const colors = { Draft: "red", Published: "green", Archived: "gray" };
		return [__(doc.status), colors[doc.status], `status,=,${doc.status}`];
	},
};
