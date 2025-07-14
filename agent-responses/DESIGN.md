# Agent Responses Design Document

## Overview

Agent Responses is a config-driven Python package that leverages the OpenAI Responses API to create AI agents with native MCP (Model Context Protocol) support. This design document outlines the architecture, key decisions, and implementation details.

## Architecture

### Core Components

1. **Configuration Layer (`config.py`)**
   - Pydantic models for type-safe configuration
   - Support for environment variable expansion
   - Validation and schema enforcement

2. **Runner Layer (`core/runner.py`)**
   - Direct integration with OpenAI Responses API
   - Conversation state management
   - Streaming and non-streaming response handling

3. **HTTP API Layer (`http/api.py`)**
   - FastAPI-based REST API
   - Streaming support via SSE
   - CORS-enabled for web frontends

4. **CLI Interface (`cli.py`)**
   - Command-line interface for all operations
   - Support for single-message and server modes
   - Configuration generation and validation

## Key Design Decisions

### 1. Direct API Integration

Unlike agent-factory which uses LangChain/LangGraph, we directly integrate with the OpenAI Responses API. This provides:

- **Reduced complexity**: No intermediate abstractions
- **Native MCP support**: No adapters needed
- **Better performance**: Direct API calls, fewer layers
- **Simpler debugging**: Clear request/response flow

### 2. Configuration-First Approach

Everything is driven by JSON configuration files:

```json
{
  "agent_card": {...},      // Public agent description
  "mcp_servers": [...],     // MCP server configurations
  "built_in_tools": [...],  // OpenAI built-in tools
  "deployment": {...}       // Runtime configuration
}
```

Benefits:
- No code required for basic agents
- Version control friendly
- Easy to share and reproduce
- Clear separation of concerns

### 3. Native MCP Integration

The OpenAI Responses API has built-in MCP support via the `mcp` tool type:

```python
{
  "type": "mcp",
  "server_label": "weather",
  "server_url": "https://example.com/mcp",
  "allowed_tools": ["get_weather"],
  "require_approval": "never"
}
```

This eliminates the need for:
- MCP adapters
- Tool conversion logic
- Schema extraction
- Complex initialization

### 4. Streaming-First Design

Both the runner and API support streaming:

```python
# Runner level
async for chunk in runner.stream(message):
    process(chunk)

# API level
POST /chat with stream=true returns SSE
```

### 5. Conversation State Management

The runner manages conversation state using `previous_response_id`:

```python
class ResponsesRunner:
    def __init__(self, config):
        self._previous_response_id = None
    
    async def invoke(self, message):
        # Uses previous_response_id for continuity
        ...
```

## Implementation Details

### MCP Server Configuration

MCP servers are configured with:
- `server_url`: The MCP server endpoint
- `server_label`: Unique identifier
- `allowed_tools`: Tool filtering (optional)
- `require_approval`: Control approval flow
- `headers`: Authentication (stored separately)

### Built-in Tools

OpenAI provides several built-in tools:
- `web_search_preview`: Web search capability
- `code_interpreter`: Code execution
- `image_generation`: Image creation

### Error Handling

- HTTP errors: Proper status codes and messages
- API errors: Graceful degradation
- MCP errors: Tool-specific error handling

### Security Considerations

1. **API Keys**: Environment variables only
2. **Headers**: Sanitized and prefixed
3. **CORS**: Configurable for production
4. **Input validation**: Pydantic models

## Comparison with Agent Factory

| Feature | Agent Factory | Agent Responses |
|---------|--------------|-----------------|
| Core Framework | LangChain/LangGraph | Direct OpenAI API |
| MCP Support | Via adapters | Native |
| Configuration | A2A + custom | Simplified JSON |
| Schema Extraction | Manual process | Automatic |
| Deployment | Modal focused | Multiple options |
| Complexity | Higher | Lower |

## Future Enhancements

1. **Additional Deployment Targets**
   - AWS Lambda
   - Google Cloud Functions
   - Vercel

2. **Enhanced MCP Features**
   - MCP server discovery
   - Dynamic tool loading
   - Tool versioning

3. **Advanced Features**
   - Multi-agent orchestration
   - Custom tool development
   - Plugin system

4. **Monitoring & Observability**
   - Token usage tracking
   - Performance metrics
   - Error analytics

## Conclusion

Agent Responses provides a simpler, more direct approach to building AI agents with the OpenAI Responses API. By leveraging native MCP support and focusing on configuration over code, it enables rapid development and deployment of sophisticated AI agents without the complexity of traditional frameworks. 