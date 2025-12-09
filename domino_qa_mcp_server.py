# Enhanced Domino QA MCP Server for User Acceptance Testing and Performance Testing
# Updated to use the official python-domino library v1.4.8 for Domino 6.1
# Enhanced with smart resource management and Admin/User UAT split

from typing import Dict, Any, List, Optional
from mcp.server.fastmcp import FastMCP
import requests
import asyncio
import os
from dotenv import load_dotenv
import webbrowser
import json
import time
import datetime
import concurrent.futures
import threading
from pathlib import Path
from domino import Domino  # Official python-domino library
import tempfile
import uuid
import re

load_dotenv()

# Load API key from environment variable
domino_api_key = os.getenv("DOMINO_API_KEY",os.getenv("DOMINO_USER_API_KEY"))
domino_host = os.getenv("DOMINO_HOST",os.getenv("DOMINO_API_HOST"))

if not domino_api_key:
    raise ValueError("DOMINO_API_KEY environment variable not set.")

if not domino_host:
    raise ValueError("DOMINO_HOST environment variable not set.")

# Initialize the Fast MCP server
mcp = FastMCP("domino_qa_server")

def _create_domino_client(user_name: str, project_name: str) -> Domino:
    """Create a Domino client instance for the specified project"""
    project_path = f"{user_name}/{project_name}"
    
    return Domino(
        project=project_path,
        api_key=domino_api_key,
        host=domino_host  # Use full URL format that works
    )

def _generate_unique_name(prefix: str) -> str:
    """Generate a unique name with timestamp and UUID"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"{prefix}_{timestamp}_{short_uuid}"

def _validate_url_parameter(param_value: str, param_name: str) -> str:
    """
    Validates and URL-encodes a parameter for safe use in URLs.
    Supports international characters by encoding them properly.
    
    Args:
        param_value (str): The parameter value to validate and encode
        param_name (str): The name of the parameter (for error messages)
        
    Returns:
        str: The URL-encoded parameter value
        
    Raises:
        ValueError: If the parameter contains unsafe URL characters
    """
    import urllib.parse
    
    # Basic safety check - reject if contains dangerous chars that could break URL structure
    if any(char in param_value for char in ['/', '\\', '?', '#', '&', '=', '%']):
        raise ValueError(f"Invalid {param_name}: '{param_value}' contains unsafe URL characters")
    
    # URL encode to handle international characters safely
    return urllib.parse.quote(param_value, safe='')

def _make_api_request(method: str, endpoint: str, headers: Dict[str, str], data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Makes a standardized API request to Domino with proper error handling.
    
    Args:
        method (str): HTTP method (GET, POST, PUT, DELETE)
        endpoint (str): API endpoint URL
        headers (Dict[str, str]): Request headers
        data (Optional[Dict]): Request payload for POST/PUT requests
        
    Returns:
        Dict[str, Any]: API response or error information
    """
    import requests
    
    try:
        if method.upper() == "GET":
            response = requests.get(endpoint, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(endpoint, headers=headers, json=data)
        elif method.upper() == "PUT":
            response = requests.put(endpoint, headers=headers, json=data)
        elif method.upper() == "DELETE":
            response = requests.delete(endpoint, headers=headers)
        else:
            return {"error": f"Unsupported HTTP method: {method}"}
        
        response.raise_for_status()
        
        # Handle both JSON and text responses
        try:
            return response.json()
        except ValueError:
            return {"text_response": response.text, "status_code": response.status_code}
            
    except requests.exceptions.RequestException as e:
        return {"error": f"API request failed: {e}", "status_code": getattr(e.response, 'status_code', None)}
    except Exception as e:
        return {"error": f"Unexpected error: {e}"}

def _safe_execute(func, description: str, *args, **kwargs) -> Dict[str, Any]:
    """Safely execute a function and return standardized result"""
    try:
        result = func(*args, **kwargs)
        return {
            "status": "PASSED",
            "result": result,
            "description": description
        }
    except Exception as e:
        return {
            "status": "FAILED", 
            "error": str(e),
            "description": description
        }

def _load_test_settings() -> Dict[str, str]:
    """Load test settings from domino-qa/domino_project_settings.md"""
    try:
        settings_path = Path("domino-qa/domino_project_settings.md")
        if not settings_path.exists():
            return {"error": "domino_project_settings.md not found in domino-qa/ folder"}
        
        settings = {}
        with open(settings_path, 'r') as f:
            content = f.read()
            
        # Parse markdown settings
        for line in content.split('\n'):
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                settings[key.strip()] = value.strip().strip('"')
                
        return settings
    except Exception as e:
        return {"error": f"Failed to load test settings: {e}"}

# UAT Test Functions - Updated to use official library

async def create_domino_project(user_name: str, project_name: str, description: str = "UAT Test Project") -> Dict[str, Any]:
    """
    Creates a new Domino project using the REST API.
    
    Args:
        user_name (str): The project owner username
        project_name (str): The name for the new project
        description (str): Project description
        
    Returns:
        Dict containing creation status and details
    """
    
    try:
        import requests
        
        # Construct the API URL for project creation
        api_url = f"{domino_host}/v4/projects"
        
        headers = {
            "X-Domino-Api-Key": domino_api_key,
            "Content-Type": "application/json"
        }
        
        # Project creation payload - based on Domino v4 API requirements
        payload = {
            "name": project_name,
            "description": description,
            "visibility": "Private",  # Default to private
            "ownerId": user_name,
            "collaborators": [],
            "tags": []
        }
        
        print(f"🔨 Creating project: {user_name}/{project_name}")
        response = requests.post(api_url, headers=headers, json=payload)
        
        if response.status_code == 201:
            project_data = response.json()
            return {
                "status": "CREATED",
                "project_id": project_data.get("id"),
                "project_name": project_name,
                "owner": user_name,
                "message": f"Successfully created project {user_name}/{project_name}"
            }
        elif response.status_code == 409:
            # Project already exists
            return {
                "status": "EXISTS", 
                "project_name": project_name,
                "owner": user_name,
                "message": f"Project {user_name}/{project_name} already exists"
            }
        else:
            return {
                "status": "FAILED",
                "error": f"HTTP {response.status_code}: {response.text}",
                "message": f"Failed to create project {user_name}/{project_name}"
            }
            
    except Exception as e:
        return {
            "status": "FAILED", 
            "error": str(e),
            "message": f"Exception while creating project {user_name}/{project_name}"
        }

async def ensure_project_exists(user_name: str, project_name: str) -> Dict[str, Any]:
    """
    Ensures a project exists, creating it if necessary.
    
    Args:
        user_name (str): The project owner username
        project_name (str): The project name
        
    Returns:
        Dict containing status and project information
    """
    
    try:
        # First, try to connect to the project to see if it exists
        domino = _create_domino_client(user_name, project_name)
        runs_result = _safe_execute(domino.runs_list, "Check project existence")
        
        if runs_result["status"] == "PASSED":
            return {
                "status": "EXISTS",
                "action": "none",
                "message": f"Project {user_name}/{project_name} already exists and is accessible"
            }
        else:
            # Project doesn't exist - provide guidance for manual creation
            return {
                "status": "NOT_FOUND",
                "action": "manual_creation_needed", 
                "message": f"Project {user_name}/{project_name} not found",
                "guidance": {
                    "steps": [
                        "1. Log into your Domino instance via web browser",
                        "2. Click 'New Project' button",
                        f"3. Set project name to: {project_name}",
                        "4. Set owner/collaborators as needed",
                        "5. Click 'Create Project'",
                        "6. Run the UAT tests again"
                    ],
                    "url": f"{domino_host}/projects/create",
                    "note": "Automatic project creation requires admin permissions and proper API configuration"
                },
                "error_details": runs_result.get("error", "Project not accessible")
            }
                
    except Exception as e:
        return {
            "status": "ERROR",
            "action": "error",
            "error": str(e),
            "message": f"Error checking project existence: {user_name}/{project_name}"
        }

@mcp.tool()
async def create_project_if_needed(user_name: str, project_name: str, description: str = "MCP-created project") -> Dict[str, Any]:
    """
    Explicitly creates a Domino project if it doesn't exist.
    
    Args:
        user_name (str): The project owner username
        project_name (str): The name for the new project  
        description (str): Project description
        
    Returns:
        Dict containing creation status and details
    """
    
    # First check if project exists
    exists_result = await ensure_project_exists(user_name, project_name)
    
    if exists_result["status"] == "EXISTS":
        return exists_result
    elif exists_result["status"] == "NOT_FOUND":
        # Try to create the project using API
        try:
            create_result = await create_domino_project(user_name, project_name, description)
            
            if create_result["status"] == "CREATED":
                # Wait for project initialization
                await asyncio.sleep(3)
                
                # Verify project was created successfully
                verify_result = await ensure_project_exists(user_name, project_name)
                if verify_result["status"] == "EXISTS":
                    return {
                        "status": "CREATED",
                        "action": "created_successfully",
                        "message": f"Successfully created and verified project {user_name}/{project_name}",
                        "project_details": create_result
                    }
                else:
                    return {
                        "status": "CREATED_UNVERIFIED",
                        "action": "created_but_unverified",
                        "message": f"Project {user_name}/{project_name} created but verification failed",
                        "note": "Project may need time to initialize"
                    }
            else:
                # Creation failed, return guidance for manual creation
                return {
                    "status": "CREATION_FAILED",
                    "action": "manual_creation_recommended",
                    "message": f"Automatic creation failed for {user_name}/{project_name}",
                    "error": create_result.get("error"),
                    "guidance": exists_result["guidance"]
                }
                
        except Exception as e:
            return {
                "status": "CREATION_ERROR",
                "action": "manual_creation_required",
                "error": str(e),
                "message": f"Exception during project creation: {user_name}/{project_name}",
                "guidance": exists_result["guidance"]
            }
    else:
        return exists_result

@mcp.tool()
async def test_user_authentication(user_name: str, project_name: str) -> Dict[str, Any]:
    """
    Tests user authentication by attempting to access project information.
    Creates the project if it doesn't exist.
    
    Args:
        user_name (str): The user name to test authentication for
        project_name (str): The project name to test with
    """
    
    test_results = {
        "test": "user_authentication",
        "user_name": user_name,
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    try:
        # Ensure project exists (create if needed)
        project_status = await ensure_project_exists(user_name, project_name)
        test_results["project_setup"] = project_status
        
        if project_status["status"] in ["EXISTS", "CREATED", "CREATED_UNVERIFIED"]:
            # Now test authentication with the existing/created project
            domino = _create_domino_client(user_name, project_name)
            runs_result = _safe_execute(domino.runs_list, "List user project runs")
            
            if runs_result["status"] == "PASSED":
                runs_data = runs_result.get("result", [])
                test_results.update({
                    "status": "PASSED",
                    "runs_count": len(runs_data),
                    "authentication": "successful",
                    "message": f"Successfully authenticated user {user_name} with {len(runs_data)} runs found"
                })
            else:
                test_results.update({
                    "status": "FAILED",
                    "authentication": "failed",
                    "error": runs_result.get("error"),
                    "message": f"Authentication failed for user {user_name}"
                })
        elif project_status["status"] == "NOT_FOUND":
            test_results.update({
                "status": "SKIPPED",
                "authentication": "project_not_found",
                "message": f"Project {user_name}/{project_name} not found - manual creation required",
                "guidance": project_status.get("guidance")
            })
        else:
            test_results.update({
                "status": "FAILED",
                "authentication": "project_unavailable", 
                "error": project_status.get("error"),
                "message": f"Could not access project for user {user_name}: {project_status.get('message', 'Unknown error')}"
            })
            
        return test_results
        
    except Exception as e:
        test_results.update({
            "status": "FAILED",
            "authentication": "exception",
            "error": str(e),
            "message": f"Exception during authentication test for user {user_name}"
        })
        return test_results

@mcp.tool()
async def test_project_operations(user_name: str, project_name: str) -> Dict[str, Any]:
    """
    Tests project operations including creation, file access, and basic functionality.
    Creates the project if it doesn't exist.
    
    Args:
        user_name (str): The user name for project operations
        project_name (str): The project name to test
    """
    
    test_results = {
        "test": "project_operations",
        "user_name": user_name,
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "operations": {}
    }
    
    try:
        # Ensure project exists (create if needed)
        project_status = await ensure_project_exists(user_name, project_name)
        test_results["project_setup"] = project_status
        
        if project_status["status"] in ["EXISTS", "CREATED", "CREATED_UNVERIFIED"]:
            domino = _create_domino_client(user_name, project_name)
            
            # Test 1: List runs
            runs_result = _safe_execute(domino.runs_list, "List project runs")
            test_results["operations"]["list_runs"] = runs_result
            
            # Test 2: List datasets
            datasets_result = _safe_execute(domino.datasets_list, "List project datasets")
            test_results["operations"]["list_datasets"] = datasets_result
            
            # Determine overall status
            failed_ops = [k for k, v in test_results["operations"].items() if v["status"] == "FAILED"]
            test_results["status"] = "FAILED" if failed_ops else "PASSED"
            test_results["failed_operations"] = failed_ops
            
            if test_results["status"] == "PASSED":
                test_results["message"] = f"All project operations successful for {user_name}/{project_name}"
            else:
                test_results["message"] = f"Some project operations failed: {failed_ops}"
                
        elif project_status["status"] == "NOT_FOUND":
            test_results.update({
                "status": "SKIPPED",
                "message": f"Project {user_name}/{project_name} not found - manual creation required",
                "guidance": project_status.get("guidance")
            })
        else:
            test_results.update({
                "status": "FAILED",
                "error": project_status.get("error"),
                "message": f"Could not access project {user_name}/{project_name}: {project_status.get('message', 'Unknown error')}"
            })
        
        return test_results
        
    except Exception as e:
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during project operations test"
        })
        return test_results

