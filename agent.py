"""
Coding agent implementation for Backspace
"""

import os
import tempfile
from typing import AsyncGenerator, Dict, Any
import git
from github import Github
import asyncio
import json
import anthropic
import logging
import time
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Only import langsmith if enabled
if os.getenv('LANGSMITH_ENABLED', 'false').lower() == 'true':
    try:
        from langsmith import Client
        langsmith_client = Client(
            api_key=os.getenv('LANGSMITH_API_KEY'),
            api_url=os.getenv('LANGSMITH_ENDPOINT', 'https://api.smith.langchain.com')
        )
        logger.info("LangSmith client initialized")
    except ImportError:
        logger.warning("langsmith not available, continuing without LangSmith tracking")
        langsmith_client = None
    except Exception as e:
        logger.warning(f"LangSmith initialization failed: {e}")
        langsmith_client = None
else:
    langsmith_client = None

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
        
        # Start LangSmith run if enabled
        langsmith_run = None
        if langsmith_client:
            try:
                langsmith_run = langsmith_client.create_run(
                    project_name=os.getenv('LANGSMITH_PROJECT', 'backspace-agent'),
                    name="repository_processing",
                    run_type="chain",
                    inputs={
                        "repo_url": repo_url,
                        "prompt": prompt,
                        "owner": owner,
                        "repo_name": repo_name
                    },
                    tags=["repository-processing", "coding-agent"]
                )
                if langsmith_run:
                    logger.info(f"LangSmith run created: {langsmith_run.id}")
                else:
                    logger.warning("LangSmith run creation returned None")
            except Exception as e:
                logger.warning(f"Failed to create LangSmith run: {e}")
        
        # Create temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                yield {"type": "AI Message", "message": f"Cloning {repo_url}..."}
                
                # Add authentication to the URL for pushing
                auth_url = repo_url.replace('https://', f'https://{self.github_token}@')
                
                # Clone with authentication
                logger.info("Cloning repository with authentication")
                
                repo = git.Repo.clone_from(auth_url, temp_dir)
                
                # Configure git user for commits
                repo.config_writer().set_value("user", "name", "Coding Agent").release()
                repo.config_writer().set_value("user", "email", "backspace-agent@users.noreply.github.com").release()
                
                yield {"type": "AI Message", "message": "Repository cloned successfully"}
                                
                # Analyze codebase
                yield {"type": "AI Message", "message": "Analyzing codebase structure..."}
                                
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
                            
                yield {"type": "AI Message", "message": f"Found {len(py_files)} Python files"}
                                
                # AI analysis and code modification workflow
                yield {"type": "AI Message", "message": "Starting AI analysis with Claude 3.5 Sonnet..."}
                                
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
                    
                    # Simple Claude request with LangSmith tracking
                    changes = await self._simple_claude_analysis(files_content, prompt, langsmith_run)
                    
                    # If Claude doesn't provide edits, return error
                    if not changes.get('edits'):
                        logger.error("Claude provided no edits for the request")
                        yield {"type": "error", "message": "AI analysis completed but no changes were identified"}
                        return
                    
                    # Apply changes
                    yield {"type": "AI Message", "message": f"Applying {len(changes['edits'])} changes..."}
                    for edit in changes['edits']:
                        # Clean up the strings - strip whitespace and show meaningful content
                        old_clean = edit["old_str"].strip()[:100].replace('\n', ' ').replace('\t', ' ').replace('    ', ' ')
                        new_clean = edit["new_str"].strip()[:100].replace('\n', ' ').replace('\t', ' ').replace('    ', ' ')
                        
                        yield {
                            "type": "Tool: Edit",
                            "filepath": edit["file"],
                            "old_str": old_clean,
                            "new_str": new_clean
                        }
                        self._apply_single_edit(temp_dir, edit)
                    
                    # After interactive implementation, commit changes
                    yield {"type": "AI Message", "message": "Creating git commit..."}
                    
                    # Git operations with simple branch name
                    branch_name = f'claude-improvements-{int(time.time())}'
                    async for bash_event in self._create_git_branch_and_commit_and_collect_events(repo, branch_name, prompt):
                        yield bash_event
                                            
                    # Create pull request
                    yield {"type": "AI Message", "message": "Creating pull request..."}
                    
                    try:
                        pr_url = await self._create_pull_request(repo_url, branch_name, prompt)
                        yield {"type": "AI Message", "message": f"Pull request created: {pr_url}"}
                    except Exception as e:
                        logger.error(f"Failed to create pull request: {str(e)}")
                        pr_url = None
                        yield {"type": "AI Message", "message": f"Warning: Failed to create pull request: {str(e)}"}
                        yield {"type": "AI Message", "message": f"Changes were pushed to branch: {branch_name}"}
                    
                    # Complete LangSmith run with success
                    if langsmith_run:
                        try:
                            langsmith_client.update_run(
                                langsmith_run.id,
                                outputs={
                                    "result": "success",
                                    "edits_applied": len(changes.get('edits', [])),
                                    "branch_name": branch_name,
                                    "pr_url": pr_url
                                }
                            )
                        except Exception as e:
                            logger.warning(f"Failed to update LangSmith run: {e}")
                    
                    yield {
                        "type": "complete",
                        "message": "Changes completed successfully - PR created!" if pr_url else f"Changes completed successfully - pushed to branch {branch_name}",
                        "pr_url": pr_url
                    }
                    
                except Exception as e:
                    # Complete LangSmith run with error
                    if langsmith_run:
                        try:
                            langsmith_client.update_run(
                                langsmith_run.id,
                                outputs={
                                    "result": "error",
                                    "error": str(e)
                                }
                            )
                        except Exception as ex:
                            logger.warning(f"Failed to update LangSmith run: {ex}")
                    yield {"type": "error", "message": f"Workflow failed: {str(e)}"}
                
            except Exception as e:
                # Complete LangSmith run with error
                if langsmith_run:
                    try:
                        langsmith_client.update_run(
                            langsmith_run.id,
                            outputs={
                                "result": "error",
                                "error": str(e)
                            }
                        )
                    except Exception as ex:
                        logger.warning(f"Failed to update LangSmith run: {ex}")
                yield {"type": "error", "message": f"Error processing repository: {str(e)}"}
    
    async def _create_pull_request(self, repo_url: str, branch_name: str, prompt: str) -> str:
        """Create a pull request for the changes"""
        # Extract owner/repo from URL
        parts = repo_url.replace("https://github.com/", "").split("/")
        owner, repo_name = parts[0], parts[1]
        
        try:
            repo = self.github.get_repo(f"{owner}/{repo_name}")
            
            # Determine the default branch (main vs master)
            default_branch = repo.default_branch
            logger.info(f"Using default branch: {default_branch}")
            
            # Create pull request with truncated title if too long
            title = f"Automated changes: {prompt}"
            if len(title) > 200:  # GitHub PR title limit
                title = f"Automated changes: {prompt[:150]}..."
            
            pr = repo.create_pull(
                title=title,
                body=f"This pull request implements the following changes:\n\n{prompt}\n\n---\n*Generated by Backspace Coding Agent*",
                head=f"{owner}:{branch_name}",  # Need owner:branch format
                base=default_branch
            )
            
            logger.info(f"Pull request created: {pr.html_url}")
            return pr.html_url
            
        except Exception as e:
            # Raise exception for proper error handling
            raise Exception(f"Failed to create pull request: {str(e)}")
    
    async def _simple_claude_analysis(self, files_content: dict, prompt: str, langsmith_run=None) -> dict:
        """Simple, fast Claude analysis with 3.5 Sonnet"""
        
        # Build a simple prompt
        files_text = ""
        for filename, content in files_content.items():
            files_text += f"\n=== {filename} ===\n{content}\n"
        
        simple_prompt = f"""You are a coding assistant that MUST implement the requested changes.

Task: {prompt}

Files to modify:
{files_text}

SIMPLE RULES:
1. Always provide at least one edit
2. To append to a file: use old_str = "" (empty string)
3. To replace: use the exact text from the file
4. If unsure, just append to the end of the file

RESPONSE FORMAT (JSON only):
{{
    "edits": [
        {{
            "file": "filename.py",
            "old_str": "text to replace (or empty string to append)",
            "new_str": "new content"
        }}
    ]
}}

Examples:
- Add a function: {{"file": "main.py", "old_str": "", "new_str": "\\ndef my_function():\\n    return True\\n"}}
- Add a comment: {{"file": "main.py", "old_str": "", "new_str": "\\n# This is my comment\\n"}}
- Replace text: {{"file": "main.py", "old_str": "old text", "new_str": "new text"}}"""

        # Create LangSmith run for Claude analysis if enabled
        claude_run = None
        if langsmith_client and langsmith_run:
            try:
                claude_run = langsmith_client.create_run(
                    project_name=os.getenv('LANGSMITH_PROJECT', 'backspace-agent'),
                    name="claude_analysis",
                    run_type="llm",
                    inputs={
                        "prompt": prompt,
                        "files_count": len(files_content),
                        "files": list(files_content.keys()),
                        "model": "claude-3-5-sonnet-20241022"
                    },
                    tags=["claude-analysis", "code-modification"],
                    parent_run_id=langsmith_run.id if langsmith_run else None
                )
                if claude_run:
                    logger.info(f"Claude LangSmith run created: {claude_run.id}")
                else:
                    logger.warning("Claude LangSmith run creation returned None")
            except Exception as e:
                logger.warning(f"Failed to create Claude LangSmith run: {e}")

        try:
            response = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                messages=[{"role": "user", "content": simple_prompt}]
            )
            
            response_text = response.content[0].text
            logger.info(f"Raw Claude response: {response_text[:500]}...")
            
            # Parse JSON response - handle various formats robustly
            
            json_text = None
            
            # Method 1: Try to extract from markdown code blocks
            code_block_pattern = r'```(?:json)?\s*(\{[^`]*\})\s*```'
            code_match = re.search(code_block_pattern, response_text, re.DOTALL)
            
            if code_match:
                json_text = code_match.group(1)
                logger.info("Extracted JSON from code block")
            else:
                # Method 2: Try to find valid JSON object anywhere in text
                # This regex looks for balanced braces
                json_pattern = r'(\{(?:[^{}]|(?:\{[^{}]*\}))*\})'
                json_matches = re.findall(json_pattern, response_text, re.DOTALL)
                
                # Try each match to find valid JSON
                for match in json_matches:
                    try:
                        # Quick validation
                        test_parse = json.loads(match)
                        if 'edits' in test_parse:  # We expect 'edits' key
                            json_text = match
                            logger.info("Found valid JSON with 'edits' key")
                            break
                    except:
                        continue
                
                # Method 3: Last resort - try the entire response
                if not json_text:
                    try:
                        test_parse = json.loads(response_text)
                        if isinstance(test_parse, dict) and 'edits' in test_parse:
                            json_text = response_text
                            logger.info("Entire response is valid JSON")
                    except:
                        logger.warning("Could not find valid JSON in response")
            
            logger.info(f"Extracted JSON: {json_text[:200]}...")
            result = json.loads(json_text)
            logger.info(f"Parsed result: edits count = {len(result.get('edits', []))}")
            
            # Update LangSmith run with success
            if claude_run:
                try:
                    langsmith_client.update_run(
                        claude_run.id,
                        outputs={
                            "response": response_text,
                            "edits_count": len(result.get('edits', [])),
                            "success": True
                        }
                    )
                except Exception as ex:
                    logger.warning(f"Failed to update Claude LangSmith run: {ex}")
            
            return result
            
        except Exception as e:
            logger.error(f"Claude analysis failed: {str(e)}")
            
            # Update LangSmith run with error
            if claude_run:
                try:
                    langsmith_client.update_run(
                        claude_run.id,
                        outputs={
                            "error": str(e),
                            "success": False
                        }
                    )
                except Exception as ex:
                    logger.warning(f"Failed to update Claude LangSmith run: {ex}")
            
            return {"edits": []}

    def _get_repo_structure(self, repo_path: str) -> list:
        """Get list of Python files in the repo, prioritizing based on README analysis"""
        # First, look for README files to understand project structure
        readme_content = None
        readme_files = ['README.md', 'README.rst', 'README.txt', 'readme.md', 'Readme.md']
        
        for readme in readme_files:
            readme_path = os.path.join(repo_path, readme)
            if os.path.exists(readme_path):
                try:
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        readme_content = f.read()
                        logger.info(f"Found README file: {readme}")
                        break
                except Exception as e:
                    logger.warning(f"Could not read {readme}: {e}")
        
        # Get all Python files
        all_py_files = []
        for root, dirs, files in os.walk(repo_path):
            if '.git' in root:
                continue
            for file in files:
                if file.endswith('.py'):
                    rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                    all_py_files.append(rel_path)
        
        # If README exists, try to identify main files mentioned
        if readme_content:
            # Look for Python files mentioned in README
            important_files = []
            for py_file in all_py_files:
                # Check if file is mentioned in README (without .py extension too)
                file_base = os.path.basename(py_file).replace('.py', '')
                if py_file in readme_content or file_base in readme_content:
                    important_files.append(py_file)
                    logger.info(f"File {py_file} found in README - marking as important")
            
            # Prioritize: important files first, then others
            # Also limit to reasonable number of files to avoid memory issues
            prioritized = important_files + [f for f in all_py_files if f not in important_files]
            
            # Return top 20 files to avoid memory issues
            if len(prioritized) > 20:
                logger.warning(f"Found {len(prioritized)} Python files, limiting to 20 for memory efficiency")
                return prioritized[:20]
            
            return prioritized
        
        # No README found, return all files (limited)
        if len(all_py_files) > 20:
            logger.warning(f"Found {len(all_py_files)} Python files, limiting to 20 for memory efficiency")
            return all_py_files[:20]
        
        return all_py_files

    def _read_file(self, repo_path: str, filename: str) -> str:
        """Read a single file's content with size limits"""
        try:
            file_path = os.path.join(repo_path, filename)
            
            # Check file size first to avoid memory issues
            file_size = os.path.getsize(file_path)
            max_size = 1024 * 1024  # 1MB limit per file
            
            if file_size > max_size:
                logger.warning(f"File {filename} is too large ({file_size} bytes), truncating to {max_size} bytes")
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read(max_size)
                    return content + f"\n\n[FILE TRUNCATED - Original size: {file_size} bytes]"
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def _apply_single_edit(self, repo_path: str, edit_info: dict):
        """Apply a single edit to a file - handles both replace and append"""
        file_path = os.path.join(repo_path, edit_info["file"])
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # If old_str is empty, append to file
            if not edit_info["old_str"]:
                logger.info(f"Appending to {edit_info['file']}")
                new_content = content + edit_info["new_str"]
            else:
                # Check if the old_str exists in the file
                if edit_info["old_str"] in content:
                    # Normal replacement
                    new_content = content.replace(edit_info["old_str"], edit_info["new_str"], 1)
                    logger.info(f"Replaced content in {edit_info['file']}")
                else:
                    # Pattern not found - raise error
                    raise ValueError(f"Pattern not found in {edit_info['file']}: {edit_info['old_str'][:100]}")
            
            # Write the modified content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
                
            logger.info(f"Successfully modified {edit_info['file']}")
        except Exception as e:
            logger.error(f"Failed to apply edit to {edit_info['file']}: {str(e)}")
            raise  # Re-raise to stop processing


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