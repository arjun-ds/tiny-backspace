# Modal Coding Agent

A sandboxed AI agent that automatically creates pull requests from natural language descriptions.

## Architecture

- **FastAPI** - Web framework with SSE streaming
- **Modal** - Serverless platform for hosting and sandboxed execution
- **Claude-4 Opus** - AI code analysis and modification
- **PyGithub** - GitHub API integration

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

Set up Modal secrets:
```bash
modal secret create github-token GITHUB_TOKEN=<your_pat>
modal secret create anthropic-api-key ANTHROPIC_API_KEY=<your_key>
```

## Usage

### Deploy to Modal

```bash
modal deploy main.py
```

This will output a public URL like: `https://your-app.modal.run`

**Note:** The deployment imports `agent.py` inside the FastAPI endpoint function to avoid dependency conflicts during deployment. Modal builds the container image with all requirements before importing the module.

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

## Testing

Test the deployed endpoint:

```bash
python test_endpoint.py https://your-app.modal.run
```

Additional options:

```bash
# Custom repository and prompt
python test_endpoint.py https://your-app.modal.run --repo https://github.com/owner/repo --prompt "Add error handling"

# Authentication test (no changes made)
python test_endpoint.py https://your-app.modal.run --auth-test

# Quiet mode with results saved to file
python test_endpoint.py https://your-app.modal.run --quiet --save-results

# Custom timeout
python test_endpoint.py https://your-app.modal.run --timeout 600
```

**Note:** Requires `requests` library (`pip install requests`)

## Implementation Status

- [x] Basic FastAPI app with SSE endpoint
- [x] Modal deployment configuration
- [x] GitHub repository cloning integration
- [x] GitHub PAT authentication setup
- [x] Anthropic Claude-4 Opus integration
- [x] Code analysis and modification workflow
- [x] Secure subprocess validation with error cycling
- [x] Git branching and commit operations
- [x] Pull request creation
- [ ] Production monitoring
- [ ] Enhanced security hardening (see Security Considerations)
- [ ] Comprehensive error handling


## Security Considerations

- Only public GitHub repositories are supported
- Code execution happens in isolated Modal sandboxes
- GitHub PAT is stored securely as Modal secret
- Input validation on all endpoints

### Code Execution Security
Code validation runs in subprocess isolation with restricted environment variables and 30-second timeouts. **Additional security measures for production deployment:**

- **Container isolation**: Docker-in-Docker or stronger containerization
- **VM-level sandboxing**: gVisor, Firecracker, or similar technologies
- **Resource quotas**: CPU, memory, disk, and network limits
- **System-level restrictions**: AppArmor/SELinux profiles for syscall filtering
- **Network isolation**: Prevent outbound connections during code execution