import sys
print(sys.path)

from fastapi import FastAPI
from shared import QueryRequest
from services.retrieval_service import retrieve
from services.reasoning_service import reason

app = FastAPI()

@app.post("/query")
def query(req: QueryRequest):
    docs = retrieve(req.query)
    answer = reason(req.query, docs)
    return {"response": answer}

