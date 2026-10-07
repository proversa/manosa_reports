import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from manosa_reports.hr_docs.audience import supersede_older_versions, sync_assignments


class HRDocPost(Document):
	def validate(self):
		self.validate_versions()
		if self.is_required and (self.due_days or 0) < 1:
			self.due_days = 7
		if self.status == "Published" and not self.versions:
			frappe.throw(_("Attach the PDF before publishing."))
		if self.status == "Published" and not self.published_on:
			self.published_on = now_datetime()

	def validate_versions(self):
		previous = self.get_doc_before_save()
		if previous and len(self.versions or []) < len(previous.versions or []):
			frappe.throw(_("Versions cannot be removed. Add a new row to replace the PDF."))
		if previous:
			for old, new in zip(previous.versions or [], self.versions or []):
				if old.file != new.file:
					frappe.throw(_("Version {0} has already been posted. Add a new row to replace the PDF.").format(old.version_no))

		ack_version_no = None
		for i, row in enumerate(self.versions or [], start=1):
			if not row.file.lower().endswith(".pdf"):
				frappe.throw(_("Version {0}: only PDF files can be posted.").format(i))
			if not row.file.startswith("/private/"):
				frappe.throw(
					_("Version {0}: upload the PDF as a private file so only targeted employees can open it.").format(i)
				)
			row.version_no = i
			if not row.uploaded_by:
				row.uploaded_by = frappe.session.user
				row.uploaded_on = now_datetime()
			if i == 1 or row.requires_reack:
				ack_version_no = i

		self.current_version_no = len(self.versions or []) or None
		self.current_file = self.versions[-1].file if self.versions else None
		self.ack_version_no = ack_version_no

	def on_update(self):
		if not (self.is_required and self.status == "Published"):
			return
		previous = self.get_doc_before_save()
		if previous and (previous.ack_version_no or 0) < (self.ack_version_no or 0):
			supersede_older_versions(self)
		sync_assignments(self)

	def on_trash(self):
		if frappe.db.exists("HR Doc Acknowledgement", {"post": self.name, "first_opened_on": ["is", "set"]}):
			frappe.throw(_("Employees have already opened this post. Archive it instead of deleting it."))
		frappe.db.delete("HR Doc Acknowledgement", {"post": self.name})
