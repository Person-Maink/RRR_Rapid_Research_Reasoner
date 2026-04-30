import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from services.environment import FRONTEND_ORIGIN, MAX_UPLOAD_BYTES
from services.job_store import PostgresJobStore
from services.logging_config import configure_logging
from services.queue import RabbitMQClient
from services.storage import LocalStorageAdapter, is_pdf_upload
from shared import ChatJobCreated, ChatJobResponse, RetrievedPage

configure_logging("api")
LOGGER = logging.getLogger(__name__)
JOB_STORE = PostgresJobStore()
STORAGE = LocalStorageAdapter()
QUEUE = RabbitMQClient()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    JOB_STORE.init_db()
    yield


app = FastAPI(title="Rapid Research Reasoner API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post(
    "/chat/jobs",
    response_model=ChatJobCreated,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_chat_job(
    request: Request,
    query: str = Form(...),
    files: list[UploadFile] = File(...),
):
    started = time.perf_counter()
    clean_query = query.strip()
    if not clean_query:
        raise HTTPException(status_code=400, detail="Query is required.")
    if not files:
        raise HTTPException(status_code=400, detail="At least one PDF is required.")

    invalid_files = [
        upload.filename or "unnamed"
        for upload in files
        if not is_pdf_upload(upload.filename, upload.content_type)
    ]
    if invalid_files:
        raise HTTPException(
            status_code=400,
            detail=f"Only PDF uploads are supported: {', '.join(invalid_files)}",
        )

    job_id = JOB_STORE.create_job(clean_query)
    try:
        for upload in files:
            stored_file = await STORAGE.save_upload(
                job_id, upload, max_bytes=MAX_UPLOAD_BYTES
            )
            JOB_STORE.add_document(stored_file)
        QUEUE.publish_job(job_id)
    except ValueError as exc:
        JOB_STORE.fail_job(job_id, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        JOB_STORE.fail_job(job_id, str(exc))
        raise HTTPException(
            status_code=503,
            detail="The job could not be queued. Check RabbitMQ connectivity.",
        ) from exc

    LOGGER.info(
        "Queued chat job",
        extra={
            "job_id": job_id,
            "status": "queued",
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return ChatJobCreated(
        job_id=job_id,
        status="queued",
        poll_url=str(request.url_for("get_chat_job", job_id=job_id)),
    )


@app.get("/chat/jobs/{job_id}", response_model=ChatJobResponse)
def get_chat_job(request: Request, job_id: str):
    job = JOB_STORE.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    retrieved_pages = [
        RetrievedPage(
            document_id=page["document_id"],
            file_name=page["file_name"],
            page_number=page["page_number"],
            pdf_url=str(request.url_for("get_pdf", document_id=page["document_id"])),
            score=page.get("score"),
        )
        for page in JOB_STORE.list_retrieved_pages(job_id)
    ]
    return ChatJobResponse(
        job_id=job_id,
        status=job["status"],
        answer=job.get("answer"),
        retrieved_pages=retrieved_pages,
        error=job.get("error"),
    )


@app.get("/documents/{document_id}/pdf", name="get_pdf")
def get_pdf(document_id: str):
    document = JOB_STORE.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    return FileResponse(
        document["storage_path"],
        media_type="application/pdf",
        filename=document["file_name"],
    )
