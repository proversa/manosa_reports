// HR Docs: badge on the portal's HR menu showing the logged-in employee's pending required reads.
(function () {
	function loggedIn() {
		var m = document.cookie.match(/(?:^|; )user_id=([^;]*)/);
		return m && decodeURIComponent(m[1]) !== "Guest";
	}

	function badge(count, dot) {
		var b = document.createElement("span");
		b.className = "hr-docs-badge badge badge-danger bg-danger ml-1 ms-1";
		b.style.cssText = "border-radius: 999px; font-size: 0.7em; vertical-align: middle;";
		b.textContent = dot ? "•" : String(count);
		b.title = count + " required HR document(s) to read";
		return b;
	}

	function render(count) {
		if (!count) return;
		document.querySelectorAll('a[href="/hr-docs"], a[href$="//' + location.host + '/hr-docs"]').forEach(function (link) {
			if (link.querySelector(".hr-docs-badge")) return;
			link.appendChild(badge(count));
			// Flag the HR dropdown itself so the badge shows before the menu is opened.
			var dropdown = link.closest(".dropdown");
			var toggle = dropdown && dropdown.querySelector(".dropdown-toggle");
			if (toggle && !toggle.querySelector(".hr-docs-badge")) toggle.appendChild(badge(count));
		});
	}

	function run() {
		if (!loggedIn()) return;
		fetch("/api/method/manosa_reports.hr_docs.api.pending_count", { credentials: "same-origin" })
			.then(function (r) { return r.ok ? r.json() : { message: 0 }; })
			.then(function (r) { render(r.message); })
			.catch(function () {});
	}

	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run);
	else run();
})();
