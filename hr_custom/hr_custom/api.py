import frappe
from frappe.utils import today

@frappe.whitelist()
def get_kiosk_data():
    employees = frappe.get_all("Employee", filters={"status": "Active"},
        fields=["name", "employee_name"], order_by="employee_name")
    ticked_today = set(frappe.get_all("Lunch Log", filters={"date": today()}, pluck="employee"))
    for emp in employees:
        emp["ticked"] = emp["name"] in ticked_today
    return employees

@frappe.whitelist()
def toggle_lunch(employee):
    existing = frappe.db.exists("Lunch Log", {"employee": employee, "date": today()})
    if existing:
        frappe.delete_doc("Lunch Log", existing, ignore_permissions=True)
        return {"ticked": False}
    doc = frappe.new_doc("Lunch Log")
    doc.employee = employee
    doc.date = today()
    doc.insert(ignore_permissions=True)
    return {"ticked": True}
