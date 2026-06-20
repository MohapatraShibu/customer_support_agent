import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from agent import build_agent
from tools import lookup_customer

load_dotenv()

_agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set in .env")
    _agent = build_agent(api_key)
    yield

app = FastAPI(title="AI Support Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# serve frontend
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
def serve_chat():
    return FileResponse(os.path.join(frontend_path, "index.html"))

@app.get("/admin")
def serve_admin():
    return FileResponse(os.path.join(frontend_path, "admin.html"))


# in-memory session store
sessions: dict[str, list] = {}
session_logs: dict[str, list] = {}


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    logs: list[dict]


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not _agent:
        raise HTTPException(503, "Agent not ready")

    history = sessions.get(req.session_id, [])
    history.append(HumanMessage(content=req.message))

    existing_logs = session_logs.get(req.session_id, [])
    state = {"messages": history, "logs": existing_logs}

    result = _agent.invoke(state)

    sessions[req.session_id] = result["messages"]
    session_logs[req.session_id] = result.get("logs", [])

    last_msg = result["messages"][-1]
    reply = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    return ChatResponse(reply=reply, logs=result.get("logs", []))


@app.get("/logs/{session_id}")
def get_logs(session_id: str):
    return {"logs": session_logs.get(session_id, [])}


@app.get("/customers")
def get_customers():
    import json
    from pathlib import Path
    with open(Path(__file__).parent / "data" / "crm.json") as f:
        data = json.load(f)
    # return sanitized list for admin dashboard
    return [
        {
            "customer_id": c["customer_id"],
            "name": c["name"],
            "email": c["email"],
            "account_standing": c["account_standing"],
            "orders": c["orders"],
            "refund_count": len(c.get("refund_history", []))
        }
        for c in data
    ]


@app.get("/sessions")
def list_sessions():
    return [
        {"session_id": sid, "message_count": len(msgs), "log_count": len(session_logs.get(sid, []))}
        for sid, msgs in sessions.items()
    ]


@app.delete("/sessions/{session_id}")
def clear_session(session_id: str):
    sessions.pop(session_id, None)
    session_logs.pop(session_id, None)
    return {"cleared": True}
