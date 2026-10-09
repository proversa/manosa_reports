import json

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import getdate, now_datetime, nowdate

from manosa_reports.hr_docs import discussion

from manosa_reports.hr_docs.audience import DONE_STATUSES, can_view, ensure_assignment, get_session_employee
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
	return ensure_assignment(doc, employee)


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


@frappe.whitelist(methods=["GET"])
def pending_count() -> int:
	"""Required reads the logged-in employee has not acknowledged yet, for the menu badge."""
	employee = get_session_employee()
	if not employee:
		return 0
	return frappe.db.count(
		"HR Doc Acknowledgement",
		{"employee": employee, "status": ["in", ["Not Opened", "Opened", "Overdue"]]},
	)


@frappe.whitelist(methods=["GET"])
def badge_counts() -> dict:
	"""Both sidebar badges in one call: unacknowledged required reads and unread comments."""
	return {"required": pending_count(), "comments": discussion.unread_count()}


@frappe.whitelist(methods=["GET"])
def get_comments(post: str) -> dict:
	doc, employee = _get_viewable_post(post)
	discussion.record_view(doc, employee)
	return {"comments": discussion.get_comments(doc), "allow_comments": bool(doc.allow_comments)}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=60)
def add_comment(post: str, content: str, mentions: str | list | None = None) -> dict:
	doc, employee = _get_viewable_post(post)
	if isinstance(mentions, str):
		mentions = json.loads(mentions or "[]")
	discussion.add_comment(doc, employee, content, [m for m in (mentions or []) if isinstance(m, str)])
	return {"comments": discussion.get_comments(doc), "allow_comments": bool(doc.allow_comments)}


@frappe.whitelist(methods=["POST"])
def remove_comment(name: str) -> dict:
	post = frappe.db.get_value("HR Doc Comment", name, "post")
	if not post:
		raise frappe.DoesNotExistError(_("Comment not found."))
	doc, _employee = _get_viewable_post(post)
	discussion.remove_comment(name)
	return {"comments": discussion.get_comments(doc), "allow_comments": bool(doc.allow_comments)}


@frappe.whitelist(methods=["GET"])
def mention_candidates(post: str, txt: str = "") -> list:
	doc, _employee = _get_viewable_post(post)
	return discussion.mention_candidates(doc, txt=txt[:50])
