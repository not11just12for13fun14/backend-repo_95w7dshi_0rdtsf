import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from database import db, create_document, get_documents
from schemas import Interview, Submission, Evaluation, Question

app = FastAPI(title="AI Interviewer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "AI Interviewer Backend running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

# -------------------------
# Models for requests
# -------------------------
class InterviewRequest(BaseModel):
    role: str
    level: str
    description: Optional[str] = ""
    num_questions: int = 5

class EvaluateRequest(BaseModel):
    interview_id: str
    candidate_name: str
    answers: List[str]

# -------------------------
# Simple rule-based generation/evaluation (no external LLM)
# -------------------------

BASE_QUESTIONS = {
    "frontend": [
        ("Explain the virtual DOM and how React reconciles updates.", ["virtual dom", "reconciliation", "diffing", "fibers"]),
        ("What are the differences between useEffect and useLayoutEffect?", ["timing", "layout", "paint", "cleanup"]),
        ("How would you optimize a large list rendering in React?", ["virtualize", "memo", "useMemo", "useCallback", "key"]),
        ("Describe how CSS specificity works and how to avoid conflicts.", ["specificity", "cascade", "!important", "BEM"]),
        ("How do you handle state management at scale?", ["redux", "zustand", "context", "atom", "query"]) 
    ],
    "backend": [
        ("Explain ACID properties in databases.", ["atomicity", "consistency", "isolation", "durability"]),
        ("How does an index work in MongoDB and when to use it?", ["b-tree", "performance", "query", "sort"]),
        ("Describe differences between multiprocessing and multithreading in Python.", ["GIL", "cpu-bound", "io-bound"]),
        ("How would you design a rate limiter for an API?", ["token bucket", "leaky bucket", "redis", "sliding window"]),
        ("What is idempotency and why is it important for APIs?", ["safe", "retry", "PUT", "POST"]) 
    ]
}

ROLE_DEFAULT = {
    "frontend": "Frontend Engineer",
    "backend": "Backend Engineer",
}

def infer_track(role: str) -> str:
    r = role.lower()
    if "front" in r or "react" in r: return "frontend"
    if "back" in r or "api" in r: return "backend"
    return "frontend"

@app.post("/api/interviews", response_model=Interview)
def create_interview(req: InterviewRequest):
    track = infer_track(req.role)
    qa = BASE_QUESTIONS.get(track, [])[: max(1, min(req.num_questions, 10))]
    questions: List[Question] = [
        Question(text=q, keywords=keys) for q, keys in qa
    ]
    interview = Interview(
        role=req.role or ROLE_DEFAULT.get(track, req.role),
        description=req.description or f"Interview for {req.role}",
        level=req.level,
        num_questions=len(questions),
        questions=questions,
    )

    try:
        interview_id = create_document("interview", interview)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return interview.model_copy(update={"id": interview_id})

@app.get("/api/interviews")
def list_interviews(limit: int = 20):
    try:
        docs = get_documents("interview", {}, limit)
        # mask mongo ids to strings if present
        for d in docs:
            if "_id" in d:
                d["id"] = str(d.pop("_id"))
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/evaluate", response_model=Evaluation)
def evaluate_answers(req: EvaluateRequest):
    # Load interview to get the expected keywords
    try:
        interviews = get_documents("interview", {"_id": {"$exists": True}}, limit=100)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    interview_doc = None
    for it in interviews:
        if str(it.get("_id")) == req.interview_id or it.get("id") == req.interview_id:
            interview_doc = it
            break

    if not interview_doc:
        raise HTTPException(status_code=404, detail="Interview not found")

    questions = interview_doc.get("questions", [])
    # Convert nested dicts to Question models if needed
    q_models: List[Question] = []
    for q in questions:
        if isinstance(q, dict):
            q_models.append(Question(**q))
        else:
            q_models.append(q)

    answers = req.answers
    if len(answers) != len(q_models):
        raise HTTPException(status_code=400, detail="Answers length must match number of questions")

    per_scores: List[float] = []
    per_feedback: List[str] = []
    total = 0.0

    for i, q in enumerate(q_models):
        ans = answers[i].lower()
        # keyword coverage simple scoring
        if q.keywords:
            covered = sum(1 for k in q.keywords if k.lower() in ans)
            score = round(100 * covered / len(q.keywords), 2)
        else:
            score = 50.0 if len(ans.split()) > 5 else 20.0
        total += score
        missing = [k for k in q.keywords if k.lower() not in ans]
        fb = "Good coverage." if score > 70 else (
            f"Missing: {', '.join(missing)}" if missing else "Could be more specific."
        )
        per_scores.append(score)
        per_feedback.append(fb)

    avg = round(total / len(q_models), 2) if q_models else 0.0
    verdict = (
        "Strong match" if avg >= 75 else
        "Promising but needs work" if avg >= 50 else
        "Below expectations"
    )

    evaluation = Evaluation(
        interview_id=req.interview_id,
        candidate_name=req.candidate_name,
        answers=req.answers,
        per_question_scores=per_scores,
        per_question_feedback=per_feedback,
        total_score=avg,
        verdict=verdict,
    )

    try:
        create_document("evaluation", evaluation)
    except Exception:
        pass

    return evaluation

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