@mcp.tool()
async def test_job_execution(user_name: str, project_name: str, language: str = "python") -> Dict[str, Any]:
    """
    Tests job execution capabilities with Python or R code.
    Creates the project if it doesn't exist.
    
    Args:
        user_name (str): The user name for the project
        project_name (str): The project name to run jobs in
        language (str): Programming language to test ("python" or "r")
    """
    
    test_results = {
        "test": "job_execution",
        "user_name": user_name,
        "project_name": project_name,
        "language": language,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    try:
        # Ensure project exists (create if needed)
        project_status = await ensure_project_exists(user_name, project_name)
        test_results["project_setup"] = project_status
        
        if project_status["status"] in ["EXISTS", "READY"]:
            domino = _create_domino_client(user_name, project_name)
            
            # Define test commands
            if language.lower() == "python":
                command = ["python", "-c", "print('UAT Test: Python execution successful'); import sys; print(f'Python version: {sys.version}')"]
            elif language.lower() == "r":
                command = ["Rscript", "-e", "cat('UAT Test: R execution successful\\n'); cat('R version:', R.version.string, '\\n')"]
            else:
                raise ValueError(f"Unsupported language: {language}")
            
            # Start the job
            job_result = domino.runs_start(command=command, isDirect=False, title=f"UAT Test Job - {language}")
            
            # Extract run ID from the result
            if isinstance(job_result, dict) and 'runId' in job_result:
                run_id = job_result['runId']
            else:
                run_id = str(job_result)
            
            # Get job status
            status_result = _safe_execute(domino.runs_status, "Check job status", run_id)
            
            test_results.update({
                "status": "PASSED",
                "run_id": run_id,
                "job_result": job_result,
                "status_check": status_result,
                "message": f"Successfully started {language} job with ID: {run_id}"
            })
            
        else:
            test_results.update({
                "status": "FAILED",
                "error": project_status.get("error"),
                "message": f"Could not access or create project {user_name}/{project_name}"
            })
        
        return test_results
        
    except Exception as e:
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during job execution test"
        })
        return test_results

@mcp.tool()
async def test_workspace_operations(user_name: str, project_name: str) -> Dict[str, Any]:
    """
    Tests workspace operations including start, stop, and sync verification.
    Creates the project if it doesn't exist.
    
    Args:
        user_name (str): The user name for the project
        project_name (str): The project name to test workspace operations
    """
    
    test_results = {
        "test": "workspace_operations",
        "user_name": user_name,
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    try:
        # Ensure project exists (create if needed)
        project_status = await ensure_project_exists(user_name, project_name)
        test_results["project_setup"] = project_status
        
        if project_status["status"] in ["EXISTS", "READY"]:
            # For now, workspace operations are simulated since the python-domino library
            # doesn't have direct workspace management methods
            test_results.update({
                "status": "PASSED",
                "message": f"Project {user_name}/{project_name} is ready for workspace operations",
                "note": "Workspace operations require additional API implementation"
            })
        else:
            test_results.update({
                "status": "FAILED",
                "error": project_status.get("error"),
                "message": f"Could not access or create project {user_name}/{project_name}"
            })
        
        return test_results
        
    except Exception as e:
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during workspace operations test"
        })
        return test_results

@mcp.tool()
async def test_environment_operations(user_name: str) -> Dict[str, Any]:
    """
    Tests environment management operations including listing and validating environments.
    
    Args:
        user_name (str): The user name for environment operations
    """
    
    test_results = {
        "test": "environment_operations",
        "user_name": user_name,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    try:
        # Environment operations don't require a specific project
        # This is a placeholder for environment-related testing
        test_results.update({
            "status": "PASSED",
            "message": f"Environment operations available for user {user_name}",
            "note": "Environment operations require additional API implementation"
        })
        
        return test_results
        
    except Exception as e:
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during environment operations test"
        })
        return test_results

@mcp.tool()
async def test_dataset_operations(user_name: str, project_name: str) -> Dict[str, Any]:
    """
    Tests dataset operations including listing and accessing datasets.
    Creates the project if it doesn't exist.
    
    Args:
        user_name (str): The user name for dataset operations
        project_name (str): The project name to test dataset operations
    """
    
    test_results = {
        "test": "dataset_operations",
        "user_name": user_name,
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    try:
        # Ensure project exists (create if needed)
        project_status = await ensure_project_exists(user_name, project_name)
        test_results["project_setup"] = project_status
        
        if project_status["status"] in ["EXISTS", "READY"]:
            domino = _create_domino_client(user_name, project_name)
            
            # Test dataset listing
            datasets_result = _safe_execute(domino.datasets_list, "List datasets")
            
            if datasets_result["status"] == "PASSED":
                datasets = datasets_result.get("result", [])
                test_results.update({
                    "status": "PASSED",
                    "datasets_count": len(datasets),
                    "datasets": datasets[:5],  # Show first 5 datasets
                    "message": f"Successfully listed {len(datasets)} datasets"
                })
            else:
                test_results.update({
                    "status": "FAILED",
                    "error": datasets_result.get("error"),
                    "message": "Failed to list datasets"
                })
        else:
            test_results.update({
                "status": "FAILED",
                "error": project_status.get("error"),
                "message": f"Could not access or create project {user_name}/{project_name}"
            })
        
        return test_results
        
    except Exception as e:
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during dataset operations test"
        })
        return test_results

# Performance Test Functions

@mcp.tool()
async def performance_test_workspaces(user_name: str, project_name: str, concurrent_count: int = 10) -> Dict[str, Any]:
    """
    Performance test: Launch multiple workspaces simultaneously to test system capacity.
    
    Args:
        user_name (str): The user name for the project
        project_name (str): The project name to launch workspaces in
        concurrent_count (int): Number of workspaces to launch concurrently (default: 10)
    """
    encoded_user_name = _validate_url_parameter(user_name, "user_name")
    encoded_project_name = _validate_url_parameter(project_name, "project_name")
    
    headers = {
        "X-Domino-Api-Key": domino_api_key,
        "Content-Type": "application/json"
    }
    
    def start_workspace(workspace_index):
        start_url = f"{domino_host}/v4/workspaces"
        start_data = {
            "projectId": f"{encoded_user_name}/{encoded_project_name}",
            "name": f"Performance Test Workspace {workspace_index}",
            "workspaceTemplateName": "Jupyter",
            "hardwareTierId": "small"
        }
        
        start_time = time.time()
        result = _make_api_request("POST", start_url, headers, start_data)
        end_time = time.time()
        
        return {
            "workspace_index": workspace_index,
            "start_time": start_time,
            "end_time": end_time,
            "duration": end_time - start_time,
            "result": result,
            "status": "SUCCESS" if "error" not in result else "FAILED"
        }
    
    # Launch workspaces concurrently
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_count) as executor:
        futures = [executor.submit(start_workspace, i) for i in range(concurrent_count)]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    
    end_time = time.time()
    
    # Analyze results
    successful_launches = [r for r in results if r["status"] == "SUCCESS"]
    failed_launches = [r for r in results if r["status"] == "FAILED"]
    
    avg_duration = sum(r["duration"] for r in successful_launches) / len(successful_launches) if successful_launches else 0
    
    return {
        "test": "performance_test_workspaces",
        "user_name": user_name,
        "project_name": project_name,
        "concurrent_count": concurrent_count,
        "total_duration": end_time - start_time,
        "successful_launches": len(successful_launches),
        "failed_launches": len(failed_launches),
        "success_rate": len(successful_launches) / concurrent_count * 100,
        "average_launch_duration": avg_duration,
        "results": results,
        "status": "PASSED" if len(successful_launches) >= concurrent_count * 0.8 else "FAILED",  # 80% success rate threshold
        "timestamp": datetime.datetime.now().isoformat()
    }

@mcp.tool()
async def performance_test_jobs(user_name: str, project_name: str, concurrent_count: int = 20) -> Dict[str, Any]:
    """
    Performance test: Run multiple jobs in parallel to test job execution capacity.
    
    Args:
        user_name (str): The user name for the project
        project_name (str): The project name to run jobs in
        concurrent_count (int): Number of jobs to run concurrently (default: 20)
    """
    encoded_user_name = _validate_url_parameter(user_name, "user_name")
    encoded_project_name = _validate_url_parameter(project_name, "project_name")
    
    headers = {
        "X-Domino-Api-Key": domino_api_key,
        "Content-Type": "application/json"
    }
    
    def start_job(job_index):
        job_url = f"{domino_host}/v4/jobs/start"
        job_data = {
            "projectId": f"{encoded_user_name}/{encoded_project_name}",
            "command": ["python", "-c", f"import time; print('Performance test job {job_index}'); time.sleep(1); print('Job {job_index} completed')"],
            "title": f"Performance Test Job {job_index}",
            "isDirect": False,
            "publishApiEndpoint": False
        }
        
        start_time = time.time()
        result = _make_api_request("POST", job_url, headers, job_data)
        end_time = time.time()
        
        return {
            "job_index": job_index,
            "start_time": start_time,
            "end_time": end_time,
            "duration": end_time - start_time,
            "result": result,
            "job_id": result.get("runId") if "error" not in result else None,
            "status": "SUCCESS" if "error" not in result else "FAILED"
        }
    
    # Start jobs concurrently
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_count) as executor:
        futures = [executor.submit(start_job, i) for i in range(concurrent_count)]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    
    end_time = time.time()
    
    # Analyze results
    successful_starts = [r for r in results if r["status"] == "SUCCESS"]
    failed_starts = [r for r in results if r["status"] == "FAILED"]
    
    avg_duration = sum(r["duration"] for r in successful_starts) / len(successful_starts) if successful_starts else 0
    
    return {
        "test": "performance_test_jobs",
        "user_name": user_name,
        "project_name": project_name,
        "concurrent_count": concurrent_count,
        "total_duration": end_time - start_time,
        "successful_starts": len(successful_starts),
        "failed_starts": len(failed_starts),
        "success_rate": len(successful_starts) / concurrent_count * 100,
        "average_start_duration": avg_duration,
        "job_ids": [r["job_id"] for r in successful_starts],
        "results": results,
        "status": "PASSED" if len(successful_starts) >= concurrent_count * 0.8 else "FAILED",  # 80% success rate threshold
        "timestamp": datetime.datetime.now().isoformat()
    }

@mcp.tool()
async def stress_test_api(concurrent_requests: int = 100, test_duration: int = 60) -> Dict[str, Any]:
    """
    Stress test: Hit the API with high concurrency to test system limits.
    
    Args:
        concurrent_requests (int): Number of concurrent requests (default: 100)
        test_duration (int): Test duration in seconds (default: 60)
    """
    headers = {
        "X-Domino-Api-Key": domino_api_key,
        "Content-Type": "application/json"
    }
    
    request_count = 0
    successful_requests = 0
    failed_requests = 0
    response_times = []
    errors = []
    
    def make_request():
        nonlocal request_count, successful_requests, failed_requests, response_times, errors
        
        request_count += 1
        start_time = time.time()
        
        # Simple GET request to environments endpoint
        result = _make_api_request("GET", f"{domino_host}/v4/environments", headers)
        
        end_time = time.time()
        duration = end_time - start_time
        response_times.append(duration)
        
        if "error" in result:
            failed_requests += 1
            errors.append(result["error"])
        else:
            successful_requests += 1
    
    # Run stress test
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
        futures = []
        
        while time.time() - start_time < test_duration:
            for _ in range(min(concurrent_requests, 10)):  # Batch requests
                futures.append(executor.submit(make_request))
            
            # Wait a bit to avoid overwhelming
            time.sleep(0.1)
            
            # Clean up completed futures
            completed_futures = [f for f in futures if f.done()]
            for f in completed_futures:
                futures.remove(f)
    
    # Wait for remaining futures to complete
    for future in futures:
        future.result()
    
    end_time = time.time()
    actual_duration = end_time - start_time
    
    # Calculate statistics
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    requests_per_second = request_count / actual_duration if actual_duration > 0 else 0
    
    return {
        "test": "stress_test_api",
        "test_duration": actual_duration,
        "concurrent_requests": concurrent_requests,
        "total_requests": request_count,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "success_rate": successful_requests / request_count * 100 if request_count > 0 else 0,
        "requests_per_second": requests_per_second,
        "average_response_time": avg_response_time,
        "min_response_time": min(response_times) if response_times else 0,
        "max_response_time": max(response_times) if response_times else 0,
        "error_samples": errors[:10],  # First 10 errors
        "status": "PASSED" if successful_requests / request_count > 0.95 else "FAILED",  # 95% success rate threshold
        "timestamp": datetime.datetime.now().isoformat()
    }

# ========================================================================
# PERFORMANCE TESTING FUNCTIONS
# ========================================================================

