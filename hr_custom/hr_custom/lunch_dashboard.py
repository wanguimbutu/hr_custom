import frappe
from frappe.utils import flt, get_first_day, get_last_day, getdate, today


@frappe.whitelist()
def get_lunch_dashboard_stats():
    month_date = getdate(today())
    period_start = get_first_day(month_date)
    period_end = get_last_day(month_date)

    total_active = frappe.db.count("Employee", {"status": "Active"})

    logged_today = frappe.db.count("Lunch Log", {"date": today()})

    month_rows = frappe.db.sql("""
        SELECT employee, SUM(plates) as plates
        FROM `tabLunch Log`
        WHERE date BETWEEN %s AND %s
        GROUP BY employee
    """, (period_start, period_end), as_dict=True)

    employees_with_logs = len(month_rows)
    total_plates_month = sum(flt(r.plates) for r in month_rows)
    projected_deduction_total = total_plates_month * 20

    already_processed = frappe.db.count("Additional Salary", {
        "salary_component": "Lunch Deduction",
        "payroll_date": period_end,
        "docstatus": ["!=", 2]
    })

    return {
        "period": f"{period_start.strftime('%d %b')} - {period_end.strftime('%d %b %Y')}",
        "total_active_employees": total_active,
        "logged_today": logged_today,
        "employees_with_logs_this_month": employees_with_logs,
        "employees_missing_logs": max(total_active - employees_with_logs, 0),
        "total_plates_month": int(total_plates_month),
        "projected_deduction_total": projected_deduction_total,
        "already_processed": already_processed,
        "pending_processing": max(employees_with_logs - already_processed, 0),
    }
