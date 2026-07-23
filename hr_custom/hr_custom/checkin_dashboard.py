import frappe
from frappe.utils import today, now_datetime, get_datetime

@frappe.whitelist()
def get_checkin_dashboard_data():
    checkins_today = frappe.get_all(
        "Employee Checkin",
        filters={"time": ["between", [f"{today()} 00:00:00", f"{today()} 23:59:59"]]},
        fields=["employee", "employee_name", "time", "log_type", "device_id"],
        order_by="time desc"
    )

    total_today = len(checkins_today)
    ins_today = len([c for c in checkins_today if c.log_type == "IN"])
    outs_today = len([c for c in checkins_today if c.log_type == "OUT"])
    blank_log_type_today = len([c for c in checkins_today if not c.log_type])

    unique_employees_today = len(set(c.employee for c in checkins_today))
    total_active = frappe.db.count("Employee", {"status": "Active"})


    recent = frappe.get_all(
        "Employee Checkin",
        fields=["employee", "employee_name", "time", "log_type", "device_id"],
        order_by="time desc",
        limit=20
    )

    return {
        "date": today(),
        "total_today": total_today,
        "ins_today": ins_today,
        "outs_today": outs_today,
        "blank_log_type_today": blank_log_type_today,
        "unique_employees_today": unique_employees_today,
        "total_active_employees": total_active,
        "recent": recent
    }
