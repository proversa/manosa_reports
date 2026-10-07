"""Date rules for required-reading reminders. Kept free of Frappe imports so they can be unit tested."""

from datetime import date

REMIND_DAYS_BEFORE_DUE = 3
REPEAT_EVERY_DAYS_AFTER_DUE = 7


def reminder_due(due_on: date, today: date) -> bool:
	"""Reminders go out 3 days before the due date, on the due date, then weekly while overdue."""
	days_left = (due_on - today).days
	if days_left in (REMIND_DAYS_BEFORE_DUE, 0):
		return True
	return days_left < 0 and (-days_left) % REPEAT_EVERY_DAYS_AFTER_DUE == 0


def acknowledged_status(due_on: date, today: date) -> str:
	return "Acknowledged Late" if today > due_on else "Acknowledged"
