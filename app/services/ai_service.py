import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:3b"


def format_inr(amount) -> str:
    return f"₹{float(amount):,.2f}"


def generate_ai_response(claim_result: dict) -> str:
    amount = claim_result.get("amount")
    limit = claim_result.get("limit")
    status = claim_result.get("status")
    reason = claim_result.get("reason")

    formatted_amount = format_inr(amount) if amount is not None else "Unavailable"
    formatted_limit = format_inr(limit) if limit is not None else "Unavailable"

    prompt = f"""
You are a reimbursement assistant.
Write one short explanation using these exact values.

Claim amount: {formatted_amount}
Maximum limit: {formatted_limit}
Decision: {status}
Reason: {reason}

Do not change any values or the decision.
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
            },
            timeout=30,
        )
        response.raise_for_status()
        explanation = response.json()["response"].strip()

        # Ensure the explanation uses the authoritative Python-formatted values.
        explanation = explanation.replace("₹", "INR ")
        explanation = explanation.replace("$", "INR ")

        return (
            f"Decision: {status}\n"
            f"Claim Amount: {formatted_amount}\n"
            f"Maximum Limit: {formatted_limit}\n"
            f"AI Explanation: {explanation}\n"
            f"Reason: {reason}"
        )

    except (requests.RequestException, KeyError, ValueError):
        return (
            f"Decision: {status}\n"
            f"Claim Amount: {formatted_amount}\n"
            f"Maximum Limit: {formatted_limit}\n"
            f"Reason: {reason}"
        )



def ask_receipt_question(
    question: str,
    extracted_text: str,
    bill_details: dict,
    claim_result: dict,
) -> dict:
    import json
    import requests

    prompt = f"""
You are an expense reimbursement assistant.

Use only the receipt text and the supplied claim details.
The Python claim decision is authoritative.

Rules:
- Never invent an invoice number, date, amount, quantity, or tax.
- Never calculate or guess a replacement amount.
- Suggest a correction only when the exact value is explicitly present
  in the extracted receipt text.
- For every proposed correction, provide an exact supporting quote
  copied from the receipt text.
- If the receipt does not clearly support a correction, return no
  proposed correction and explain why.
- Never approve or reject a claim yourself.
- Ask the employee to confirm a proposed correction before it is applied.
- Only propose these fields: bill_number, bill_date, total_amount.
- Return valid JSON only, with this structure:
{{
  "answer": "A concise conversational answer for the employee",
  "proposed_corrections": {{
    "bill_number": {{
      "value": "exact value from the receipt",
      "evidence": "exact quote containing the value"
    }}
  }}
}}
- Include only fields you can support with an exact quote.
- If there are no supported corrections, use an empty object:
  "proposed_corrections": {{}}
- Do not include markdown fences or text outside the JSON.

Employee question:
{question}

Extracted receipt text:
{extracted_text[:120000]}

Currently extracted bill details:
{json.dumps(bill_details, ensure_ascii=False)}

Current claim decision:
{json.dumps(claim_result, ensure_ascii=False)}
"""

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen2.5:3b",
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
            timeout=90,
        )
        response.raise_for_status()

        raw_response = response.json().get("response", "")
        data = json.loads(raw_response)

        answer = str(data.get("answer", "")).strip()
        proposed = data.get("proposed_corrections", {})

        if not isinstance(proposed, dict):
            proposed = {}

        # Accept a correction only if its value and evidence are
        # explicitly supported by the extracted receipt text.
        verified_corrections = {}
        allowed_fields = {"bill_number", "bill_date", "total_amount"}

        for field, item in proposed.items():
            if field not in allowed_fields or not isinstance(item, dict):
                continue

            value = str(item.get("value", "")).strip()
            evidence = str(item.get("evidence", "")).strip()

            if (
                value
                and evidence
                and evidence in extracted_text
                and value in evidence
            ):
                verified_corrections[field] = {
                    "value": value,
                    "evidence": evidence,
                }

        return {
            "answer": answer or "I could not prepare an answer from the receipt.",
            "proposed_corrections": verified_corrections,
        }

    except (requests.RequestException, json.JSONDecodeError, ValueError):
        return {
            "answer": (
                "I could not get a reliable response from the AI model. "
                "Please check that Ollama is running and try again."
            ),
            "proposed_corrections": {},
        }
