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
	ensure_portal_menu()
	ensure_portal_badge_script()
	nest_workspace_under_hr()
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


PORTAL_MENU_PARENT = "HR"
PORTAL_MENU_LABEL = "HR Docs & Advisories"
PORTAL_ROUTE = "/hr-docs"
BADGE_START = "// >>> HR Docs badge (managed by manosa_reports, do not edit)"
BADGE_END = "// <<< HR Docs badge"


def ensure_portal_menu():
	"""Add an "HR" dropdown to the website top bar with HR Docs under it, keeping existing items."""
	settings = frappe.get_single("Website Settings")
	items = settings.top_bar_items or []
	changed = False
	if not any(i.label == PORTAL_MENU_PARENT and not i.parent_label for i in items):
		settings.append("top_bar_items", {"label": PORTAL_MENU_PARENT})
		changed = True
	if not any((i.url or "").rstrip("/").endswith(PORTAL_ROUTE) for i in items):
		settings.append(
			"top_bar_items",
			{"label": PORTAL_MENU_LABEL, "url": PORTAL_ROUTE, "parent_label": PORTAL_MENU_PARENT},
		)
		changed = True
	if changed:
		settings.flags.ignore_mandatory = True
		settings.save(ignore_permissions=True)


def ensure_portal_badge_script():
	"""Keep the badge script inside Website Script, between markers, without touching other code there."""
	with open(os.path.join(os.path.dirname(__file__), "portal_badge.js")) as f:
		block = f"{BADGE_START}\n{f.read().strip()}\n{BADGE_END}"

	doc = frappe.get_single("Website Script")
	current = doc.javascript or ""
	if BADGE_START in current and BADGE_END in current:
		before, rest = current.split(BADGE_START, 1)
		after = rest.split(BADGE_END, 1)[1]
		updated = f"{before}{block}{after}"
	else:
		updated = f"{current.rstrip()}\n\n{block}\n" if current.strip() else f"{block}\n"
	if updated != current:
		doc.javascript = updated
		doc.save(ignore_permissions=True)


def nest_workspace_under_hr():
	"""Show the HR Docs workspace as a sub-item of the HR workspace in the Desk sidebar."""
	if frappe.db.exists("Workspace", "HR") and frappe.db.exists("Workspace", "HR Docs"):
		if frappe.db.get_value("Workspace", "HR Docs", "parent_page") != "HR":
			frappe.db.set_value("Workspace", "HR Docs", "parent_page", "HR")
