import re


DATE_PATTERN = (
    r"\b(?:"
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{1,2}[- ](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[- ]\d{2,4}"
    r")\b"
)

BILL_LABEL = re.compile(
    r"\b(?:invoice\s*cum\s*receipt\s*no\.?"
    r"|bill\s*(?:no\.?|number)"
    r"|receipt\s*(?:no\.?|number)"
    r"|invoice\s*(?:no\.?|number)"
    r"|inv\.?\s*no\.?"
    r"|tax\s*invoice"
    r"|cash\s*memo\s*(?:no\.?)?)\b",
    re.IGNORECASE,
)

AMOUNT_PATTERN = re.compile(
    r"(?<![A-Z0-9])(?:INR\s*|RS\.?\s*|₹\s*)?"
    r"(\d[\d,]{0,9}(?:\.\d{1,3})?)",
    re.IGNORECASE,
)


def parse_amount(value: str) -> float | None:
    """Convert common OCR amount formats to a number."""
    value = value.strip().replace("₹", "").replace("Rs.", "")
    value = re.sub(r"^INR\s*", "", value, flags=re.IGNORECASE)
    value = value.replace(" ", "")

    # OCR may read 511.46 as 511,46
    if "," in value and "." not in value:
        if re.search(r",\d{2,3}$", value):
            value = value.replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(",", "")

    try:
        return float(value)
    except ValueError:
        return None



def detect_bill_type(text: str) -> str:
    text_lower = text.lower()

    # Fuel bills
    if any(keyword in text_lower for keyword in [
        "indianoil",
        "bharat petroleum",
        "hp petrol",
        "petroleum",
        "rate (rs/l)",
        "volume(l)",
        "rate/litre",
    ]):
        return "fuel"

    # Broadband / internet bills
    if any(keyword in text_lower for keyword in [
        "tata play fiber",
        "broadband",
        "internet service",
        "fiber broadband",
    ]):
        return "broadband"

    # Medical laboratory bills
    if any(keyword in text_lower for keyword in [
        "pathlabs",
        "pathology",
        "diagnostic",
        "lab test",
        "laboratory",
        "test report",
    ]):
        return "medical_test"

    # Pharmacy / medicine bills
    if any(keyword in text_lower for keyword in [
        "medical store",
        "medical & general stores",
        "chemist",
        "pharmacy",
        "registered pharmacist",
        "batch",
        "medicine",
        "medicines",
        "tablet",
        "capsule",
        "patient:",
        "gst medicine",
    ]):
        return "medical_or_pharmacy"

    # Vehicle servicing bills
    if any(keyword in text_lower for keyword in [
        "vehicle service",
        "service centre",
        "spare parts",
        "motor garage",
        "repair charges",
    ]):
        return "vehicle_service"

    # Medical consultation bills
    if any(keyword in text_lower for keyword in [
        "doctor consultation",
        "consultation fee",
        "physician",
        "maternity home",
    ]):
        return "medical_consultation"

    return "other"

def extract_bill_number(text: str) -> str | None:
    """Find a number associated with a bill/invoice label."""
    lines = text.splitlines()

    import re

    text_lower = text.lower()

    # HP petrol pump cash memo
    if (
        "shiv shilpika petroleum" in text_lower
        or "hindustan petroleum corporation" in text_lower
    ):
        match = re.search(
            r"\b(?:ne|no\.?)\s*[:.]?\s*(\d{5,})\b",
            text,
            re.IGNORECASE
        )
        if match:
            return match.group(1)

    # Tata Play Fiber: OCR may separate the invoice label and value.
    if "tata play fiber" in text.lower():
        match = re.search(
            r"\bMHI\d{10,}\b",
            text,
            re.IGNORECASE
        )
        if match:
            return match.group(0)
        
    for index, line in enumerate(lines):
        match = BILL_LABEL.search(line)

        if not match:
            continue

        # First try the value on the same line.
        remainder = line[match.end():].strip(" \t:.-#")

        if remainder:
            # Capture the first plausible identifier.
            value_match = re.match(
                r"([A-Z0-9][A-Z0-9/-]*(?:\s+[0-9][A-Z0-9/-]*)*)",
                remainder,
                re.IGNORECASE,
            )

            if value_match:
                value = value_match.group(1).strip()

                # Join OCR-split numeric invoice identifiers.
                if re.fullmatch(r"(?:\d+\s+)+\d+", value):
                    value = re.sub(r"\s+", "", value)

                if len(value) >= 3:
                    return value

        # If the label has no value, inspect the next nonempty line.
        for next_line in lines[index + 1:index + 3]:
            candidate = next_line.strip()

            if not candidate:
                continue

            # Do not mistake another field label for the bill number.
            if re.match(
                r"^(date|time|patient|customer|amount|gstin|address)\b",
                candidate,
                re.IGNORECASE,
            ):
                break

            candidate_match = re.match(
                r"([A-Z0-9][A-Z0-9/-]*)",
                candidate,
                re.IGNORECASE,
            )

            if candidate_match and len(candidate_match.group(1)) >= 3:
                return candidate_match.group(1)

            break

    return None


def extract_bill_date(text: str) -> str | None:
    """Prefer dates next to a Date label."""
    lines = text.splitlines()

    for index, line in enumerate(lines):
        if re.search(r"\bdate\b", line, re.IGNORECASE):
            match = re.search(DATE_PATTERN, line, re.IGNORECASE)

            if match:
                return match.group(0)

            # Handle layouts where the date is on the next line.
            if index + 1 < len(lines):
                match = re.search(
                    DATE_PATTERN, lines[index + 1], re.IGNORECASE
                )
                if match:
                    return match.group(0)

    # Fallback: first recognizable date anywhere in the document.
    match = re.search(DATE_PATTERN, text, re.IGNORECASE)
    return match.group(0) if match else None


def extract_total_amount(text: str) -> float | None:
    """Find the most likely invoice total."""

    
    # Handle OCR text such as "TOTAL AT:-754.384"
    total_at_match = re.search(
        r"\bTOTAL\s+AT\s*[:\-]?\s*"
        r"(?:INR\s*|Rs\.?\s*|₹\s*)?"
        r"([\d,]+(?:\.\d{1,3})?)",
        text,
        re.IGNORECASE,
)
        # Handle receipts such as:
    # "the sum of Rupees 4000 towards Wacin"
    receipt_amount_match = re.search(
        r"\b(?:sum\s+of\s+)?rupees\s+([\d,]+(?:\.\d{1,2})?)",
        text,
        re.IGNORECASE,
    )

    if receipt_amount_match:
        amount = parse_amount(receipt_amount_match.group(1))
        if amount is not None and amount > 0:
            return amount
        
    if total_at_match:
        amount = parse_amount(total_at_match.group(1))
        if amount is not None and amount > 0:
            return amount

    # Strong, explicit total labels first.
    labels = [
        r"net\s+payable\s+amount",
        r"net\s+amt",
        r"net\s+amount",
        r"total\s+order\s+value",
        r"total\s+invoice\s+amount",
        r"grand\s+total",
        r"total\s+amount",
        r"total\s+at",          # Handles OCR text such as TOTAL AT:-754.384
        r"amount\s+payable",
        r"invoice\s+total",
    ]

    for label in labels:
        pattern = re.compile(
            label
            + r"\s*[:\-]?\s*(?:INR\s*|RS\.?\s*|₹\s*)?"
            + r"([\d,]+(?:[.,]\d{1,3})?)",
            re.IGNORECASE,
        )

        match = pattern.search(text)
        if match:
            amount = parse_amount(match.group(1))
            if amount is not None:
                return amount

        # Cash receipts often repeat the paid amount beside CASH.
        match = re.search(
        r"\bCASH\s*(?:RS\.?\s*|INR\s*|₹\s*)"
        r"([\d,]+(?:\.\d{1,3})?)",
        text,
        re.IGNORECASE,
    )

    if match:
        amount = parse_amount(match.group(1))
        if amount is not None and amount > 0:
            return amount

    # Handle a total label whose value is on the next line.
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.search(
            r"\b(?:NET\s*AMT|NET\s*AMOUNT|TOTAL|GROSS\s*AMT)\b"
            r"(?:rupees|rs\.?|inr)\s*[:.]?\s*([\d,]+(?:\.\d{1,2})?)",
            line,
            re.IGNORECASE,
        ):
            for candidate in [line, *lines[index + 1:index + 2]]:
                if re.search(r"[A-Z]{3,}", candidate, re.IGNORECASE):
                    continue

                match = AMOUNT_PATTERN.search(candidate)
                if match:
                    amount = parse_amount(match.group(1))
                    if amount is not None:
                        return amount

    
    # Handle OCR variations such as "Gros" instead of "Gross"
        gross_match = re.search(
        r"\b(?:gross|gros)\b[^\d\n]{0,20}\n?\s*"
        r"(?:₹|Rs\.?|INR)?\s*"
        r"([\d,]+(?:\.\d{1,2})?)",
        text,
        re.IGNORECASE,
    )

    if gross_match:
        amount = parse_amount(gross_match.group(1))
        if amount is not None and amount > 0:
            return amount


    # Safer fallback: use an amount only when there is
    # exactly one distinct plausible decimal value.
    # If several values are present, require manual review
    # instead of guessing which one is the invoice total.
    candidates = re.findall(
        r"(?<!\d)(\d{1,3}(?:,\d{3})+|\d{1,7})[.,](\d{2,3})(?!\d)",
        text,
    )

    amounts = set()

    for whole, fraction in candidates:
        amount = parse_amount(f"{whole}.{fraction}")

        if amount is not None and amount > 0:
            amounts.add(round(amount, 2))

    if len(amounts) == 1:
        return amounts.pop()

    return None



def extract_fuel_details(text: str) -> tuple[float | None, float | None]:
    """Extract fuel volume and rate when explicitly labelled."""
    rate = None
    quantity = None

    rate_match = re.search(
        r"rate\s*\(?\s*(?:rs\s*/\s*l|rs/l|s/l)?\s*\)?"
        r"\s*[:\-]?\s*(\d{1,5}(?:[.,]\s*\d{1,3})?)"
        r"(?:rupees|rs\.?|inr)\s*[:.]?\s*([\d,]+(?:\.\d{1,2})?)",
        text,
        re.IGNORECASE,
    )

    if rate_match:
        rate = parse_amount(rate_match.group(1))

    quantity_match = re.search(
        r"(?:volume\s*\(\s*l\s*\)|volume\s*\(l\)|volume\s*\(l\)|"
        r"volume\s*\(l\)|qty\.?|quantity)"
        r"\s*[:\-]?\s*(\d{1,6}(?:\.\d{1,3})?)",
        text,
        re.IGNORECASE,
    )

    if quantity_match:
        quantity = parse_amount(quantity_match.group(1))

    return quantity, rate


def parse_bill_text(text: str) -> dict:
    """Parse common fields from different bill layouts."""
    bill_type = detect_bill_type(text)
    quantity = None
    rate_per_litre = None

    if bill_type == "fuel":
        quantity, rate_per_litre = extract_fuel_details(text)

    return {
        "bill_type": bill_type,
        "bill_number": extract_bill_number(text),
        "bill_date": extract_bill_date(text),
        "total_amount": extract_total_amount(text),
        "quantity": quantity,
        "rate_per_litre": rate_per_litre,
    }