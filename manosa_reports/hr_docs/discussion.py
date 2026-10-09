"""Comments on posts, @mentions, who has seen a post, and unread comment counts."""

import json

import frappe
from frappe import _
from frappe.utils import escape_html, format_datetime, get_url, now_datetime, pretty_date

from manosa_reports.hr_docs.audience import (
	get_audience_employees,
	get_session_employee,
	get_visible_posts,
	is_manager,
)

MAX_COMMENT_LENGTH = 2000


def record_view(post, employee: str | None) -> None:
	"""Note that the logged-in user opened the post page, and that they have now seen its comments."""
	user = frappe.session.user
	if user == "Guest" or post.status != "Published":
		return
	now = now_datetime()
	name = frappe.db.get_value("HR Doc View", {"post": post.name, "user": user}, "name")
	if name:
		frappe.db.set_value(
			"HR Doc View",
			name,
			{"last_viewed_on": now, "comments_seen_on": now, "employee": employee},
			update_modified=False,
		)
	else:
		frappe.get_doc(
			{
				"doctype": "HR Doc View",
				"post": post.name,
				"user": user,
				"employee": employee,
				"first_viewed_on": now,
				"last_viewed_on": now,
				"comments_seen_on": now,
			}
		).insert(ignore_permissions=True)
	# Called from GET pages, which are not committed automatically.
	frappe.db.commit()


def seen_counts(posts: list[str]) -> dict:
	"""Distinct employees who opened each post, on the post page or through the required-read log."""
	if not posts:
		return {}
	rows = frappe.db.sql(
		"""select post, count(distinct employee) from (
			select post, employee from `tabHR Doc View`
			where post in %(posts)s and ifnull(employee, '') != ''
			union
			select post, employee from `tabHR Doc Acknowledgement`
			where post in %(posts)s and first_opened_on is not null
		) seen group by post""",
		{"posts": tuple(posts)},
	)
	return dict(rows)


def comment_counts(posts: list[str]) -> dict:
	if not posts:
		return {}
	rows = frappe.db.sql(
		"""select post, count(*) from `tabHR Doc Comment`
		where post in %(posts)s and is_removed = 0 group by post""",
		{"posts": tuple(posts)},
	)
	return dict(rows)


def unread_by_post(user: str | None = None, posts: list[str] | None = None) -> dict:
	"""Comments by other people posted since the user last opened each post (all of them if never opened)."""
	user = user or frappe.session.user
	if user == "Guest":
		return {}
	if posts is None:
		posts = [p.name for p in get_visible_posts(get_session_employee(), fields=["name"])]
	if not posts:
		return {}
	rows = frappe.db.sql(
		"""select c.post, count(*) from `tabHR Doc Comment` c
		left join `tabHR Doc View` v on v.post = c.post and v.user = %(user)s
		where c.post in %(posts)s and c.is_removed = 0 and c.author != %(user)s
			and (v.comments_seen_on is null or c.creation > v.comments_seen_on)
		group by c.post""",
		{"user": user, "posts": tuple(posts)},
	)
	return dict(rows)


def unread_count(user: str | None = None) -> int:
	return sum(unread_by_post(user).values())


def get_comments(post) -> list[dict]:
	user = frappe.session.user
	manager = is_manager()
	rows = frappe.get_all(
		"HR Doc Comment",
		filters={"post": post.name, "is_removed": 0},
		fields=["name", "author", "author_name", "content", "mentions", "creation"],
		order_by="creation asc",
	)
	out = []
	for row in rows:
		mentions = _load_mentions(row.mentions)
		out.append(
			{
				"name": row.name,
				"author_name": row.author_name or row.author,
				"initials": "".join(w[0] for w in (row.author_name or row.author).split()[:2]).upper(),
				"is_mine": row.author == user,
				"can_remove": row.author == user or manager,
				"mentions_me": any(m["user"] == user for m in mentions),
				"when": pretty_date(row.creation),
				"when_full": format_datetime(row.creation),
				"html": render_comment(row.content, mentions),
			}
		)
	return out


def render_comment(content: str, mentions: list[dict]) -> str:
	"""Escape the text, then highlight the @Name call-outs that were verified when it was posted."""
	html = escape_html(content or "")
	for name in sorted({m["name"] for m in mentions}, key=len, reverse=True):
		token = escape_html("@" + name)
		html = html.replace(token, f'<span class="hr-docs-mention">{token}</span>')
	return html


def add_comment(post, employee: str | None, content: str, mentions: list[str]) -> None:
	if post.status != "Published":
		frappe.throw(_("Comments are only open on published posts."))
	if not post.allow_comments:
		frappe.throw(_("Comments are turned off for this post."))
	content = (content or "").strip()
	if not content:
		frappe.throw(_("Write a comment first."))
	if len(content) > MAX_COMMENT_LENGTH:
		frappe.throw(_("Comments can be at most {0} characters.").format(MAX_COMMENT_LENGTH))

	user = frappe.session.user
	verified = [m for m in mention_candidates(post, users=mentions) if "@" + m["name"] in content]
	author_name = (
		frappe.db.get_value("Employee", employee, "employee_name") if employee else None
	) or frappe.utils.get_fullname(user)

	comment = frappe.get_doc(
		{
			"doctype": "HR Doc Comment",
			"post": post.name,
			"post_title": post.title,
			"author": user,
			"author_name": author_name,
			"employee": employee,
			"content": content,
			"mentions": json.dumps(verified) if verified else None,
		}
	)
	comment.insert(ignore_permissions=True)
	record_view(post, employee)
	for m in verified:
		if m["user"] != user:
			send_mention(post, author_name, content, m["user"])


def remove_comment(name: str) -> None:
	comment = frappe.get_doc("HR Doc Comment", name)
	if comment.author != frappe.session.user and not is_manager():
		frappe.throw(_("You can only remove your own comments."), frappe.PermissionError)
	comment.db_set("is_removed", 1)


def mention_candidates(post, txt: str = "", users: list[str] | None = None, limit: int = 10) -> list[dict]:
	"""People who can see the post and can be called out with @: its audience, with a login."""
	if users is not None and not users:
		return []
	audience = get_audience_employees(post)
	out = []
	words = txt.lower().split()
	for emp in sorted(audience.values(), key=lambda e: e.employee_name or ""):
		if not emp.user_id or emp.user_id == frappe.session.user:
			continue
		if users is not None and emp.user_id not in users:
			continue
		name = emp.employee_name or emp.user_id
		if words and not all(w in name.lower() for w in words):
			continue
		out.append({"user": emp.user_id, "name": name, "designation": emp.designation or ""})
		if users is None and len(out) >= limit:
			break
	return out


def send_mention(post, author_name: str, content: str, user: str) -> None:
	link = get_url(f"/hr-docs/post?name={post.name}#comments")
	frappe.sendmail(
		recipients=[user],
		subject=_("{0} mentioned you on {1}").format(author_name, post.title),
		message=f"""
			<p>{escape_html(_("{0} mentioned you in a comment:").format(author_name))}</p>
			<blockquote style="white-space: pre-wrap;">{escape_html(content)}</blockquote>
			<p><a href="{link}">{escape_html(_("Open the post and reply"))}</a></p>
		""",
		reference_doctype="HR Doc Post",
		reference_name=post.name,
	)


def _load_mentions(raw: str | None) -> list[dict]:
	if not raw:
		return []
	try:
		return [m for m in json.loads(raw) if m.get("user") and m.get("name")]
	except (ValueError, AttributeError):
		return []
