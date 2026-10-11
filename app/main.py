from fastapi import FastAPI
from app.api.onmreimbursement import router as reimbursement_router

app = FastAPI(
    title="ONM Reimbursement App",
    description="AI-powered reimbursement bill processing system",
    version="1.0.0"
)

app.include_router(
    reimbursement_router,
    prefix="/onmreimbursement",
    tags=["Reimbursement"]
)

@app.get("/")
def home():
    return {
        "message": "Reimbursement AI API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }