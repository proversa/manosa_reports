# HR Docs module (manosa_reports)

An employee portal at `/hr-docs` on merps.manosa.com. Employees browse official HR documents and advisories by category there. Admins post PDFs from the Desk. Any post can be marked as required reading for a chosen audience, and each person's opening and acknowledgment is kept in a read log.

## What it adds

| Piece | What it does |
| --- | --- |
| HR Doc Category | The portal's categories. The five starting ones are created after the first migrate. |
| HR Doc Post | One document or advisory: details, audience, required-reading settings, and PDF versions. |
| HR Doc Acknowledgement | The read log, with one row per person, per required post, per version. Nobody can edit or delete these rows. |
| `/hr-docs`, `/hr-docs/post?name=…` | The employee portal and PDF viewer, with the "I have read and understood this" button. |
| HR Docs workspace, HR Doc Compliance report | Admin home in the Desk, and acknowledged, pending and overdue counts for each post. |
| Daily job | Archives expired advisories, adds new hires to required posts, marks reads overdue, and emails reminders to the employee. |
| HR Docs Manager role | Gives posting rights. It is given to Administrator after migrate. |

## Wiring into the app (one time)

Add `HR Docs` as a new line in `manosa_reports/modules.txt`. Then merge these into `manosa_reports/hooks.py`, appending to any lists or dicts that already exist:

```python
after_migrate = ["manosa_reports.hr_docs.install.after_migrate"]

scheduler_events = {
	"cron": {
		# 07:00 in the site's time zone (System Settings). Frappe reads cron times in that
		# zone, not the server's CET clock. 07:00 keeps it clear of the 02:00-03:00 server backups.
		"0 7 * * *": ["manosa_reports.hr_docs.tasks.daily"],
	},
}

standard_portal_menu_items = [
	{"title": "HR Docs & Advisories", "route": "/hr-docs", "role": "Employee"},
]
```

## Deploying on MERPS (Docker, project `erpnext-one`)

There is no bench on the host. Do not use `bench get-app`. Run these as `admin_mci`.

```bash
# 1. Back up first
/home/admin_mci/backup-manager.sh --cron >> /home/admin_mci/backups/backup.log 2>&1

# 2. Update the staging copy of manosa_reports
cd ~/gitops/staging/manosa_projects && git pull

# 3. Copy the app package into every container that runs app code
for c in backend frontend scheduler queue-short queue-long websocket; do
  docker cp ~/gitops/staging/manosa_projects/manosa_reports/. \
    erpnext-one-$c-1:/home/frappe/frappe-bench/apps/manosa_reports/manosa_reports/
done

# 4. Create the DocTypes, role, categories, workspace and report
docker exec erpnext-one-backend-1 bench --site merps.manosa.com migrate

# 5. Restart by name
docker restart erpnext-one-backend-1 erpnext-one-frontend-1 erpnext-one-scheduler-1 \
  erpnext-one-websocket-1 erpnext-one-queue-short-1 erpnext-one-queue-long-1
```

Check that it worked:

```bash
docker exec erpnext-one-backend-1 bench --site merps.manosa.com execute frappe.get_all --kwargs "{'doctype': 'HR Doc Category', 'pluck': 'name'}"
docker exec erpnext-one-backend-1 bench --site merps.manosa.com execute frappe.utils.get_system_timezone
docker exec erpnext-one-backend-1 bench --site merps.manosa.com scheduler status
```

The second command should print `Asia/Manila`. If it prints a European zone, the daily job runs at 07:00 that zone's time, which is 13:00 or 14:00 in Manila.

Code copied with `docker cp` lives only in the running containers. It is lost if the stack is recreated. Include this branch the next time the `custom-erpnext` image is built so the change is permanent.

## Posting a document

1. In the Desk, open **HR Docs → New Post**.
2. Fill in the title, category, type and summary. The PDFs are scans, so search only finds words in the title, summary and tags.
3. Under **PDF**, add a row and attach the PDF. Leave "Private" ticked.
4. For required reading, tick **Required Reading**, set the days allowed (7 by default), and add audience rows. Leave the audience empty to target everyone.
5. Set the status to **Published** and save. Everyone in the audience gets an email, and the post appears under "Required for you".

To replace a PDF, add a new row under **PDF**. Untick "Everyone Must Acknowledge Again" when the change is only a correction.

## Notes

- Employees need a website login linked to an active Employee record (Employee → User ID).
- Reminders go 3 days before the due date, on the due date, then weekly, to the employee only.
- Never commit HR PDFs to this repository.
