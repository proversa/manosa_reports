frappe.query_reports["HR Doc Compliance"] = {
	filters: [
		{ fieldname: "post", label: __("Post"), fieldtype: "Link", options: "HR Doc Post" },
		{ fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department" },
	],
};
