"""Idempotent setup for the HR Docs module, run after every migrate."""

import os

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
	remove_old_portal_menu()
	remove_old_portal_badge_script()
	sync_workspace()
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


# Earlier builds added an "HR" dropdown to the website top bar and a badge script to Website Script.
# The badge now lives in the Desk sidebar instead, so remove those if they are still there.
OLD_MENU_PARENT = "HR"
OLD_PORTAL_ROUTE = "/hr-docs"
OLD_BADGE_START = "// >>> HR Docs badge (managed by manosa_reports, do not edit)"
OLD_BADGE_END = "// <<< HR Docs badge"


def remove_old_portal_menu():
	settings = frappe.get_single("Website Settings")
	items = list(settings.top_bar_items or [])
	keep = [
		i for i in items
		if not ((i.url or "").rstrip("/").endswith(OLD_PORTAL_ROUTE) and i.parent_label == OLD_MENU_PARENT)
	]
	has_children = any(i.parent_label == OLD_MENU_PARENT for i in keep)
	keep = [
		i for i in keep
		if not (i.label == OLD_MENU_PARENT and not i.parent_label and not i.url and not has_children)
	]
	if len(keep) != len(items):
		settings.set("top_bar_items", keep)
		settings.flags.ignore_mandatory = True
		settings.save(ignore_permissions=True)


def remove_old_portal_badge_script():
	current = frappe.db.get_single_value("Website Script", "javascript") or ""
	if OLD_BADGE_START not in current or OLD_BADGE_END not in current:
		return
	before, rest = current.split(OLD_BADGE_START, 1)
	after = rest.split(OLD_BADGE_END, 1)[1]
	doc = frappe.get_single("Website Script")
	doc.javascript = (before.rstrip() + "\n" + after.lstrip()).strip()
	doc.save(ignore_permissions=True)

def sync_workspace():
	"""Reload the HR Docs workspace from its file so every Desk user sees it under HR.

	Migrate skips workspace files whose timestamp has not changed, so an earlier copy that only
	HR Docs Managers could see would otherwise stay in place.
	"""
	from frappe.modules.import_file import import_file_by_path

	import_file_by_path(
		os.path.join(os.path.dirname(__file__), "workspace", "hr_docs", "hr_docs.json"), force=True
	)
	if not frappe.db.exists("Workspace", "HR"):
		frappe.db.set_value("Workspace", "HR Docs", "parent_page", "")
