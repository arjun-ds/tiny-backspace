# Modal Coding Agent

A sandboxed AI agent that automatically creates pull requests from natural language descriptions.

## Project Structure

- **main.py**: FastAPI app entrypoint (SSE streaming API)
- **agent.py**: Core coding agent logic
- **test_endpoint.py**: Test script for the deployed endpoint
- **core/**: Event system, SSE formatting, streaming helpers, security, errors
- **requirements.txt**: Python dependencies

## Key Features

- Real-time Server-Sent Events (SSE) streaming
- Modal serverless sandboxing
- Claude-4 Opus AI code analysis and modification
- GitHub PR automation
- Secure, event-driven architecture

## Setup

### Prerequisites
1. Python 3.8+
2. Modal account (https://modal.com)
3. GitHub Personal Access Token

### Installation
```bash
git clone <repo-url>
cd modal-coding-agent
pip install -r requirements.txt
modal token new
```

### Configuration
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

### API Endpoint
**POST /code**
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
```bash
python test_endpoint.py https://your-app.modal.run
```

## Implementation Status & TODOs
- [x] FastAPI SSE endpoint
- [x] Modal deployment
- [x] GitHub repo cloning
- [x] Anthropic Claude-4 Opus integration
- [x] Code analysis/modification workflow
- [x] Secure subprocess validation
- [x] Git branching/commit/PR
- [ ] Production monitoring
- [ ] Enhanced security hardening
- [ ] Comprehensive error handling

### High Priority TODOs
- [ ] Fix SSE output to match spec (Tool: Read/Edit/Bash, AI Message)
- [ ] Stream agent thinking process in real-time
- [ ] Fix agent timeout issues
- [ ] Test multi-file changes

### Medium/Low Priority
- [ ] Enhance error cycling visibility
- [ ] Implement observability (Datadog, metrics)
- [ ] Improve code quality, docstrings, error messages
- [ ] Add input validation, rate limiting, security logging
- [ ] Handle GitHub API rate limits gracefully
- [ ] Add comprehensive test suite
- [ ] Performance optimizations (repo caching, parallel analysis)
- [ ] Feature additions (private repos, multiple LLMs, webhooks)
- [ ] Refactor monolithic agent.py

## Architecture & Migration

- **V2**: Event-driven, real-time streaming, proper error handling, secure credential management, clean separation of concerns
- **V1**: Monolithic, synchronous, poor error handling, credentials in URLs
- **Migration**: See `ARCHITECTURE.md` for full details

## Security Considerations
- Only public GitHub repos supported
- Code runs in Modal sandboxes
- GitHub PAT stored as Modal secret
- Input validation on all endpoints
- Subprocess isolation for code validation
- (See `ARCHITECTURE.md` for advanced security notes)

## Quick Troubleshooting
- **SSE not streaming?**
  - Check Modal logs for errors
  - Ensure agent is using streaming API correctly
- **Timeouts?**
  - Increase Modal function timeout
  - Chunk large operations
- **PR not created?**
  - Check GitHub PAT permissions
  - See logs for error details
- **Agent fails on analysis?**
  - Ensure Anthropic API key is valid
  - See logs for stack traces

## Further Reading
- See `ARCHITECTURE.md` for design, migration, and event system details
- See `CODE_REVIEW_AND_STATUS.md` for review findings, open issues, and implementation status
- See `CLAUDE.md` for LLM/AI-specific notes