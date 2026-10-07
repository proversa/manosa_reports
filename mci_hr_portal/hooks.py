app_name = "mci_hr_portal"
app_title = "MCI HR Portal"
app_publisher = "Mañosa & Co., Inc."
app_description = "Employee portal for official HR documents and advisories, with required-reading logs"
app_email = "mail@manosa.com"
app_license = "Proprietary"
required_apps = ["frappe/erpnext", "frappe/hrms"]

before_install = "mci_hr_portal.install.before_install"
after_install = "mci_hr_portal.install.after_install"

scheduler_events = {
	"daily": ["mci_hr_portal.tasks.daily"],
}

standard_portal_menu_items = [
	{"title": "HR Docs & Advisories", "route": "/hr-docs", "role": "Employee"},
]
