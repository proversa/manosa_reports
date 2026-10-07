import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, nowdate

from manosa_reports.hr_docs.audience import DONE_STATUSES, can_view, get_session_employee
from manosa_reports.hr_docs.schedule import acknowledged_status


def _get_viewable_post(post: str):
	if frappe.session.user == "Guest":
		raise frappe.PermissionError(_("Please log in to view HR documents."))
	doc = frappe.get_doc("HR Doc Post", post)
	employee = get_session_employee()
	if not can_view(doc, employee):
		raise frappe.PermissionError(_("You do not have access to this document."))
	return doc, employee


def _current_ack(doc, employee):
	if not (doc.is_required and employee and doc.ack_version_no):
		return None
	name = frappe.db.get_value(
		"HR Doc Acknowledgement",
		{"post": doc.name, "employee": employee, "version_no": doc.ack_version_no},
		"name",
	)
	return frappe.get_doc("HR Doc Acknowledgement", name) if name else None


@frappe.whitelist(methods=["GET"])
def view_pdf(post: str):
	"""Stream the current PDF of a post inline, after checking the viewer is in its audience."""
	doc, employee = _get_viewable_post(post)
	if not doc.current_file:
		raise frappe.DoesNotExistError(_("This post has no PDF yet."))

	ack = _current_ack(doc, employee)
	if ack and not ack.first_opened_on:
		ack.first_opened_on = now_datetime()
		if ack.status == "Not Opened":
			ack.status = "Opened"
		ack.save(ignore_permissions=True)
		# GET requests are not committed automatically, and this is the read log's "opened" record.
		frappe.db.commit()

	file_doc = frappe.get_doc("File", {"file_url": doc.current_file})
	frappe.local.response.filename = file_doc.file_name
	frappe.local.response.filecontent = file_doc.get_content()
	frappe.local.response.type = "pdf"


@frappe.whitelist(methods=["POST"])
def acknowledge(post: str):
	doc, employee = _get_viewable_post(post)
	ack = _current_ack(doc, employee)
	if not ack:
		frappe.throw(_("This document is not required reading for you."))
	if ack.status in DONE_STATUSES:
		return {"status": ack.status, "acknowledged_on": ack.acknowledged_on}
	if not ack.first_opened_on:
		frappe.throw(_("Please open the document before acknowledging it."))

	ack.acknowledged_on = now_datetime()
	ack.status = acknowledged_status(getdate(ack.due_on), getdate(nowdate()))
	ack.ip_address = frappe.local.request_ip
	ack.user_agent = (frappe.get_request_header("User-Agent") or "")[:500]
	ack.save(ignore_permissions=True)
	return {"status": ack.status, "acknowledged_on": ack.acknowledged_on}
