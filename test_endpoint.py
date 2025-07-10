#!/usr/bin/env python3

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

"""
Test script for the Modal Coding Agent endpoint
"""

import json
import sys
import time
import urllib.parse
from typing import Optional

# Check for requests dependency
try:
    import requests
except ImportError:
    print("Error: requests library not found")
    print("Install with: pip install requests")
    sys.exit(1)

def test_endpoint(
    base_url: str, 
    repo_url: str = "https://github.com/psf/requests", 
    prompt: str = "Add a docstring to the main function explaining its purpose",
    timeout: int = 300,
    verbose: bool = True
) -> dict:
    """Test the /code endpoint with SSE streaming
    
    Args:
        base_url: Base URL of the deployed Modal app
        repo_url: GitHub repository URL to test with
        prompt: Coding prompt to send
        timeout: Timeout in seconds for SSE stream
        verbose: Print detailed progress messages
        
    Returns:
        dict: Test results with success status and details
    """
    
    results = {
        "success": False,
        "health_check": False,
        "sse_connection": False,
        "events_received": 0,
        "pr_url": None,
        "error": None,
        "duration": 0
    }
    
    start_time = time.time()
    
    if verbose:
        logger.info(f"Testing endpoint: {base_url}")
        logger.info(f"Repository: {repo_url}")
        logger.info(f"Prompt: {prompt}")
        logger.info(f"Timeout: {timeout}s")
        logger.info("-" * 50)
    
    try:
        # Test health check first
        if verbose:
            print("Testing health check...")
        
        health_response = requests.get(f"{base_url}/", timeout=10)
        results["health_check"] = health_response.status_code == 200
        
        if verbose:
            logger.info(f"Health check: {health_response.status_code}")
            if health_response.status_code == 200:
                logger.info(f"Response: {health_response.json()}")
            else:
                logger.error(f"Error response: {health_response.text}")
        
        if not results["health_check"]:
            results["error"] = f"Health check failed: {health_response.status_code}"
            return results
        
        # Test main endpoint
        payload = {
            "repoUrl": repo_url,
            "prompt": prompt
        }
        
        if verbose:
            logger.info("Starting SSE stream...")
        
        response = requests.post(
            f"{base_url}/code",
            json=payload,
            stream=True,
            headers={"Accept": "text/event-stream"},
            timeout=timeout
        )
        
        if response.status_code != 200:
            results["error"] = f"HTTP {response.status_code}: {response.text}"
            if verbose:
                print(f"Error: {response.status_code}")
                print(f"Response: {response.text}")
            return results
        
        results["sse_connection"] = True
        
        # Process SSE stream with timeout
        stream_start = time.time()
        for line in response.iter_lines(decode_unicode=True, chunk_size=1):
            # Check timeout
            if time.time() - stream_start > timeout:
                results["error"] = f"Stream timeout after {timeout}s"
                if verbose:
                    logger.warning(f"Stream exceeded {timeout}s")
                return results
                
            if line.startswith("data: "):
                results["events_received"] += 1
                try:
                    data = json.loads(line[6:])  # Remove "data: " prefix
                    event_type = data.get("type", "unknown")
                    message = data.get("message", "")
                    
                    if event_type == "status":
                        stage = data.get("stage", "")
                        if verbose:
                            logger.info(f"[{stage.upper()}] {message}")
                            # Show additional details if available
                            if "details" in data:
                                logger.info(f"    Details: {data['details']}")
                    elif event_type == "error":
                        results["error"] = message
                        if verbose:
                            print(f"[ERROR] {message}")
                            # Show additional error details if available
                            if "details" in data:
                                print(f"    Error details: {data['details']}")
                            if "validation_results" in data:
                                print(f"    Validation results: {json.dumps(data['validation_results'], indent=2)}")
                        return results
                    elif event_type == "preview":
                        # Handle change preview event
                        if verbose:
                            print(f"\n[PREVIEW] Change Analysis:")
                            print(f"  Interpretation: {data.get('interpretation', '')}")
                            print(f"  Found target: {data.get('found_target', 'N/A')}")
                            
                            assumptions = data.get('assumptions', [])
                            if assumptions:
                                print(f"  Assumptions:")
                                for assumption in assumptions:
                                    print(f"    - {assumption}")
                            
                            change_summary = data.get('change_summary', {})
                            if change_summary:
                                print(f"  Change Summary:")
                                print(f"    - Files affected: {change_summary.get('files_affected', 0)}")
                                print(f"    - Lines added: {change_summary.get('lines_added', 0)}")
                                print(f"    - Lines removed: {change_summary.get('lines_removed', 0)}")
                                print(f"    - Change type: {change_summary.get('change_type', 'unknown')}")
                            
                            files_to_change = data.get('files_to_change', [])
                            if files_to_change:
                                print(f"  Files to change:")
                                for file_change in files_to_change:
                                    print(f"    - {file_change['file']} ({file_change['action']}): +{file_change.get('lines_added', 0)}/-{file_change.get('lines_removed', 0)}")
                                    if file_change.get('description'):
                                        print(f"      {file_change['description']}")
                    elif event_type == "complete":
                        pr_url = data.get("pr_url", "")
                        results["pr_url"] = pr_url
                        results["success"] = True
                        if verbose:
                            print(f"[SUCCESS] {message}")
                            if pr_url:
                                print(f"PR URL: {pr_url}")
                        
                        # Validate PR URL if provided
                        if pr_url and _validate_pr_url(pr_url, verbose):
                            results["pr_validated"] = True
                        
                        return results
                    else:
                        if verbose:
                            print(f"[{event_type.upper()}] {message}")
                            # Show all available data for unknown event types in verbose mode
                            if verbose:
                                print(f"    Full event data: {json.dumps(data, indent=2)}")
                        
                except json.JSONDecodeError:
                    if verbose:
                        print(f"Invalid JSON: {line}")
                except Exception as e:
                    if verbose:
                        print(f"Error parsing event: {e}")
                        print(f"Raw line: {line}")
        
        # Stream ended without completion
        if verbose:
            print(f"\nStream ended. Received {results['events_received']} events")
        
        if results["events_received"] == 0:
            results["error"] = "No events received from stream"
        
        return results
        
    except requests.exceptions.Timeout:
        results["error"] = f"Request timeout after {timeout}s"
        if verbose:
            print(f"Error: Request timeout after {timeout}s")
        return results
    except requests.exceptions.ConnectionError:
        results["error"] = "Could not connect to endpoint"
        if verbose:
            print("Error: Could not connect to endpoint")
        return results
    except Exception as e:
        results["error"] = str(e)
        if verbose:
            print(f"Error: {e}")
        return results
    finally:
        results["duration"] = time.time() - start_time

