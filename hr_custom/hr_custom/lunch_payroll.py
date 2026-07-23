import frappe
from frappe.utils import flt, get_first_day, get_last_day, getdate

LUNCH_COMPONENT = "Lunch Deduction"   # must exist as a Salary Component (Deduction)
PLATE_RATE = 20

@frappe.whitelist()
def create_lunch_deductions(month_date=None, company=None):
    """
    Sums Lunch Log entries for the month containing month_date and creates
    one Additional Salary (Deduction) per employee for that payroll period.
    month_date: any date within the target month (defaults to today).
    """
    month_date = getdate(month_date) if month_date else getdate()
    period_start = get_first_day(month_date)
    period_end = get_last_day(month_date)

    if not company:
        company = frappe.db.get_single_value("Global Defaults", "default_company")

    counts = frappe.db.sql("""
        SELECT employee, COUNT(*) as plates
        FROM `tabLunch Log`
        WHERE date BETWEEN %s AND %s
        GROUP BY employee
    """, (period_start, period_end), as_dict=True)

    created, skipped, errors = [], [], []

    for row in counts:
        employee = row.employee
        amount = flt(row.plates) * PLATE_RATE

        if frappe.db.exists("Additional Salary", {
            "employee": employee,
            "salary_component": LUNCH_COMPONENT,
            "payroll_date": period_end,
            "docstatus": ["!=", 2]
        }):
            skipped.append(employee)
            continue

        try:
            doc = frappe.new_doc("Additional Salary")
            doc.employee = employee
            doc.salary_component = LUNCH_COMPONENT
            doc.type = "Deduction"
            doc.amount = amount
            doc.payroll_date = period_end
            doc.company = company or frappe.db.get_value("Employee", employee, "company")
            doc.insert(ignore_permissions=True)
            doc.submit()
            created.append(employee)
        except Exception as e:
            frappe.log_error(f"Lunch deduction failed for {employee}: {e}", "Lunch Payroll Sync")
            errors.append((employee, str(e)))

    frappe.db.commit()

    result = {
        "period": f"{period_start} to {period_end}",
        "created": len(created),
        "skipped_existing": len(skipped),
        "errors": errors,
    }
    frappe.msgprint(
        f"Lunch deductions: {len(created)} created, {len(skipped)} already existed, {len(errors)} failed."
    )
    return result

def scheduled_lunch_deduction_run():
    """Wrapper for cron — logs result instead of relying on msgprint."""
    result = create_lunch_deductions()
    frappe.logger("lunch_payroll").info(
        f"Scheduled lunch deduction run: {result}"
    )
