import frappe
from frappe.utils import flt, get_first_day, get_last_day, getdate

LUNCH_COMPONENT = "Lunch Deduction"
PLATE_RATE = 20


@frappe.whitelist()
def create_lunch_deductions(month_date=None, company=None):
    """
    Sums Lunch Log entries for the month containing month_date and creates
    one Additional Salary (Deduction) per employee for that payroll period.

    Employees with no active Salary Structure Assignment covering the period
    are SKIPPED (no Additional Salary created for them) and reported back
    separately as warnings, rather than being treated as errors or halting
    the batch.
    """
    month_date = getdate(month_date) if month_date else getdate()
    period_start = get_first_day(month_date)
    period_end = get_last_day(month_date)

    if not company:
        company = frappe.db.get_single_value("Global Defaults", "default_company")

    counts = frappe.db.sql("""
        SELECT employee, SUM(plates) as plates
        FROM `tabLunch Log`
        WHERE date BETWEEN %s AND %s
        GROUP BY employee
    """, (period_start, period_end), as_dict=True)

    # Pre-fetch everyone who HAS a valid Salary Structure Assignment for this period,
    # so we're not running a query per employee inside the loop.
    assigned = frappe.get_all(
        "Salary Structure Assignment",
        filters={"from_date": ["<=", period_end], "docstatus": 1},
        fields=["employee"],
        distinct=True
    )
    has_structure = {a.employee for a in assigned}

    created, skipped_existing, no_structure, errors = [], [], [], []

    for row in counts:
        employee = row.employee
        amount = flt(row.plates) * PLATE_RATE

        if employee not in has_structure:
            no_structure.append(employee)
            continue

        if frappe.db.exists("Additional Salary", {
            "employee": employee,
            "salary_component": LUNCH_COMPONENT,
            "payroll_date": period_end,
            "docstatus": ["!=", 2]
        }):
            skipped_existing.append(employee)
            continue

        try:
            doc = frappe.new_doc("Additional Salary")
            doc.employee = employee
            doc.salary_component = LUNCH_COMPONENT
            doc.type = "Deduction"
            doc.amount = amount
            doc.payroll_date = period_end
            doc.company = company or frappe.db.get_value("Employee", employee, "company")
            doc.overwrite_salary_structure_amount = 0
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
        "skipped_existing": len(skipped_existing),
        "no_structure": no_structure,
        "no_structure_count": len(no_structure),
        "errors": errors,
    }

    msg = (
        f"Created: {len(created)}, Already existed: {len(skipped_existing)}, "
        f"Errors: {len(errors)}"
    )
    if no_structure:
        msg += (
            f"<br><br><b>Skipped (no Salary Structure yet):</b> {len(no_structure)} employee(s)<br>"
            + ", ".join(no_structure)
        )
    frappe.msgprint(msg)

    return result
