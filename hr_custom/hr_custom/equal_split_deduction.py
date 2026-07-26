import frappe
from frappe.utils import flt, get_last_day, getdate, today


@frappe.whitelist()
def create_equal_split_deduction(total_amount, salary_component, payroll_month=None,
                                   exclude_employees=None, remarks=None, company=None):
    """
    Splits total_amount equally across active employees with a submitted
    Salary Structure Assignment, excluding any employees in exclude_employees.
    Any rounding remainder is added to the first employee's share so the
    total always reconciles exactly.
    """
    total_amount = flt(total_amount)
    payroll_month = getdate(payroll_month) if payroll_month else getdate(today())
    period_end = get_last_day(payroll_month)
    exclude_employees = frappe.parse_json(exclude_employees) if isinstance(exclude_employees, str) else (exclude_employees or [])

    if not company:
        company = frappe.db.get_single_value("Global Defaults", "default_company")

    if not frappe.db.exists("Salary Component", salary_component):
        frappe.throw(f"Salary Component '{salary_component}' does not exist. Create it first.")

    assigned = frappe.get_all(
        "Salary Structure Assignment",
        filters={"from_date": ["<=", period_end], "docstatus": 1},
        fields=["employee"],
        distinct=True
    )
    employee_ids = list({a.employee for a in assigned})

    active_ids = frappe.get_all(
        "Employee", filters={"status": "Active", "name": ["in", employee_ids]}, pluck="name"
    )
    active_ids = [e for e in active_ids if e not in exclude_employees]

    count = len(active_ids)
    if count == 0:
        frappe.throw("No eligible employees found after exclusions.")

    base_share = int(total_amount // count)
    remainder = total_amount - (base_share * count)

    created, errors = [], []

    for i, employee in enumerate(active_ids):
        amount = base_share + (remainder if i == 0 else 0)

        if frappe.db.exists("Additional Salary", {
            "employee": employee,
            "salary_component": salary_component,
            "payroll_date": period_end,
            "docstatus": ["!=", 2]
        }):
            continue

        try:
            doc = frappe.new_doc("Additional Salary")
            doc.employee = employee
            doc.salary_component = salary_component
            doc.type = "Deduction"
            doc.amount = amount
            doc.payroll_date = period_end
            doc.company = company or frappe.db.get_value("Employee", employee, "company")
            doc.remarks = remarks or f"Equal split deduction - {salary_component}"
            doc.insert(ignore_permissions=True)
            doc.submit()
            created.append(employee)
        except Exception as e:
            errors.append((employee, str(e)))

    frappe.db.commit()

    return {
        "count": count,
        "base_share": base_share,
        "remainder": remainder,
        "created": len(created),
        "errors": errors,
        "period_end": str(period_end),
    }