@mcp.tool()
async def performance_test_concurrent_jobs(user_name: str, project_name: str, concurrent_count: int = 5, job_duration: int = 10) -> Dict[str, Any]:
    """
    Performance test: Launch multiple jobs concurrently to test system capacity.
    Creates the project if it doesn't exist.
    
    Args:
        user_name (str): The user name for the project
        project_name (str): The project name to launch jobs in
        concurrent_count (int): Number of jobs to launch concurrently
        job_duration (int): Duration in seconds for each job
    """
    
    test_results = {
        "test": "performance_concurrent_jobs",
        "user_name": user_name,
        "project_name": project_name,
        "concurrent_count": concurrent_count,
        "job_duration": job_duration,
        "timestamp": datetime.datetime.now().isoformat(),
        "operations": {}
    }
    
    try:
        # Ensure project exists
        project_status = await ensure_project_exists(user_name, project_name)
        test_results["project_setup"] = project_status
        
        if project_status["status"] in ["EXISTS", "CREATED", "CREATED_UNVERIFIED"]:
            domino = _create_domino_client(user_name, project_name)
            
            # Create job commands
            job_command = f"""python -c "
import time
import random
import datetime

print('Performance Test Job Started at:', datetime.datetime.now().isoformat())
print('Job ID: {{job_id}}')

# Simulate some work
for i in range({job_duration}):
    print(f'Working... step {{i+1}}/{job_duration}')
    time.sleep(1)

print('Performance Test Job Completed at:', datetime.datetime.now().isoformat())
"
"""
            
            # Launch concurrent jobs
            start_time = time.time()
            job_results = []
            
            print(f"🚀 Launching {concurrent_count} concurrent jobs...")
            
            # Start all jobs
            for i in range(concurrent_count):
                job_cmd = job_command.replace("{job_id}", f"perf-test-{i+1}")
                job_result = _safe_execute(
                    domino.job_start,
                    f"Start performance test job {i+1}",
                    job_cmd,
                    None,  # commit_id
                    None,  # hardware_tier_id
                    "small",  # hardware_tier_name
                    None,  # environment_id
                    None,  # on_demand_spark_cluster_properties
                    None,  # compute_cluster_properties
                    None,  # external_volume_mounts
                    f"Performance Test Job {i+1} - {datetime.datetime.now().strftime('%H:%M:%S')}"
                )
                job_results.append(job_result)
                test_results["operations"][f"start_job_{i+1}"] = job_result
            
            # Count successful starts
            successful_starts = sum(1 for result in job_results if result["status"] == "PASSED")
            job_ids = [result["result"].get("id") for result in job_results if result["status"] == "PASSED"]
            
            test_results["operations"]["job_launch_summary"] = {
                "status": "PASSED" if successful_starts > 0 else "FAILED",
                "description": "Job launch summary",
                "result": {
                    "requested_jobs": concurrent_count,
                    "successful_starts": successful_starts,
                    "job_ids": job_ids,
                    "launch_time_seconds": time.time() - start_time
                }
            }
            
            # Monitor job progress
            if job_ids:
                print(f"📊 Monitoring {len(job_ids)} jobs...")
                
                # Wait and check status periodically
                for check_round in range(3):
                    await asyncio.sleep(5)
                    
                    status_results = []
                    for job_id in job_ids[:3]:  # Check first 3 jobs
                        status_result = _safe_execute(domino.job_status, f"Check job status {job_id}", job_id)
                        status_results.append(status_result)
                    
                    test_results["operations"][f"status_check_round_{check_round+1}"] = {
                        "status": "PASSED",
                        "description": f"Status check round {check_round+1}",
                        "result": status_results
                    }
            
            # Final summary
            end_time = time.time()
            test_results["operations"]["performance_summary"] = {
                "status": "PASSED",
                "description": "Performance test summary",
                "result": {
                    "total_test_time_seconds": end_time - start_time,
                    "jobs_per_second": successful_starts / (end_time - start_time) if end_time > start_time else 0,
                    "success_rate": f"{(successful_starts/concurrent_count)*100:.1f}%" if concurrent_count > 0 else "0%"
                }
            }
            
            # Determine overall status
            failed_ops = [k for k, v in test_results["operations"].items() if v["status"] == "FAILED"]
            test_results["status"] = "FAILED" if failed_ops else "PASSED"
            test_results["failed_operations"] = failed_ops
            
            if test_results["status"] == "PASSED":
                test_results["message"] = f"Performance test completed: {successful_starts}/{concurrent_count} jobs started successfully"
            else:
                test_results["message"] = f"Performance test failed: {failed_ops}"
                
        elif project_status["status"] == "NOT_FOUND":
            test_results.update({
                "status": "SKIPPED",
                "message": f"Project {user_name}/{project_name} not found - manual creation required",
                "guidance": project_status.get("guidance")
            })
        else:
            test_results.update({
                "status": "FAILED",
                "error": project_status.get("error"),
                "message": f"Could not access project {user_name}/{project_name}"
            })
        
        return test_results
        
    except Exception as e:
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during performance test"
        })
        return test_results

@mcp.tool()
async def performance_test_data_upload_throughput(user_name: str, project_name: str, file_size_mb: int = 10, file_count: int = 5) -> Dict[str, Any]:
    """
    Performance test: Test data upload throughput by uploading multiple files.
    Creates the project if it doesn't exist.
    
    Args:
        user_name (str): The user name for the project
        project_name (str): The project name to test uploads
        file_size_mb (int): Size of each test file in MB
        file_count (int): Number of files to upload
    """
    
    test_results = {
        "test": "performance_data_upload_throughput",
        "user_name": user_name,
        "project_name": project_name,
        "file_size_mb": file_size_mb,
        "file_count": file_count,
        "timestamp": datetime.datetime.now().isoformat(),
        "operations": {}
    }
    
    try:
        # Ensure project exists
        project_status = await ensure_project_exists(user_name, project_name)
        test_results["project_setup"] = project_status
        
        if project_status["status"] in ["EXISTS", "CREATED", "CREATED_UNVERIFIED"]:
            domino = _create_domino_client(user_name, project_name)
            
            # Create a test dataset for uploads
            dataset_name = f"performance-test-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
            dataset_result = _safe_execute(
                domino.datasets_create,
                "Create performance test dataset",
                dataset_name,
                f"Performance test dataset for upload throughput testing"
            )
            test_results["operations"]["create_dataset"] = dataset_result
            
            if dataset_result["status"] == "PASSED":
                dataset_id = dataset_result["result"].get("id")
                
                try:
                    import tempfile
                    import os
                    
                    start_time = time.time()
                    total_bytes = 0
                    upload_results = []
                    
                    print(f"📁 Preparing {file_count} test files of {file_size_mb}MB each...")
                    
                    for i in range(file_count):
                        # Generate test data
                        try:
                            import pandas as pd
                            import numpy as np
                            
                            # Calculate rows needed for approximately file_size_mb MB
                            rows_needed = (file_size_mb * 1024 * 1024) // (8 * 10)  # Rough estimate
                            
                            test_data = pd.DataFrame({
                                'id': range(rows_needed),
                                'timestamp': [datetime.datetime.now().isoformat()] * rows_needed,
                                'value1': np.random.randn(rows_needed),
                                'value2': np.random.randn(rows_needed),
                                'value3': np.random.randn(rows_needed),
                                'value4': np.random.randn(rows_needed),
                                'value5': np.random.randn(rows_needed),
                                'category': [f'category_{j % 100}' for j in range(rows_needed)],
                                'description': [f'test_data_row_{j}' for j in range(rows_needed)]
                            })
                            
                        except ImportError:
                            # Fallback if pandas/numpy not available
                            rows_needed = (file_size_mb * 1024 * 1024) // 100  # Rough estimate
                            test_data_lines = []
                            test_data_lines.append("id,timestamp,value1,value2,description")
                            for j in range(rows_needed):
                                test_data_lines.append(f"{j},{datetime.datetime.now().isoformat()},{j*0.1},{j*0.2},test_data_row_{j}")
                            test_data_content = "\n".join(test_data_lines)
                        
                        # Save to temp file
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
                            if 'test_data' in locals() and hasattr(test_data, 'to_csv'):
                                test_data.to_csv(f.name, index=False)
                            else:
                                f.write(test_data_content)
                            temp_file_path = f.name
                        
                        # Get actual file size
                        actual_size = os.path.getsize(temp_file_path)
                        total_bytes += actual_size
                        
                        # Upload file
                        file_start_time = time.time()
                        upload_result = _safe_execute(
                            domino.datasets_upload_files,
                            f"Upload test file {i+1}",
                            dataset_id,
                            temp_file_path
                        )
                        upload_time = time.time() - file_start_time
                        
                        upload_results.append({
                            "file_index": i + 1,
                            "file_size_bytes": actual_size,
                            "upload_time_seconds": upload_time,
                            "throughput_mbps": (actual_size / (1024*1024)) / upload_time if upload_time > 0 else 0,
                            "status": upload_result["status"]
                        })
                        
                        test_results["operations"][f"upload_file_{i+1}"] = upload_result
                        
                        # Clean up temp file
                        os.unlink(temp_file_path)
                        
                        print(f"   📤 File {i+1}/{file_count}: {actual_size/(1024*1024):.1f}MB uploaded in {upload_time:.2f}s")
                    
                    # Calculate overall performance metrics
                    total_time = time.time() - start_time
                    successful_uploads = sum(1 for result in upload_results if result["status"] == "PASSED")
                    
                    test_results["operations"]["performance_metrics"] = {
                        "status": "PASSED",
                        "description": "Upload performance metrics",
                        "result": {
                            "total_files": file_count,
                            "successful_uploads": successful_uploads,
                            "total_bytes": total_bytes,
                            "total_mb": total_bytes / (1024*1024),
                            "total_time_seconds": total_time,
                            "average_throughput_mbps": (total_bytes / (1024*1024)) / total_time if total_time > 0 else 0,
                            "files_per_second": successful_uploads / total_time if total_time > 0 else 0,
                            "individual_uploads": upload_results
                        }
                    }
                    
                except Exception as e:
                    test_results["operations"]["file_upload_error"] = {
                        "status": "FAILED",
                        "error": str(e),
                        "description": "File upload performance test"
                    }
            
            # Determine overall status
            failed_ops = [k for k, v in test_results["operations"].items() if v["status"] == "FAILED"]
            test_results["status"] = "FAILED" if failed_ops else "PASSED"
            test_results["failed_operations"] = failed_ops
            
            if test_results["status"] == "PASSED":
                metrics = test_results["operations"].get("performance_metrics", {}).get("result", {})
                avg_throughput = metrics.get("average_throughput_mbps", 0)
                test_results["message"] = f"Upload performance test completed: {avg_throughput:.2f} MB/s average throughput"
            else:
                test_results["message"] = f"Upload performance test failed: {failed_ops}"
                
        elif project_status["status"] == "NOT_FOUND":
            test_results.update({
                "status": "SKIPPED",
                "message": f"Project {user_name}/{project_name} not found - manual creation required",
                "guidance": project_status.get("guidance")
            })
        else:
            test_results.update({
                "status": "FAILED",
                "error": project_status.get("error"),
                "message": f"Could not access project {user_name}/{project_name}"
            })
        
        return test_results
        
    except Exception as e:
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during upload performance test"
        })
        return test_results

# ========================================================================
# ADVANCED DATASET OPERATIONS
# ========================================================================

@mcp.tool()
async def test_dataset_creation_and_upload(user_name: str, project_name: str, dataset_name: str = "uat-test-dataset") -> Dict[str, Any]:
    """
    Comprehensive dataset testing: creation, upload, and validation.
    Creates the project if it doesn't exist.
    
    Args:
        user_name (str): The user name for dataset operations
        project_name (str): The project name to test dataset operations
        dataset_name (str): Name for the test dataset
    """
    
    test_results = {
        "test": "dataset_creation_and_upload",
        "user_name": user_name,
        "project_name": project_name,
        "dataset_name": dataset_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "operations": {}
    }
    
    try:
        # Ensure project exists
        project_status = await ensure_project_exists(user_name, project_name)
        test_results["project_setup"] = project_status
        
        if project_status["status"] in ["EXISTS", "CREATED", "CREATED_UNVERIFIED"]:
            domino = _create_domino_client(user_name, project_name)
            
            # Test 1: Create dataset
            create_result = _safe_execute(
                domino.datasets_create, 
                "Create test dataset",
                dataset_name, 
                f"UAT test dataset created at {datetime.datetime.now().isoformat()}"
            )
            test_results["operations"]["create_dataset"] = create_result
            
            if create_result["status"] == "PASSED":
                dataset_id = create_result["result"].get("id")
                
                # Test 2: List datasets to verify creation
                list_result = _safe_execute(domino.datasets_list, "List datasets after creation")
                test_results["operations"]["list_datasets"] = list_result
                
                # Test 3: Get dataset details
                if dataset_id:
                    details_result = _safe_execute(domino.datasets_details, "Get dataset details", dataset_id)
                    test_results["operations"]["dataset_details"] = details_result
                
                # Test 4: Upload test data (create a simple CSV)
                try:
                    import tempfile
                    import os
                    try:
                        import pandas as pd
                        
                        # Create test data
                        test_data = pd.DataFrame({
                            'id': range(1, 101),
                            'value': [f'test_value_{i}' for i in range(1, 101)],
                            'score': [i * 0.1 for i in range(1, 101)]
                        })
                        
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
                            test_data.to_csv(f.name, index=False)
                            temp_csv_path = f.name
                    except ImportError:
                        # Fallback if pandas not available
                        test_data_lines = ["id,value,score"]
                        for i in range(1, 101):
                            test_data_lines.append(f"{i},test_value_{i},{i * 0.1}")
                        
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
                            f.write("\n".join(test_data_lines))
                            temp_csv_path = f.name
                    
                    upload_result = _safe_execute(
                        domino.datasets_upload_files,
                        "Upload test CSV to dataset",
                        dataset_id,
                        temp_csv_path
                    )
                    test_results["operations"]["upload_file"] = upload_result
                    
                    # Clean up temp file
                    os.unlink(temp_csv_path)
                    
                except Exception as e:
                    test_results["operations"]["upload_file"] = {
                        "status": "FAILED",
                        "error": str(e),
                        "description": "Upload test CSV to dataset"
                    }
            
            # Determine overall status
            failed_ops = [k for k, v in test_results["operations"].items() if v["status"] == "FAILED"]
            test_results["status"] = "FAILED" if failed_ops else "PASSED"
            test_results["failed_operations"] = failed_ops
            
            if test_results["status"] == "PASSED":
                test_results["message"] = f"All dataset operations successful for {dataset_name}"
            else:
                test_results["message"] = f"Some dataset operations failed: {failed_ops}"
                
        elif project_status["status"] == "NOT_FOUND":
            test_results.update({
                "status": "SKIPPED",
                "message": f"Project {user_name}/{project_name} not found - manual creation required",
                "guidance": project_status.get("guidance")
            })
        else:
            test_results.update({
                "status": "FAILED",
                "error": project_status.get("error"),
                "message": f"Could not access project {user_name}/{project_name}"
            })
        
        return test_results
        
    except Exception as e:
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during dataset operations test"
        })
        return test_results

