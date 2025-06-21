# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
```bash
cd agent-factory
source .venv/bin/activate

# Test weather agent (requires MCP server on localhost:8123)
agent-factory test examples/weather_agent.json "What's the weather in SF?"

# Verbose testing for debugging
agent-factory -v test examples/weather_agent.json "test"

# Validate configurations
agent-factory validate examples/weather_agent.json
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