# Agent Responses

A simplified, config-driven Python package for creating AI agents using the OpenAI Responses API with native MCP (Model Context Protocol) support.

## Overview

Agent Responses provides a streamlined approach to building AI agents by:

- **Config-driven approach**: Define agent behavior through JSON configuration files
- **Native MCP support**: Direct integration with OpenAI Responses API's MCP capabilities  
- **Minimal abstractions**: Simple, direct API calls without unnecessary wrappers
- **a2a-sdk integration**: Leverages standard agent card types from the a2a ecosystem
- **Clean architecture**: Separate server and client processes
- **Streaming support**: Real-time streaming responses

## Architecture

This package follows a clean server/client architecture:

- **Server** (`agent-responses`): Runs the AI agent as an HTTP service
- **Client** (`agent-responses-chat`): Interactive or single-message client
- **Configuration**: Simple JSON files with a2a-sdk types (AgentCard, AgentSkill)  
- **HTTP API**: Minimal FastAPI wrapper with agent card and chat endpoints

## Installation

```bash
pip install agent-responses
```

For development:
```bash
pip install agent-responses[dev]
```

For Modal deployment:
```bash
pip install agent-responses[modal]
```

## Quick Start

### 1. Set Your API Key

```bash
export OPENAI_API_KEY="your-api-key-here"
```

### 2. Use an Example Configuration

The package includes example configurations:
- `examples/basic_assistant.json`: Simple assistant without external dependencies
- `examples/weather_assistant.json`: MCP-enabled weather assistant

### 3. Run Your Agent

**Terminal 1: Start the server**
```bash
agent-responses examples/basic_assistant.json
```

**Terminal 2: Interactive client**
```bash
agent-responses-chat
```

**Or send a single message**
```bash
agent-responses-chat --message "Hello, how are you?"
```

**Different port**
```bash
# Server
agent-responses examples/basic_assistant.json --port 8001

# Client  
agent-responses-chat --port 8001
```

## Configuration Structure

```json
{
  "card": {
    "name": "My Assistant",
    "description": "AI assistant with MCP tools",
    "version": "1.0.0",
    "capabilities": ["chat", "tool_use", "mcp"],
    "tags": ["general", "assistant"],
    "skills": [
      {
        "name": "example_mcp",
        "description": "Example MCP server",
        "server_label": "example",
        "server_url": "https://example.com/mcp",
        "allowed_tools": ["tool1", "tool2"],
        "require_approval": "never",
        "headers": {
          "Authorization": "Bearer ${API_KEY}"
        }
      }
    ]
  },
  "deployment": {
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_output_tokens": 2048,
    "system_prompt": "You are a helpful assistant.",
    "modal_cpu": 1.0,
    "modal_memory": 1024,
    "modal_timeout": 300
  }
}
```

## MCP Server Integration

The OpenAI Responses API natively supports MCP servers through the `mcp` tool type:

```json
{
  "mcp_servers": [
    {
      "id": "github-docs",
      "server_label": "github",
      "server_url": "https://gitmcp.io/openai/tiktoken",
      "allowed_tools": ["search_documentation", "fetch_documentation"],
      "require_approval": "never"
    }
  ]
}
```

Supported MCP transports:
- HTTP over SSE
- Streamable HTTP

## Built-in Tools

OpenAI provides several built-in tools:

### Web Search
```json
{
  "type": "web_search_preview",
  "enabled": true,
  "config": {
    "search_context_size": "medium"
  }
}
```

### Code Interpreter
```json
{
  "type": "code_interpreter",
  "enabled": true,
  "config": {
    "container": {
      "type": "auto"
    }
  }
}
```

### Image Generation
```json
{
  "type": "image_generation",
  "enabled": true
}
```

## API Usage

### Python SDK

```python
from agent_responses import AgentConfiguration, Runner

# Load configuration
config = AgentConfiguration.from_file("my-agent.json")

# Create runner
runner = Runner(config)

# Send a message
response = runner.invoke_sync("Hello, how are you?")
print(response)

# Stream responses
async for chunk in runner.stream("Tell me a story"):
    print(chunk)
```

### HTTP API

When running the server (`agent-responses config.json`):

```bash
# Chat endpoint
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello",
    "stream": false
  }'

# Get agent card
curl http://localhost:8000/.well-known/agent.json
```

## Environment Variables

The package supports environment variable expansion in configurations:

```json
{
  "mcp_servers": [{
    "server_url": "${MCP_SERVER_URL}",
    "headers": {
      "Authorization": "Bearer ${MCP_API_KEY}"
    }
  }]
}
```

## Deployment

### Local Development

```bash
agent-responses run config.json --port 8000
```

### Modal Deployment

Coming soon! Modal deployment will allow you to deploy your agents to the cloud with a single command.

## Advanced Features

### Tool Approval

Control when tool calls require approval:

- `"never"`: Auto-approve all calls
- `"always"`: Always require approval
- `"auto"`: Let the API decide (default)

### Reasoning Models

For complex tasks, use reasoning models:

```json
{
  "deployment": {
    "llm": {
      "model": "o4-mini",
      "reasoning": {
        "effort": "medium",
        "summary": "auto"
      }
    }
  }
}
```

### Conversation Management

The runner maintains conversation state automatically:

```python
# Continue a conversation
runner.invoke_sync("Follow up message")

# Reset conversation
runner.reset_conversation()
```

## Best Practices

1. **Filter MCP tools**: Use `allowed_tools` to limit which tools are available
2. **Set appropriate models**: Use reasoning models for complex tasks, standard models for simple queries
3. **Configure timeouts**: Set appropriate timeouts for your use case
4. **Use environment variables**: Keep sensitive data out of config files
5. **Monitor token usage**: Track usage to optimize costs

## Troubleshooting

### Common Issues

1. **MCP server connection failed**: Check server URL and authentication headers
2. **Tool not found**: Ensure the tool is listed in `allowed_tools` or remove the restriction
3. **Timeout errors**: Increase timeout in deployment config
4. **Authentication errors**: Verify API keys are set correctly

### Debug Mode

Run with verbose output for debugging:

```bash
agent-responses run config.json --verbose
```

## Contributing

Contributions are welcome! Please see our contributing guidelines.

## License

MIT License - see LICENSE file for details.

## Related Projects

- [OpenAI Responses API Documentation](https://platform.openai.com/docs/guides/tools-remote-mcp)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Agent Factory](https://github.com/example/agent-factory) - Inspiration for this project 