"""Who a post is for, and the per-person read log rows for required posts."""

import frappe
from frappe import _
from frappe.utils import add_days, get_url, getdate, now_datetime, nowdate

EMPLOYEE_FIELDS = ["name", "employee_name", "user_id", "department", "designation", "date_of_joining"]
PENDING_STATUSES = ("Not Opened", "Opened", "Overdue")
DONE_STATUSES = ("Acknowledged", "Acknowledged Late")


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
		created += 1
		if notify:
			send_notice(ack, post, first=True)
	return created


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
