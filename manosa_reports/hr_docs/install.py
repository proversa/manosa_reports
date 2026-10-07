"""Idempotent setup for the HR Docs module, run after every migrate."""

import frappe

ROLE = "HR Docs Manager"
DEFAULT_CATEGORIES = [
	("Company Handbook & Code of Conduct", "The employee handbook, conduct rules, discipline and grievance."),
	("Pay, Benefits & Reimbursements", "Compensation, benefits, overtime and meal claims."),
	("Travel & Official Business", "Per diem, official business rules, mileage and travel approvals."),
	("Advisories & Announcements", "Short-lived notices with an end date, such as schedule changes."),
	("Forms & Templates", "Blank forms employees download."),
]


def ensure_role():
	if not frappe.db.exists("Role", ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert(ignore_permissions=True)


def after_migrate():
	ensure_role()
	if frappe.db.get_value("Has Role", {"parent": "Administrator", "role": ROLE}) is None:
		# Posting rights go to the Administrator first; HR staff can be given the role later.
		admin = frappe.get_doc("User", "Administrator")
		admin.append("roles", {"role": ROLE})
		admin.save(ignore_permissions=True)

	if not frappe.db.exists("DocType", "HR Doc Category") or frappe.db.count("HR Doc Category"):
		return
	for order, (name, description) in enumerate(DEFAULT_CATEGORIES, start=1):
		frappe.get_doc(
			{
				"doctype": "HR Doc Category",
				"category_name": name,
				"description": description,
				"sort_order": order * 10,
				"is_active": 1,
			}
		).insert(ignore_permissions=True)
