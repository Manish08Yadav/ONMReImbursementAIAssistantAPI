from app.services.bill_parser import parse_bill_text

sample_text = """
Cash Memo - original
25/09/2026 20:42:18
26092512019
Product Qty
5.28
UOM Litre 111.36
Rate -Rs Amount -Rs 587.98
Total Invoice Amount:
CASH
RS.587.98
"""

result = parse_bill_text(sample_text)
print(result)