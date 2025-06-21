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
1. Reads agent.json configurations
2. Instantiates LangGraph agents with specified tools
3. Deploys to Modal serverless infrastructure
4. Exposes APIs for agent interaction

### Key Patterns
- **Config-driven**: Agents defined declaratively in JSON
- **Tool composition**: MCP servers provide modular capabilities
- **Serverless deployment**: Modal handles scaling and infrastructure
- **Supervisor patterns**: Multi-agent coordination via LangGraph

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