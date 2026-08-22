"""
MCP Server for Text Translation using local LLM (Ollama).
Provides real translation capabilities without mock implementations.
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


# Global storage for last translation (for follow-up queries)
_last_translation: Dict[str, Any] = {}


# Supported languages with their codes
SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "zh": "Chinese (Simplified)",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "fi": "Finnish",
}


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
                        "temperature": 0.2,
                    }
                }
            )
            response.raise_for_status()
            return response.json().get("response", "").strip()
    except Exception as e:
        return f"Error calling Ollama: {str(e)}"


def build_translation_prompt(text: str, target_lang: str, source_lang: str = "auto") -> str:
    """Build prompt for translation."""
    target_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
    source_name = SUPPORTED_LANGUAGES.get(source_lang, source_lang) if source_lang != "auto" else "auto-detect"
    
    if source_lang == "auto":
        return f"""You are a professional translator. Translate the following text to {target_name} ({target_lang}).
Auto-detect the source language.

Text to translate:
{text}

Translation:"""
    else:
        return f"""You are a professional translator. Translate the following text from {source_name} ({source_lang}) to {target_name} ({target_lang}).

Text to translate:
{text}

Translation:"""


def validate_language_code(lang: str) -> bool:
    """Validate if language code is supported."""
    return lang in SUPPORTED_LANGUAGES


async def handle_list_tools(params: PaginatedRequestParams) -> ListToolsResult:
    """List available translation tools."""
    tools = [
        Tool(
            name="translate",
            description="Translate text using local LLM (Ollama). Supports 20+ languages. Auto-detects source language if not specified.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to translate"},
                    "target_language": {"type": "string", "description": "Target language code (e.g., 'es', 'fr', 'de', 'zh', 'ja')"},
                    "source_language": {"type": "string", "default": "auto", "description": "Source language code (default: auto-detect)"},
                    "model": {"type": "string", "default": "llama3.2:3b", "description": "Ollama model to use"},
                },
                "required": ["text", "target_language"],
            },
        ),
        Tool(
            name="translate_file",
            description="Translate content from a file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to file to translate"},
                    "target_language": {"type": "string", "description": "Target language code"},
                    "source_language": {"type": "string", "default": "auto"},
                    "model": {"type": "string", "default": "llama3.2:3b"},
                },
                "required": ["file_path", "target_language"],
            },
        ),
        Tool(
            name="get_last_translation",
            description="Get the last translation for follow-up queries.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="list_languages",
            description="List all supported language codes and names.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]
    return ListToolsResult(tools=tools)


async def handle_call_tool(params: CallToolRequestParams) -> CallToolResult:
    """Handle tool calls for translation."""
    global _last_translation
    
    name = params.name
    arguments = params.arguments or {}
    
    if name == "translate":
        text = arguments.get("text", "")
        target_lang = arguments.get("target_language", "").lower()
        source_lang = arguments.get("source_language", "auto").lower()
        model = arguments.get("model", "llama3.2:3b")
        
        if not text.strip():
            return CallToolResult(
                content=[TextContent(type="text", text="Error: Empty text provided")]
            )
        
        if not validate_language_code(target_lang):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: Unsupported target language '{target_lang}'. Use list_languages to see supported codes.")]
            )
        
        if source_lang != "auto" and not validate_language_code(source_lang):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: Unsupported source language '{source_lang}'.")]
            )
        
        prompt = build_translation_prompt(text, target_lang, source_lang)
        translation = await call_ollama(prompt, model, max_tokens=len(text.split()) * 2 + 100)
        
        # Store for follow-up
        _last_translation = {
            "original_text": text[:5000],
            "translated_text": translation,
            "source_language": source_lang,
            "target_language": target_lang,
            "model": model,
        }
        
        response = {
            "translated_text": translation,
            "source_language": source_lang,
            "target_language": target_lang,
            "target_language_name": SUPPORTED_LANGUAGES.get(target_lang, target_lang),
            "model": model,
        }
        
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(response, indent=2))]
        )
    
    elif name == "translate_file":
        file_path = arguments.get("file_path", "")
        target_lang = arguments.get("target_language", "").lower()
        source_lang = arguments.get("source_language", "auto").lower()
        model = arguments.get("model", "llama3.2:3b")
        
        if not os.path.exists(file_path):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: File '{file_path}' does not exist")]
            )
        
        if not validate_language_code(target_lang):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: Unsupported target language '{target_lang}'.")]
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
        
        prompt = build_translation_prompt(text, target_lang, source_lang)
        translation = await call_ollama(prompt, model, max_tokens=len(text.split()) * 2 + 100)
        
        _last_translation = {
            "original_text": text[:5000],
            "translated_text": translation,
            "source_language": source_lang,
            "target_language": target_lang,
            "model": model,
            "file_path": file_path,
        }
        
        response = {
            "translated_text": translation,
            "source_language": source_lang,
            "target_language": target_lang,
            "target_language_name": SUPPORTED_LANGUAGES.get(target_lang, target_lang),
            "file_path": file_path,
            "model": model,
        }
        
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(response, indent=2))]
        )
    
    elif name == "get_last_translation":
        if not _last_translation:
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps({"error": "No previous translation available"}))]
            )
        
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(_last_translation, indent=2))]
        )
    
    elif name == "list_languages":
        languages = [{"code": code, "name": name} for code, name in SUPPORTED_LANGUAGES.items()]
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"languages": languages}, indent=2))]
        )
    
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Unknown tool: {name}")]
        )


# Register request handlers
server = Server("translation-mcp-server")
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