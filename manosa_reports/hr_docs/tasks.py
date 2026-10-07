import frappe
from frappe.utils import getdate, nowdate

from manosa_reports.hr_docs.audience import mark_overdue, send_notice, sync_assignments
from manosa_reports.hr_docs.schedule import reminder_due


def daily():
	"""Run once a day by the Frappe scheduler."""
	archive_expired_advisories()
	sync_all_required_posts()
	mark_overdue()
	send_reminders()


def archive_expired_advisories():
	for name in frappe.get_all(
		"HR Doc Post",
		filters={"post_type": "Advisory", "status": "Published", "expiry_date": ["<", nowdate()]},
		pluck="name",
	):
		frappe.db.set_value("HR Doc Post", name, "status", "Archived")
		frappe.db.set_value(
			"HR Doc Acknowledgement",
			{"post": name, "status": ["in", ["Not Opened", "Opened", "Overdue"]]},
			"status",
			"Superseded",
		)
	frappe.db.commit()


def sync_all_required_posts():
	"""Add read log rows for new hires and people who moved into a targeted group."""
	for name in frappe.get_all("HR Doc Post", filters={"status": "Published", "is_required": 1}, pluck="name"):
		sync_assignments(frappe.get_doc("HR Doc Post", name))
		frappe.db.commit()


def send_reminders():
	today = getdate(nowdate())
	pending = frappe.get_all(
		"HR Doc Acknowledgement",
		filters={"status": ["in", ["Not Opened", "Opened", "Overdue"]]},
		fields=["name", "post", "due_on", "last_reminder_on"],
	)
	posts = {}
	for row in pending:
		if not row.due_on or not reminder_due(getdate(row.due_on), today):
			continue
		if row.last_reminder_on and getdate(row.last_reminder_on) == today:
			continue
		if row.post not in posts:
			posts[row.post] = frappe.get_doc("HR Doc Post", row.post)
		ack = frappe.get_doc("HR Doc Acknowledgement", row.name)
		send_notice(ack, posts[row.post])
		frappe.db.set_value(
			"HR Doc Acknowledgement",
			row.name,
			{"reminders_sent": (ack.reminders_sent or 0) + 1, "last_reminder_on": today},
		)
	frappe.db.commit()
