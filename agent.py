async def _cycle_errors_with_claude(self, repo_path: str, validation_results: dict, original_prompt: str, attempt: int = 1) -> dict:
    
    if attempt > 5:  # Maximum 5 attempts
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