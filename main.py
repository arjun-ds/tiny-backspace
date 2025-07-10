import modal
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import asyncio
import json
from typing import AsyncGenerator

# Define the Modal app
app = modal.App("backspace-agent")

# Create FastAPI instance
web_app = FastAPI(title="Backspace Coding Agent")

# Add CORS middleware
web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    
    # Import agent inside the function to avoid issues during deployment
    from agent import run_agent
    
    # Validate the request
    repo_url = str(request.repoUrl)
    if not repo_url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Only GitHub repositories are supported")
    
    print(f"Starting code changes for repo: {repo_url}, prompt: {request.prompt}")
    
    # Stream the coding agent's progress
    return StreamingResponse(
        run_agent(repo_url, request.prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering for nginx
            "Access-Control-Allow-Origin": "*",  # Allow CORS for testing
            "Access-Control-Allow-Headers": "*"
        }
    )

# Modal ASGI app decorator
@app.function(
    image=modal.Image.debian_slim()
        .pip_install_from_requirements("requirements.txt")
        .apt_install("git")
        .env({"LOG_LEVEL": "INFO", "DD_TRACE_ENABLED": "false"})
        .add_local_file("agent.py", "/root/agent.py"),
    secrets=[
        modal.Secret.from_name("github-token"),
        modal.Secret.from_name("anthropic-api-key")
    ],
    timeout=300
)
@modal.asgi_app()
def modal_asgi():
    """Deploys the FastAPI application as a Modal ASGI app.
    
    This function configures the deployment environment for the FastAPI app including:
    - Base Debian slim image
    - Required pip packages from requirements.txt
    - Git installation
    - Environment variables for logging and tracing
    - Local agent.py file copy
    - GitHub and Anthropic API secrets
    - 5 minute (300s) timeout
    
    Returns:
        The FastAPI web application instance configured for Modal deployment
    """
    """Deploy FastAPI app on Modal"""
    return web_app