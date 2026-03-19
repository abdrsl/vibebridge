import os
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.llm import ask_deepseek_for_design_advice
from app.task_parser import extract_text_from_feishu_payload
from app.task_store import save_task, list_tasks, get_task

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("App starting...")
    yield
    print("App shutting down...")


app = FastAPI(
    title="Embrace AI Product Lab",
    version="0.1.0",
    lifespan=lifespan,
)

origins = [
    item.strip()
    for item in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if item.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "name": "Embrace AI Product Lab",
        "status": "ok",
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/config-check")
def config_check():
    return {
        "DEEPSEEK_BASE_URL": os.getenv("DEEPSEEK_BASE_URL"),
        "DEEPSEEK_MODEL": os.getenv("DEEPSEEK_MODEL"),
        "DEEPSEEK_API_KEY_present": bool(os.getenv("DEEPSEEK_API_KEY")),
    }


@app.get("/tasks")
def api_list_tasks(limit: int = 20):
    return {
        "ok": True,
        "items": list_tasks(limit=limit),
    }


@app.get("/tasks/{task_id}")
def api_get_task(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")

    return {
        "ok": True,
        "item": task,
    }


@app.post("/feishu/webhook")
async def feishu_webhook(body: dict[str, Any]):
    task = extract_text_from_feishu_payload(body)
    text = task.get("raw_text", "").strip()
    status = task.get("status", "queued")
    llm_result = None

    if status != "ignored":
        try:
            llm_result = ask_deepseek_for_design_advice(text)
            status = "completed"
        except Exception as e:
            llm_result = f"LLM error: {e}"
            status = "failed"

    task["status"] = status

    result = {
        "ok": True,
        "source": "feishu",
        "parsed_text": text,
        "task": task,
        "llm_result": llm_result,
    }

    saved = save_task(result)
    result["saved"] = saved

    return result
