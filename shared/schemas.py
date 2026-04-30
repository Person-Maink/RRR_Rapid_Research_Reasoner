from typing import Literal

from pydantic import BaseModel, Field

JobStatus = Literal["queued", "processing", "completed", "failed"]


class QueryRequest(BaseModel):
    query: str


class RetrievedPage(BaseModel):
    document_id: str
    file_name: str
    page_number: int = Field(ge=1)
    pdf_url: str
    score: float | None = None


class ChatJobCreated(BaseModel):
    job_id: str
    status: JobStatus
    poll_url: str


class ChatJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    answer: str | None = None
    retrieved_pages: list[RetrievedPage] = Field(default_factory=list)
    error: str | None = None
