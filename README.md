# manosa_reports

Custom Frappe apps and reports for MERPS (ERPNext 15) at Mañosa & Co.

## mci_hr_portal: HR Docs & Advisories

An employee portal page at `/hr-docs` where employees browse official HR documents and advisories by category. Admins post PDFs from the Desk. Any post can be marked as required reading for a chosen audience, and every person's opening and acknowledgment is kept in a read log.

### What it adds

| Piece | What it does |
| --- | --- |
| HR Doc Category | The portal's categories. Five are created on install. |
| HR Doc Post | One document or advisory: details, audience, required-reading settings, and PDF versions. |
| HR Doc Acknowledgement | The read log, with one row per person, per required post, per version. Nobody can edit or delete these rows. |
| `/hr-docs` | The employee portal: a "Required for you" list, search, categories, and an archived view. |
| `/hr-docs/post?name=…` | The PDF viewer with the "I have read and understood this" button. |
| HR Docs workspace | The admin home in the Desk, with shortcuts to posts, the read log and the compliance report. |
| HR Doc Compliance | A report of the acknowledged, pending and overdue counts for each post, exportable to Excel. |
| Daily job | Archives expired advisories, adds new hires to required posts, marks reads overdue, and emails reminders. |
| HR Docs Manager role | Gives posting rights. It is given to Administrator on install. |

### Install on the MERPS server

Run these over SSH as the bench user, from the bench folder. Take a backup first.

```bash
bench --site merps.manosa.com backup --with-files
bench get-app https://github.com/proversa/manosa_reports --branch main
bench --site merps.manosa.com install-app mci_hr_portal
bench --site merps.manosa.com migrate
bench build --app mci_hr_portal
sudo supervisorctl restart all   # or: bench restart
```

The daily job needs the scheduler to be on: `bench --site merps.manosa.com enable-scheduler`.

### Update after changes are merged

```bash
bench update --apps mci_hr_portal --pull --no-backup   # or: cd apps/mci_hr_portal && git pull
bench --site merps.manosa.com migrate
bench restart
```

### Posting a document

1. In the Desk, open **HR Docs → New Post**.
2. Fill in the title, category, type and summary. The PDFs are scans, so search only finds words in the title, summary and tags.
3. Under **PDF**, add a row and attach the PDF. Leave "Private" ticked.
4. For required reading, tick **Required Reading**, set the days allowed (7 by default), and add audience rows. Leave the audience empty to target everyone.
5. Set the status to **Published** and save. Everyone in the audience gets an email, and the post appears in their "Required for you" list.

To replace a PDF, add a new row under **PDF**. Untick "Everyone Must Acknowledge Again" when the change is only a correction.

### Notes

- Employees must have a website login linked to an active Employee record (Employee → User ID).
- Reminders go out 3 days before the due date, on the due date, and then weekly. They go to the employee only.
- Do not commit the HR PDFs to this repository. It is public, and `.gitignore` excludes `*.pdf`.