def _validate_pr_url(pr_url: str, verbose: bool = True) -> bool:
    """Validate that PR URL is accessible"""
    try:
        if not pr_url.startswith("https://github.com/"):
            return False
            
        # Try to access the PR (just check if it exists)
        response = requests.get(pr_url, timeout=10)
        is_valid = response.status_code == 200
        
        if verbose:
            if is_valid:
                print("[VALIDATION] PR URL is accessible")
            else:
                print(f"[VALIDATION] PR URL returned {response.status_code}")
        
        return is_valid
        
    except Exception as e:
        if verbose:
            print(f"[VALIDATION] Could not validate PR URL: {e}")
        return False

def _save_results(results: dict, filename: str = "test_results.json"):
    """Save test results to file"""
    try:
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {filename}")
    except Exception as e:
        print(f"Could not save results: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_endpoint.py <base_url> [options]")
        print("Options:")
        print("  --repo <url>      Custom repository URL")
        print("  --prompt <text>   Custom prompt")
        print("  --timeout <sec>   Timeout in seconds (default: 300)")
        print("  --quiet           Minimal output")
        print("  --debug           Maximum verbosity with all event details")
        print("  --save-results    Save results to JSON file")
        print("  --auth-test       Test authentication without making changes")
        print()
        print("Examples:")
        print("  python test_endpoint.py https://your-app.modal.run")
        print("  python test_endpoint.py https://your-app.modal.run --debug")
        print("  python test_endpoint.py https://your-app.modal.run --repo https://github.com/owner/repo")
        print("  python test_endpoint.py https://your-app.modal.run --quiet --save-results")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    repo_url = "https://github.com/arjun-ds/tiny-backspace"
    prompt = "Add comprehensive docstrings and comments to all Python files. For each function and class, add clear docstrings explaining their purpose, parameters, and return values. Add inline comments for complex logic sections. Make the code more readable and well-documented."
    timeout = 300
    verbose = True
    debug = False
    save_results = False
    auth_test = False
    
    # Parse additional arguments
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--repo" and i + 1 < len(sys.argv):
            repo_url = sys.argv[i + 1]
            i += 2
        elif arg == "--prompt" and i + 1 < len(sys.argv):
            prompt = sys.argv[i + 1]
            i += 2
        elif arg == "--timeout" and i + 1 < len(sys.argv):
            timeout = int(sys.argv[i + 1])
            i += 2
        elif arg == "--quiet":
            verbose = False
            i += 1
        elif arg == "--debug":
            verbose = True
            debug = True
            i += 1
        elif arg == "--save-results":
            save_results = True
            i += 1
        elif arg == "--auth-test":
            auth_test = True
            prompt = "Just analyze the code structure, don't make any changes"
            i += 1
        else:
            print(f"Unknown argument: {arg}")
            sys.exit(1)
    
    # Run the test
    results = test_endpoint(base_url, repo_url, prompt, timeout, verbose)
    
    # Print summary
    if verbose:
        print("\n" + "="*50)
        print("TEST SUMMARY")
        print("="*50)
    
    print(f"Success: {results['success']}")
    print(f"Duration: {results['duration']:.1f}s")
    print(f"Events received: {results['events_received']}")
    
    if results['error']:
        print(f"Error: {results['error']}")
    
    if results['pr_url']:
        print(f"PR URL: {results['pr_url']}")
    
    if save_results:
        _save_results(results)
    
    sys.exit(0 if results['success'] else 1)

if __name__ == "__main__":
    main()