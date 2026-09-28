"""
Keep salary slips in step with Additional Salary created after Payroll Entry has run.

Draft slips: re-saved so HRMS pulls in new Additional Salary; rows for cancelled
Additional Salary are removed first (HRMS does not drop them on its own).
Submitted slips: cannot change, so the user is warned.

Bulk creators (Deduction Upload, recurring deductions) wrap their work in
`deferred_slip_refresh()` so each slip is re-saved once instead of once per row.
"""

from contextlib import contextmanager

import frappe
from frappe.utils import getdate


def on_additional_salary_change(doc, method=None):
	if frappe.flags.pending_slip_refresh is not None:
		frappe.flags.pending_slip_refresh.add((doc.employee, getdate(doc.payroll_date)))
		return
	refresh_salary_slips([(doc.employee, getdate(doc.payroll_date))])


@contextmanager
def deferred_slip_refresh():
	frappe.flags.pending_slip_refresh = set()
	try:
		yield
		pending = frappe.flags.pending_slip_refresh
	finally:
		frappe.flags.pending_slip_refresh = None
	refresh_salary_slips(pending)


def get_salary_slips(employee, payroll_date, docstatus):
	return frappe.get_all(
		"Salary Slip",
		filters={
			"employee": employee,
			"start_date": ["<=", payroll_date],
			"end_date": [">=", payroll_date],
			"docstatus": docstatus,
		},
		pluck="name",
	)


def refresh_salary_slips(employee_dates):
	"""Re-save draft slips covering each (employee, payroll_date); warn about submitted ones."""
	refreshed, submitted, failed = [], [], []

	for employee, payroll_date in sorted(set(employee_dates)):
		submitted += get_salary_slips(employee, payroll_date, 1)

		for name in get_salary_slips(employee, payroll_date, 0):
			try:
				slip = frappe.get_doc("Salary Slip", name)
				remove_cancelled_additional_salary(slip)
				slip.save(ignore_permissions=True)
				refreshed.append(name)
			except Exception:
				frappe.log_error(f"Could not refresh Salary Slip {name}", "Salary Slip Sync")
				failed.append(name)

	if refreshed:
		frappe.msgprint(f"Updated draft salary slips: {', '.join(refreshed)}", alert=True)
	if submitted:
		frappe.msgprint(
			f"These salary slips are already submitted and do NOT include this change: {', '.join(submitted)}. "
			"Cancel and amend the slip, or record the deduction in next month's payroll.",
			title="Salary Slip Already Submitted",
			indicator="orange",
		)
	if failed:
		frappe.msgprint(
			f"Could not update draft salary slips: {', '.join(failed)}. Open and save them manually (see Error Log).",
			indicator="red",
		)
	return {"refreshed": refreshed, "submitted": submitted, "failed": failed}


def remove_cancelled_additional_salary(slip):
	linked = {d.additional_salary for d in slip.earnings + slip.deductions if d.additional_salary}
	if not linked:
		return
	live = set(frappe.get_all(
		"Additional Salary", filters={"name": ["in", list(linked)], "docstatus": 1}, pluck="name"
	))
	for table in ("earnings", "deductions"):
		slip.set(table, [d for d in slip.get(table) if not d.additional_salary or d.additional_salary in live])
