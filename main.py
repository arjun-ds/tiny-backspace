import modal
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl
import asyncio
import json
from typing import AsyncGenerator
import agent
from agent import run_agent

# Define the Modal app
app = modal.App("backspace-agent")

# Create FastAPI instance
web_app = FastAPI(title="Backspace Coding Agent")

# Request model
class CodeRequest(BaseModel):
    repoUrl: HttpUrl
    prompt: str


@web_app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "Backspace Coding Agent"}

@web_app.post("/code")
async def create_code_changes(request: CodeRequest):
    """Main endpoint that streams the coding process"""
    
    # Validate the request
    repo_url = str(request.repoUrl)
    if not repo_url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Only GitHub repositories are supported")
    
    # Stream the coding agent's progress
    return StreamingResponse(
        run_agent(repo_url, request.prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering for nginx
        }
    )

# Modal ASGI app decorator
@app.function(
    image=modal.Image.debian_slim()
        .pip_install_from_requirements("requirements.txt")
        .apt_install("git")
        .copy_local_file("agent.py", "/root/agent.py"),
    secrets=[modal.Secret.from_name("github-token")],
    timeout=300  # 5 minute timeout for long operations
)
@modal.asgi_app()
def modal_asgi():
    """Deploy FastAPI app on Modal"""
    return web_app