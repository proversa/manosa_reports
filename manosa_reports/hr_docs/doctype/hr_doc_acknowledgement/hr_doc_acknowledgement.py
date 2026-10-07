import frappe
from frappe import _
from frappe.model.document import Document

# Once set, these fields are the record of who read what and when.
LOCKED_ONCE_SET = ("post", "version_no", "employee", "assigned_on", "first_opened_on", "acknowledged_on")


class HRDocAcknowledgement(Document):
	def validate(self):
		if self.is_new():
			return
		previous = self.get_doc_before_save()
		for field in LOCKED_ONCE_SET:
			if previous.get(field) and previous.get(field) != self.get(field):
				frappe.throw(_("{0} cannot be changed in the read log.").format(self.meta.get_label(field)))

	def on_trash(self):
		frappe.throw(_("Read log entries cannot be deleted."))
