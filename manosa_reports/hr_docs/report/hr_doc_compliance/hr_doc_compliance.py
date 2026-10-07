import frappe
from frappe import _

DONE = ("Acknowledged", "Acknowledged Late")


def execute(filters=None):
	filters = filters or {}
	conditions = {"status": ["!=", "Superseded"]}
	if filters.get("post"):
		conditions["post"] = filters["post"]
	if filters.get("department"):
		conditions["department"] = filters["department"]

	rows = frappe.get_all(
		"HR Doc Acknowledgement",
		filters=conditions,
		fields=["post", "post_title", "version_no", "status"],
	)
	summary = {}
	for row in rows:
		key = (row.post, row.version_no)
		s = summary.setdefault(
			key,
			{"post": row.post, "post_title": row.post_title, "version_no": row.version_no,
			 "assigned": 0, "acknowledged": 0, "late": 0, "pending": 0, "overdue": 0},
		)
		s["assigned"] += 1
		if row.status in DONE:
			s["acknowledged"] += 1
			if row.status == "Acknowledged Late":
				s["late"] += 1
		elif row.status == "Overdue":
			s["overdue"] += 1
		else:
			s["pending"] += 1

	data = []
	for s in sorted(summary.values(), key=lambda s: (s["post"], s["version_no"])):
		s["percent"] = round(100.0 * s["acknowledged"] / s["assigned"], 1) if s["assigned"] else 0
		data.append(s)
	return get_columns(), data


def get_columns():
	return [
		{"fieldname": "post", "label": _("Post"), "fieldtype": "Link", "options": "HR Doc Post", "width": 120},
		{"fieldname": "post_title", "label": _("Title"), "fieldtype": "Data", "width": 280},
		{"fieldname": "version_no", "label": _("Version"), "fieldtype": "Int", "width": 80},
		{"fieldname": "assigned", "label": _("Assigned"), "fieldtype": "Int", "width": 90},
		{"fieldname": "acknowledged", "label": _("Acknowledged"), "fieldtype": "Int", "width": 120},
		{"fieldname": "late", "label": _("Of Which Late"), "fieldtype": "Int", "width": 110},
		{"fieldname": "pending", "label": _("Pending"), "fieldtype": "Int", "width": 90},
		{"fieldname": "overdue", "label": _("Overdue"), "fieldtype": "Int", "width": 90},
		{"fieldname": "percent", "label": _("% Acknowledged"), "fieldtype": "Percent", "width": 130},
	]
