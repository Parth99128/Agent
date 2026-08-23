"""
MCP Server for Code Analysis Agent

Exposes code analysis tools via the Model Context Protocol.
Tools: analyze_repo, analyze_file, get_security_issues, get_quality_metrics
"""

import asyncio
import json
import os
import subprocess
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    Tool,
    TextContent,
    ListToolsRequest,
    CallToolRequest,
    CallToolRequestParams,
    PaginatedRequestParams,
)
import mcp.types as types


# Create the MCP server
server = Server("code-analysis-agent")


# Store last analysis results for follow-up queries
_last_analysis: Dict[str, Any] = {}


# Define available tools
TOOLS = [
    Tool(
        name="analyze_repo",
        description="Analyze a Python repository for security vulnerabilities and code quality issues",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the repository or directory to analyze"
                },
                "include_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File patterns to include (default: ['*.py'])",
                    "default": ["*.py"]
                },
                "exclude_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File patterns to exclude",
                    "default": ["*/__pycache__/*", "*/.git/*", "*/venv/*", "*/.venv/*"]
                }
            },
            "required": ["path"]
        }
    ),
    Tool(
        name="analyze_file",
        description="Analyze a single Python file for security and quality issues",
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the Python file to analyze"
                }
            },
            "required": ["file_path"]
        }
    ),
    Tool(
        name="get_security_issues",
        description="Get security issues from the last analysis",
        inputSchema={
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "enum": ["HIGH", "MEDIUM", "LOW", "ALL"],
                    "description": "Filter by severity level",
                    "default": "ALL"
                }
            },
            "required": []
        }
    ),
    Tool(
        name="get_quality_metrics",
        description="Get code quality metrics from the last analysis",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
]


def run_bandit(path: str, include_patterns: List[str] = None, exclude_patterns: List[str] = None) -> Dict[str, Any]:
    """Run Bandit security analysis on a path."""
    cmd = ["bandit", "-r", path, "-f", "json"]
    
    if exclude_patterns:
        for pattern in exclude_patterns:
            cmd.extend(["-x", pattern])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.stdout:
            return json.loads(result.stdout)
        return {"results": [], "metrics": {}}
    except subprocess.TimeoutExpired:
        return {"error": "Bandit analysis timed out", "results": [], "metrics": {}}
    except json.JSONDecodeError:
        return {"error": "Failed to parse Bandit output", "results": [], "metrics": {}}
    except Exception as e:
        return {"error": str(e), "results": [], "metrics": {}}


def run_pylint(path: str, include_patterns: List[str] = None, exclude_patterns: List[str] = None) -> Dict[str, Any]:
    """Run Pylint code quality analysis on a path."""
    # Use pyproject.toml config for ignore patterns
    import os
    config_path = os.path.join(os.getcwd(), "pyproject.toml")
    if os.path.exists(config_path):
        cmd = ["pylint", path, "--output-format=json", "--reports=y", "--rcfile", config_path]
    else:
        cmd = ["pylint", path, "--output-format=json", "--reports=y"]
    
    if exclude_patterns:
        for pattern in exclude_patterns:
            # Pylint uses --ignore for directories and --ignore-patterns for file patterns
            if pattern.endswith("/*"):
                # Directory pattern like "*/__pycache__/*" -> --ignore=__pycache__
                dir_name = pattern.replace("*/", "").replace("/*", "")
                cmd.extend(["--ignore", dir_name])
            else:
                # File pattern
                cmd.extend(["--ignore-patterns", pattern])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.stdout:
            return json.loads(result.stdout)
        return []
    except subprocess.TimeoutExpired:
        return [{"error": "Pylint analysis timed out"}]
    except json.JSONDecodeError:
        return [{"error": "Failed to parse Pylint output"}]
    except Exception as e:
        return [{"error": str(e)}]


