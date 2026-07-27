import frappe
from frappe.utils import flt, get_last_day, getdate, today


@frappe.whitelist()
def create_recurring_deductions(month_date=None, company=None):
    month_date = getdate(month_date) if month_date else getdate(today())
    period_end = get_last_day(month_date)

    if not company:
        company = frappe.db.get_single_value("Global Defaults", "default_company")

    results = {"loans": _process_loans(period_end, company), "sacco": _process_sacco(period_end, company)}
    frappe.db.commit()
    frappe.msgprint(
        f"Loans: {results['loans']['created']} created, {results['loans']['closed']} closed. "
        f"SACCO: {results['sacco']['created']} created."
    )
    return results


def _process_loans(period_end, company):
    created, closed, skipped, errors = [], [], [], []

    loans = frappe.get_all(
        "Staff Loan",
        filters={"status": "Active", "start_date": ["<=", period_end]},
        fields=["name", "employee", "monthly_installment", "balance"]
    )

    for loan in loans:
        if frappe.db.exists("Additional Salary", {
            "employee": loan.employee,
            "salary_component": "Staff Loan Repayment",
            "payroll_date": period_end,
            "reference_doctype": "Staff Loan",
            "reference_name": loan.name,
            "docstatus": ["!=", 2]
        }):
            skipped.append(loan.employee)
            continue

        amount = min(flt(loan.monthly_installment), flt(loan.balance))
        if amount <= 0:
            continue

        try:
            doc = frappe.new_doc("Additional Salary")
            doc.employee = loan.employee
            doc.salary_component = "Staff Loan Repayment"
            doc.type = "Deduction"
            doc.amount = amount
            doc.payroll_date = period_end
            doc.company = company or frappe.db.get_value("Employee", loan.employee, "company")
            doc.reference_doctype = "Staff Loan"
            doc.reference_name = loan.name
            doc.overwrite_salary_structure_amount = 0
            doc.insert(ignore_permissions=True)
            doc.submit()
            created.append(loan.employee)

            new_balance = flt(loan.balance) - amount
            loan_doc = frappe.get_doc("Staff Loan", loan.name)
            loan_doc.balance = new_balance
            if new_balance <= 0:
                loan_doc.status = "Closed"
                closed.append(loan.employee)
            loan_doc.save(ignore_permissions=True)

        except Exception as e:
            frappe.log_error(f"Loan deduction failed for {loan.employee}: {e}", "Recurring Deductions")
            errors.append((loan.employee, str(e)))

    return {"created": len(created), "closed": len(closed), "skipped": len(skipped), "errors": errors}


def _process_sacco(period_end, company):
    created, skipped, errors = [], [], []

    members = frappe.get_all(
        "SACCO Membership",
        filters={"active": 1, "start_date": ["<=", period_end]},
        fields=["employee", "monthly_contribution"]
    )

    for m in members:
        if frappe.db.exists("Additional Salary", {
            "employee": m.employee,
            "salary_component": "SACCO Contribution",
            "payroll_date": period_end,
            "docstatus": ["!=", 2]
        }):
            skipped.append(m.employee)
            continue

        if flt(m.monthly_contribution) <= 0:
            continue

        try:
            doc = frappe.new_doc("Additional Salary")
            doc.employee = m.employee
            doc.salary_component = "SACCO Contribution"
            doc.type = "Deduction"
            doc.amount = m.monthly_contribution
            doc.payroll_date = period_end
            doc.company = company or frappe.db.get_value("Employee", m.employee, "company")
            doc.overwrite_salary_structure_amount = 0
            doc.insert(ignore_permissions=True)
            doc.submit()
            created.append(m.employee)
        except Exception as e:
            frappe.log_error(f"SACCO deduction failed for {m.employee}: {e}", "Recurring Deductions")
            errors.append((m.employee, str(e)))

    return {"created": len(created), "skipped": len(skipped), "errors": errors}
