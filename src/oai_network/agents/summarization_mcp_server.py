"""
MCP Server for Text Summarization using local LLM (Ollama).
Provides real summarization capabilities without mock implementations.
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)


# Global storage for last analysis (for follow-up queries)
_last_summary: Dict[str, Any] = {}


async def call_ollama(prompt: str, model: str = "llama3.2:3b", max_tokens: int = 500) -> str:
    """Call Ollama API for text generation."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.3,
                    }
                }
            )
            response.raise_for_status()
            return response.json().get("response", "").strip()
    except Exception as e:
        return f"Error calling Ollama: {str(e)}"


def build_summary_prompt(text: str, style: str, max_length: int) -> str:
    """Build prompt for summarization based on style."""
    style_instructions = {
        "concise": f"Provide a concise summary in under {max_length} words.",
        "bullet_points": "Provide a summary as bullet points covering key points.",
        "detailed": f"Provide a detailed summary in under {max_length} words with key details.",
        "executive": "Provide an executive summary with key findings and recommendations.",
        "technical": "Provide a technical summary preserving important technical details.",
    }
    
    instruction = style_instructions.get(style, style_instructions["concise"])
    
    return f"""You are an expert summarizer. {instruction}

Text to summarize:
{text}

Summary:"""


async def handle_list_tools(params: PaginatedRequestParams) -> ListToolsResult:
    """List available summarization tools."""
    tools = [
        Tool(
            name="summarize",
            description="Summarize text using local LLM (Ollama). Supports multiple styles: concise, bullet_points, detailed, executive, technical.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to summarize"},
                    "style": {
                        "type": "string",
                        "enum": ["concise", "bullet_points", "detailed", "executive", "technical"],
                        "default": "concise",
                        "description": "Summary style"
                    },
                    "max_length": {"type": "integer", "default": 200, "description": "Maximum summary length in words"},
                    "model": {"type": "string", "default": "llama3.2:3b", "description": "Ollama model to use"},
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="summarize_file",
            description="Summarize content from a file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to file to summarize"},
                    "style": {
                        "type": "string",
                        "enum": ["concise", "bullet_points", "detailed", "executive", "technical"],
                        "default": "concise",
                    },
                    "max_length": {"type": "integer", "default": 200},
                    "model": {"type": "string", "default": "llama3.2:3b"},
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="get_last_summary",
            description="Get the last generated summary for follow-up queries.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]
    return ListToolsResult(tools=tools)


async def handle_call_tool(params: CallToolRequestParams) -> CallToolResult:
    """Handle tool calls for summarization."""
    global _last_summary
    
    name = params.name
    arguments = params.arguments or {}
    
    if name == "summarize":
        text = arguments.get("text", "")
        style = arguments.get("style", "concise")
        max_length = arguments.get("max_length", 200)
        model = arguments.get("model", "llama3.2:3b")
        
        if not text.strip():
            return CallToolResult(
                content=[TextContent(type="text", text="Error: Empty text provided")]
            )
        
        prompt = build_summary_prompt(text, style, max_length)
        summary = await call_ollama(prompt, model, max_tokens=max_length * 2)
        
        # Store for follow-up
        _last_summary = {
            "original_text": text[:5000],  # Truncate for storage
            "summary": summary,
            "style": style,
            "max_length": max_length,
            "model": model,
            "original_length": len(text.split()),
            "summary_length": len(summary.split()),
        }
        
        compression_ratio = len(summary.split()) / max(len(text.split()), 1)
        
        response = {
            "summary": summary,
            "style": style,
            "original_length": len(text.split()),
            "summary_length": len(summary.split()),
            "compression_ratio": round(compression_ratio, 3),
            "model": model,
        }
        
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(response, indent=2))]
        )
    
    elif name == "summarize_file":
        file_path = arguments.get("file_path", "")
        style = arguments.get("style", "concise")
        max_length = arguments.get("max_length", 200)
        model = arguments.get("model", "llama3.2:3b")
        
        if not os.path.exists(file_path):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: File '{file_path}' does not exist")]
            )
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error reading file: {str(e)}")]
            )
        
        if not text.strip():
            return CallToolResult(
                content=[TextContent(type="text", text="Error: File is empty")]
            )
        
        prompt = build_summary_prompt(text, style, max_length)
        summary = await call_ollama(prompt, model, max_tokens=max_length * 2)
        
        _last_summary = {
            "original_text": text[:5000],
            "summary": summary,
            "style": style,
            "max_length": max_length,
            "model": model,
            "file_path": file_path,
            "original_length": len(text.split()),
            "summary_length": len(summary.split()),
        }
        
        compression_ratio = len(summary.split()) / max(len(text.split()), 1)
        
        response = {
            "summary": summary,
            "style": style,
            "file_path": file_path,
            "original_length": len(text.split()),
            "summary_length": len(summary.split()),
            "compression_ratio": round(compression_ratio, 3),
            "model": model,
        }
        
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(response, indent=2))]
        )
    
    elif name == "get_last_summary":
        if not _last_summary:
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps({"error": "No previous summary available"}))]
            )
        
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(_last_summary, indent=2))]
        )
    
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Unknown tool: {name}")]
        )


# Register request handlers
server = Server("summarization-mcp-server")
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