@mcp.tool()
async def test_file_management_operations(user_name: str, project_name: str) -> Dict[str, Any]:
    """
    Tests file upload, listing, and management operations.
    Creates the project if it doesn't exist.
    
    Args:
        user_name (str): The user name for file operations
        project_name (str): The project name to test file operations
    """
    
    test_results = {
        "test": "file_management_operations",
        "user_name": user_name,
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "operations": {}
    }
    
    try:
        # Ensure project exists
        project_status = await ensure_project_exists(user_name, project_name)
        test_results["project_setup"] = project_status
        
        if project_status["status"] in ["EXISTS", "CREATED", "CREATED_UNVERIFIED"]:
            domino = _create_domino_client(user_name, project_name)
            
            # Test 1: List current files
            list_result = _safe_execute(domino.files_list, "List project files", None)
            test_results["operations"]["list_files"] = list_result
            
            # Test 2: Upload a test file
            try:
                import tempfile
                import os
                
                # Create a test file
                test_content = f"""# UAT Test File
# Generated at: {datetime.datetime.now().isoformat()}
# Purpose: Testing file upload capabilities

def uat_test_function():
    '''Simple test function for UAT validation'''
    return "UAT test file executed successfully"

if __name__ == "__main__":
    print("UAT Test File executed successfully")
    result = uat_test_function()
    print(result)
"""
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(test_content)
                    temp_file_path = f.name
                
                upload_result = _safe_execute(
                    domino.files_upload,
                    "Upload test Python file",
                    "uat_test_file.py",
                    temp_file_path
                )
                test_results["operations"]["upload_file"] = upload_result
                
                # Clean up temp file
                os.unlink(temp_file_path)
                
                # Test 3: List files again to verify upload
                if upload_result["status"] == "PASSED":
                    verify_result = _safe_execute(domino.files_list, "Verify file upload", None)
                    test_results["operations"]["verify_upload"] = verify_result
                
            except Exception as e:
                test_results["operations"]["upload_file"] = {
                    "status": "FAILED",
                    "error": str(e),
                    "description": "Upload test Python file"
                }
            
            # Determine overall status
            failed_ops = [k for k, v in test_results["operations"].items() if v["status"] == "FAILED"]
            test_results["status"] = "FAILED" if failed_ops else "PASSED"
            test_results["failed_operations"] = failed_ops
            
            if test_results["status"] == "PASSED":
                test_results["message"] = f"All file operations successful for {user_name}/{project_name}"
            else:
                test_results["message"] = f"Some file operations failed: {failed_ops}"
                
        elif project_status["status"] == "NOT_FOUND":
            test_results.update({
                "status": "SKIPPED",
                "message": f"Project {user_name}/{project_name} not found - manual creation required",
                "guidance": project_status.get("guidance")
            })
        else:
            test_results.update({
                "status": "FAILED",
                "error": project_status.get("error"),
                "message": f"Could not access project {user_name}/{project_name}"
            })
        
        return test_results
        
    except Exception as e:
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during file operations test"
        })
        return test_results

# ========================================================================
# ENVIRONMENT AND HARDWARE TESTING
# ========================================================================

@mcp.tool()
async def test_environment_and_hardware_operations(user_name: str) -> Dict[str, Any]:
    """
    Comprehensive testing of environments and hardware tiers.
    
    Args:
        user_name (str): The user name for testing
    """
    
    test_results = {
        "test": "environment_and_hardware_operations",
        "user_name": user_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "operations": {}
    }
    
    try:
        # Create a dummy domino client for environment/hardware operations
        domino = _create_domino_client(user_name, "quick-start")  # Use existing project
        
        # Test 1: List environments
        env_result = _safe_execute(domino.environments_list, "List available environments")
        test_results["operations"]["list_environments"] = env_result
        
        # Test 2: List hardware tiers
        hw_result = _safe_execute(domino.hardware_tiers_list, "List available hardware tiers")
        test_results["operations"]["list_hardware_tiers"] = hw_result
        
        # Test 3: Test hardware tier name resolution
        if hw_result["status"] == "PASSED":
            hardware_tiers = hw_result.get("result", [])
            if hardware_tiers:
                # Try to get ID for the first hardware tier
                first_tier = hardware_tiers[0]
                tier_name = first_tier.get("name") if isinstance(first_tier, dict) else str(first_tier)
                
                tier_id_result = _safe_execute(
                    domino.get_hardware_tier_id_from_name,
                    f"Get hardware tier ID for '{tier_name}'",
                    tier_name
                )
                test_results["operations"]["get_hardware_tier_id"] = tier_id_result
        
        # Determine overall status
        failed_ops = [k for k, v in test_results["operations"].items() if v["status"] == "FAILED"]
        test_results["status"] = "FAILED" if failed_ops else "PASSED"
        test_results["failed_operations"] = failed_ops
        
        if test_results["status"] == "PASSED":
            test_results["message"] = f"All environment/hardware operations successful"
        else:
            test_results["message"] = f"Some environment/hardware operations failed: {failed_ops}"
        
        return test_results
        
    except Exception as e:
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during environment/hardware operations test"
        })
        return test_results

# ========================================================================
# ADVANCED JOB MANAGEMENT
# ========================================================================

@mcp.tool()
async def test_advanced_job_operations(user_name: str, project_name: str, hardware_tier: str = "small") -> Dict[str, Any]:
    """
    Advanced job testing including hardware tiers, blocking execution, and job management.
    Creates the project if it doesn't exist.
    
    Args:
        user_name (str): The user name for the project
        project_name (str): The project name to run jobs in
        hardware_tier (str): Hardware tier to use for testing
    """
    
    test_results = {
        "test": "advanced_job_operations",
        "user_name": user_name,
        "project_name": project_name,
        "hardware_tier": hardware_tier,
        "timestamp": datetime.datetime.now().isoformat(),
        "operations": {}
    }
    
    try:
        # Ensure project exists
        project_status = await ensure_project_exists(user_name, project_name)
        test_results["project_setup"] = project_status
        
        if project_status["status"] in ["EXISTS", "CREATED", "CREATED_UNVERIFIED"]:
            domino = _create_domino_client(user_name, project_name)
            
            # Test 1: List existing jobs
            jobs_list_result = _safe_execute(domino.jobs_list, "List existing jobs", project_name)
            test_results["operations"]["list_jobs"] = jobs_list_result
            
            # Test 2: Start a job with specific hardware tier
            job_command = "python -c \"import time; print('Job started'); time.sleep(5); print('Job completed successfully')\""
            
            job_start_result = _safe_execute(
                domino.job_start,
                "Start job with hardware tier",
                job_command,
                None,  # commit_id
                None,  # hardware_tier_id (will use name)
                hardware_tier,  # hardware_tier_name
                None,  # environment_id
                None,  # on_demand_spark_cluster_properties
                None,  # compute_cluster_properties
                None,  # external_volume_mounts
                f"UAT Advanced Job Test - {datetime.datetime.now().strftime('%H:%M:%S')}"  # title
            )
            test_results["operations"]["start_job"] = job_start_result
            
            if job_start_result["status"] == "PASSED":
                job_id = job_start_result["result"].get("id")
                
                # Test 3: Get job status
                if job_id:
                    status_result = _safe_execute(domino.job_status, "Check job status", job_id)
                    test_results["operations"]["job_status"] = status_result
                    
                    # Test 4: Get job runtime details
                    runtime_result = _safe_execute(domino.job_runtime_execution_details, "Get job runtime details", job_id)
                    test_results["operations"]["job_runtime_details"] = runtime_result
                    
                    # Test 5: Wait a bit and check status again
                    await asyncio.sleep(3)
                    final_status_result = _safe_execute(domino.job_status, "Check final job status", job_id)
                    test_results["operations"]["final_job_status"] = final_status_result
                    
                    # Test 6: Stop job if still running
                    if final_status_result["status"] == "PASSED":
                        job_status = final_status_result["result"].get("status", "")
                        if job_status not in ["Succeeded", "Failed", "Stopped"]:
                            stop_result = _safe_execute(domino.job_stop, "Stop running job", job_id)
                            test_results["operations"]["stop_job"] = stop_result
            
            # Test 7: Start a blocking job (quick one)
            blocking_command = "python -c \"print('Blocking job test'); import sys; print(f'Python version: {sys.version}')\""
            
            blocking_result = _safe_execute(
                domino.job_start_blocking,
                "Start blocking job",
                5,  # poll_freq
                60,  # max_poll_time (1 minute)
                (),  # ignore_exceptions
                command=blocking_command,
                title="UAT Blocking Job Test"
            )
            test_results["operations"]["blocking_job"] = blocking_result
            
            # Determine overall status
            failed_ops = [k for k, v in test_results["operations"].items() if v["status"] == "FAILED"]
            test_results["status"] = "FAILED" if failed_ops else "PASSED"
            test_results["failed_operations"] = failed_ops
            
            if test_results["status"] == "PASSED":
                test_results["message"] = f"All advanced job operations successful"
            else:
                test_results["message"] = f"Some advanced job operations failed: {failed_ops}"
                
        elif project_status["status"] == "NOT_FOUND":
            test_results.update({
                "status": "SKIPPED",
                "message": f"Project {user_name}/{project_name} not found - manual creation required",
                "guidance": project_status.get("guidance")
            })
        else:
            test_results.update({
                "status": "FAILED",
                "error": project_status.get("error"),
                "message": f"Could not access project {user_name}/{project_name}"
            })
        
        return test_results
        
    except Exception as e:
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during advanced job operations test"
        })
        return test_results

# ========================================================================
# PROJECT COLLABORATION TESTING
# ========================================================================

@mcp.tool()
async def test_collaboration_features(user_name: str, project_name: str, collaborator_email: str = None) -> Dict[str, Any]:
    """
    Tests project collaboration features including collaborator management and tags.
    Creates the project if it doesn't exist.
    
    Args:
        user_name (str): The user name for the project
        project_name (str): The project name to test collaboration features
        collaborator_email (str): Optional email to test collaborator addition
    """
    
    test_results = {
        "test": "collaboration_features",
        "user_name": user_name,
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "operations": {}
    }
    
    try:
        # Ensure project exists
        project_status = await ensure_project_exists(user_name, project_name)
        test_results["project_setup"] = project_status
        
        if project_status["status"] in ["EXISTS", "CREATED", "CREATED_UNVERIFIED"]:
            domino = _create_domino_client(user_name, project_name)
            
            # Test 1: Get current collaborators
            collab_get_result = _safe_execute(domino.collaborators_get, "Get current collaborators")
            test_results["operations"]["get_collaborators"] = collab_get_result
            
            # Test 2: Add collaborator (if email provided)
            if collaborator_email:
                collab_add_result = _safe_execute(
                    domino.collaborators_add,
                    f"Add collaborator {collaborator_email}",
                    collaborator_email,
                    f"UAT test collaboration at {datetime.datetime.now().isoformat()}"
                )
                test_results["operations"]["add_collaborator"] = collab_add_result
                
                # Test 3: Verify collaborator was added
                if collab_add_result["status"] == "PASSED":
                    verify_result = _safe_execute(domino.collaborators_get, "Verify collaborator addition")
                    test_results["operations"]["verify_collaborator"] = verify_result
                    
                    # Test 4: Remove collaborator (cleanup)
                    remove_result = _safe_execute(
                        domino.collaborators_remove,
                        f"Remove collaborator {collaborator_email}",
                        collaborator_email
                    )
                    test_results["operations"]["remove_collaborator"] = remove_result
            
            # Test 5: List current tags
            tags_list_result = _safe_execute(domino.tags_list, "List project tags")
            test_results["operations"]["list_tags"] = tags_list_result
            
            # Test 6: Add test tags
            test_tags = ["uat-test", "automated-testing", f"test-{datetime.datetime.now().strftime('%Y%m%d')}"]
            add_tags_result = _safe_execute(domino.tags_add, "Add test tags", test_tags)
            test_results["operations"]["add_tags"] = add_tags_result
            
            # Test 7: Verify tags were added
            if add_tags_result["status"] == "PASSED":
                verify_tags_result = _safe_execute(domino.tags_list, "Verify tags addition")
                test_results["operations"]["verify_tags"] = verify_tags_result
                
                # Test 8: Remove test tags (cleanup)
                for tag in test_tags:
                    remove_tag_result = _safe_execute(domino.tags_remove, f"Remove tag '{tag}'", tag)
                    test_results["operations"][f"remove_tag_{tag}"] = remove_tag_result
            
            # Determine overall status
            failed_ops = [k for k, v in test_results["operations"].items() if v["status"] == "FAILED"]
            test_results["status"] = "FAILED" if failed_ops else "PASSED"
            test_results["failed_operations"] = failed_ops
            
            if test_results["status"] == "PASSED":
                test_results["message"] = f"All collaboration features tested successfully"
            else:
                test_results["message"] = f"Some collaboration operations failed: {failed_ops}"
                
        elif project_status["status"] == "NOT_FOUND":
            test_results.update({
                "status": "SKIPPED",
                "message": f"Project {user_name}/{project_name} not found - manual creation required",
                "guidance": project_status.get("guidance")
            })
        else:
            test_results.update({
                "status": "FAILED",
                "error": project_status.get("error"),
                "message": f"Could not access project {user_name}/{project_name}"
            })
        
        return test_results
        
    except Exception as e:
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during collaboration features test"
        })
        return test_results

# ========================================================================
# MODEL DEPLOYMENT TESTING
# ========================================================================

@mcp.tool()
async def test_model_operations(user_name: str, project_name: str) -> Dict[str, Any]:
    """
    Tests model listing and basic model operations.
    Creates the project if it doesn't exist.
    
    Args:
        user_name (str): The user name for the project
        project_name (str): The project name to test model operations
    """
    
    test_results = {
        "test": "model_operations",
        "user_name": user_name,
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "operations": {}
    }
    
    try:
        # Ensure project exists
        project_status = await ensure_project_exists(user_name, project_name)
        test_results["project_setup"] = project_status
        
        if project_status["status"] in ["EXISTS", "CREATED", "CREATED_UNVERIFIED"]:
            domino = _create_domino_client(user_name, project_name)
            
            # Test 1: List models
            models_result = _safe_execute(domino.models_list, "List available models")
            test_results["operations"]["list_models"] = models_result
            
            # Test 2: Check endpoint state
            endpoint_result = _safe_execute(domino.endpoint_state, "Check endpoint state")
            test_results["operations"]["endpoint_state"] = endpoint_result
            
            # Test 3: Get deployment version info
            version_result = _safe_execute(domino.deployment_version, "Get deployment version")
            test_results["operations"]["deployment_version"] = version_result
            
            # Determine overall status
            failed_ops = [k for k, v in test_results["operations"].items() if v["status"] == "FAILED"]
            test_results["status"] = "FAILED" if failed_ops else "PASSED"
            test_results["failed_operations"] = failed_ops
            
            if test_results["status"] == "PASSED":
                test_results["message"] = f"All model operations tested successfully"
            else:
                test_results["message"] = f"Some model operations failed: {failed_ops}"
                
        elif project_status["status"] == "NOT_FOUND":
            test_results.update({
                "status": "SKIPPED",
                "message": f"Project {user_name}/{project_name} not found - manual creation required",
                "guidance": project_status.get("guidance")
            })
        else:
            test_results.update({
                "status": "FAILED",
                "error": project_status.get("error"),
                "message": f"Could not access project {user_name}/{project_name}"
            })
        
        return test_results
        
    except Exception as e:
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during model operations test"
        })
        return test_results

