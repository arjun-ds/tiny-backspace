# Modal Coding Agent

A sandboxed AI agent that automatically creates pull requests from natural language descriptions.

## Architecture

- **FastAPI** - Web framework with native SSE support
- **Modal** - Serverless platform for both API hosting and sandboxed code execution
- **PyGithub** - GitHub API integration for PR creation

## Setup

### Prerequisites

1. Python 3.8+
2. Modal account (create at https://modal.com)
3. GitHub Personal Access Token

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd modal-coding-agent

# Install dependencies
pip install -r requirements.txt

# Authenticate with Modal
modal token new
```

### Configuration

Create a `.env` file with:
```
GITHUB_TOKEN=your_github_pat_here
```

## Usage

### Deploy to Modal

```bash
modal deploy main.py
```

This will output a public URL like: `https://your-app.modal.run`

### API Endpoint

**POST /code**

Request body:
```json
{
  "repoUrl": "https://github.com/owner/repo",
  "prompt": "Add input validation to all POST endpoints"
}
```

Response: Server-Sent Events stream with real-time updates

### Example Usage

```bash
curl -X POST https://your-app.modal.run/code \
  -H "Content-Type: application/json" \
  -d '{
    "repoUrl": "https://github.com/owner/repository",
    "prompt": "Add error handling to all API endpoints"
  }'
```

## Local Development

For local testing without Modal:

```bash
# Run the FastAPI app locally
python test_local.py

# In another terminal, test SSE streaming
python test_sse.py
```

## Architecture Decisions

### Why Modal?
- Single platform for both API hosting and sandboxed execution
- Native FastAPI support via `@modal.asgi_app()`
- Excellent Python SDK and documentation
- Built-in security and isolation

### Why FastAPI?
- Native SSE support with `StreamingResponse`
- Async/await for efficient I/O operations
- Automatic API documentation
- Type safety with Pydantic

## Implementation Status

- [x] Basic FastAPI app with SSE endpoint
- [x] Modal deployment configuration
- [x] GitHub repository cloning integration
- [x] GitHub PAT authentication setup
- [ ] AI agent integration
- [ ] Pull request creation
- [ ] Production monitoring
- [ ] Comprehensive error handling


## Security Considerations

- Only public GitHub repositories are supported
- Code execution happens in isolated Modal sandboxes
- GitHub PAT is stored securely as Modal secret
- Input validation on all endpoints