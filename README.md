# Backspace Coding Agent

A streaming API service that automatically creates GitHub pull requests from natural language descriptions. Built with FastAPI, Modal sandboxing, and Claude 3.5 Sonnet.

## 🚀 Live Demo

**Public URL**: https://arjun-ds--backspace-agent-modal-asgi.modal.run

## 📋 Deliverables

### 1. How to Hit the Public URL

The service is already deployed and configured with my GitHub PAT.

**Option 1: Use the Web UI**

- Go to https://arjun-ds--backspace-agent-modal-asgi.modal.run
- Enter `https://github.com/arjun-ds/tiny-backspace` as the repository URL (only this repo works with my deployment)
- Enter a coding prompt
- Click submit to see real-time progress

**Option 2: Use the Test Script**

```bash
# Clone this repo first
git clone https://github.com/arjun-ds/backspace-agent.git
cd backspace-agent

# Install dependencies
pip install -r requirements.txt

# Run the test script with custom prompt
python test_endpoint.py https://arjun-ds--backspace-agent-modal-asgi.modal.run \
  --repo https://github.com/arjun-ds/tiny-backspace \
  --prompt "Add a helpful comment explaining what the main function does"
```

**Example Input:**

- Repository URL: `https://github.com/arjun-ds/tiny-backspace`
- Prompt: `Add a helpful comment explaining what the main function does`

**Important**: My deployed service is restricted to only work with `arjun-ds/tiny-backspace` due to GitHub PAT permissions. It will create PRs using my GitHub account. You can view the created PRs but won't have merge access.

The API returns a Server-Sent Events (SSE) stream showing:

- Repository cloning progress
- File analysis (`Tool: Read` events)
- AI planning messages (`AI Message` events)
- Code changes being made (`Tool: Edit` events)
- Git operations (`Tool: Bash` events)
- Final PR URL

### 2. How to Run It Locally (Deploy Your Own Instance)

If you want to deploy your own instance to work with your own repositories:

#### Prerequisites

1. **Python 3.8+**
2. **Modal Account** - Sign up at https://modal.com
3. **Your Own GitHub Personal Access Token (PAT)**
   - Go to https://github.com/settings/tokens/new
   - Select scopes: `repo` (Full control of private repositories)
   - Copy the generated token
4. **Your Own Anthropic API Key**
   - Sign up at https://www.anthropic.com
   - Go to https://console.anthropic.com/settings/keys
   - Create a new API key

#### Step-by-Step Setup

```bash
# 1. Clone this repository
git clone https://github.com/arjun-ds/backspace-agent.git
cd backspace-agent

# 2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install and authenticate Modal
modal token new
# This will open a browser - log in with your Modal account

# 5. Set up Modal secrets with YOUR credentials
modal secret create github-token GITHUB_TOKEN=<your-github-pat>
modal secret create anthropic ANTHROPIC_API_KEY=<your-anthropic-key>

# 6. Build the frontend (Next.js)
cd ../web
npm install
npm run build  # Creates the 'out' directory
cd ../backspace-agent

# 7. Deploy to Modal
modal deploy main.py

# 8. Test your deployment
# Your deployment will be available at a URL like:
# https://your-username--backspace-agent-modal-asgi.modal.run

# Use the same test script with YOUR Modal URL:
python test_endpoint.py https://your-username--backspace-agent-modal-asgi.modal.run \
  --repo https://github.com/your-username/your-repo \
  --prompt "Your coding task here"
```

### 3. Which Coding Agent Approach I Chose and Why

The agent follows this workflow:

1. **Intelligent File Selection**:

   - Reads README files first to understand project structure
   - Prioritizes files mentioned in documentation
   - Limits to 20 files (1MB each) for memory efficiency

2. **Robust JSON Parsing**:

   - Uses regex-based extraction to handle various response formats
   - Validates JSON structure before processing
   - No fallback mechanisms - fails cleanly on errors

3. **Streaming Architecture**:
   - Real-time SSE updates for transparency
   - Event-driven design matching the spec format
   - Comprehensive logging with optional LangSmith observability

## 🏗️ Architecture

### Core Components

- **main.py**: FastAPI server with SSE streaming endpoint
- **agent.py**: Coding agent logic with Claude integration
- **Modal**: Provides both web hosting and sandboxed execution environment

### Security Features

- Runs in Modal's isolated containers
- GitHub PAT stored as Modal secret (never exposed)
- Only supports public repositories
- Automatic cleanup of temporary files

### Event Stream Format

```json
data: {"type": "Tool: Read", "filepath": "app.py"}
data: {"type": "AI Message", "message": "Analyzing codebase..."}
data: {"type": "Tool: Edit", "filepath": "app.py", "old_str": "...", "new_str": "..."}
data: {"type": "Tool: Bash", "command": "git add .", "output": ""}
data: {"type": "complete", "pr_url": "https://github.com/owner/repo/pull/123"}
```

## 📊 Observability

The agent includes comprehensive logging throughout the workflow:

- Repository cloning status
- File analysis progress
- AI decision making
- Git operations
- Error tracking

### LangSmith Integration (Bonus Feature)

The agent includes optional LangSmith integration for advanced observability:

**What it provides:**

- Real-time tracing of the agent's thinking process
- Detailed view of Claude API calls with prompts and responses
- Performance metrics for each step (latency, token usage)
- Visual trace explorer to debug issues
- Helps identify why certain changes were made or skipped

**To enable:**

```bash
# Sign up at https://www.langchain.com/langsmith
modal secret create langsmith LANGSMITH_API_KEY=<your-key> LANGSMITH_ENABLED=true LANGSMITH_PROJECT=backspace-agent
```

Once enabled, you can view traces at https://smith.langchain.com for real-time telemetry and insights into the agent's decision-making process.

## 🛠️ Troubleshooting

### Common Issues

1. **"GitHub token not configured"**

   - Ensure you've run: `modal secret create github-token GITHUB_TOKEN=<pat>`

2. **"Anthropic API key not configured"**

   - Ensure you've run: `modal secret create anthropic ANTHROPIC_API_KEY=<key>`

3. **Modal deployment fails**

   - Check you're authenticated: `modal token`
   - Try redeploying: `modal deploy main.py --force`

4. **PR creation fails**

   - Verify your GitHub PAT has `repo` scope
   - Check the repository is public
   - Ensure you have push access to the repository

5. **Agent timeout**
   - Large repositories may take longer to process
   - The agent limits to 20 files for efficiency

## 📝 Notes

- Only public GitHub repositories are supported
- The agent creates PRs under your GitHub account
- Each request runs in an isolated Modal container
- File size limit: 1MB per file, max 20 files per repository

## 🎥 Demo Video

[Optional: Add link to demo video here]