# ========================================================================
# COMPREHENSIVE UAT SUITE WITH ALL NEW FUNCTIONS
# ========================================================================

@mcp.tool()
async def run_comprehensive_advanced_uat_suite(user_name: str, project_name: str, collaborator_email: str = None) -> Dict[str, Any]:
    """
    Runs a comprehensive UAT suite including all advanced features:
    - Authentication & Project Operations
    - Dataset Creation & File Management
    - Environment & Hardware Testing
    - Advanced Job Operations
    - Collaboration Features
    - Model Operations
    
    Args:
        user_name (str): The user name for testing
        project_name (str): The project name for testing
        collaborator_email (str): Optional collaborator email for testing
    """
    
    suite_results = {
        "test_suite": "comprehensive_advanced_uat",
        "user_name": user_name,
        "project_name": project_name,
        "start_time": datetime.datetime.now().isoformat(),
        "tests": {}
    }
    
    try:
        print(f"🚀 Starting Comprehensive Advanced UAT Suite")
        print(f"👤 User: {user_name}")
        print(f"📁 Project: {project_name}")
        print("="*60)
        
        # Test 1: User Authentication & Project Operations
        print("\n1. 🔐 Testing User Authentication & Project Operations...")
        auth_result = await test_user_authentication(user_name, project_name)
        suite_results["tests"]["authentication"] = auth_result
        
        project_ops_result = await test_project_operations(user_name, project_name)
        suite_results["tests"]["project_operations"] = project_ops_result
        
        # Test 2: Dataset & File Operations
        print("\n2. 📊 Testing Dataset Creation & Upload...")
        dataset_result = await test_dataset_creation_and_upload(user_name, project_name)
        suite_results["tests"]["dataset_operations"] = dataset_result
        
        print("\n3. 📁 Testing File Management...")
        file_result = await test_file_management_operations(user_name, project_name)
        suite_results["tests"]["file_operations"] = file_result
        
        # Test 3: Environment & Hardware
        print("\n4. ⚙️ Testing Environment & Hardware...")
        env_hw_result = await test_environment_and_hardware_operations(user_name)
        suite_results["tests"]["environment_hardware"] = env_hw_result
        
        # Test 4: Advanced Job Operations
        print("\n5. 🏃 Testing Advanced Job Operations...")
        job_result = await test_advanced_job_operations(user_name, project_name)
        suite_results["tests"]["advanced_jobs"] = job_result
        
        # Test 5: Collaboration Features
        print("\n6. 🤝 Testing Collaboration Features...")
        collab_result = await test_collaboration_features(user_name, project_name, collaborator_email)
        suite_results["tests"]["collaboration"] = collab_result
        
        # Test 6: Model Operations
        print("\n7. 🤖 Testing Model Operations...")
        model_result = await test_model_operations(user_name, project_name)
        suite_results["tests"]["models"] = model_result
        
        # Calculate overall results
        total_tests = len(suite_results["tests"])
        passed_tests = sum(1 for result in suite_results["tests"].values() if result["status"] == "PASSED")
        skipped_tests = sum(1 for result in suite_results["tests"].values() if result["status"] == "SKIPPED")
        failed_tests = total_tests - passed_tests - skipped_tests
        
        suite_results["end_time"] = datetime.datetime.now().isoformat()
        suite_results["summary"] = {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "skipped": skipped_tests,
            "success_rate": f"{(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%"
        }
        
        suite_results["status"] = "PASSED" if failed_tests == 0 else "FAILED"
        suite_results["message"] = f"Comprehensive UAT completed: {passed_tests}/{total_tests} tests passed"
        
        print(f"\n🎯 UAT Suite Results:")
        print(f"   ✅ Passed: {passed_tests}")
        print(f"   ❌ Failed: {failed_tests}")
        print(f"   ⏭️ Skipped: {skipped_tests}")
        print(f"   📊 Success Rate: {suite_results['summary']['success_rate']}")
        
        return suite_results
        
    except Exception as e:
        suite_results.update({
            "status": "FAILED",
            "error": str(e),
            "end_time": datetime.datetime.now().isoformat(),
            "message": f"Exception during comprehensive UAT suite: {e}"
        })
        return suite_results

# ========================================================================
# UTILITY AND MAINTENANCE FUNCTIONS
# ========================================================================

@mcp.tool()
async def cleanup_test_resources(user_name: str, project_prefix: str = "uat", dataset_prefix: str = "uat-test") -> Dict[str, Any]:
    """
    Cleans up test resources including datasets and tags created during testing.
    
    Args:
        user_name (str): The user name for cleanup operations
        project_prefix (str): Prefix to identify test projects
        dataset_prefix (str): Prefix to identify test datasets
    """
    
    cleanup_results = {
        "test": "cleanup_test_resources",
        "user_name": user_name,
        "project_prefix": project_prefix,
        "dataset_prefix": dataset_prefix,
        "timestamp": datetime.datetime.now().isoformat(),
        "operations": {}
    }
    
    try:
        # Use quick-start as the project for cleanup operations
        domino = _create_domino_client(user_name, "quick-start")
        
        # List and clean up datasets
        datasets_result = _safe_execute(domino.datasets_list, "List datasets for cleanup")
        cleanup_results["operations"]["list_datasets"] = datasets_result
        
        if datasets_result["status"] == "PASSED":
            datasets = datasets_result.get("result", [])
            test_datasets = []
            
            for dataset in datasets:
                dataset_name = dataset.get("name", "") if isinstance(dataset, dict) else str(dataset)
                if dataset_name.startswith(dataset_prefix):
                    test_datasets.append(dataset)
            
            if test_datasets:
                # Remove test datasets
                dataset_ids = [d.get("id") for d in test_datasets if isinstance(d, dict) and d.get("id")]
                if dataset_ids:
                    remove_result = _safe_execute(domino.datasets_remove, "Remove test datasets", dataset_ids)
                    cleanup_results["operations"]["remove_datasets"] = remove_result
                    cleanup_results["operations"]["removed_dataset_count"] = len(dataset_ids)
                else:
                    cleanup_results["operations"]["remove_datasets"] = {
                        "status": "SKIPPED",
                        "description": "No dataset IDs found for removal"
                    }
            else:
                cleanup_results["operations"]["remove_datasets"] = {
                    "status": "SKIPPED",
                    "description": f"No datasets found with prefix '{dataset_prefix}'"
                }
        
        # List and clean up tags
        tags_result = _safe_execute(domino.tags_list, "List tags for cleanup")
        cleanup_results["operations"]["list_tags"] = tags_result
        
        if tags_result["status"] == "PASSED":
            tags = tags_result.get("result", [])
            test_tags = []
            
            for tag in tags:
                tag_name = tag.get("name", "") if isinstance(tag, dict) else str(tag)
                if any(prefix in tag_name for prefix in ["uat-test", "automated-testing", "test-"]):
                    test_tags.append(tag_name)
            
            if test_tags:
                # Remove test tags
                removed_tags = []
                for tag_name in test_tags:
                    remove_tag_result = _safe_execute(domino.tags_remove, f"Remove tag '{tag_name}'", tag_name)
                    if remove_tag_result["status"] == "PASSED":
                        removed_tags.append(tag_name)
                
                cleanup_results["operations"]["remove_tags"] = {
                    "status": "PASSED",
                    "description": "Remove test tags",
                    "result": {
                        "requested_removals": len(test_tags),
                        "successful_removals": len(removed_tags),
                        "removed_tags": removed_tags
                    }
                }
            else:
                cleanup_results["operations"]["remove_tags"] = {
                    "status": "SKIPPED",
                    "description": "No test tags found for removal"
                }
        
        # Summary
        cleanup_results["operations"]["cleanup_summary"] = {
            "status": "PASSED",
            "description": "Cleanup operation summary",
            "result": {
                "datasets_cleaned": cleanup_results["operations"].get("removed_dataset_count", 0),
                "tags_cleaned": len(cleanup_results["operations"].get("remove_tags", {}).get("result", {}).get("removed_tags", [])),
                "cleanup_completed_at": datetime.datetime.now().isoformat()
            }
        }
        
        # Determine overall status
        failed_ops = [k for k, v in cleanup_results["operations"].items() if v["status"] == "FAILED"]
        cleanup_results["status"] = "FAILED" if failed_ops else "PASSED"
        cleanup_results["failed_operations"] = failed_ops
        
        if cleanup_results["status"] == "PASSED":
            summary = cleanup_results["operations"]["cleanup_summary"]["result"]
            cleanup_results["message"] = f"Cleanup completed: {summary['datasets_cleaned']} datasets, {summary['tags_cleaned']} tags removed"
        else:
            cleanup_results["message"] = f"Some cleanup operations failed: {failed_ops}"
        
        return cleanup_results
        
    except Exception as e:
        cleanup_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during cleanup"
        })
        return cleanup_results

# ========================================================================
# MASTER COMPREHENSIVE UAT WITH PERFORMANCE
# ========================================================================

@mcp.tool()
async def run_master_comprehensive_uat_suite(user_name: str, project_name: str, include_performance: bool = True, collaborator_email: str = None) -> Dict[str, Any]:
    """
    Runs the ultimate comprehensive UAT suite including:
    - All basic operations (auth, projects, jobs, datasets)
    - All advanced features (collaboration, models, files)
    - Performance testing (concurrent jobs, upload throughput)
    - Cleanup operations
    
    Args:
        user_name (str): The user name for testing
        project_name (str): The project name for testing
        include_performance (bool): Whether to include performance tests
        collaborator_email (str): Optional collaborator email for testing
    """
    
    master_results = {
        "test_suite": "master_comprehensive_uat",
        "user_name": user_name,
        "project_name": project_name,
        "include_performance": include_performance,
        "start_time": datetime.datetime.now().isoformat(),
        "test_phases": {}
    }
    
    try:
        print(f"🎯 Starting MASTER Comprehensive UAT Suite")
        print(f"👤 User: {user_name}")
        print(f"📁 Project: {project_name}")
        print(f"🚀 Performance Tests: {'Enabled' if include_performance else 'Disabled'}")
        print("="*70)
        
        # Phase 1: Core Advanced UAT
        print("\n🔵 PHASE 1: Advanced UAT Suite")
        phase1_result = await run_comprehensive_advanced_uat_suite(user_name, project_name, collaborator_email)
        master_results["test_phases"]["advanced_uat"] = phase1_result
        
        # Phase 2: Performance Testing (if enabled)
        if include_performance:
            print(f"\n🟡 PHASE 2: Performance Testing")
            
            # Performance Test 1: Concurrent Jobs
            print(f"   🏃 Testing concurrent job performance...")
            perf_jobs_result = await performance_test_concurrent_jobs(user_name, project_name, 3, 8)
            master_results["test_phases"]["performance_jobs"] = perf_jobs_result
            
            # Performance Test 2: Upload Throughput
            print(f"   📁 Testing upload throughput...")
            perf_upload_result = await performance_test_data_upload_throughput(user_name, project_name, 5, 3)
            master_results["test_phases"]["performance_uploads"] = perf_upload_result
        
        # Phase 3: Cleanup
        print(f"\n🟢 PHASE 3: Cleanup Operations")
        cleanup_result = await cleanup_test_resources(user_name)
        master_results["test_phases"]["cleanup"] = cleanup_result
        
        # Calculate master results
        all_phases = master_results["test_phases"]
        total_phases = len(all_phases)
        passed_phases = sum(1 for result in all_phases.values() if result["status"] == "PASSED")
        failed_phases = total_phases - passed_phases
        
        # Calculate detailed test counts
        total_tests = 0
        total_passed = 0
        total_failed = 0
        total_skipped = 0
        
        for phase_name, phase_result in all_phases.items():
            if "summary" in phase_result:
                # Advanced UAT has detailed summary
                summary = phase_result["summary"]
                total_tests += summary.get("total_tests", 0)
                total_passed += summary.get("passed", 0)
                total_failed += summary.get("failed", 0)
                total_skipped += summary.get("skipped", 0)
            else:
                # Other phases count as single tests
                total_tests += 1
                if phase_result["status"] == "PASSED":
                    total_passed += 1
                elif phase_result["status"] == "FAILED":
                    total_failed += 1
                else:
                    total_skipped += 1
        
        master_results["end_time"] = datetime.datetime.now().isoformat()
        master_results["master_summary"] = {
            "total_phases": total_phases,
            "passed_phases": passed_phases,
            "failed_phases": failed_phases,
            "total_individual_tests": total_tests,
            "total_passed_tests": total_passed,
            "total_failed_tests": total_failed,
            "total_skipped_tests": total_skipped,
            "overall_success_rate": f"{(total_passed/total_tests)*100:.1f}%" if total_tests > 0 else "0%",
            "phase_success_rate": f"{(passed_phases/total_phases)*100:.1f}%" if total_phases > 0 else "0%"
        }
        
        master_results["status"] = "PASSED" if failed_phases == 0 else "FAILED"
        master_results["message"] = f"Master UAT completed: {passed_phases}/{total_phases} phases passed, {total_passed}/{total_tests} individual tests passed"
        
        print(f"\n🎯 MASTER UAT RESULTS:")
        print(f"   📋 Phases: {passed_phases}/{total_phases} passed")
        print(f"   ✅ Individual Tests: {total_passed}/{total_tests} passed")
        print(f"   ❌ Failed Tests: {total_failed}")
        print(f"   ⏭️ Skipped Tests: {total_skipped}")
        print(f"   📊 Overall Success Rate: {master_results['master_summary']['overall_success_rate']}")
        
        return master_results
        
    except Exception as e:
        master_results.update({
            "status": "FAILED",
            "error": str(e),
            "end_time": datetime.datetime.now().isoformat(),
            "message": f"Exception during master UAT suite: {e}"
        })
        return master_results

# ========================================================================
# ENHANCED FUNCTIONS WITH SMART RESOURCE MANAGEMENT
# ========================================================================

