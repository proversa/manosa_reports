"""Who a post is for, and the per-person read log rows for required posts."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, get_url, getdate, now_datetime, nowdate

EMPLOYEE_FIELDS = ["name", "employee_name", "user_id", "department", "designation", "date_of_joining"]
PENDING_STATUSES = ("Not Opened", "Opened", "Overdue")
DONE_STATUSES = ("Acknowledged", "Acknowledged Late")


POST_FIELDS = [
	"name",
	"title",
	"category",
	"post_type",
	"status",
	"summary",
	"tags",
	"memo_date",
	"expiry_date",
	"is_required",
	"is_pinned",
	"sort_order",
	"published_on",
	"allow_comments",
]


def get_audience_employees(post) -> dict:
	"""Active employees the post targets, keyed by employee ID. An empty audience means everyone."""
	rows = post.get("audience") or []
	filters_list = []
	for row in rows:
		if row.audience_type == "All Employees":
			filters_list = [{}]
			break
		if row.audience_type == "Department" and row.department:
			filters_list.append({"department": row.department})
		elif row.audience_type == "Designation" and row.designation:
			filters_list.append({"designation": row.designation})
		elif row.audience_type == "Employee" and row.employee:
			filters_list.append({"name": row.employee})
		elif row.audience_type == "Hired On or After" and row.hired_after:
			filters_list.append({"date_of_joining": [">=", row.hired_after]})
	if not rows:
		filters_list = [{}]

	employees = {}
	for filters in filters_list:
		for emp in frappe.get_all(
			"Employee", filters={"status": "Active", **filters}, fields=EMPLOYEE_FIELDS
		):
			employees[emp.name] = emp
	return employees


def employee_matches(rows, emp) -> bool:
	"""In-memory audience check for one employee record, used when listing many posts at once."""
	if not rows:
		return True
	if not emp:
		return False
	for row in rows:
		if row.audience_type == "All Employees":
			return True
		if row.audience_type == "Department" and row.department == emp.department:
			return True
		if row.audience_type == "Designation" and row.designation == emp.designation:
			return True
		if row.audience_type == "Employee" and row.employee == emp.name:
			return True
		if (
			row.audience_type == "Hired On or After"
			and row.hired_after
			and emp.date_of_joining
			and getdate(emp.date_of_joining) >= getdate(row.hired_after)
		):
			return True
	return False


def is_in_audience(post, employee: str | None) -> bool:
	if not post.get("audience"):
		return True
	if not employee:
		return False
	return employee in get_audience_employees(post)


def sync_assignments(post, notify: bool = True) -> int:
	"""Create read log rows for everyone in the audience who has none for the current version.

	Safe to run repeatedly: it only adds rows that are missing, so it also picks up new hires
	and people who move into a targeted department or designation.
	"""
	if not (post.is_required and post.status == "Published" and post.ack_version_no):
		return 0

	existing = set(
		frappe.get_all(
			"HR Doc Acknowledgement",
			filters={"post": post.name, "version_no": post.ack_version_no},
			pluck="employee",
		)
	)
	due_on = add_days(nowdate(), post.due_days or 7)
	created = 0
	for emp in get_audience_employees(post).values():
		if emp.name in existing:
			continue
		ack = _create_ack(post, emp, due_on)
		created += 1
		if notify:
			send_notice(ack, post, first=True)
	return created


def ensure_assignment(post, employee: str | None):
	"""The employee's read log row for the current version, created on the spot if it is missing.

	Covers people who joined the audience after the post was saved and before the daily sync ran.
	"""
	if not (employee and post.is_required and post.status == "Published" and post.ack_version_no):
		return None
	filters = {"post": post.name, "employee": employee, "version_no": post.ack_version_no}
	name = frappe.db.get_value("HR Doc Acknowledgement", filters, "name")
	if name:
		return frappe.get_doc("HR Doc Acknowledgement", name)
	if not is_in_audience(post, employee):
		return None
	emp = frappe.db.get_value("Employee", employee, EMPLOYEE_FIELDS, as_dict=True)
	ack = _create_ack(post, emp, add_days(nowdate(), post.due_days or 7))
	# Called from GET pages, which are not committed automatically.
	frappe.db.commit()
	return ack


def _create_ack(post, emp, due_on):
	ack = frappe.get_doc(
		{
			"doctype": "HR Doc Acknowledgement",
			"post": post.name,
			"post_title": post.title,
			"version_no": post.ack_version_no,
			"employee": emp.name,
			"employee_name": emp.employee_name,
			"user": emp.user_id,
			"department": emp.department,
			"designation": emp.designation,
			"status": "Not Opened",
			"assigned_on": now_datetime(),
			"due_on": due_on,
		}
	)
	ack.flags.from_portal_logic = True
	ack.insert(ignore_permissions=True)
	return ack


def supersede_older_versions(post) -> None:
	"""Stop reminding people about an older version once a re-acknowledge version is published."""
	frappe.db.sql(
		"""update `tabHR Doc Acknowledgement`
		set status = 'Superseded'
		where post = %s and version_no < %s and status in %s""",
		(post.name, post.ack_version_no, PENDING_STATUSES),
	)


def send_notice(ack, post, first: bool = False) -> None:
	recipient = get_employee_email(ack.employee, ack.user)
	if not recipient:
		return
	link = get_url(f"/hr-docs/post?name={post.name}")
	due = frappe.utils.formatdate(ack.due_on)
	if first:
		subject = _("Required reading: {0}").format(post.title)
		intro = _("A new HR document has been posted that you are required to read.")
	else:
		subject = _("Reminder: please read {0}").format(post.title)
		intro = _("You have not yet acknowledged this required HR document.")
	message = f"""
		<p>{intro}</p>
		<p><b>{frappe.utils.escape_html(post.title)}</b><br>{_("Due")}: {due}</p>
		<p><a href="{link}">{_("Open the document and acknowledge it")}</a></p>
	"""
	frappe.sendmail(
		recipients=[recipient],
		subject=subject,
		message=message,
		reference_doctype="HR Doc Post",
		reference_name=post.name,
	)


def get_employee_email(employee: str, user: str | None) -> str | None:
	if user and "@" in user:
		return user
	emp = frappe.db.get_value(
		"Employee", employee, ["prefered_email", "company_email", "personal_email"], as_dict=True
	)
	if not emp:
		return None
	return emp.prefered_email or emp.company_email or emp.personal_email


def get_session_employee() -> str | None:
	if frappe.session.user == "Guest":
		return None
	return frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")


def is_manager(user: str | None = None) -> bool:
	roles = frappe.get_roles(user or frappe.session.user)
	return "HR Docs Manager" in roles or "System Manager" in roles


def can_view(post, employee: str | None) -> bool:
	if is_manager():
		return True
	if post.status != "Published":
		return False
	return is_in_audience(post, employee)


def mark_overdue(today=None) -> None:
	today = getdate(today or nowdate())
	frappe.db.sql(
		"""update `tabHR Doc Acknowledgement`
		set status = 'Overdue'
		where status in ('Not Opened', 'Opened') and due_on < %s""",
		(today,),
	)


def get_visible_posts(employee: str | None, include_archived: bool = False, fields=None) -> list:
	"""Published (optionally archived) posts this employee can see, best first."""
	statuses = ["Published", "Archived"] if include_archived else ["Published"]
	posts = frappe.get_all(
		"HR Doc Post",
		filters={"status": ["in", statuses]},
		fields=fields or POST_FIELDS,
		order_by="is_pinned desc, sort_order asc, published_on desc",
	)
	if is_manager():
		return posts

	audience = defaultdict(list)
	for row in frappe.get_all(
		"HR Doc Audience",
		filters={"parenttype": "HR Doc Post", "parent": ["in", [p.name for p in posts] or [""]]},
		fields=["parent", "audience_type", "department", "designation", "employee", "hired_after"],
	):
		audience[row.parent].append(row)

	emp = frappe.db.get_value("Employee", employee, EMPLOYEE_FIELDS, as_dict=True) if employee else None
	return [p for p in posts if employee_matches(audience[p.name], emp)]
