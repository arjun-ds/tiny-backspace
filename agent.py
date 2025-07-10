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
        
        # Create temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Clone repository with authentication
                yield {"type": "status", "stage": "clone", "message": f"Cloning {repo_url}..."}
                
                # Add authentication to the URL for pushing
                auth_url = repo_url.replace('https://', f'https://{self.github_token}@')
                
                # Clone with authentication
                logger.info("Cloning repository with authentication")
                
                repo = git.Repo.clone_from(auth_url, temp_dir)
                
                # Configure git user for commits
                repo.config_writer().set_value("user", "name", "Coding Agent").release()
                repo.config_writer().set_value("user", "email", "backspace-agent@users.noreply.github.com").release()
                
                yield {"type": "status", "stage": "clone", "message": "Repository cloned successfully"}
                
                # Analyze codebase
                yield {"type": "status", "stage": "analyze", "message": "Analyzing codebase structure..."}
                
                # List all Python files as an example
                py_files = []
                for root, dirs, files in os.walk(temp_dir):
                    # Skip .git directory
                    if '.git' in root:
                        continue
                    for file in files:
                        if file.endswith('.py'):
                            py_files.append(os.path.join(root, file))
                
                yield {
                    "type": "status", 
                    "stage": "analyze", 
                    "message": f"Found {len(py_files)} Python files"
                }
                
                # AI analysis and code modification workflow
                yield {"type": "status", "stage": "analyze", "message": "Starting AI analysis with Claude-4 Opus..."}
                
                try:
                    # Analyze codebase and plan changes
                    changes = await self._analyze_and_plan_changes(temp_dir, prompt)
                    
                    logger.info(f"Claude planned {len(changes.get('plan', []))} changes")
                    logger.debug(f"Change plan: {json.dumps(changes, indent=2)}")
                    
                    yield {
                        "type": "status", 
                        "stage": "analyze", 
                        "message": f"Analysis complete. Planning {len(changes.get('plan', []))} changes"
                    }
                    
                    # Stream change preview
                    yield {
                        "type": "preview",
                        "stage": "preview",
                        "interpretation": changes.get("interpretation", ""),
                        "found_target": changes.get("found_target", None),
                        "assumptions": changes.get("assumptions", []),
                        "change_summary": changes.get("change_summary", {}),
                        "files_to_change": [
                            {
                                "file": change["file"],
                                "action": change["action"],
                                "lines_added": change.get("lines_added", 0),
                                "lines_removed": change.get("lines_removed", 0),
                                "description": change.get("description", "")
                            } for change in changes.get("plan", [])
                        ]
                    }
                    
                    # Apply code changes
                    yield {"type": "status", "stage": "modify", "message": "Applying code changes..."}
                    await self._apply_code_changes(temp_dir, changes)
                    
                    # Validate code with error cycling
                    yield {"type": "status", "stage": "validate", "message": "Running comprehensive code validation..."}
                    
                    attempt = 1
                    max_attempts = 3
                    validation_passed = False
                    
                    while attempt <= max_attempts and not validation_passed:
                        validation_results = await self._run_code_validation(temp_dir)
                        
                        if validation_results["success"]:
                            validation_passed = True
                            yield {"type": "status", "stage": "validate", "message": "Code validation successful"}
                        else:
                            yield {
                                "type": "status", 
                                "stage": "validate", 
                                "message": f"Validation failed (attempt {attempt}/{max_attempts}), asking Claude to fix errors..."
                            }
                            
                            if attempt < max_attempts:
                                # Get fixes from Claude
                                fixes = await self._cycle_errors_with_claude(temp_dir, validation_results, prompt, attempt)
                                
                                # Apply fixes
                                yield {"type": "status", "stage": "fix", "message": "Applying error fixes..."}
                                await self._apply_code_changes(temp_dir, fixes)
                                
                                attempt += 1
                            else:
                                # Max attempts reached
                                error_summary = []
                                if validation_results["syntax_errors"]:
                                    error_summary.append(f"Syntax errors: {', '.join(validation_results['syntax_errors'])}")
                                if validation_results["compilation_errors"]:
                                    error_summary.append(f"Compilation errors: {len(validation_results['compilation_errors'])} files")
                                
                                yield {
                                    "type": "error",
                                    "message": f"Validation failed after {max_attempts} attempts: {'; '.join(error_summary)}"
                                }
                                return
                    
                    # Check git status before commit
                    git_status = repo.git.status()
                    
                    # Create git branch and commit
                    branch_name = changes.get('branch_name', f'agent-changes-{int(asyncio.get_event_loop().time())}')
                    yield {"type": "status", "stage": "commit", "message": f"Creating branch '{branch_name}'..."}
                    await self._create_git_branch_and_commit(repo, branch_name, prompt)
                    
                    # Create pull request
                    yield {"type": "status", "stage": "pr", "message": "Creating pull request..."}
                    pr_url = await self._create_pull_request(repo_url, branch_name, prompt)
                    
                    yield {
                        "type": "complete",
                        "message": "Pull request created successfully",
                        "pr_url": pr_url
                    }
                    
                except Exception as e:
                    yield {
                        "type": "error",
                        "message": f"Workflow failed: {str(e)}"
                    }
                
            except Exception as e:
                yield {
                    "type": "error",
                    "message": f"Error processing repository: {str(e)}"
                }
    
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
                head=branch_name,
                base="main"
            )
            
            return pr.html_url
            
        except Exception as e:
            # Raise exception for proper error handling
            raise Exception(f"Failed to create pull request: {str(e)}")
    
    async def _analyze_and_plan_changes(self, repo_path: str, prompt: str) -> dict:
        """Analyze codebase and plan changes using Claude-4 Opus"""
        
        # Read key files for analysis
        files_content = self._collect_codebase_files(repo_path)
        
        # Generate analysis using Claude
        system_prompt = self._get_analysis_system_prompt()
        user_prompt = self._build_analysis_user_prompt(prompt, files_content)
        
        try:
            response = self.anthropic_client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=4000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            # Parse the JSON response
            response_text = response.content[0].text
            return self._parse_claude_response(response_text)
            
        except Exception as e:
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
    
    async def _create_git_branch_and_commit(self, repo, branch_name: str, prompt: str) -> None:
        """Create git branch and commit changes"""
        
        try:
            # Create and checkout new branch
            new_branch = repo.create_head(branch_name)
            repo.head.reference = new_branch
            
            # Stage all changes - use the git command directly
            repo.git.add('-A')
            
            # Log what's staged
            staged_files = repo.git.diff('--cached', '--name-only')
            logger.info(f"Staged files: {staged_files}")
            
            # Check if there are any changes to commit
            if repo.is_dirty() or repo.untracked_files:
                # Commit changes
                commit_message = f"Implement: {prompt}"
                repo.index.commit(commit_message)
                
                # Push branch to remote
                try:
                    origin = repo.remote('origin')
                    origin.push(new_branch)
                    logger.info(f"Successfully pushed branch {branch_name}")
                except Exception as push_error:
                    logger.error(f"Failed to push branch: {push_error}")
                    raise Exception(f"Cannot create PR without pushing branch: {str(push_error)}")
            else:
                raise Exception("No changes to commit")
                
        except Exception as e:
            raise Exception(f"Failed to create branch and commit: {str(e)}")


async def run_agent(repo_url: str, prompt: str) -> AsyncGenerator[str, None]:
    """
    Run the coding agent and yield SSE-formatted events
    """
    
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
    
    agent = CodingAgent(github_token)
    
    async for event in agent.process_repository(repo_url, prompt):
        yield f"data: {json.dumps(event)}\n\n"