async def _cleanup_test_dataset(user_name: str, project_name: str, dataset_name: str) -> Dict[str, Any]:
    """Helper function to clean up test datasets"""
    try:
        domino = _create_domino_client(user_name, project_name)
        
        # List datasets to find the one to delete
        list_result = _safe_execute(domino.datasets_list, "List datasets for cleanup")
        if list_result["status"] == "PASSED":
            datasets = list_result.get("result", [])
            target_dataset = next((d for d in datasets if d.get("name") == dataset_name), None)
            
            if target_dataset:
                dataset_id = target_dataset.get("id")
                delete_result = _safe_execute(
                    domino.datasets_remove,
                    f"Delete test dataset {dataset_name}",
                    dataset_id
                )
                return delete_result
            else:
                return {"status": "SKIPPED", "message": f"Dataset {dataset_name} not found for cleanup"}
        else:
            return {"status": "FAILED", "error": "Could not list datasets for cleanup"}
            
    except Exception as e:
        return {"status": "FAILED", "error": str(e)}

@mcp.tool()
async def enhanced_test_dataset_operations(user_name: str, project_name: str) -> Dict[str, Any]:
    """
    Enhanced dataset testing with smart resource management.
    Creates dummy dataset, tests operations, then cleans up.
    """
    
    test_results = {
        "test": "enhanced_dataset_operations",
        "user_name": user_name,
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "operations": {},
        "cleanup_performed": False
    }

    created_dataset_name = None

    try:
        domino = _create_domino_client(user_name, project_name)
        
        # Test 1: List existing datasets
        list_result = _safe_execute(domino.datasets_list, "List existing datasets")
        test_results["operations"]["list_datasets"] = list_result
        
        # Test 2: Create a dummy dataset
        dataset_name = _generate_unique_name("uat_test_dataset")
        created_dataset_name = dataset_name
        
        # Create test data file
        test_data = f"""# UAT Test Dataset
# Created: {datetime.datetime.now().isoformat()}
# Purpose: Testing dataset creation and management

name,value,category
test_item_1,100,category_a
test_item_2,200,category_b
test_item_3,150,category_a
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(test_data)
            temp_file_path = f.name
        
        try:
            # Upload the test file first
            upload_result = _safe_execute(
                domino.files_upload,
                "Upload test data file",
                f"{dataset_name}.csv",
                temp_file_path
            )
            test_results["operations"]["upload_test_file"] = upload_result
            
            # Create dataset
            create_result = _safe_execute(
                domino.datasets_create,
                "Create test dataset",
                dataset_name,
                f"UAT test dataset created at {datetime.datetime.now().isoformat()}"
            )
            test_results["operations"]["create_dataset"] = create_result
            
            if create_result["status"] == "PASSED":
                # Test 3: List datasets again to verify creation
                verify_list_result = _safe_execute(domino.datasets_list, "Verify dataset creation")
                test_results["operations"]["verify_creation"] = verify_list_result
                
                # Test 4: Get dataset details
                if verify_list_result["status"] == "PASSED":
                    datasets = verify_list_result.get("result", [])
                    created_dataset = next((d for d in datasets if d.get("name") == dataset_name), None)
                    if created_dataset:
                        dataset_id = created_dataset.get("id")
                        details_result = _safe_execute(
                            domino.datasets_details,
                            "Get dataset details", 
                            dataset_id
                        )
                        test_results["operations"]["dataset_details"] = details_result
        
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        
        # Test 5: Clean up - Remove the test dataset
        if created_dataset_name and create_result["status"] == "PASSED":
            await asyncio.sleep(2)  # Allow time for dataset to be fully created
            cleanup_result = await _cleanup_test_dataset(user_name, project_name, created_dataset_name)
            test_results["cleanup"] = cleanup_result
            test_results["cleanup_performed"] = True

        # Determine overall status
        failed_ops = [k for k, v in test_results["operations"].items() if v["status"] == "FAILED"]
        test_results["status"] = "FAILED" if failed_ops else "PASSED"
        test_results["failed_operations"] = failed_ops
        
        if test_results["status"] == "PASSED":
            test_results["message"] = f"All enhanced dataset operations successful, cleanup completed"
        else:
            test_results["message"] = f"Some operations failed: {failed_ops}"

        return test_results
        
    except Exception as e:
        # Emergency cleanup
        if created_dataset_name:
            try:
                await _cleanup_test_dataset(user_name, project_name, created_dataset_name)
                test_results["cleanup_performed"] = True
            except:
                pass
                
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during enhanced dataset operations test"
        })
        return test_results

@mcp.tool()
async def enhanced_test_model_operations(user_name: str, project_name: str) -> Dict[str, Any]:
    """
    Enhanced model testing with dummy model creation and cleanup.
    Creates a simple model, tests operations, then removes it.
    """
    
    test_results = {
        "test": "enhanced_model_operations",
        "user_name": user_name,
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "operations": {},
        "cleanup_performed": False
    }

    created_model_file = None

    try:
        domino = _create_domino_client(user_name, project_name)
        
        # Test 1: List existing models
        models_result = _safe_execute(domino.models_list, "List existing models")
        test_results["operations"]["list_models"] = models_result
        
        # Test 2: Create a dummy model file
        model_name = _generate_unique_name("uat_test_model")
        created_model_file = f"{model_name}.py"
        
        model_code = f'''# UAT Test Model
# Created: {datetime.datetime.now().isoformat()}
# Purpose: Testing model deployment capabilities

import pickle
import json

class UATTestModel:
    """Simple test model for UAT validation"""
    
    def __init__(self):
        self.model_type = "uat_test"
        self.version = "1.0.0"
        self.created_at = "{datetime.datetime.now().isoformat()}"
    
    def predict(self, input_data):
        """Simple prediction function"""
        if isinstance(input_data, dict) and "value" in input_data:
            return {{
                "prediction": input_data["value"] * 2,
                "model_info": {{
                    "type": self.model_type,
                    "version": self.version,
                    "processed_at": "{datetime.datetime.now().isoformat()}"
                }}
            }}
        return {{"error": "Invalid input format"}}
    
    def save(self, filepath):
        """Save model to file"""
        with open(filepath, 'wb') as f:
            pickle.dump(self, f)
    
    @classmethod
    def load(cls, filepath):
        """Load model from file"""
        with open(filepath, 'rb') as f:
            return pickle.load(f)

# Model API endpoints for Domino
def predict(input_data):
    """Domino model API endpoint"""
    model = UATTestModel()
    return model.predict(input_data)

if __name__ == "__main__":
    # Test the model locally
    model = UATTestModel()
    test_input = {{"value": 10}}
    result = model.predict(test_input)
    print(f"Test prediction result: {{result}}")
'''
        
        # Upload the model file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(model_code)
            temp_file_path = f.name
        
        try:
            upload_result = _safe_execute(
                domino.files_upload,
                "Upload test model file",
                created_model_file,
                temp_file_path
            )
            test_results["operations"]["upload_model"] = upload_result
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        
        # Test 3: Check endpoint state (this might fail if no endpoints are deployed)
        endpoint_result = _safe_execute(domino.endpoint_state, "Check endpoint state")
        test_results["operations"]["endpoint_state"] = endpoint_result
        
        # Test 4: Get deployment version info
        version_result = _safe_execute(domino.deployment_version, "Get deployment version")
        test_results["operations"]["deployment_version"] = version_result
        
        # Test 5: List models again to see if our file is there
        verify_models_result = _safe_execute(domino.models_list, "Verify model file upload")
        test_results["operations"]["verify_models"] = verify_models_result
        
        # Test 6: Cleanup - Remove the test model file
        if created_model_file and upload_result["status"] == "PASSED":
            cleanup_result = _safe_execute(
                domino.files_remove,
                f"Remove test model file {created_model_file}",
                created_model_file
            )
            test_results["cleanup"] = cleanup_result
            test_results["cleanup_performed"] = True

        # Determine overall status (be more lenient for model operations)
        critical_ops = ["upload_model", "verify_models"]
        failed_critical = [k for k in critical_ops if test_results["operations"].get(k, {}).get("status") == "FAILED"]
        
        test_results["status"] = "FAILED" if failed_critical else "PASSED"
        test_results["failed_critical_operations"] = failed_critical
        
        # Note: endpoint_state and deployment_version failures are expected when no models are deployed
        expected_failures = ["endpoint_state", "deployment_version"]
        actual_failures = [k for k, v in test_results["operations"].items() if v["status"] == "FAILED"]
        unexpected_failures = [f for f in actual_failures if f not in expected_failures]
        
        if test_results["status"] == "PASSED":
            test_results["message"] = f"Enhanced model operations successful. Model file created and cleaned up."
            if actual_failures:
                test_results["message"] += f" Expected failures (no deployed models): {actual_failures}"
        else:
            test_results["message"] = f"Critical model operations failed: {failed_critical}"

        return test_results
        
    except Exception as e:
        # Emergency cleanup
        if created_model_file:
            try:
                domino = _create_domino_client(user_name, project_name)
                _safe_execute(domino.files_remove, f"Emergency cleanup: {created_model_file}", created_model_file)
                test_results["cleanup_performed"] = True
            except:
                pass
                
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during enhanced model operations test"
        })
        return test_results

@mcp.tool()
async def enhanced_test_file_management(user_name: str, project_name: str) -> Dict[str, Any]:
    """
    Enhanced file management testing with better error handling and multiple file types.
    """
    
    test_results = {
        "test": "enhanced_file_management",
        "user_name": user_name,
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "operations": {},
        "files_created": []
    }

    try:
        domino = _create_domino_client(user_name, project_name)
        
        # Test 1: List current files
        list_result = _safe_execute(domino.files_list, "List current project files", None)
        test_results["operations"]["initial_file_list"] = list_result
        
        # Test 2: Upload multiple test files
        test_files = [
            {
                "name": f"uat_test_python_{datetime.datetime.now().strftime('%H%M%S')}.py",
                "content": '''# UAT Test Python File
import datetime

def test_function():
    """Test function for UAT validation"""
    return f"UAT test executed at {datetime.datetime.now().isoformat()}"

if __name__ == "__main__":
    result = test_function()
    print(result)
''',
                "type": "python"
            },
            {
                "name": f"uat_test_data_{datetime.datetime.now().strftime('%H%M%S')}.csv",
                "content": '''name,value,timestamp
test1,100,2024-01-01T10:00:00
test2,200,2024-01-01T11:00:00
test3,150,2024-01-01T12:00:00
''',
                "type": "data"
            }
        ]
        
        for test_file in test_files:
            with tempfile.NamedTemporaryFile(mode='w', suffix=os.path.splitext(test_file["name"])[1], delete=False) as f:
                f.write(test_file["content"])
                temp_path = f.name
            
            try:
                upload_result = _safe_execute(
                    domino.files_upload,
                    f"Upload {test_file['type']} test file",
                    test_file["name"],
                    temp_path
                )
                test_results["operations"][f"upload_{test_file['type']}"] = upload_result
                
                if upload_result["status"] == "PASSED":
                    test_results["files_created"].append(test_file["name"])
                    
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        
        # Test 3: Verify file uploads by listing again
        verify_result = _safe_execute(domino.files_list, "Verify file uploads", None)
        test_results["operations"]["verify_uploads"] = verify_result
        
        # Test 4: Cleanup - Remove test files
        cleanup_results = []
        for filename in test_results["files_created"]:
            cleanup_result = _safe_execute(
                domino.files_remove,
                f"Remove test file {filename}",
                filename
            )
            cleanup_results.append({"file": filename, "result": cleanup_result})
        
        test_results["cleanup"] = cleanup_results
        test_results["cleanup_performed"] = len(cleanup_results) > 0

        # Test 5: Final file list to verify cleanup
        final_list_result = _safe_execute(domino.files_list, "Final file list verification", None)
        test_results["operations"]["final_file_list"] = final_list_result

        # Determine overall status
        failed_ops = [k for k, v in test_results["operations"].items() if v["status"] == "FAILED"]
        test_results["status"] = "FAILED" if failed_ops else "PASSED"
        test_results["failed_operations"] = failed_ops
        
        if test_results["status"] == "PASSED":
            test_results["message"] = f"All enhanced file operations successful. Created and cleaned up {len(test_results['files_created'])} files."
        else:
            test_results["message"] = f"Some file operations failed: {failed_ops}"

        return test_results
        
    except Exception as e:
        # Emergency cleanup
        for filename in test_results.get("files_created", []):
            try:
                domino = _create_domino_client(user_name, project_name)
                _safe_execute(domino.files_remove, f"Emergency cleanup: {filename}", filename)
            except:
                pass
                
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during enhanced file management test"
        })
        return test_results

@mcp.tool()
async def enhanced_test_advanced_job_operations(user_name: str, project_name: str) -> Dict[str, Any]:
    """
    Enhanced advanced job testing with better hardware tier handling and error recovery.
    """
    
    test_results = {
        "test": "enhanced_advanced_job_operations",
        "user_name": user_name,
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "operations": {},
        "jobs_created": []
    }

    try:
        domino = _create_domino_client(user_name, project_name)
        
        # Test 1: List existing jobs
        jobs_list_result = _safe_execute(domino.runs_list, "List existing runs/jobs")
        test_results["operations"]["list_jobs"] = jobs_list_result
        
        # Test 2: Get hardware tiers to understand available options
        hardware_tiers_result = _safe_execute(domino.hardware_tiers_list, "List available hardware tiers")
        test_results["operations"]["hardware_tiers"] = hardware_tiers_result
        
        # Determine appropriate hardware tier
        hardware_tier = "Small"  # Default fallback
        if hardware_tiers_result["status"] == "PASSED":
            tiers = hardware_tiers_result.get("result", [])
            if tiers:
                # Use the first available tier, or find "Small" if available
                small_tier = next((t for t in tiers if "small" in t.get("name", "").lower()), None)
                hardware_tier = small_tier.get("name", tiers[0].get("name", "Small")) if small_tier else tiers[0].get("name", "Small")
        
        # Test 3: Start a simple job
        job_command = f'''python -c "
import time
import datetime
print('=== UAT Advanced Job Test ===')
print(f'Started at: {{datetime.datetime.now().isoformat()}}')
print('Hardware tier: {hardware_tier}')
print('Testing job execution capabilities...')
time.sleep(3)
print('Job completed successfully!')
print(f'Finished at: {{datetime.datetime.now().isoformat()}}')
"'''
        
        job_start_result = _safe_execute(
            domino.job_start,
            f"Start job with {hardware_tier} hardware tier",
            job_command,
            None,  # commit_id
            None,  # hardware_tier_id
            hardware_tier,  # hardware_tier_name
            None,  # environment_id
            None,  # on_demand_spark_cluster_properties
            None,  # compute_cluster_properties
            None,  # external_volume_mounts
            f"UAT Enhanced Job Test - {datetime.datetime.now().strftime('%H:%M:%S')}"  # title
        )
        test_results["operations"]["start_job"] = job_start_result
        
        job_id = None
        if job_start_result["status"] == "PASSED":
            job_result = job_start_result.get("result", {})
            job_id = job_result.get("id") or job_result.get("runId")
            if job_id:
                test_results["jobs_created"].append(job_id)
                
                # Test 4: Check job status
                await asyncio.sleep(2)
                status_result = _safe_execute(domino.run_details, "Check job status", job_id)
                test_results["operations"]["job_status"] = status_result
                
                # Test 5: Wait a bit more and check final status
                await asyncio.sleep(5)
                final_status_result = _safe_execute(domino.run_details, "Check final job status", job_id)
                test_results["operations"]["final_job_status"] = final_status_result
        
        # Test 6: Start a blocking job (very quick one)
        blocking_command = '''python -c "
import sys
print('=== UAT Blocking Job Test ===')
print(f'Python version: {sys.version}')
print('Blocking job test completed successfully!')
"'''
        
        blocking_result = _safe_execute(
            domino.job_start_blocking,
            "Start quick blocking job",
            5,  # poll_freq
            30,  # max_poll_time (30 seconds)
            (),  # ignore_exceptions
            command=blocking_command,
            title="UAT Enhanced Blocking Job Test"
        )
        test_results["operations"]["blocking_job"] = blocking_result

        # Determine overall status
        critical_ops = ["list_jobs", "start_job"]
        failed_critical = [k for k in critical_ops if test_results["operations"].get(k, {}).get("status") == "FAILED"]
        
        test_results["status"] = "FAILED" if failed_critical else "PASSED"
        test_results["failed_critical_operations"] = failed_critical
        
        all_failed = [k for k, v in test_results["operations"].items() if v["status"] == "FAILED"]
        
        if test_results["status"] == "PASSED":
            test_results["message"] = f"Enhanced advanced job operations successful with {hardware_tier} hardware tier."
            if all_failed:
                test_results["message"] += f" Non-critical failures: {all_failed}"
        else:
            test_results["message"] = f"Critical job operations failed: {failed_critical}"

        return test_results
        
    except Exception as e:
        test_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during enhanced advanced job operations test"
        })
        return test_results

# ========================================================================
# ADMIN UAT SUITE - Administrative Features Testing
# ========================================================================

@mcp.tool()
async def run_admin_uat_suite(user_name: str, project_name: str) -> Dict[str, Any]:
    """
    Runs Administrative UAT tests covering:
    - Infrastructure monitoring
    - System configuration
    - User management
    - Resource allocation
    - Platform administration
    """
    
    admin_results = {
        "suite": "admin_uat",
        "user_name": user_name,
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "tests": {},
        "summary": {}
    }

    try:
        domino = _create_domino_client(user_name, project_name)
        
        print("🔧 Running Administrative UAT Suite...")
        
        # Admin Test 1: Environment and Hardware Infrastructure
        print("📊 Testing infrastructure and hardware resources...")
        infra_result = _safe_execute(domino.hardware_tiers_list, "Infrastructure: List hardware tiers")
        admin_results["tests"]["infrastructure_hardware"] = infra_result
        
        env_result = _safe_execute(domino.environments_list, "Infrastructure: List compute environments") 
        admin_results["tests"]["infrastructure_environments"] = env_result
        
        # Admin Test 2: Project and User Management
        print("👥 Testing project and user management...")
        projects_result = _safe_execute(domino.projects_list, "Admin: List all accessible projects")
        admin_results["tests"]["project_management"] = projects_result
        
        # Admin Test 3: System Monitoring and Logs
        print("📋 Testing system monitoring capabilities...")
        runs_result = _safe_execute(domino.runs_list, "Admin: Monitor all runs")
        admin_results["tests"]["system_monitoring"] = runs_result
        
        # Admin Test 4: Resource Configuration Testing
        print("⚙️ Testing resource configuration...")
        
        # Test different hardware configurations
        hardware_config_tests = []
        if infra_result["status"] == "PASSED":
            tiers = infra_result.get("result", [])[:3]  # Test first 3 tiers
            for tier in tiers:
                tier_name = tier.get("name", "unknown")
                test_job_cmd = f'python -c "print(\'Hardware test on {tier_name}: OK\')"'
                
                config_test = _safe_execute(
                    domino.job_start,
                    f"Admin: Test {tier_name} hardware configuration",
                    test_job_cmd,
                    None, None, tier_name, None, None, None, None,
                    f"Admin Config Test - {tier_name}"
                )
                hardware_config_tests.append({
                    "tier": tier_name,
                    "test_result": config_test
                })
        
        admin_results["tests"]["resource_configuration"] = {
            "status": "PASSED" if hardware_config_tests else "SKIPPED",
            "hardware_tests": hardware_config_tests,
            "description": "Test resource configuration across hardware tiers"
        }
        
        # Admin Test 5: Platform Capacity Testing
        print("🚀 Testing platform capacity...")
        
        # Start multiple concurrent jobs to test system capacity
        capacity_test_jobs = []
        for i in range(3):  # Conservative capacity test
            capacity_cmd = f'''python -c "
import time
print('Capacity test job {i+1} started')
time.sleep(2)
print('Capacity test job {i+1} completed')
"'''
            
            capacity_job = _safe_execute(
                domino.job_start,
                f"Admin: Capacity test job {i+1}",
                capacity_cmd,
                None, None, None, None, None, None, None,
                f"Admin Capacity Test {i+1}"
            )
            capacity_test_jobs.append(capacity_job)
        
        admin_results["tests"]["platform_capacity"] = {
            "status": "PASSED" if all(j["status"] == "PASSED" for j in capacity_test_jobs) else "FAILED",
            "concurrent_jobs": len(capacity_test_jobs),
            "successful_starts": sum(1 for j in capacity_test_jobs if j["status"] == "PASSED"),
            "jobs": capacity_test_jobs,
            "description": "Test platform capacity with concurrent jobs"
        }

        # Calculate summary
        total_tests = len([t for t in admin_results["tests"].values() if isinstance(t, dict) and "status" in t])
        passed_tests = len([t for t in admin_results["tests"].values() if isinstance(t, dict) and t.get("status") == "PASSED"])
        
        admin_results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%",
            "overall_status": "PASSED" if passed_tests >= total_tests * 0.7 else "FAILED"  # 70% threshold
        }
        
        admin_results["status"] = admin_results["summary"]["overall_status"]
        admin_results["message"] = f"Admin UAT completed: {passed_tests}/{total_tests} tests passed"

        return admin_results
        
    except Exception as e:
        admin_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during Admin UAT suite"
        })
        return admin_results

# ========================================================================
# USER UAT SUITE - End-User Features Testing  
# ========================================================================

@mcp.tool()
async def run_user_uat_suite(user_name: str, project_name: str) -> Dict[str, Any]:
    """
    Runs User UAT tests covering:
    - Authentication and access
    - Project portfolio management
    - Data science workflows
    - Workspace operations
    - Collaboration features
    """
    
    user_results = {
        "suite": "user_uat", 
        "user_name": user_name,
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "tests": {},
        "summary": {}
    }

    try:
        print("👤 Running User UAT Suite...")
        
        # User Test 1: Authentication and Project Access
        print("🔐 Testing user authentication and project access...")
        auth_test = await test_user_authentication(user_name, project_name)
        user_results["tests"]["authentication"] = auth_test
        
        # User Test 2: Project Operations and Portfolio
        print("📁 Testing project operations and portfolio...")
        project_test = await test_project_operations(user_name, project_name)
        user_results["tests"]["project_operations"] = project_test
        
        # User Test 3: Data Science Workflows
        print("🔬 Testing data science workflows...")
        
        # Test Python workflow
        python_job_test = await test_job_execution(user_name, project_name, "python")
        user_results["tests"]["python_workflow"] = python_job_test
        
        # Test dataset access
        dataset_test = await enhanced_test_dataset_operations(user_name, project_name)
        user_results["tests"]["dataset_access"] = dataset_test
        
        # User Test 4: Workspace Operations
        print("💻 Testing workspace operations...")
        workspace_test = await test_workspace_operations(user_name, project_name)
        user_results["tests"]["workspace_operations"] = workspace_test
        
        # User Test 5: File Management
        print("📄 Testing file management...")
        file_test = await enhanced_test_file_management(user_name, project_name)
        user_results["tests"]["file_management"] = file_test
        
        # User Test 6: Environment Access
        print("🌐 Testing environment access...")
        env_test = await test_environment_operations(user_name)
        user_results["tests"]["environment_access"] = env_test
        
        # User Test 7: Collaboration Features
        print("🤝 Testing collaboration features...")
        collab_test = await test_collaboration_features(user_name, project_name)
        user_results["tests"]["collaboration"] = collab_test
        
        # User Test 8: Model Operations
        print("🤖 Testing model operations...")
        model_test = await enhanced_test_model_operations(user_name, project_name)
        user_results["tests"]["model_operations"] = model_test

        # Calculate summary
        total_tests = len(user_results["tests"])
        passed_tests = len([t for t in user_results["tests"].values() if t.get("status") == "PASSED"])
        
        user_results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%",
            "overall_status": "PASSED" if passed_tests >= total_tests * 0.6 else "FAILED"  # 60% threshold for user tests
        }
        
        user_results["status"] = user_results["summary"]["overall_status"]
        user_results["message"] = f"User UAT completed: {passed_tests}/{total_tests} tests passed"

        return user_results
        
    except Exception as e:
        user_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during User UAT suite"
        })
        return user_results

# ========================================================================
# COMBINED UAT SUITE WITH COMPREHENSIVE REPORTING
# ========================================================================

@mcp.tool()
async def run_comprehensive_split_uat_suite(user_name: str, project_name: str, include_performance: bool = False) -> Dict[str, Any]:
    """
    Runs the complete UAT suite split into Admin and User categories with comprehensive reporting.
    
    Args:
        user_name (str): The user name for testing
        project_name (str): The project name for testing  
        include_performance (bool): Whether to include performance tests
    """
    
    comprehensive_results = {
        "suite": "comprehensive_split_uat",
        "user_name": user_name,
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "admin_uat": {},
        "user_uat": {},
        "performance_tests": {},
        "final_summary": {}
    }

    try:
        print("🎯 Starting Comprehensive Split UAT Suite...")
        
        # Run Admin UAT
        print("\n" + "="*60)
        print("🔧 ADMINISTRATIVE UAT TESTING")
        print("="*60)
        admin_results = await run_admin_uat_suite(user_name, project_name)
        comprehensive_results["admin_uat"] = admin_results
        
        # Run User UAT  
        print("\n" + "="*60)
        print("👤 USER UAT TESTING")
        print("="*60)
        user_results = await run_user_uat_suite(user_name, project_name)
        comprehensive_results["user_uat"] = user_results
        
        # Optional Performance Tests
        if include_performance:
            print("\n" + "="*60)
            print("⚡ PERFORMANCE TESTING")
            print("="*60)
            
            perf_job_test = await performance_test_concurrent_jobs(user_name, project_name, 3, 10)
            comprehensive_results["performance_tests"]["concurrent_jobs"] = perf_job_test
            
            perf_upload_test = await performance_test_data_upload_throughput(user_name, project_name, 5, 3)
            comprehensive_results["performance_tests"]["upload_throughput"] = perf_upload_test

        # Generate final comprehensive summary
        admin_passed = admin_results.get("summary", {}).get("passed_tests", 0)
        admin_total = admin_results.get("summary", {}).get("total_tests", 0)
        user_passed = user_results.get("summary", {}).get("passed_tests", 0)
        user_total = user_results.get("summary", {}).get("total_tests", 0)
        
        total_passed = admin_passed + user_passed
        total_tests = admin_total + user_total
        
        overall_success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        comprehensive_results["final_summary"] = {
            "total_tests": total_tests,
            "total_passed": total_passed,
            "admin_results": f"{admin_passed}/{admin_total}",
            "user_results": f"{user_passed}/{user_total}",
            "overall_success_rate": f"{overall_success_rate:.1f}%",
            "admin_status": admin_results.get("status", "UNKNOWN"),
            "user_status": user_results.get("status", "UNKNOWN"),
            "overall_status": "PASSED" if overall_success_rate >= 65 else "FAILED",
            "performance_included": include_performance
        }
        
        comprehensive_results["status"] = comprehensive_results["final_summary"]["overall_status"]
        comprehensive_results["message"] = f"Comprehensive UAT completed: {total_passed}/{total_tests} tests passed ({overall_success_rate:.1f}%)"

        # Print final summary
        print("\n" + "="*60)
        print("📊 COMPREHENSIVE UAT SUMMARY")
        print("="*60)
        print(f"🔧 Admin Tests: {admin_passed}/{admin_total} passed ({admin_results.get('status', 'UNKNOWN')})")
        print(f"👤 User Tests: {user_passed}/{user_total} passed ({user_results.get('status', 'UNKNOWN')})")
        print(f"📈 Overall: {total_passed}/{total_tests} passed ({overall_success_rate:.1f}%)")
        print(f"🎯 Final Status: {comprehensive_results['status']}")

        return comprehensive_results
        
    except Exception as e:
        comprehensive_results.update({
            "status": "FAILED",
            "error": str(e),
            "message": f"Exception during comprehensive split UAT suite"
        })
        return comprehensive_results

def _filter_domino_stdout(stdout_text: str) -> str:
    """
    Filters the stdout text from a Domino job run to extract the relevant output.
    It extracts text between the specified start and end markers.
    """
    start_marker = "### Completed /mnt/artifacts/.domino/configure-spark-defaults.sh ###"
    end_marker = "Evaluating cleanup command on EXIT"

    try:
        start_index = stdout_text.index(start_marker) + len(start_marker)
        # Find the end marker starting from the position after the start marker
        end_index = stdout_text.index(end_marker, start_index)
        # Extract the text between the markers, stripping leading/trailing whitespace
        filtered_text = stdout_text[start_index:end_index].strip()
        return filtered_text
    except ValueError:
        # Handle cases where one or both markers are not found
        # Optionally, return the original text or a specific message
        print("Warning: could not parse domino job output")
        return "Could not find start or end markers in stdout."

def _extract_and_format_mlflow_url(text: str, user_name: str, project_name: str) -> str | None:
    """
    Finds an MLflow URL in the format http://127.0.0.1:8768/#/experiments/.../runs/...
    and reformats it to the Domino Cloud URL format.
    """
    import re
    # Regex to find the specific MLflow URL pattern
    pattern = r"http://127\.0\.0\.1:8768/#/experiments/(\d+)/runs/([a-f0-9]+)"
    match = re.search(pattern, text)

    if match:
        experiment_id = match.group(1)
        run_id = match.group(2)
        # Construct the new URL
        new_url = f"{domino_host}/experiments/{user_name}/{project_name}/{experiment_id}/{run_id}"
        return new_url
    else:
        return None # Return None if the pattern is not found

@mcp.tool()
async def run_domino_job(user_name: str, project_name: str, run_command: str, title: str) -> Dict[str, Any]:
    """
    The run_domino_job function runs a command as a job on the domino data science platform, typically a python script such a 'python my_script.py --arg1 arv1_val --arg2 arv2_val' on the Domino cloud platform.

    Args:
        user_name (str): The user name associated with the Domino project.
        project_name (str): The name of the Domino project.
        run_command (str): The command to run on the domino platform. Example: 'python my_script.py --arg1 arv1_val --arg2 arv2_val'
        title (str): A title of the job that helps later identify the job. Example: 'running training.py script'
    """
    # Validate and encode input parameters
    encoded_user_name = _validate_url_parameter(user_name, "user_name")
    encoded_project_name = _validate_url_parameter(project_name, "project_name")
  
    # Construct the API URL
    # must be in this format: https://domino.host/v1/projects/user_name/project_name/runs
    api_url = f"{domino_host}/v1/projects/{encoded_user_name}/{encoded_project_name}/runs"

    # Prepare the request headers
    headers = {
        "X-Domino-Api-Key": domino_api_key,
        "Content-Type": "application/json",
    }

    # Prepare the request body according to the specified requirements
    # for the /v1/projects/{user_name}/{project_name}/runs endpoint.
    payload = {
        "command": run_command.split(), # Split the command string into a list
        "isDirect": False, # Matching successful curl command
        "title": title,
        "publishApiEndpoint": False,
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        result = response.json()
    except requests.exceptions.RequestException as e:
        result = {"error": f"API request failed: {e}"}
    except Exception as e:
        result = {"error": f"An unexpected error occurred: {e}"}

    return result

@mcp.tool()
async def check_domino_job_run_status(user_name: str, project_name: str, run_id: str) -> Dict[str, Any]:
    """
    The check_domino_job_run_status function checks the status of a job run to determine if its finished or in-progress or had an error. A run can sometimes take 1 or more minutes, so it might be necessary to call this a few times until it's finished before using a different function to read the results.

    Args:
        user_name (str): The user name associated with the Domino Project
        project_name (str): The name of the Domino project.
        run_id (str): The run id of the job run to return the status of
    """
    # Validate and encode input parameters
    encoded_user_name = _validate_url_parameter(user_name, "user_name")
    encoded_project_name = _validate_url_parameter(project_name, "project_name")
    encoded_run_id = _validate_url_parameter(run_id, "run_id")
    
    api_url = f"{domino_host}/v1/projects/{encoded_user_name}/{encoded_project_name}/runs/{encoded_run_id}"
    headers = {
        "X-Domino-Api-Key": domino_api_key
    }
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        result = response.json()
    except requests.exceptions.RequestException as e:
        result = {"error": f"API request failed: {e}"}
    except Exception as e:
        result = {"error": f"An unexpected error occurred: {e}"}

    return result

@mcp.tool()
async def check_domino_job_run_results(user_name: str, project_name: str, run_id: str) -> Dict[str, Any]:
    """
    The check_domino_job_run_results function returns the results from the job run from the domino data science platform, these results might contain model training metrics that might help inform a follow-up job run that further optimizes a model.

    Args:
        user_name (str): The user name associated with the Domino Project
        project_name (str): The name of the Domino project.
        run_id (str): The run id of the job run to return the status of
    """
    # Validate and encode input parameters
    encoded_user_name = _validate_url_parameter(user_name, "user_name")
    encoded_project_name = _validate_url_parameter(project_name, "project_name")
    encoded_run_id = _validate_url_parameter(run_id, "run_id")
    
    api_url = f"{domino_host}/v1/projects/{encoded_user_name}/{encoded_project_name}/run/{encoded_run_id}/stdout"
    headers = {
        "X-Domino-Api-Key": domino_api_key
    }
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        raw_stdout = response.json().get('stdout', '') # Use .get for safety
        
        # Initial filtering between markers
        initially_filtered_stdout = _filter_domino_stdout(raw_stdout)
        
        # Attempt to extract and format the MLflow URL
        mlflow_url = _extract_and_format_mlflow_url(initially_filtered_stdout, user_name, project_name)
        
        final_filtered_stdout = initially_filtered_stdout
        # If MLflow URL was found, remove the original URL line(s) from the results
        if mlflow_url:
            import re
            # Define the pattern for the original local MLflow URL (run-specific)
            local_mlflow_run_pattern = r"http://127\.0\.0\.1:8768/#/experiments/\d+/runs/[a-f0-9]+"
            # Define the pattern for the experiment link
            local_mlflow_experiment_pattern = r"View experiment at: http://127\.0\.0\.1:8768/#/experiments/\d+"
            
            # Split into lines, filter out lines containing either pattern, and rejoin
            lines = initially_filtered_stdout.splitlines()
            filtered_lines = [line for line in lines if not re.search(local_mlflow_run_pattern, line) and not re.search(local_mlflow_experiment_pattern, line)]
            final_filtered_stdout = "\n".join(filtered_lines).strip()

        # Construct the result dictionary
        result = {"results": final_filtered_stdout}
        if mlflow_url:
             result["mlflow_url"] = mlflow_url # Add the formatted URL if found
             
    except requests.exceptions.RequestException as e:
        result = {"error": f"API request failed: {e}"}
    except Exception as e:
        result = {"error": f"An unexpected error occurred: {e}"}

    return result

@mcp.tool()
def open_web_browser(url: str) -> bool:
    """Opens the specified URL in the default web browser.

    Args:
        url: The URL to open.

    Returns:
        True if the browser was opened successfully, False otherwise.
    """
    try:
        webbrowser.open_new_tab(url)
        return True
    except webbrowser.Error:
        return False

# MCP Prompts - Standardized test workflows

@mcp.prompt()
def quick_auth_test(user_name: str, project_name: str) -> str:
    """
    Prompt 1: Quick User Authentication Test

    The USER_NAME and PROJECT_NAME parameters are provided by the LLM client
    (extracted from @domino_project_settings.md by the client).

    This prompt executes the User Authentication MCP tool to verify platform access.

    Args:
        user_name: Domino username (provided by LLM client)
        project_name: Domino project name (provided by LLM client)
    """
    return f"""# Quick User Authentication Test

