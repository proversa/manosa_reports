from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import strip_html

from manosa_reports.hr_docs import discussion
from manosa_reports.hr_docs.audience import (
	PENDING_STATUSES,
	get_session_employee,
	get_visible_posts,
	is_manager,
)

no_cache = 1

def require_login(path: str):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = f"/login?redirect-to={path}"
		raise frappe.Redirect


def get_my_acks(employee: str | None) -> dict:
	"""The newest read log row per post for this employee, ignoring superseded versions."""
	if not employee:
		return {}
	acks = {}
	for row in frappe.get_all(
		"HR Doc Acknowledgement",
		filters={"employee": employee, "status": ["!=", "Superseded"]},
		fields=["name", "post", "version_no", "status", "due_on", "acknowledged_on"],
		order_by="version_no asc",
	):
		acks[row.post] = row
	return acks


def matches_search(post, q: str) -> bool:
	haystack = " ".join(filter(None, [post.title, strip_html(post.summary or ""), post.tags, post.category])).lower()
	return all(word in haystack for word in q.lower().split())


def get_context(context):
	require_login("/hr-docs")
	context.no_cache = 1
	context.show_sidebar = True
	context.title = _("HR Docs & Advisories")

	employee = get_session_employee()
	q = (frappe.form_dict.get("q") or "").strip()
	selected_category = frappe.form_dict.get("category") or ""
	view = frappe.form_dict.get("view") or ""
	show_archived = view == "archived"

	acks = get_my_acks(employee)
	posts = get_visible_posts(employee, include_archived=show_archived)
	names = [p.name for p in posts]
	seen = discussion.seen_counts(names)
	comments = discussion.comment_counts(names)
	unread = discussion.unread_by_post(posts=names)
	for post in posts:
		post.ack = acks.get(post.name)
		post.pending = bool(post.ack and post.ack.status in PENDING_STATUSES)
		post.seen_count = seen.get(post.name, 0)
		post.comment_count = comments.get(post.name, 0)
		post.unread_comments = unread.get(post.name, 0)

	context.required_for_you = sorted(
		[p for p in posts if p.pending and p.status == "Published"],
		key=lambda p: str(p.ack.due_on or ""),
	)

	if show_archived:
		posts = [p for p in posts if p.status == "Archived"]
	if view == "required":
		posts = [p for p in posts if p.is_required]
	if view == "pending":
		posts = [p for p in posts if p.pending]
	if q:
		posts = [p for p in posts if matches_search(p, q)]

	categories = frappe.get_all(
		"HR Doc Category",
		filters={"is_active": 1},
		fields=["name", "description"],
		order_by="sort_order asc, name asc",
	)
	by_category = defaultdict(list)
	for post in posts:
		by_category[post.category].append(post)
	for category in categories:
		category.posts = by_category.get(category.name, [])

	if selected_category:
		categories = [c for c in categories if c.name == selected_category]

	context.employee = employee
	context.is_manager = is_manager()
	context.q = q
	context.view = view
	context.selected_category = selected_category
	context.all_categories = frappe.get_all(
		"HR Doc Category", filters={"is_active": 1}, pluck="name", order_by="sort_order asc, name asc"
	)
	context.categories = [c for c in categories if c.posts or selected_category]
	context.pinned = [p for p in posts if p.is_pinned and not q and not selected_category]
	context.result_count = len(posts)
	context.unread_comments = sum(unread.values())
