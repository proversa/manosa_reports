// HR Docs: badges on "HR > HR Docs" in the Desk sidebar for the logged-in user.
// Red: required reads not yet acknowledged. Blue: comments posted since the user last opened those posts.
// Served by Frappe at /hr_docs_sidebar.js and loaded on every Desk page through app_include_js in hooks.py,
// so it needs no asset build.
(function () {
	var counts = { required: 0, comments: 0 };
	var REFRESH_MS = 5 * 60 * 1000;
	var KINDS = [
		{ key: "required", color: "var(--red-500,#e03636)", title: " required HR document(s) not yet acknowledged" },
		{ key: "comments", color: "var(--blue-500,#2490ef)", title: " new comment(s) on HR Docs posts" },
	];

	function text(n) {
		return n > 99 ? "99+" : String(n);
	}

	function badge(kind, n) {
		var b = document.createElement("span");
		b.className = "hr-docs-badge hr-docs-badge-" + kind.key;
		b.textContent = (kind.key === "comments" ? "💬 " : "") + text(n);
		b.title = n + kind.title;
		b.style.cssText =
			"display:inline-block;margin-left:6px;min-width:18px;height:18px;padding:0 5px;border-radius:9px;" +
			"background:" + kind.color + ";color:#fff;font-size:11px;font-weight:600;" +
			"line-height:18px;text-align:center;flex-shrink:0;";
		return b;
	}

	function itemRow(name) {
		var container = document.querySelector('.sidebar-item-container[item-name="' + name + '"]');
		if (!container) return null;
		return container.querySelector(":scope > .standard-sidebar-item .item-anchor, :scope > .standard-sidebar-item, :scope > a");
	}

	function paintRow(row) {
		if (!row) return;
		var label = row.querySelector(".sidebar-item-label") || row;
		KINDS.forEach(function (kind) {
			var n = counts[kind.key];
			var existing = label.querySelector(".hr-docs-badge-" + kind.key);
			if (existing && (!n || existing.title !== n + kind.title)) {
				existing.remove();
				existing = null;
			}
			if (n && !existing) label.appendChild(badge(kind, n));
		});
	}

	function paint() {
		paintRow(itemRow("HR Docs"));
		// Also flag the HR parent, so the counts show while the HR group is collapsed.
		paintRow(itemRow("HR"));
	}

	function refresh() {
		frappe.call({
			method: "manosa_reports.hr_docs.api.badge_counts",
			type: "GET",
			callback: function (r) {
				var m = r.message || {};
				counts = { required: cint(m.required), comments: cint(m.comments) };
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
		// The sidebar is re-rendered when switching workspaces; put the badges back when that happens.
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
