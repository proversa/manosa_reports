// HR Docs: red badge on "HR > HR Docs" in the Desk sidebar with the logged-in user's unacknowledged required reads.
// Served by Frappe at /hr_docs_sidebar.js and loaded on every Desk page through app_include_js in hooks.py,
// so it needs no asset build.
(function () {
	var count = 0;
	var REFRESH_MS = 5 * 60 * 1000;

	function badge(cls) {
		var b = document.createElement("span");
		b.className = "hr-docs-badge " + cls;
		b.textContent = count > 99 ? "99+" : String(count);
		b.title = count + " required HR document(s) not yet acknowledged";
		b.style.cssText =
			"display:inline-block;margin-left:6px;min-width:18px;height:18px;padding:0 5px;border-radius:9px;" +
			"background:var(--red-500,#e03636);color:#fff;font-size:11px;font-weight:600;" +
			"line-height:18px;text-align:center;flex-shrink:0;";
		return b;
	}

	function itemRow(name) {
		var container = document.querySelector('.sidebar-item-container[item-name="' + name + '"]');
		if (!container) return null;
		return container.querySelector(":scope > .standard-sidebar-item .item-anchor, :scope > .standard-sidebar-item, :scope > a");
	}

	function paint() {
		document.querySelectorAll(".hr-docs-badge").forEach(function (b) {
			if (!count || b.textContent !== (count > 99 ? "99+" : String(count))) b.remove();
		});
		if (!count) return;
		var docs = itemRow("HR Docs");
		if (docs && !docs.querySelector(".hr-docs-badge")) {
			var label = docs.querySelector(".sidebar-item-label") || docs;
			label.appendChild(badge("hr-docs-badge-item"));
		}
		// Also flag the HR parent, so the count shows while the HR group is collapsed.
		var hr = itemRow("HR");
		if (hr && !hr.querySelector(".hr-docs-badge")) {
			var hrLabel = hr.querySelector(".sidebar-item-label") || hr;
			hrLabel.appendChild(badge("hr-docs-badge-parent"));
		}
	}

	function refresh() {
		frappe.call({
			method: "manosa_reports.hr_docs.api.pending_count",
			type: "GET",
			callback: function (r) {
				count = cint(r.message);
				paint();
			},
			error: function () {},
		});
	}

	function start() {
		if (!window.frappe || !frappe.session || frappe.session.user === "Guest") return;
		refresh();
		setInterval(refresh, REFRESH_MS);
		if (frappe.router && frappe.router.on) frappe.router.on("change", refresh);
		// The sidebar is re-rendered when switching workspaces; put the badge back when that happens.
		var pending = null;
		new MutationObserver(function () {
			if (pending) return;
			pending = setTimeout(function () {
				pending = null;
				paint();
			}, 200);
		}).observe(document.body, { childList: true, subtree: true });
	}

	if (window.frappe && frappe.boot && frappe.boot.user) start();
	else $(document).on("app_ready", start);
})();
