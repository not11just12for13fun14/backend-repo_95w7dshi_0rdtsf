"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List

# Example schemas (you can keep these around for reference)
class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# --------------------------------------------------
# AI Interviewer Platform Schemas
# --------------------------------------------------

class Question(BaseModel):
    text: str = Field(..., description="Question prompt")
    keywords: List[str] = Field(default_factory=list, description="Expected key concepts for evaluation")

class Interview(BaseModel):
    role: str = Field(..., description="Job role, e.g., Frontend Engineer")
    description: str = Field(..., description="Brief role context or JD highlights")
    level: str = Field(..., description="Seniority level: junior | mid | senior")
    num_questions: int = Field(..., ge=1, le=15, description="How many questions were generated")
    questions: List[Question] = Field(..., description="Generated interview questions")

class Submission(BaseModel):
    interview_id: str = Field(..., description="Interview identifier")
    candidate_name: str = Field(..., description="Candidate full name")
    answers: List[str] = Field(..., description="Answers mapped by index to interview questions")

class Evaluation(BaseModel):
    interview_id: str
    candidate_name: str
    answers: List[str]
    per_question_scores: List[float]
    per_question_feedback: List[str]
    total_score: float
    verdict: str
