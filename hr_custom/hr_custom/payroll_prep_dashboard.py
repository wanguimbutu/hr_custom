import frappe
from frappe.utils import get_first_day, get_last_day, getdate, today, date_diff, add_days

@frappe.whitelist()
def get_payroll_prep_data(month_date=None, company=None):
    month_date = getdate(month_date) if month_date else getdate(today())
    period_start = get_first_day(month_date)
    period_end = get_last_day(month_date)

    if not company:
        company = frappe.db.get_single_value("Global Defaults", "default_company")

    active_filters = {"status": "Active"}
    if company:
        active_filters["company"] = company

    active_employees = frappe.get_all("Employee", filters=active_filters, fields=["name", "employee_name"])
    active_ids = [e.name for e in active_employees]
    total_active = len(active_ids)

    # 1. Pending leave applications overlapping this period
    pending_leaves = frappe.get_all(
        "Leave Application",
        filters={
            "status": "Open",
            "employee": ["in", active_ids] if active_ids else ["in", [""]],
            "from_date": ["<=", period_end],
            "to_date": [">=", period_start],
        },
        fields=["employee", "employee_name", "leave_type", "from_date", "to_date"]
    )

    # 2. Employees without an active Salary Structure Assignment covering this period
    assigned = frappe.get_all(
        "Salary Structure Assignment",
        filters={
            "employee": ["in", active_ids] if active_ids else ["in", [""]],
            "from_date": ["<=", period_end],
            "docstatus": 1,
        },
        fields=["employee"]
    )
    assigned_ids = set(a.employee for a in assigned)
    missing_structure = [e for e in active_employees if e.name not in assigned_ids]

    # 3. Employees with zero Attendance records in the period
    attended = frappe.get_all(
        "Attendance",
        filters={
            "employee": ["in", active_ids] if active_ids else ["in", [""]],
            "attendance_date": ["between", [period_start, period_end]],
            "docstatus": 1,
        },
        fields=["employee"]
    )
    attended_ids = set(a.employee for a in attended)
    zero_attendance_ids = [e for e in active_employees if e.name not in attended_ids]

    # 3b. Cross-check: exclude employees fully covered by an approved leave for the whole period
    period_days = date_diff(period_end, period_start) + 1
    approved_leaves = frappe.get_all(
        "Leave Application",
        filters={
            "status": "Approved",
            "employee": ["in", [e.name for e in zero_attendance_ids]] if zero_attendance_ids else ["in", [""]],
            "from_date": ["<=", period_end],
            "to_date": [">=", period_start],
        },
        fields=["employee", "from_date", "to_date"]
    )

    # Build per-employee covered day count (simple overlap sum; assumes no overlapping leave apps per employee)
    covered_days = {}
    for leave in approved_leaves:
        overlap_start = max(getdate(leave.from_date), period_start)
        overlap_end = min(getdate(leave.to_date), period_end)
        days = date_diff(overlap_end, overlap_start) + 1
        covered_days[leave.employee] = covered_days.get(leave.employee, 0) + days

    missing_attendance = [
        e for e in zero_attendance_ids
        if covered_days.get(e.name, 0) < period_days
    ]
    on_full_leave = [
        e for e in zero_attendance_ids
        if covered_days.get(e.name, 0) >= period_days
    ]

    # 4. Outstanding Additional Salary — Draft (not submitted) for this period
    draft_additional_salary = frappe.get_all(
        "Additional Salary",
        filters={
            "employee": ["in", active_ids] if active_ids else ["in", [""]],
            "payroll_date": ["between", [period_start, period_end]],
            "docstatus": 0,
        },
        fields=["employee", "employee_name", "salary_component", "amount"]
    )

    # 5. Lunch deduction specifically
    lunch_processed = frappe.db.count("Additional Salary", {
        "salary_component": "Lunch Deduction",
        "payroll_date": period_end,
        "docstatus": 1
    })
    lunch_logged_employees = frappe.db.sql("""
        SELECT COUNT(DISTINCT employee) as cnt FROM `tabLunch Log`
        WHERE date BETWEEN %s AND %s
    """, (period_start, period_end), as_dict=True)[0].cnt

    return {
        "period": f"{period_start.strftime('%d %b')} - {period_end.strftime('%d %b %Y')}",
        "total_active_employees": total_active,
        "pending_leaves": pending_leaves,
        "pending_leaves_count": len(pending_leaves),
        "missing_structure": missing_structure,
        "missing_structure_count": len(missing_structure),
        "missing_attendance": missing_attendance,
        "missing_attendance_count": len(missing_attendance),
        "on_full_leave_count": len(on_full_leave),
        "draft_additional_salary": draft_additional_salary,
        "draft_additional_salary_count": len(draft_additional_salary),
        "lunch_logged_employees": lunch_logged_employees,
        "lunch_processed": lunch_processed,
    }
