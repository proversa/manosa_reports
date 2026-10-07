import frappe
from frappe import _
from frappe.utils import cint

from manosa_reports.hr_docs.audience import DONE_STATUSES, can_view, get_session_employee, is_manager

no_cache = 1


def get_context(context):
	name = frappe.form_dict.get("name")
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = f"/login?redirect-to=/hr-docs/post?name={name or ''}"
		raise frappe.Redirect
	if not name or not frappe.db.exists("HR Doc Post", name):
		raise frappe.DoesNotExistError(_("Document not found."))

	post = frappe.get_doc("HR Doc Post", name)
	employee = get_session_employee()
	if not can_view(post, employee):
		raise frappe.PermissionError(_("You do not have access to this document."))

	ack = None
	if post.is_required and employee and post.ack_version_no:
		ack = frappe.db.get_value(
			"HR Doc Acknowledgement",
			{"post": post.name, "employee": employee, "version_no": post.ack_version_no},
			["name", "status", "due_on", "first_opened_on", "acknowledged_on"],
			as_dict=True,
		)

	context.no_cache = 1
	context.show_sidebar = True
	context.title = post.title
	context.post = post
	context.ack = ack
	context.acknowledged = bool(ack and ack.status in DONE_STATUSES)
	context.is_manager = is_manager()
	context.pdf_url = f"/api/method/manosa_reports.hr_docs.api.view_pdf?post={post.name}"
	context.parents = [{"route": "hr-docs", "title": _("HR Docs & Advisories")}]
	context.version_count = cint(post.current_version_no)
