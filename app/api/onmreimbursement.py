from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
import requests


from app.services.pdf_service import extract_pdf_text
from app.services.ocr_service import extract_image_text
from app.services.bill_parser import parse_bill_text
from app.services.claim_rules import evaluate_claim, reevaluate_claim
from app.services.ai_service import generate_ai_response

from pydantic import BaseModel, Field
from app.services.ai_service import ask_receipt_question
from app.services.submission_service import submit_claim

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


@router.post("/upload")
async def upload_reimbursement_bill(file: UploadFile = File(...)):
    extension = Path(file.filename or "").suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, JPG, JPEG, and PNG files are allowed."
        )

    file_path = UPLOAD_DIR / Path(file.filename).name

    try:
        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty."
            )

        file_path.write_bytes(content)

        if extension == ".pdf":
            extracted_text = extract_pdf_text(str(file_path))
        else:
            extracted_text = extract_image_text(str(file_path))

        bill_details = parse_bill_text(extracted_text)

        # Apply reimbursement business rules
        claim_result = evaluate_claim(bill_details)

        # Generate an explanation using Ollama
        try:
            ai_explanation = generate_ai_response(claim_result)
        except (requests.RequestException, KeyError, ValueError):
            ai_explanation = (
                "AI explanation is currently unavailable. "
                "The claim status was determined by the reimbursement rules."
            )

        return {
            "filename": file.filename,
            "message": "Bill uploaded and processed successfully",
            "extracted_text": extracted_text,
            "bill_details": bill_details,
            "claim_result": claim_result,
            "ai_explanation": ai_explanation
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process bill: {str(exc)}"
        ) from exc
    finally:
        await file.close()

class ReceiptAssistantRequest(BaseModel):
    question: str
    extracted_text: str
    bill_details: dict = Field(default_factory=dict)
    claim_result: dict = Field(default_factory=dict)

class ClaimCorrectionRequest(BaseModel):
    bill_details: dict = Field(default_factory=dict)
    corrections: dict = Field(default_factory=dict)
    employee_confirmed: bool = False

class SubmitClaimRequest(BaseModel):
    bill_details: dict = Field(default_factory=dict)

@router.post("/assistant/ask")
def ask_assistant(request: ReceiptAssistantRequest):
    if not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Please enter a question."
        )

    if not request.extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No extracted receipt text is available."
        )

    answer = ask_receipt_question(
        question=request.question,
        extracted_text=request.extracted_text,
        bill_details=request.bill_details,
        claim_result=request.claim_result,
    )

    return answer


@router.post("/claim/reevaluate")
def reevaluate_reimbursement_claim(
    request: ClaimCorrectionRequest
):
    if not request.employee_confirmed:
        raise HTTPException(
            status_code=400,
            detail="Please verify and confirm the corrections first."
        )

    if not request.corrections:
        raise HTTPException(
            status_code=400,
            detail="No corrections were provided."
        )

    result = reevaluate_claim(
        bill_details=request.bill_details,
        corrections=request.corrections
    )

    return {
        "message": "Claim re-evaluated using reimbursement rules.",
        "claim_result": result
    }


@router.post("/claim/submit")
def submit_reimbursement_claim(request: SubmitClaimRequest):
    # Recalculate the decision using authoritative Python rules.
    claim_result = evaluate_claim(request.bill_details)

    if claim_result.get("status") != "Approved":
        raise HTTPException(
            status_code=400,
            detail=(
                "Only approved claims can be submitted. "
                f"Current status: {claim_result.get('status', 'Unknown')}."
            ),
        )

    try:
        submission = submit_claim(
            bill_details=request.bill_details,
            claim_result=claim_result,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not save the claim submission.",
        ) from exc

    return {
        "message": "Claim submitted successfully.",
        "submission": submission,
    }


