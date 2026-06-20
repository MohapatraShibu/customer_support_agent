import json
from pathlib import Path
from datetime import datetime, date

DATA_DIR = Path(__file__).parent / "data"

def _load_crm():
    with open(DATA_DIR / "crm.json") as f:
        return json.load(f)

def _load_policy():
    with open(DATA_DIR / "policy.json") as f:
        return json.load(f)

def _days_since(date_str: str) -> int:
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (date.today() - d).days

def lookup_customer(identifier: str) -> dict:
    """Look up a customer by email, customer_id, or order_id."""
    customers = _load_crm()
    identifier = identifier.strip().lower()
    for c in customers:
        if (c["customer_id"].lower() == identifier or
                c["email"].lower() == identifier):
            return {"found": True, "customer": c}
        for o in c["orders"]:
            if o["order_id"].lower() == identifier:
                return {"found": True, "customer": c}
    return {"found": False, "customer": None}

def get_order_details(order_id: str, customer_id: str) -> dict:
    """Get details for a specific order belonging to a customer."""
    customers = _load_crm()
    customer = next((c for c in customers if c["customer_id"] == customer_id), None)
    if not customer:
        return {"found": False, "error": "Customer not found"}
    order = next((o for o in customer["orders"] if o["order_id"] == order_id), None)
    if not order:
        return {"found": False, "error": f"Order {order_id} not found for this customer"}
    return {"found": True, "order": order}

def check_refund_policy(customer_id: str, order_id: str) -> dict:
    """
    Run all policy rules against a customer's order.
    Returns a detailed eligibility report with pass/fail for each rule.
    """
    customers = _load_crm()
    policy = _load_policy()

    customer = next((c for c in customers if c["customer_id"] == customer_id), None)
    if not customer:
        return {"eligible": False, "reason": "Customer not found", "checks": []}

    order = next((o for o in customer["orders"] if o["order_id"] == order_id), None)
    if not order:
        return {"eligible": False, "reason": f"Order {order_id} not found", "checks": []}

    checks = []
    all_pass = True

    # r1: return window
    if order.get("delivery_date"):
        days = _days_since(order["delivery_date"])
        window = policy["refund_window_days"]
        passed = days <= window
        checks.append({
            "rule": "R1 - Return Window",
            "passed": passed,
            "detail": f"Delivered {days} days ago. Window is {window} days."
        })
        if not passed:
            all_pass = False
    else:
        checks.append({"rule": "R1 - Return Window", "passed": False, "detail": "No delivery date recorded."})
        all_pass = False

    # r2: order status
    status = order.get("status", "")
    passed = status in policy["eligible_statuses"]
    checks.append({
        "rule": "R2 - Order Status",
        "passed": passed,
        "detail": f"Order status is '{status}'. Must be 'delivered'."
    })
    if not passed:
        all_pass = False

    # r3: refund abuse
    now = date.today()
    recent_refunds = [
        r for r in customer.get("refund_history", [])
        if (now - datetime.strptime(r["date"], "%Y-%m-%d").date()).days <= 365
    ]
    count = len(recent_refunds)
    max_allowed = policy["max_refunds_per_year"]
    passed = count < max_allowed
    checks.append({
        "rule": "R3 - Refund Abuse Prevention",
        "passed": passed,
        "detail": f"Customer has {count} refund(s) in the last 12 months. Limit is {max_allowed}."
    })
    if not passed:
        all_pass = False

    # r4: flagged account
    standing = customer.get("account_standing", "good")
    passed = standing != "flagged"
    checks.append({
        "rule": "R4 - Account Standing",
        "passed": passed,
        "detail": f"Account standing is '{standing}'."
    })
    if not passed:
        all_pass = False

    return {
        "eligible": all_pass,
        "customer_name": customer["name"],
        "order_id": order_id,
        "product": order["product"],
        "amount": order["amount"],
        "checks": checks
    }

def process_refund(customer_id: str, order_id: str, reason: str) -> dict:
    """
    Finalize and record a refund decision after all policy checks pass.
    Returns approval or denial with a clear explanation.
    """
    policy_result = check_refund_policy(customer_id, order_id)
    if not policy_result["eligible"]:
        failed = [c for c in policy_result["checks"] if not c["passed"]]
        return {
            "approved": False,
            "order_id": order_id,
            "reason": "Refund denied due to policy violations.",
            "violations": [c["detail"] for c in failed]
        }

    policy = _load_policy()
    reason_lower = reason.lower().replace(" ", "_")
    auto_deny = any(r in reason_lower for r in policy["auto_deny_reasons"])
    if auto_deny:
        return {
            "approved": False,
            "order_id": order_id,
            "reason": f"Refund denied: '{reason}' is not an accepted refund reason per policy."
        }

    return {
        "approved": True,
        "order_id": order_id,
        "amount": policy_result["amount"],
        "product": policy_result["product"],
        "reason": f"Refund of ${policy_result['amount']:.2f} approved for order {order_id}.",
        "next_steps": "Refund will be processed within 3-5 business days to your original payment method."
    }

def get_policy_summary() -> dict:
    """Return a human-readable summary of the refund policy."""
    policy = _load_policy()
    return {
        "return_window": f"{policy['refund_window_days']} days from delivery",
        "max_refunds_per_year": policy["max_refunds_per_year"],
        "eligible_order_statuses": policy["eligible_statuses"],
        "non_refundable_items": policy["non_refundable_categories"],
        "approved_reasons": policy["approved_reasons"],
        "discretionary_reasons": policy["discretionary_reasons"],
        "auto_deny_reasons": policy["auto_deny_reasons"],
        "flagged_accounts": "Automatically denied"
    }
