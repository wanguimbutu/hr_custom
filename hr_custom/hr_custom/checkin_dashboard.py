import frappe
from frappe.utils import today, get_datetime

@frappe.whitelist()
def get_checkin_dashboard_data(from_date=None, to_date=None):
    from_date = from_date or today()
    to_date = to_date or today()

    start = f"{from_date} 00:00:00"
    end = f"{to_date} 23:59:59"

    checkins = frappe.get_all(
        "Employee Checkin",
        filters={"time": ["between", [start, end]]},
        fields=["employee", "employee_name", "time", "log_type", "device_id"],
        order_by="time desc"
    )

    total = len(checkins)
    ins = len([c for c in checkins if c.log_type == "IN"])
    outs = len([c for c in checkins if c.log_type == "OUT"])
    blank_log_type = len([c for c in checkins if not c.log_type])

    unique_employees = len(set(c.employee for c in checkins))
    total_active = frappe.db.count("Employee", {"status": "Active"})

    # cap the feed so wide ranges don't blow up the page
    recent = checkins[:100]

    return {
        "from_date": str(from_date),
        "to_date": str(to_date),
        "total": total,
        "ins": ins,
        "outs": outs,
        "blank_log_type": blank_log_type,
        "unique_employees": unique_employees,
        "total_active_employees": total_active,
        "recent": recent,
        "truncated": total > 100
    }