def format_bandit_results(bandit_output: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Format Bandit results into a standardized format."""
    issues = []
    for result in bandit_output.get("results", []):
        issues.append({
            "type": "security",
            "severity": result.get("issue_severity", "UNKNOWN"),
            "confidence": result.get("issue_confidence", "UNKNOWN"),
            "message": result.get("issue_text", ""),
            "file": result.get("filename", ""),
            "line": result.get("line_number", 0),
            "code": result.get("code", ""),
            "test_id": result.get("test_id", ""),
            "test_name": result.get("test_name", ""),
        })
    return issues


def format_pylint_results(pylint_output: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format Pylint results into a standardized format."""
    issues = []
    for result in pylint_output:
        if "error" in result:
            issues.append({
                "type": "error",
                "message": result["error"],
            })
            continue
            
        issues.append({
            "type": "quality",
            "severity": result.get("type", "").upper(),  # error, warning, convention, refactor, info
            "message": result.get("message", ""),
            "file": result.get("path", ""),
            "line": result.get("line", 0),
            "column": result.get("column", 0),
            "symbol": result.get("symbol", ""),
            "message_id": result.get("message-id", ""),
        })
    return issues


def calculate_metrics(security_issues: List[Dict], quality_issues: List[Dict]) -> Dict[str, Any]:
    """Calculate summary metrics from analysis results."""
    security_by_severity = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for issue in security_issues:
        sev = issue.get("severity", "").upper()
        if sev in security_by_severity:
            security_by_severity[sev] += 1
    
    quality_by_type = {"ERROR": 0, "WARNING": 0, "CONVENTION": 0, "REFACTOR": 0, "INFO": 0}
    for issue in quality_issues:
        sev = issue.get("severity", "").upper()
        if sev in quality_by_type:
            quality_by_type[sev] += 1
    
    return {
        "security": {
            "total": len(security_issues),
            "by_severity": security_by_severity,
        },
        "quality": {
            "total": len(quality_issues),
            "by_type": quality_by_type,
        },
        "files_analyzed": len(set(i.get("file", "") for i in security_issues + quality_issues if i.get("file"))),
    }


async def handle_list_tools(ctx, params: PaginatedRequestParams) -> ListToolsResult:
    """Handle tools/list request."""
    return ListToolsResult(tools=TOOLS)


async def handle_call_tool(ctx, params: CallToolRequestParams) -> CallToolResult:
    """Handle tools/call request."""
    global _last_analysis
    
    name = params.name
    arguments = params.arguments or {}
    
    if name == "analyze_repo":
        path = arguments.get("path", ".")
        include_patterns = arguments.get("include_patterns", ["*.py"])
        exclude_patterns = arguments.get("exclude_patterns", ["*/__pycache__/*", "*/.git/*", "*/venv/*", "*/.venv/*"])
        
        # Validate path exists
        if not os.path.exists(path):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: Path '{path}' does not exist")]
            )
        
        # Run Bandit for security analysis
        bandit_output = run_bandit(path, include_patterns, exclude_patterns)
        security_issues = format_bandit_results(bandit_output)
        
        # Run Pylint for quality analysis
        pylint_output = run_pylint(path, include_patterns, exclude_patterns)
        quality_issues = format_pylint_results(pylint_output)
        
        # Calculate metrics
        metrics = calculate_metrics(security_issues, quality_issues)
        
        # Store for follow-up queries
        _last_analysis = {
            "security_issues": security_issues,
            "quality_issues": quality_issues,
            "metrics": metrics,
            "path": path,
        }
        
        # Format response
        response = {
            "summary": {
                "path": path,
                "security_issues_found": len(security_issues),
                "quality_issues_found": len(quality_issues),
                "metrics": metrics,
            },
            "security_issues": security_issues[:50],  # Limit to first 50
            "quality_issues": quality_issues[:50],  # Limit to first 50
        }
        
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(response, indent=2))]
        )
    
    elif name == "analyze_file":
        file_path = arguments.get("file_path", "")
        
        if not os.path.exists(file_path):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: File '{file_path}' does not exist")]
            )
        
        if not file_path.endswith(".py"):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: File '{file_path}' is not a Python file")]
            )
        
        # Default exclude patterns for single file analysis
        exclude_patterns = ["*/__pycache__/*", "*/.git/*", "*/venv/*", "*/.venv/*"]
        
        # Run Bandit on single file
        bandit_output = run_bandit(file_path)
        security_issues = format_bandit_results(bandit_output)
        
        # Run Pylint on single file
        pylint_output = run_pylint(file_path, exclude_patterns=exclude_patterns)
        quality_issues = format_pylint_results(pylint_output)
        
        metrics = calculate_metrics(security_issues, quality_issues)
        
        _last_analysis = {
            "security_issues": security_issues,
            "quality_issues": quality_issues,
            "metrics": metrics,
            "path": file_path,
        }
        
        response = {
            "summary": {
                "file": file_path,
                "security_issues_found": len(security_issues),
                "quality_issues_found": len(quality_issues),
                "metrics": metrics,
            },
            "security_issues": security_issues,
            "quality_issues": quality_issues,
        }
        
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(response, indent=2))]
        )
    
    elif name == "get_security_issues":
        severity = arguments.get("severity", "ALL").upper()
        security_issues = _last_analysis.get("security_issues", [])
        
        if severity != "ALL":
            security_issues = [i for i in security_issues if i.get("severity", "").upper() == severity]
        
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({
                "security_issues": security_issues,
                "count": len(security_issues),
                "filter": severity,
            }, indent=2))]
        )
    
    elif name == "get_quality_metrics":
        metrics = _last_analysis.get("metrics", {})
        quality_issues = _last_analysis.get("quality_issues", [])
        
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({
                "metrics": metrics,
                "quality_issues_sample": quality_issues[:20],
            }, indent=2))]
        )
    
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Unknown tool: {name}")]
        )


# Register request handlers with correct method names and params types
server.add_request_handler("tools/list", PaginatedRequestParams, handle_list_tools)
server.add_request_handler("tools/call", CallToolRequestParams, handle_call_tool)


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())