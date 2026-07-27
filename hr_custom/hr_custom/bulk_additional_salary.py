import frappe
from frappe.utils import flt, get_last_day, getdate, today


@frappe.whitelist()
def create_bulk_additional_salary(salary_component, salary_type, payroll_month=None,
                                    mode="equal_split", total_amount=None,
                                    exclude_employees=None, entries=None,
                                    remarks=None, company=None):
    """
    Generic bulk Additional Salary creator — works for any Earning or Deduction.

    mode="equal_split": splits total_amount evenly across active employees
        with a Salary Structure, minus exclude_employees. Remainder from
        rounding goes to the first employee.

    mode="custom": entries is a list of {"employee": ..., "amount": ...}
        supplied directly by HR — for cases where amounts differ per person.
    """
    payroll_month = getdate(payroll_month) if payroll_month else getdate(today())
    period_end = get_last_day(payroll_month)
    exclude_employees = frappe.parse_json(exclude_employees) if isinstance(exclude_employees, str) else (exclude_employees or [])
    entries = frappe.parse_json(entries) if isinstance(entries, str) else entries

    if not company:
        company = frappe.db.get_single_value("Global Defaults", "default_company")

    if not frappe.db.exists("Salary Component", salary_component):
        frappe.throw(f"Salary Component '{salary_component}' does not exist. Create it first.")

    if salary_type not in ("Earning", "Deduction"):
        frappe.throw("salary_type must be 'Earning' or 'Deduction'")

    final_entries = []

    if mode == "equal_split":
        total_amount = flt(total_amount)
        if total_amount <= 0:
            frappe.throw("Total amount must be greater than zero")

        assigned = frappe.get_all(
            "Salary Structure Assignment",
            filters={"from_date": ["<=", period_end], "docstatus": 1},
            fields=["employee"], distinct=True
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

        for i, employee in enumerate(active_ids):
            amount = base_share + (remainder if i == 0 else 0)
            final_entries.append({"employee": employee, "amount": amount})

    elif mode == "custom":
        if not entries:
            frappe.throw("No entries provided")
        for e in entries:
            employee = e.get("employee")
            amount = flt(e.get("amount"))
            if not employee or amount <= 0:
                continue
            if not frappe.db.exists("Employee", employee):
                frappe.throw(f"Employee '{employee}' not found")
            final_entries.append({"employee": employee, "amount": amount})

    else:
        frappe.throw("mode must be 'equal_split' or 'custom'")

    created, skipped, errors = [], [], []

    for entry in final_entries:
        employee = entry["employee"]
        amount = entry["amount"]

        if frappe.db.exists("Additional Salary", {
            "employee": employee,
            "salary_component": salary_component,
            "payroll_date": period_end,
            "docstatus": ["!=", 2]
        }):
            skipped.append(employee)
            continue

        try:
            doc = frappe.new_doc("Additional Salary")
            doc.employee = employee
            doc.salary_component = salary_component
            doc.type = salary_type
            doc.amount = amount
            doc.payroll_date = period_end
            doc.company = company or frappe.db.get_value("Employee", employee, "company")
            doc.remarks = remarks or f"Bulk {salary_type.lower()} - {salary_component}"
            doc.overwrite_salary_structure_amount = 0
            doc.insert(ignore_permissions=True)
            doc.submit()
            created.append(employee)
        except Exception as e:
            errors.append((employee, str(e)))

    frappe.db.commit()

    return {
        "total_entries": len(final_entries),
        "created": len(created),
        "skipped_existing": len(skipped),
        "errors": errors,
        "period_end": str(period_end),
    }