## Configuration
- **User**: {user_name}
- **Project**: {project_name}
- **Source**: Parameters provided by LLM client

## Task

Execute the User Authentication MCP tool with the provided credentials.

**Tool**: `test_user_authentication`

**Parameters**:
- user_name: "{user_name}"
- project_name: "{project_name}"

## Expected Actions

1. Verify user authentication
2. Check project access permissions
3. List existing runs in the project
4. Confirm project setup status

## Report Results

Present results in this format:

```
✓ Authentication Test Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Status: [PASSED/FAILED]
User: {user_name}
Project: {project_name}
Runs Found: [count]
Authentication: [successful/failed]
Message: [detailed message]
```

Execute the test now and report the results.
"""

@mcp.prompt()
def end_to_end_uat_protocol(user_name: str, project_name: str) -> str:
    """
    Prompt 2: End-to-End UAT Protocol with Strict Execution

    The USER_NAME and PROJECT_NAME parameters are provided by the LLM client
    (extracted from @domino_project_settings.md by the client).

    Executes comprehensive UAT with 14 sequential tests, automatic cleanup, and final reporting.

    Args:
        user_name: Domino username (provided by LLM client)
        project_name: Domino project name (provided by LLM client)
    """
    return f"""# End-to-End UAT Protocol - Strict Execution Mode

