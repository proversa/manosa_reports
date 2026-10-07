frappe.listview_settings["HR Doc Acknowledgement"] = {
	get_indicator(doc) {
		const colors = {
			"Not Opened": "orange",
			Opened: "blue",
			Acknowledged: "green",
			"Acknowledged Late": "green",
			Overdue: "red",
			Superseded: "gray",
		};
		return [__(doc.status), colors[doc.status], `status,=,${doc.status}`];
	},
};
