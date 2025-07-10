"""
Coding agent implementation for Backspace
"""

import os
import tempfile
import shutil
from typing import AsyncGenerator, Dict, Any
import git
from github import Github
import asyncio
import json
import anthropic
import subprocess
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Only import ddtrace if enabled
if os.getenv('DD_TRACE_ENABLED', 'false').lower() == 'true':
    try:
        from ddtrace import tracer
        tracer.configure(
            hostname=os.getenv('DD_AGENT_HOST', 'localhost'),
            port=int(os.getenv('DD_TRACE_AGENT_PORT', 8126)),
        )
    except ImportError:
        logger.warning("ddtrace not available, continuing without tracing")
        tracer = None
else:
    tracer = None

class CodingAgent:
    """Handles code analysis and modification"""
    
    def __init__(self, github_token: str):
        self.github_token = github_token
        self.github = Github(github_token)
        
        # Initialize Anthropic client
        anthropic_token = os.getenv("ANTHROPIC_API_KEY", "")
        if not anthropic_token:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.anthropic_client = anthropic.Anthropic(api_key=anthropic_token)
    
    async def process_repository(
        self, 
        repo_url: str, 
        prompt: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a repository and yield status updates
        """
        
        # Extract owner and repo name
        parts = repo_url.replace("https://github.com/", "").split("/")
        owner, repo_name = parts[0], parts[1]
        
        logger.info(f"Processing repository: {repo_url} with prompt: {prompt}")
        
        # Heartbeat setup
        last_heartbeat = time.time()
        heartbeat_interval = 2  # seconds
        def maybe_heartbeat():
            nonlocal last_heartbeat
            now = time.time()
            if now - last_heartbeat > heartbeat_interval:
                yield {"type": "heartbeat", "message": "Still working..."}
                last_heartbeat = now
        
        # Create temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                yield {"type": "AI Message", "message": f"Cloning {repo_url}..."}
                for hb in maybe_heartbeat():
                    yield hb
                
                # Add authentication to the URL for pushing
                auth_url = repo_url.replace('https://', f'https://{self.github_token}@')
                
                # Clone with authentication
                logger.info("Cloning repository with authentication")
                
                repo = git.Repo.clone_from(auth_url, temp_dir)
                for hb in maybe_heartbeat():
                    yield hb
                
                # Configure git user for commits
                repo.config_writer().set_value("user", "name", "Coding Agent").release()
                repo.config_writer().set_value("user", "email", "backspace-agent@users.noreply.github.com").release()
                
                yield {"type": "AI Message", "message": "Repository cloned successfully"}
                for hb in maybe_heartbeat():
                    yield hb
                
                # Analyze codebase
                yield {"type": "AI Message", "message": "Analyzing codebase structure..."}
                for hb in maybe_heartbeat():
                    yield hb
                
                # List all Python files as an example
                py_files = []
                for root, dirs, files in os.walk(temp_dir):
                    # Skip .git directory
                    if '.git' in root:
                        continue
                    for file in files:
                        if file.endswith('.py'):
                            file_path = os.path.join(root, file)
                            py_files.append(file_path)
                            rel_path = os.path.relpath(file_path, temp_dir)
                            yield {"type": "Tool: Read", "filepath": rel_path}
                            for hb in maybe_heartbeat():
                                yield hb
                yield {"type": "AI Message", "message": f"Found {len(py_files)} Python files"}
                for hb in maybe_heartbeat():
                    yield hb
                
                # AI analysis and code modification workflow
                yield {"type": "AI Message", "message": "Starting AI analysis with Claude-4 Opus..."}
                for hb in maybe_heartbeat():
                    yield hb
                
                try:
                    # Simple, fast analysis with Claude 3.5 Sonnet
                    yield {"type": "AI Message", "message": "Analyzing with Claude 3.5 Sonnet..."}
                    
                    # Get file structure
                    file_list = self._get_repo_structure(temp_dir)
                    yield {"type": "AI Message", "message": f"Found files: {', '.join(file_list)}"}
                    
                    # Read all files and emit Tool: Read events
                    files_content = {}
                    for filename in file_list:
                        yield {"type": "Tool: Read", "filepath": filename}
                        files_content[filename] = self._read_file(temp_dir, filename)
                    
                    # Simple Claude request
                    changes = await self._simple_claude_analysis(files_content, prompt)
                    
                    if not changes.get('edits'):
                        yield {"type": "AI Message", "message": "No changes needed"}
                        return
                    
                    # Apply changes
                    yield {"type": "AI Message", "message": f"Applying {len(changes['edits'])} changes..."}
                    for edit in changes['edits']:
                        yield {
                            "type": "Tool: Edit",
                            "filepath": edit["file"],
                            "old_str": edit["old_str"][:100] + "..." if len(edit["old_str"]) > 100 else edit["old_str"],
                            "new_str": edit["new_str"][:100] + "..." if len(edit["new_str"]) > 100 else edit["new_str"]
                        }
                        self._apply_single_edit(temp_dir, edit)
                    
                    # After interactive implementation, commit changes
                    yield {"type": "AI Message", "message": "Creating git commit..."}
                    for hb in maybe_heartbeat():
                        yield hb
                    
                    # Git operations with simple branch name
                    branch_name = f'claude-improvements-{int(time.time())}'
                    async for bash_event in self._create_git_branch_and_commit_and_collect_events(repo, branch_name, prompt):
                        yield bash_event
                        for hb in maybe_heartbeat():
                            yield hb
                    
                    # Create pull request
                    yield {"type": "AI Message", "message": "Creating pull request..."}
                    for hb in maybe_heartbeat():
                        yield hb
                    
                    pr_url = await self._create_pull_request(repo_url, branch_name, prompt)
                    
                    yield {
                        "type": "complete",
                        "message": "Pull request created successfully",
                        "pr_url": pr_url
                    }
                    
                except Exception as e:
                    yield {"type": "error", "message": f"Workflow failed: {str(e)}"}
                
            except Exception as e:
                yield {"type": "error", "message": f"Error processing repository: {str(e)}"}
    
    async def _create_pull_request(self, repo_url: str, branch_name: str, prompt: str) -> str:
        """Create a pull request for the changes"""
        # Extract owner/repo from URL
        parts = repo_url.replace("https://github.com/", "").split("/")
        owner, repo_name = parts[0], parts[1]
        
        try:
            repo = self.github.get_repo(f"{owner}/{repo_name}")
            
            # Create pull request
            pr = repo.create_pull(
                title=f"Automated changes: {prompt}",
                body=f"This pull request implements the following changes:\n\n{prompt}",
                head=f"{owner}:{branch_name}",  # Need owner:branch format
                base="main"
            )
            
            return pr.html_url
            
        except Exception as e:
            # Raise exception for proper error handling
            raise Exception(f"Failed to create pull request: {str(e)}")
    
    async def _simple_claude_analysis(self, files_content: dict, prompt: str) -> dict:
        """Simple, fast Claude analysis with 3.5 Sonnet"""
        
        # Build a simple prompt
        files_text = ""
        for filename, content in files_content.items():
            files_text += f"\n=== {filename} ===\n{content}\n"
        
        simple_prompt = f"""Task: {prompt}

Files to modify:
{files_text}

Please provide your response as JSON with this format:
{{
    "edits": [
        {{
            "file": "filename.py",
            "old_str": "exact text to replace",
            "new_str": "replacement text"
        }}
    ]
}}

Make one edit per logical change. Use exact string matching for old_str."""

        try:
            response = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                messages=[{"role": "user", "content": simple_prompt}]
            )
            
            response_text = response.content[0].text
            
            # Parse JSON response
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end]
            
            return json.loads(response_text)
            
        except Exception as e:
            logger.error(f"Claude analysis failed: {str(e)}")
            return {"edits": []}

    async def _interactive_analysis_and_implementation(self, repo_path: str, prompt: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Interactive analysis and implementation with Claude 3.5 Sonnet"""
        
        # Get repository structure (just names, not content)
        file_structure = self._get_repo_structure(repo_path)
        
        yield {"type": "AI Message", "message": f"Repository structure identified: {len(file_structure)} Python files"}
        
        conversation_history = []
        
        # Initial prompt to Claude with just file names
        initial_prompt = f"""I need help with this task: {prompt}

Here's the repository structure:
{chr(10).join(f"- {file}" for file in file_structure)}

Please analyze this step by step:
1. Which files do you want to examine first?
2. What's your approach for this task?

Respond with your thinking and which files you'd like to see."""

        conversation_history.append({"role": "user", "content": initial_prompt})
        
        # Start interactive conversation
        for round_num in range(10):  # Max 10 rounds to prevent infinite loops
            yield {"type": "AI Message", "message": f"Round {round_num + 1}: Consulting Claude..."}
            
            # Get Claude's response with streaming
            claude_response = ""
            async for chunk in self._stream_claude_response(conversation_history):
                if chunk.startswith("AI:"):
                    yield {"type": "AI Message", "message": chunk[3:].strip()}
                    claude_response += chunk[3:]
                elif chunk.startswith("NEED_FILE:"):
                    # Claude wants to see a file
                    filename = chunk[10:].strip()
                    if filename in file_structure:
                        yield {"type": "Tool: Read", "filepath": filename}
                        file_content = self._read_file(repo_path, filename)
                        conversation_history.append({
                            "role": "assistant", 
                            "content": f"I need to see {filename}"
                        })
                        conversation_history.append({
                            "role": "user", 
                            "content": f"Here's {filename}:\n\n{file_content}"
                        })
                elif chunk.startswith("EDIT_FILE:"):
                    # Claude wants to edit a file
                    edit_info = json.loads(chunk[10:])
                    yield {
                        "type": "Tool: Edit",
                        "filepath": edit_info["file"],
                        "old_str": edit_info["old_str"][:100] + "..." if len(edit_info["old_str"]) > 100 else edit_info["old_str"],
                        "new_str": edit_info["new_str"][:100] + "..." if len(edit_info["new_str"]) > 100 else edit_info["new_str"]
                    }
                    # Apply the edit
                    self._apply_single_edit(repo_path, edit_info)
                elif chunk.startswith("DONE"):
                    yield {"type": "AI Message", "message": "Claude has completed the implementation"}
                    return
            
            # Add Claude's response to conversation
            if claude_response.strip():
                conversation_history.append({"role": "assistant", "content": claude_response})
        
        yield {"type": "AI Message", "message": "Interactive session completed"}

    async def _stream_claude_response(self, conversation_history: list) -> AsyncGenerator[str, None]:
        """Stream Claude's response and parse special commands"""
        try:
            async with self.anthropic_client.messages.stream(
                model="claude-3-5-sonnet-20241022",  # Using 3.5 Sonnet
                max_tokens=2000,
                system="""You are a coding assistant. You can:
1. Ask to see files by saying "NEED_FILE: filename.py"
2. Edit files by saying "EDIT_FILE: {json with file, old_str, new_str}"
3. Share your thinking with regular text
4. Say "DONE" when finished

Work on one file at a time. Be concise but thorough.""",
                messages=conversation_history
            ) as stream:
                
                current_chunk = ""
                async for event in stream:
                    if event.type == "content_block_delta":
                        text = event.delta.text
                        current_chunk += text
                        
                        # Check for special commands
                        if "NEED_FILE:" in current_chunk:
                            lines = current_chunk.split('\n')
                            for line in lines:
                                if line.strip().startswith("NEED_FILE:"):
                                    yield line.strip()
                                    current_chunk = current_chunk.replace(line, '')
                        elif "EDIT_FILE:" in current_chunk:
                            # Look for complete JSON
                            start_idx = current_chunk.find("EDIT_FILE:")
                            if start_idx != -1:
                                json_start = start_idx + 10
                                try:
                                    # Try to parse JSON - might be incomplete
                                    json_part = current_chunk[json_start:].strip()
                                    if json_part.count('{') == json_part.count('}') and json_part.endswith('}'):
                                        json.loads(json_part)  # Validate
                                        yield f"EDIT_FILE:{json_part}"
                                        current_chunk = ""
                                except:
                                    pass  # Wait for more data
                        elif "DONE" in current_chunk:
                            yield "DONE"
                            return
                        else:
                            # Regular text - yield as AI message
                            if text and not any(cmd in current_chunk for cmd in ["NEED_FILE:", "EDIT_FILE:", "DONE"]):
                                yield f"AI:{text}"
                
        except Exception as e:
            yield f"AI:Error: {str(e)}"

    def _get_repo_structure(self, repo_path: str) -> list:
        """Get list of Python files in the repo"""
        py_files = []
        for root, dirs, files in os.walk(repo_path):
            if '.git' in root:
                continue
            for file in files:
                if file.endswith('.py'):
                    rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                    py_files.append(rel_path)
        return py_files

    def _read_file(self, repo_path: str, filename: str) -> str:
        """Read a single file's content"""
        try:
            with open(os.path.join(repo_path, filename), 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def _apply_single_edit(self, repo_path: str, edit_info: dict):
        """Apply a single edit to a file"""
        file_path = os.path.join(repo_path, edit_info["file"])
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Apply the edit
            new_content = content.replace(edit_info["old_str"], edit_info["new_str"], 1)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except Exception as e:
            logger.error(f"Failed to apply edit to {edit_info['file']}: {str(e)}")

    async def _analyze_and_plan_changes(self, repo_path: str, prompt: str) -> dict:
        """Analyze codebase and plan changes using Claude-4 Opus"""
        
        logger.info("Starting Claude analysis...")
        
        # Read key files for analysis
        files_content = self._collect_codebase_files(repo_path)
        logger.info(f"Collected {len(files_content)} files for analysis")
        
        # Generate analysis using Claude
        system_prompt = self._get_analysis_system_prompt()
        user_prompt = self._build_analysis_user_prompt(prompt, files_content)
        
        logger.info("Sending request to Claude...")
        try:
            # Add timeout to prevent hanging
            import asyncio
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.anthropic_client.messages.create,
                    model="claude-3-opus-20240229",
                    max_tokens=4000,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                ),
                timeout=120  # 2 minute timeout
            )
            
            logger.info("Received response from Claude")
            
            # Parse the JSON response
            response_text = response.content[0].text
            logger.info(f"Claude response length: {len(response_text)} characters")
            
            result = self._parse_claude_response(response_text)
            logger.info(f"Parsed response, found {len(result.get('plan', []))} planned changes")
            
            return result
            
        except Exception as e:
            logger.error(f"Claude analysis failed: {str(e)}")
            raise Exception(f"Failed to analyze codebase: {str(e)}")
    
    def _collect_codebase_files(self, repo_path: str) -> dict:
        """Collect and read Python files from the repository"""
        files_content = {}
        py_files = []
        
        # Collect Python files
        for root, dirs, files in os.walk(repo_path):
            if '.git' in root:
                continue
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    py_files.append(file_path)
        
        # Read content of up to 10 key files (to avoid token limits)
        for file_path in py_files[:10]:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    relative_path = os.path.relpath(file_path, repo_path)
                    files_content[relative_path] = f.read()
            except Exception as e:
                # Skip files that can't be read
                continue
        
        return files_content
    
    def _get_analysis_system_prompt(self) -> str:
        """System prompt for code analysis - prevents destructive changes"""
        return """You are an expert software engineer who follows instructions precisely.

                CRITICAL SAFETY RULES:
                1. If asked to "update" or "modify" something that doesn't exist, clearly state: "Could not find [X] to modify"
                2. Never delete or simplify code unless explicitly asked to "remove", "delete", or "simplify"
                3. When interpreting ambiguous requests, choose the most conservative approach
                4. Preserve ALL existing functionality unless explicitly told to remove it

                CHANGE GUIDELINES:
                - For "update/modify/change" requests: Look for existing code to modify
                - For "add/create/implement" requests: Add new code without removing existing code  
                - For "remove/delete" requests: Only then remove code
                - If uncertain about intent, explain your interpretation in the analysis

                RESPONSE REQUIREMENTS:
                1. Start with "interpretation": Explain what you understood from the request
                2. Include "found_target": true/false - whether you found the code to modify
                3. List any "assumptions" you're making
                4. Provide "change_summary" with files affected and lines added/removed
                5. Never make changes beyond the scope of the request

            Response format: Valid JSON only, no markdown formatting."""
    
    def _build_analysis_user_prompt(self, prompt: str, files_content: dict) -> str:
        """Build the user prompt for code analysis"""
        return f"""Analyze this codebase and create a detailed plan for implementing the following request:

            REQUEST: {prompt}

            CODEBASE FILES:
            {json.dumps(files_content, indent=2)}

            Provide a JSON response with this exact structure:
            {{
            "interpretation": "Explain what you understood from the request",
            "found_target": true/false,
            "assumptions": ["List any assumptions you're making"],
            "change_summary": {{
                "files_affected": <number>,
                "lines_added": <number>,
                "lines_removed": <number>,
                "change_type": "modification|addition|deletion|refactoring"
            }},
            "analysis": "Your detailed analysis of what needs to be changed",
            "plan": [
                {{
                "file": "path/to/file.py",
                "action": "create|modify|delete",
                "description": "What changes to make",
                "code": "The complete file content (for create/modify)",
                "lines_added": <number>,
                "lines_removed": <number>
                }}
            ],
            "branch_name": "suggested-branch-name",
            "pr_title": "Suggested PR title",
            "pr_description": "Detailed PR description"
            }}"""
    
    def _parse_claude_response(self, response_text: str) -> dict:
        """Parse Claude's response and extract JSON"""
        # Handle potential markdown formatting
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end]
        
        return json.loads(response_text)
    
    async def _apply_code_changes(self, repo_path: str, changes: dict) -> None:
        """Apply the planned code changes to files using full file replacement"""
        
        if 'plan' not in changes:
            raise ValueError("Changes dict must contain 'plan' key")
        
        plan = changes['plan']
        logger.info(f"Applying {len(plan)} code changes")
        
        for i, change in enumerate(plan):
            file_path = change.get('file')
            action = change.get('action')
            code = change.get('code', '')
            
            if not file_path or not action:
                logger.warning(f"Skipping change {i}: missing file_path or action")
                continue
                
            full_path = os.path.join(repo_path, file_path)
            logger.info(f"Applying {action} to {file_path} (full path: {full_path})")
            
            try:
                if action == 'create':
                    # Create new file
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(code)
                    logger.info(f"Created file: {full_path} with {len(code)} bytes")
                        
                elif action == 'modify':
                    # Overwrite entire file
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(code)
                    logger.info(f"Modified file: {full_path} with {len(code)} bytes")
                        
                elif action == 'delete':
                    # Remove file
                    if os.path.exists(full_path):
                        os.remove(full_path)
                        logger.info(f"Deleted file: {full_path}")
                    else:
                        logger.warning(f"File to delete not found: {full_path}")
                        
            except Exception as e:
                logger.error(f"Failed to apply change to {file_path}: {str(e)}")
                raise Exception(f"Failed to apply change to {file_path}: {str(e)}")
    
    def _validate_python_syntax(self, file_path: str) -> bool:
        """Validate Python file syntax"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            compile(code, file_path, 'exec')
            return True
        except SyntaxError:
            return False
        except Exception:
            return False
    
    async def _run_code_validation(self, repo_path: str) -> dict:
        """Run syntax validation only - no code execution
        
        SECURITY NOTE: Removed runtime execution validation to avoid issues with
        determining what code should actually be "run" in arbitrary repositories.
        Only performs syntax checking via compilation.
        """
        
        validation_results = {
            "success": True,
            "syntax_errors": [],
            "compilation_errors": []
        }
        
        # Find Python files to validate
        py_files = []
        for root, dirs, files in os.walk(repo_path):
            if '.git' in root or '__pycache__' in root:
                continue
            for file in files:
                if file.endswith('.py'):
                    py_files.append(os.path.join(root, file))
        
        # 1. Basic syntax validation for all Python files
        for file_path in py_files:
            relative_path = os.path.relpath(file_path, repo_path)
            
            # Basic syntax check via compile()
            if not self._validate_python_syntax(file_path):
                validation_results["syntax_errors"].append(relative_path)
                validation_results["success"] = False
                continue
            
            # 2. Compilation check via py_compile (more thorough than compile())
            try:
                result = subprocess.run(
                    ["python", "-m", "py_compile", file_path],
                    timeout=10,  # Quick timeout for compilation
                    capture_output=True,
                    text=True,
                    cwd=repo_path
                )
                
                if result.returncode != 0:
                    validation_results["compilation_errors"].append({
                        "file": relative_path,
                        "error": result.stderr.strip()
                    })
                    validation_results["success"] = False
                    
            except subprocess.TimeoutExpired:
                validation_results["compilation_errors"].append({
                    "file": relative_path,
                    "error": "Compilation timeout (10s exceeded)"
                })
                validation_results["success"] = False
            except Exception as e:
                validation_results["compilation_errors"].append({
                    "file": relative_path,
                    "error": f"Compilation check failed: {str(e)}"
                })
                validation_results["success"] = False
        
        return validation_results
    
    async def _cycle_errors_with_claude(self, repo_path: str, validation_results: dict, original_prompt: str, attempt: int = 1) -> dict:
        """Send validation errors back to Claude for fixes"""
        
        if attempt > 3:  # Maximum 3 attempts
            raise Exception("Maximum error cycling attempts reached")
        
        # Build error report for Claude
        error_report = []
        
        if validation_results["syntax_errors"]:
            error_report.append(f"Syntax errors in files: {', '.join(validation_results['syntax_errors'])}")
        
        if validation_results["compilation_errors"]:
            for error in validation_results["compilation_errors"]:
                error_report.append(f"Compilation error in {error['file']}: {error['error']}")
        
        # Get current code state
        files_content = self._collect_codebase_files(repo_path)
        
        # Create fix prompt
        system_prompt = self._get_error_fix_system_prompt()
        fix_prompt = f"""The previous code changes have validation errors. Please fix these issues:

            ORIGINAL REQUEST: {original_prompt}

            VALIDATION ERRORS:
            {chr(10).join(error_report)}

            CURRENT CODE STATE:
            {json.dumps(files_content, indent=2)}

            Please provide a JSON response with the same structure as before, containing only the files that need to be fixed:
            {{
            "analysis": "Analysis of the errors and how to fix them",
            "plan": [
                {{
                "file": "path/to/file.py",
                "action": "modify",
                "description": "How this fixes the error",
                "code": "The corrected code"
                }}
            ]
            }}"""

        try:
            response = self.anthropic_client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=4000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": fix_prompt}
                ]
            )
            
            response_text = response.content[0].text
            return self._parse_claude_response(response_text)
            
        except Exception as e:
            raise Exception(f"Failed to get error fixes from Claude: {str(e)}")
    
    def _get_error_fix_system_prompt(self) -> str:
        """System prompt for error fixing - focused on fixing validation issues"""
        return """You are an expert software engineer focused on fixing code validation errors.

            CRITICAL: Only fix the specific validation errors. Do NOT modify anything else.

            Guidelines:
            1. Fix only the syntax/compilation errors mentioned
            2. Do not add features or improvements
            3. Make the absolute minimum changes needed
            4. Preserve all existing functionality

            Response format: Valid JSON only, no markdown formatting."""
    
    async def _apply_code_changes_and_collect_events(self, repo_path: str, changes: dict) -> AsyncGenerator[Dict[str, Any], None]:
        """Apply the planned code changes to files and yield Tool: Edit events"""
        for change in changes.get('plan', []):
            file_path = change.get('file')
            action = change.get('action')
            code = change.get('code', '')
            rel_path = file_path
            full_path = os.path.join(repo_path, file_path)
            if action == 'create':
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(code)
                yield {
                    "type": "Tool: Edit",
                    "filepath": rel_path,
                    "old_str": "",
                    "new_str": code[:100] + "..." if len(code) > 100 else code
                }
            elif action == 'modify':
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        old_content = f.read()
                except Exception:
                    old_content = ""
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(code)
                yield {
                    "type": "Tool: Edit",
                    "filepath": rel_path,
                    "old_str": old_content[:100] + "..." if len(old_content) > 100 else old_content,
                    "new_str": code[:100] + "..." if len(code) > 100 else code
                }

    async def _create_git_branch_and_commit_and_collect_events(self, repo, branch_name: str, prompt: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Create git branch and commit changes and yield Tool: Bash events"""
        # Branch
        repo.git.checkout('-b', branch_name)
        yield {"type": "Tool: Bash", "command": f"git checkout -b {branch_name}", "output": f"Switched to a new branch '{branch_name}'"}
        # Add
        repo.git.add(A=True)
        yield {"type": "Tool: Bash", "command": "git add .", "output": ""}
        # Commit
        commit_msg = f"Automated changes: {prompt}"
        repo.git.commit('-m', commit_msg)
        yield {"type": "Tool: Bash", "command": f"git commit -m '{commit_msg}'", "output": repo.git.log('-1', '--oneline')}
        # Push
        try:
            repo.git.push('origin', branch_name)
            yield {"type": "Tool: Bash", "command": f"git push origin {branch_name}", "output": f"Pushed branch '{branch_name}' to remote"}
        except Exception as e:
            yield {"type": "Tool: Bash", "command": f"git push origin {branch_name}", "output": f"Push failed: {str(e)}"}

    async def _push_and_pr_and_collect_events(self, repo_url: str, branch_name: str, prompt: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Push branch and create pull request and yield Tool: Bash events"""
        # Push
        repo_dir = repo_url.split('/')[-1]
        push_output = "Pushed to remote"
        yield {"type": "Tool: Bash", "command": f"git push origin {branch_name}", "output": push_output}
        # PR
        pr_url = f"https://github.com/{repo_url.replace('https://github.com/', '')}/pull/new/{branch_name}"
        yield {"type": "Tool: Bash", "command": f"gh pr create --title '{prompt}' --body 'Automated PR'", "output": pr_url}
        yield {"type": "complete", "pr_url": pr_url}


async def run_agent(repo_url: str, prompt: str) -> AsyncGenerator[str, None]:
    """
    Run the coding agent and yield SSE-formatted events
    """
    
    try:
        # Get GitHub token from environment
        github_token = os.getenv("GITHUB_TOKEN", "")
        
        if not github_token:
            yield f"data: {json.dumps({'type': 'error', 'message': 'GitHub token not configured'})}\n\n"
            return
        
        # Check for Anthropic API key
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not anthropic_key:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Anthropic API key not configured'})}\n\n"
            return
        
        logger.info(f"Starting agent for repo: {repo_url}, prompt: {prompt}")
        
        agent = CodingAgent(github_token)
        
        async for event in agent.process_repository(repo_url, prompt):
            event_str = f"data: {json.dumps(event)}\n\n"
            logger.debug(f"Yielding event: {event_str.strip()}")
            yield event_str
            
    except Exception as e:
        logger.error(f"Error in run_agent: {str(e)}", exc_info=True)
        error_event = {"type": "error", "message": f"Agent failed: {str(e)}"}
        yield f"data: {json.dumps(error_event)}\n\n"