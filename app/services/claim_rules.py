
from datetime import datetime
import math


def evaluate_claim(bill_details: dict) -> dict:
    claim_limit = 5000

    # 1. Validate the amount.
    raw_amount = bill_details.get("total_amount")

    try:
        if raw_amount is None:
            raise ValueError("Amount is missing")

        amount = float(
            str(raw_amount)
            .replace("₹", "")
            .replace(",", "")
            .strip()
        )

        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("Amount is invalid")

    except (ValueError, TypeError):
        return {
            "status": "Manual Review",
            "amount": None,
            "limit": claim_limit,
            "reason": "Bill amount is missing or invalid."
        }

    # 2. Validate the bill number.
    bill_number = bill_details.get("bill_number")

    if not bill_number or not str(bill_number).strip():
        return {
            "status": "Manual Review",
            "amount": amount,
            "limit": claim_limit,
            "reason": "Bill number is missing. Please verify the receipt."
        }

    # 3. Validate the bill date.
    raw_date = bill_details.get("bill_date")

    if not raw_date or not str(raw_date).strip():
        return {
            "status": "Manual Review",
            "amount": amount,
            "limit": claim_limit,
            "reason": "Bill date is missing. Please verify the receipt."
        }

    # Accept the date formats supported by this demo.
    date_text = str(raw_date).strip()
    valid_date = False

    date_formats = (
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d %b %Y",
    "%d-%b-%Y",
    "%d %B %Y",
    "%d-%B-%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    )

    for date_format in date_formats:
            try:
                datetime.strptime(date_text, date_format)
                valid_date = True
                break
            except ValueError:
                continue

    if not valid_date:
        return {
            "status": "Manual Review",
            "amount": amount,
            "limit": claim_limit,
            "reason": "Bill date is invalid or unrecognized."
        }

    # 4. Apply the illustrative per-bill limit.
    if amount > claim_limit:
        return {
            "status": "Rejected",
            "amount": amount,
            "limit": claim_limit,
            "reason": "Claim amount exceeds the maximum limit of ₹5,000."
        }

    # 5. Approve only when all checks pass.
    return {
        "status": "Approved",
        "amount": amount,
        "limit": claim_limit,
        "reason": "Required bill details are present and the amount is within the demo limit."
    }

def reevaluate_claim(
    bill_details: dict,
    corrections: dict
) -> dict:
    """
    Apply employee-verified corrections and run claim rules again.
    Only explicitly supported bill fields can be changed.
    """

    allowed_fields = {
        "bill_number",
        "bill_date",
        "total_amount"
    }

    updated_details = bill_details.copy()

    for field, value in corrections.items():
        if field not in allowed_fields:
            return {
                "status": "Manual Review",
                "reason": f"Correction field '{field}' is not allowed."
            }

        if value is None or not str(value).strip():
            return {
                "status": "Manual Review",
                "reason": f"The corrected value for '{field}' cannot be empty."
            }

        updated_details[field] = value

    # Always use the existing Python validation rules.
    result = evaluate_claim(updated_details)

    return {
        **result,
        "bill_details": updated_details
    }
