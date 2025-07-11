#!/usr/bin/env python3
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
    
    This function sends a request to the coding agent endpoint and processes the Server-Sent Events (SSE)
    stream response. It monitors the stream for completion or errors and validates any pull request URLs
    that are generated.

    Args:
        base_url (str): Base URL of the deployed Modal app endpoint
        repo_url (str, optional): GitHub repository URL to test modifications on. 
            Defaults to requests repository.
        prompt (str, optional): Coding instruction prompt to send to the agent.
            Defaults to adding a docstring.
        timeout (int, optional): Maximum time in seconds to wait for stream completion.
            Defaults to 300 seconds.
        verbose (bool, optional): Whether to print detailed progress messages.
            Defaults to True.

    Returns:
        dict: Test results containing:
            - success (bool): Whether the test completed successfully
            - health_check (bool): If initial health check passed
            - sse_connection (bool): If SSE stream connected
            - events_received (int): Number of events received
            - pr_url (str, optional): URL of created pull request 
            - error (str, optional): Error message if failed
            - duration (float): Test duration in seconds
    """
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
    
    # Removed verbose output for cleaner display
    
    try:
        # Test health check first
        health_response = requests.get(f"{base_url}/", timeout=10)
        results["health_check"] = health_response.status_code == 200
        
        if not results["health_check"]:
            results["error"] = f"Health check failed: {health_response.status_code}"
            return results
        
        # Test main endpoint
        payload = {
            "repoUrl": repo_url,
            "prompt": prompt
        }
        
        # Starting SSE stream
        
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
                    print(f"[TIMEOUT] Stream exceeded {timeout}s")
                return results
                
            if line.startswith("data: "):
                results["events_received"] += 1
                try:
                    data = json.loads(line[6:])  # Remove "data: " prefix
                    event_type = data.get("type", "unknown")
                    message = data.get("message", "")
                    
                    if event_type == "error":
                        results["error"] = message
                        if verbose:
                            print(f"data: {json.dumps(data, separators=(',', ':'))}")
                        return results
                    elif event_type == "complete":
                        pr_url = data.get("pr_url", "")
                        results["pr_url"] = pr_url
                        results["success"] = True
                        if verbose:
                            print(f"data: {json.dumps(data, separators=(',', ':'))}")
                        
                        # Validate PR URL if provided
                        if pr_url and _validate_pr_url(pr_url, verbose):
                            results["pr_validated"] = True
                        
                        return results
                    else:
                        if verbose:
                            # Just print the clean event format
                            print(f"data: {json.dumps(data, separators=(',', ':'))}")
                        
                except json.JSONDecodeError:
                    if verbose:
                        print(f"Invalid JSON: {line}")
                except Exception as e:
                    if verbose:
                        print(f"Error parsing event: {e}")
                        print(f"Raw line: {line}")
        
        # Stream ended without completion
        
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
    """Validate that a GitHub pull request URL is accessible

    Args:
        pr_url (str): Pull request URL to validate
        verbose (bool, optional): Whether to print validation details. Defaults to True.

    Returns:
        bool: True if URL is valid and accessible, False otherwise
    """
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
    """Save test results to a JSON file

    Args:
        results (dict): Test results dictionary to save
        filename (str, optional): Output JSON filename. Defaults to "test_results.json".
    """
    """Save test results to file"""
    try:
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {filename}")
    except Exception as e:
        print(f"Could not save results: {e}")

def main():
    """Main entry point for test script
    
    Parses command line arguments and runs endpoint testing. Supports options for:
    - Custom repository URL
    - Custom prompt
    - Timeout duration
    - Verbosity levels
    - Results saving
    - Authentication testing
    
    Exit codes:
        0: Test completed successfully 
        1: Test failed or invalid arguments
    """
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
    
    # Print minimal summary
    print(f"Success: {results['success']} | Duration: {results['duration']:.1f}s | Events: {results['events_received']}")
    
    if results['error']:
        print(f"Error: {results['error']}")
    
    if results['pr_url']:
        print(f"PR URL: {results['pr_url']}")
    
    if save_results:
        _save_results(results)
    
    sys.exit(0 if results['success'] else 1)

if __name__ == "__main__":
    main()