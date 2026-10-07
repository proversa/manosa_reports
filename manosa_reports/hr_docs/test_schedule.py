import unittest
from datetime import date

from manosa_reports.hr_docs.schedule import acknowledged_status, reminder_due

DUE = date(2026, 10, 14)


class TestReminderSchedule(unittest.TestCase):
	def test_three_days_before_and_on_due_date(self):
		self.assertTrue(reminder_due(DUE, date(2026, 10, 11)))
		self.assertTrue(reminder_due(DUE, date(2026, 10, 14)))

	def test_no_reminder_on_other_days_before_due(self):
		for day in (7, 8, 9, 10, 12, 13):
			self.assertFalse(reminder_due(DUE, date(2026, 10, day)))

	def test_weekly_while_overdue(self):
		self.assertTrue(reminder_due(DUE, date(2026, 10, 21)))
		self.assertTrue(reminder_due(DUE, date(2026, 10, 28)))
		for day in (15, 16, 20, 22):
			self.assertFalse(reminder_due(DUE, date(2026, 10, day)))

	def test_acknowledged_status(self):
		self.assertEqual(acknowledged_status(DUE, date(2026, 10, 14)), "Acknowledged")
		self.assertEqual(acknowledged_status(DUE, date(2026, 10, 15)), "Acknowledged Late")