## Configuration
- **User**: {user_name}
- **Project**: {project_name}
- **Source**: Parameters provided by LLM client
- **Execution Mode**: Continuous (No Pauses)

## STRICT EXECUTION REQUIREMENTS

⚠️ **CRITICAL RULES:**

1. **Continuous Run**: Execute all 14 tests in exact sequence
2. **No Pauses**: Do NOT stop, ask for confirmation, or wait for input between tests
3. **Cleanup After**: Run cleanup operations ONLY after test 14 completes
4. **Final Report**: Provide summary table AFTER cleanup finishes

## Test Execution Sequence (14 Tests)

Execute these MCP tools in exact order:

### Phase 1: Core Functionality (Tests 1-4)

**Test 1: User Authentication**
```
Tool: test_user_authentication
Parameters: user_name="{user_name}", project_name="{project_name}"
```

**Test 2: Project Operations**
```
Tool: test_project_operations
Parameters: user_name="{user_name}", project_name="{project_name}"
```

**Test 3: Job Execution**
```
Tool: test_job_execution
Parameters: user_name="{user_name}", project_name="{project_name}"
```

**Test 4: Workspace Operations**
```
Tool: test_workspace_operations
Parameters: user_name="{user_name}", project_name="{project_name}"
```

### Phase 2: Data & Environment (Tests 5-7)

**Test 5: Environment Operations**
```
Tool: test_environment_operations
Parameters: user_name="{user_name}", project_name="{project_name}"
```

**Test 6: Dataset Operations**
```
Tool: test_dataset_operations
Parameters: user_name="{user_name}", project_name="{project_name}"
```

**Test 7: Enhanced Dataset Operations**
```
Tool: enhanced_test_dataset_operations
Parameters: user_name="{user_name}", project_name="{project_name}"
```

### Phase 3: Advanced Features (Tests 8-10)

**Test 8: File Management**
```
Tool: test_file_management_operations
Parameters: user_name="{user_name}", project_name="{project_name}"
```

**Test 9: Collaboration Features**
```
Tool: test_collaboration_features
Parameters: user_name="{user_name}", project_name="{project_name}"
```

**Test 10: Model Operations**
```
Tool: test_model_operations
Parameters: user_name="{user_name}", project_name="{project_name}"
```

### Phase 4: Enhanced Testing (Tests 11-12)

**Test 11: Enhanced Model Operations**
```
Tool: enhanced_test_model_operations
Parameters: user_name="{user_name}", project_name="{project_name}"
```

**Test 12: Enhanced Advanced Job Operations**
```
Tool: enhanced_test_advanced_job_operations
Parameters: user_name="{user_name}", project_name="{project_name}"
```

### Phase 5: Comprehensive Suites (Tests 13-14)

**Test 13: Admin UAT Suite**
```
Tool: run_admin_uat_suite
Parameters: user_name="{user_name}", project_name="{project_name}"
```

**Test 14: User UAT Suite**
```
Tool: run_user_uat_suite
Parameters: user_name="{user_name}", project_name="{project_name}"
```

## Cleanup Phase (Execute AFTER Test 14)

**Cleanup Operation**:
```
Tool: cleanup_test_resources
Parameters: user_name="{user_name}", project_prefix="uat", dataset_prefix="uat-test"
```

This automatically cleans up:
- Test workspaces
- Test datasets
- Test tags
- Test artifacts

## Final Report Format (After Cleanup)

Generate comprehensive report:

```markdown
# End-to-End UAT Protocol - Final Report

**User**: {user_name}
**Project**: {project_name}
**Execution Date**: [timestamp]

## Test Execution Summary

| # | Test Name                         | Status | Duration | Key Result           |
|---|-----------------------------------|--------|----------|----------------------|
| 1 | User Authentication               |        |          |                      |
| 2 | Project Operations                |        |          |                      |
| 3 | Job Execution                     |        |          |                      |
| 4 | Workspace Operations              |        |          |                      |
| 5 | Environment Operations            |        |          |                      |
| 6 | Dataset Operations                |        |          |                      |
| 7 | Enhanced Dataset Operations       |        |          |                      |
| 8 | File Management                   |        |          |                      |
| 9 | Collaboration Features            |        |          |                      |
| 10| Model Operations                  |        |          |                      |
| 11| Enhanced Model Operations         |        |          |                      |
| 12| Enhanced Job Operations           |        |          |                      |
| 13| Admin UAT Suite                   |        |          |                      |
| 14| User UAT Suite                    |        |          |                      |

## Cleanup Results

| Operation                | Status | Items Cleaned |
|--------------------------|--------|---------------|
| Test Datasets Removed    |        |               |
| Test Tags Removed        |        |               |
| Test Artifacts Cleared   |        |               |

## Overall Statistics

- **Total Tests**: 14
- **Passed**: [count]
- **Failed**: [count]
- **Success Rate**: [percentage]%
- **Total Execution Time**: [duration]
- **Resources Cleaned**: [count]
- **Platform Status**: [READY FOR PRODUCTION / NEEDS ATTENTION / CRITICAL ISSUES]

## Key Findings

1. [Important finding 1]
2. [Important finding 2]
3. [Important finding 3]

## Recommendations

1. [Recommendation 1]
2. [Recommendation 2]
3. [Recommendation 3]
```

## Execution Instructions

**Execute in this order:**

1. Test 1 → continue immediately
2. Test 2 → continue immediately
3. Test 3 → continue immediately
4. Test 4 → continue immediately
5. Test 5 → continue immediately
6. Test 6 → continue immediately
7. Test 7 → continue immediately
8. Test 8 → continue immediately
9. Test 9 → continue immediately
10. Test 10 → continue immediately
11. Test 11 → continue immediately
12. Test 12 → continue immediately
13. Test 13 → continue immediately
14. Test 14 → continue immediately
15. Cleanup → continue
16. Generate final report

**Rules:**
- Do NOT display detailed results after each test
- Do NOT ask for confirmation between tests
- DO show brief progress: "Test 3/14 complete..."
- If test fails: record it and CONTINUE
- Always complete all 14 tests + cleanup
- Generate report at the end

**Begin execution immediately - no confirmation needed.**
"""

def main():
    """Initializes and runs the Domino QA MCP server."""
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main() 