// Copyright (c) 2026, wangui and contributors
// For license information, please see license.txt

frappe.ui.form.on("Deduction Upload", {
	onload(frm) {
		if (frm.is_new()) {
			if (!frm.doc.company) {
				frm.set_value("company", frappe.defaults.get_user_default("Company"));
			}
			if (!frm.doc.payroll_month) {
				frm.set_value("payroll_month", frappe.datetime.get_today());
			}
			if (!(frm.doc.components || []).length) {
				frappe.call("hr_custom.hr_custom.doctype.deduction_upload.deduction_upload.get_default_components")
					.then((r) => {
						(r.message || []).forEach((c) => frm.add_child("components", { salary_component: c }));
						frm.refresh_field("components");
					});
			}
		}
	},

	setup(frm) {
		frm.set_query("salary_component", "components", () => ({ filters: { type: "Deduction", disabled: 0 } }));
	},

	refresh(frm) {
		if (frm.doc.docstatus !== 0) return;

		frm.add_custom_button(__("Download Template"), () => {
			const components = (frm.doc.components || []).map((c) => c.salary_component);
			if (!frm.doc.company || !components.length) {
				frappe.msgprint(__("Select the Company and at least one Deduction Column first."));
				return;
			}
			open_url_post("/api/method/hr_custom.hr_custom.doctype.deduction_upload.deduction_upload.download_template", {
				company: frm.doc.company,
				components: components,
				payroll_month: frm.doc.payroll_month || "",
			});
		});

		if (frm.doc.upload_file) {
			frm.add_custom_button(__("Load File"), () => load_file(frm));
		}
	},

	upload_file(frm) {
		if (frm.doc.upload_file) load_file(frm);
	},
});

function load_file(frm) {
	const saved = frm.is_new() || frm.is_dirty() ? frm.save() : Promise.resolve();
	saved.then(() =>
		frm.call({ doc: frm.doc, method: "load_from_file", freeze: true, freeze_message: __("Reading file...") })
	).then(() => frm.refresh());
}
