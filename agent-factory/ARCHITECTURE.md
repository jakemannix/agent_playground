# Agent Factory Architecture

## Overview

Agent Factory has been refactored to provide a cleaner separation between public A2A-compliant agent descriptions and private deployment configurations. The architecture supports the MCP (Model Context Protocol) specification by extracting schema information from the tools created by MCP servers.

## Key Components

### 1. Configuration Structure

The configuration is now split into two main parts:

```python
class AgentConfiguration:
    agent_card: MCPAgentCard  # Public, A2A-compliant
    deployment: DeploymentConfig  # Private, internal only
```

#### MCPAgentCard (Public)

The `MCPAgentCard` extends the standard A2A `AgentCard` and includes:

- **MCPSkills**: Skills that include MCP server configuration and extracted schemas
- **agent_type**: Agent behavior type ("react" only)
- **ui_modes**: Supported UI interaction modes
- **A2A Extension**: Declares MCP support via standard A2A extension mechanism

This is what gets served at `/.well-known/agent.json`.

#### DeploymentConfig (Private)

Contains internal implementation details:

- **LLMConfig**: Model, temperature, max_tokens, system_prompt
- **ModalConfig**: CPU, memory, timeout, secrets
- **ui_config**: Full UI implementation details

### 2. MCPSkill

The `MCPSkill` class extends A2A's `AgentSkill` with MCP-specific fields:

```python
class MCPSkill(AgentSkill):
    mcp_config: Dict[str, Any]  # MCP server connection config
    input_schema: Optional[Dict[str, Any]]  # From tool.input_schema
    output_schema: Optional[Dict[str, Any]]  # From tool.output_schema
```

The schemas are extracted by introspecting the `BaseTool` objects created by `langchain-mcp-adapters`.

### 3. Schema Extraction

The harness automatically extracts schemas when initializing the agent:
1. Creates tools using `MultiServerMCPClient` 
2. Extracts `input_schema` and `output_schema` from each tool
3. Updates the `MCPSkill` objects in the agent card with the extracted schemas

This happens during agent initialization, so the same tools used for execution also provide the schema information. No duplicate tool creation is needed.

### 4. Current Limitations

While we can extract and expose schemas, the actual tool execution still happens within:
- `langchain-mcp-adapters` for creating LangChain tools
- `langgraph` for agent orchestration

This means structured output handling (per MCP 2025-06-18) is managed by these libraries.

## Benefits

1. **Clean Separation**: Public API (agent card) is clearly separated from private deployment details
2. **A2A Compliance**: Uses standard A2A extension mechanisms rather than breaking the schema
3. **Schema Transparency**: MCP tool schemas are extracted and exposed in the agent card
4. **No Redundancy**: MCP configuration and schemas live directly in skills
5. **Backward Compatible**: Older configuration files are automatically converted

## Migration

### Previous Format

```json
{
  "name": "My Agent",
  "model": "claude-3-5-sonnet-20241022",
  "skills": [{
    "id": "mcp_weather",
    "name": "weather",
    "mcp_config": {"transport": "http", "url": "..."}
  }],
  "modal_config": {...}
}
```

### New Format

```json
{
  "agent_card": {
    "name": "My Agent",
    "skills": [{
      "id": "mcp_weather_get_forecast",
      "name": "weather_get_forecast",
      "mcp_config": {"transport": "http", "url": "..."},
      "input_schema": {
        "type": "object",
        "properties": {
          "location": {"type": "string"}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "forecast": {"type": "array"}
        }
      }
    }],
    "capabilities": {
      "extensions": [{
        "uri": "https://modelcontextprotocol.io/mcp/1.0",
        "params": {"version": "2025-06-18"}
      }]
    }
  },
  "deployment": {
    "llm": {
      "model": "claude-3-5-sonnet-20241022"
    },
    "modal": {...}
  }
}
```

The `AgentConfiguration.from_file()` method automatically converts older formats.

## Example Usage

See `examples/` directory for sample agent configurations demonstrating MCP tool integration.

## Design Philosophy

1. **A2A Protocol Compliance**: Extends the Agent-to-Agent protocol with MCP-specific fields
2. **Clean Separation**: Public agent card vs private deployment configuration
3. **Schema Extraction**: Automatic extraction and caching of tool schemas from MCP servers
4. **Template-Based Configuration**: Support for base configs with environment-specific overrides
5. **Tool Reliability**: Agents should not claim capabilities they cannot deliver
   - Required skills must be available or initialization fails
   - Optional skills can fail gracefully
   - Strict validation can be disabled for development/debugging 