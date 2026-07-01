import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.retrieval import run_graph_strategy, run_filter_strategy, init_resources

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_resources()
    yield

app = FastAPI(title="Causal Insight", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str
    history: list = []
    model_type: str = "graph" 

@app.get("/health")
def health():
    return {"status": "ready"}

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Streaming Endpoint.
    Returns: Server-Sent Events (SSE)
    """
    async def sse_generator():
        try:
            if req.model_type == "filter":
                iterator = run_filter_strategy(req.query, req.history)
            else:
                iterator = run_graph_strategy(req.query, req.history)
            
            # Stream Loop
            async for item in iterator:
                encoded = json.dumps(item)
                yield f"data: {encoded}\n\n"
                await asyncio.sleep(0.2)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            err = json.dumps({"event": "error", "message": str(e)})
            yield f"data: {err}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)