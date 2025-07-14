# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overall development guidlines:
- This repository is under rapid development: only attempt to "preserve prior functionality" when asked.  Generally, adding new code paths in parallel to the old, with flags allowing both to work, "for backwards compatibility" MUST be avoided unless requested.  When in doubt, ask if backwards compat is needed, if some functionality is being removed.

## Project Overview

Agent development platform for building and deploying AI agents with MCP tools and Modal serverless infrastructure. Features config-driven agent creation, LangGraph orchestration, and FastHTML-based UIs.

## Architecture

### Core Components
- **agent_factory/**: Modal deployment harness for config-driven agents using LangGraph
- **tools/**: Collection of MCP (Model Context Protocol) servers providing agent capabilities  
- **generative_ui/**: FastHTML-based web interfaces for agent interaction

### Technology Stack
- **Modal**: Serverless deployment infrastructure
- **LangGraph**: Agent orchestration via `create_react_agent()` and `create_supervisor()`
- **MCP**: Tool integration protocol for agent capabilities
- **FastHTML + HTMX**: Dynamic web UIs with LLM-driven interactions

## Development Setup

### Dependencies
```bash
pip install modal langgraph fasthtml claudette
```

### Agent Configuration
Agents are defined via `agent.json` configuration files containing:
- Agent metadata and behavior
- MCP tool specifications
- Deployment parameters
- UI configuration

## Agent Factory

The agent_factory provides a deployment harness that:
1. Reads agent.json configurations ✅ WORKING
2. Instantiates LangGraph agents with specified tools ✅ WORKING
3. Deploys to Modal serverless infrastructure (coming soon)
4. Exposes APIs for agent interaction (coming soon)

### Current Status
- **Local testing**: ✅ FULLY WORKING - Can test agents locally with MCP tools
- **Configuration validation**: ✅ WORKING
- **MCP integration**: ✅ WORKING via langchain-mcp-adapters
- **Modal deployment**: Coming soon
- **API endpoints**: Coming soon

### Key Patterns
- **Config-driven**: Agents defined declaratively in JSON
- **Tool composition**: MCP servers provide modular capabilities
- **Local development**: Test with localhost MCP servers
- **Serverless deployment**: Modal handles scaling and infrastructure (coming soon)
- **Supervisor patterns**: Multi-agent coordination via LangGraph

### Testing Commands

#### Weather Agent Example (Full MCP Setup)

The weather agent requires external MCP servers. Follow these steps:

```bash
# 1. Environment setup
cd agent-factory
cp dummy.env .env  # Edit to add ANTHROPIC_API_KEY
source .venv/bin/activate

# 2. Launch MCP proxy server (in separate terminal)
cd ../tools
pip install mcp-proxy
python -m mcp_proxy \
    --port=18456 \
    --host=127.0.0.1 \
    --named-server-config=servers_config.json \
    --pass-environment \
    --allow-origin="*" \
    --debug

# 3. Launch weather MCP server (in another terminal)
# Option A: If you have cloned invariantlabs-ai/mcp-streamable-http
cd path/to/mcp-streamable-http/python-example/server
python weather.py --port 8123

# Option B: Use example server
cd agent_playground/tools
python example_mcp_server.py --port 8123

# 4. Test the weather agent (with both servers running)
cd agent-factory
agent-factory examples/weather_agent.json --message "What's the weather in Seattle?"

# Verbose testing for debugging
agent-factory examples/weather_agent.json --message "test" --verbose

# Start interactive server
agent-factory examples/weather_agent.json --port 8000
```

#### Simple Testing (No External Servers)

```bash
# Test research agent (may not require external MCP servers)
agent-factory examples/research_agent.json --message "Research recent AI developments"
```

## Tools Package

MCP servers in the tools/ directory provide agent capabilities:
- File system operations
- Web scraping and search
- Database interactions
- API integrations
- Custom business logic

## Generative UI

FastHTML applications provide interactive agent interfaces:
- Real-time chat with HTMX updates
- LLM-driven UI generation
- Dynamic tool result visualization
- Multi-agent conversation flows
