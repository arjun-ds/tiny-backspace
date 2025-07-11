import modal
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
import asyncio
import json
from typing import AsyncGenerator
import os

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

@web_app.get("/healthz")
async def healthz():
    """Health check endpoint to verify service status.
    
    Returns:
        dict: Status response with service name
    """
    return {"status": "ok", "service": "Backspace Coding Agent"}

# Request model
class CodeRequest(BaseModel):
    repoUrl: HttpUrl
    prompt: str

@web_app.post("/code")
async def create_code_changes(request: CodeRequest):
    """Run the agent and format output like test_endpoint.py does"""
    from agent import run_agent
    
    # Hardcode the repo URL as requested
    repo_url = "https://github.com/arjun-ds/tiny-backspace"
    prompt = request.prompt
    
    async def format_like_test_endpoint():
        """Format agent output exactly like test_endpoint.py does"""
        # First, emit the initial messages that test_endpoint would show
        yield f"data: {json.dumps({'type': 'AI Message', 'message': f'Starting agent for repository: {repo_url}'})}\n\n"
        yield f"data: {json.dumps({'type': 'AI Message', 'message': f'Task: {prompt}'})}\n\n"
        
        # Then run the agent and forward its events
        async for event in run_agent(repo_url, prompt):
            # The agent already returns SSE-formatted strings, just forward them
            yield event
    
    return StreamingResponse(
        format_like_test_endpoint(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )

# Add /api/code endpoint that calls the agent directly like test_endpoint does
@web_app.post("/api/code")
async def create_code_changes_api(request: CodeRequest):
    # Call the /code endpoint directly (which uses the agent)
    return await create_code_changes(request)

# Add a debug endpoint that shows what's happening
@web_app.post("/api/code-debug")
async def create_code_changes_debug(request: CodeRequest):
    """Debug endpoint that shows step-by-step what's happening"""
    # Hardcode the repo URL as requested
    repo_url = "https://github.com/arjun-ds/tiny-backspace"
    prompt = request.prompt
    
    async def debug_stream():
        """Stream debug events showing each step"""
        try:
            # Step 1: Check environment
            yield f"data: {json.dumps({'type': 'AI Message', 'message': 'Starting debug process...'})}\n\n"
            
            github_token = os.getenv("GITHUB_TOKEN", "")
            anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
            
            yield f"data: {json.dumps({'type': 'AI Message', 'message': f'GitHub token present: {bool(github_token)}'})}\n\n"
            yield f"data: {json.dumps({'type': 'AI Message', 'message': f'Anthropic API key present: {bool(anthropic_key)}'})}\n\n"
            
            if not github_token or not anthropic_key:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Missing required API keys'})}\n\n"
                return
            
            # Step 2: Import and run agent
            yield f"data: {json.dumps({'type': 'AI Message', 'message': 'Loading agent module...'})}\n\n"
            
            try:
                from agent import CodingAgent
                yield f"data: {json.dumps({'type': 'AI Message', 'message': 'Agent module loaded successfully'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to import agent: {str(e)}'})}\n\n"
                return
            
            # Step 3: Initialize agent
            try:
                agent = CodingAgent(github_token)
                yield f"data: {json.dumps({'type': 'AI Message', 'message': 'Agent initialized successfully'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to initialize agent: {str(e)}'})}\n\n"
                return
            
            # Step 4: Process repository
            yield f"data: {json.dumps({'type': 'AI Message', 'message': f'Processing repository: {repo_url}'})}\n\n"
            yield f"data: {json.dumps({'type': 'AI Message', 'message': f'Prompt: {prompt}'})}\n\n"
            
            event_count = 0
            async for event in agent.process_repository(repo_url, prompt):
                event_count += 1
                # Add event number for debugging
                event['debug_event_num'] = event_count
                yield f"data: {json.dumps(event)}\n\n"
                
                # Flush to prevent buffering
                await asyncio.sleep(0)
            
            yield f"data: {json.dumps({'type': 'AI Message', 'message': f'Total events processed: {event_count}'})}\n\n"
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': f'Debug stream error: {str(e)}', 'traceback': error_details})}\n\n"
    
    return StreamingResponse(
        debug_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )

# Modal ASGI app decorator
@app.function(
    image=modal.Image.debian_slim()
        .pip_install_from_requirements("requirements.txt")
        .apt_install("git")
        .env({
            "LOG_LEVEL": "INFO", 
            "DD_TRACE_ENABLED": "false",
            "LANGSMITH_ENABLED": "false",
            "LANGSMITH_TRACING": "false",
            "LANGSMITH_ENDPOINT": "https://api.smith.langchain.com",
            "LANGSMITH_PROJECT": "backspace-agent"
        })
        .add_local_file("agent.py", "/root/agent.py")
        .add_local_file("test_endpoint.py", "/root/test_endpoint.py")
        .add_local_dir("../web/out", "/root/web/out"),
    secrets=[
        modal.Secret.from_name("github-token"),
        modal.Secret.from_name("anthropic-api-key")
    ],
    timeout=300
)
@modal.asgi_app()
def modal_asgi():
    """Deploy FastAPI app on Modal with configuration.
    
    This function configures the FastAPI app for Modal deployment with:
    - Required Python packages and system dependencies
    - Environment variables for logging and tracing
    - Local files and directories mounted
    - GitHub and Anthropic API secrets
    - Static file serving
    
    Returns:
        FastAPI: Configured FastAPI application
    """
    # Mount static files LAST so API routes take precedence
    static_dir = "/root/web/out"
    if os.path.exists(static_dir):
        web_app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
        print(f"Static files mounted from {static_dir}")
    else:
        print(f"Warning: Static directory {static_dir} not found")
    
    return web_app