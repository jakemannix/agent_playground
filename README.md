# Agent Playground

Experimental development tools and frameworks for building AI agents, featuring config-driven deployment and modern tooling.

## Projects

### 🚀 [Agent Factory](./agent-factory/)

A modern Python framework for deploying config-driven AI agents to Modal serverless infrastructure.

**Features:**
- Config-driven agents using JSON and A2A protocol standards
- MCP tool integration via langchain-mcp-adapters
- Modal serverless deployment with automatic scaling
- LangGraph orchestration for react/supervisor agents
- FastAPI endpoints with A2A discovery
- Full test coverage with modern Python tooling

**Quick Start:**
```bash
cd agent-factory
uv venv && source .venv/bin/activate
uv pip install -e .
cp dummy.env .env  # Edit with your API keys
cp agent-factory/examples/configs/basic-example.json my_agent.json
agent-factory my_agent.json --message "Hello!"
```

See [agent-factory/README.md](./agent-factory/README.md) for detailed documentation.

### 🎨 [Generative UI](./generative_ui/)

Interactive web application demonstrating LLM-driven UI with FastHTML and HTMX.

**Features:**
- HAL 9000 interactive chat interface
- Dynamic SVG mood visualization
- FastHTML + HTMX for real-time updates
- Claude integration with structured responses

### 🔧 [Tools](./tools/)

Collection of MCP (Model Context Protocol) servers providing agent capabilities.

**Current Tools:**
- Example MCP server with basic operations
- File system operations (planned)
- Web search integration (planned)
- Database tools (planned)

## Architecture

```
agent_playground/
├── agent-factory/     # Standalone Python package for agent deployment
├── generative_ui/     # FastHTML demo applications  
├── tools/             # MCP server collection
└── README.md         # This file
```

## Development

This repository contains multiple related projects for agent development. Each subdirectory has its own development setup and documentation.

### Global Prerequisites

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) for Python package management
- [Modal](https://modal.com/) account for serverless deployment
- [Anthropic](https://console.anthropic.com/) API key

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Ensure all projects still work
5. Submit a pull request

## Desired Protocol Interaction

Below is a spec-level walk-through showing how to:

* Register and discover back-end agents & their typed skills
* Generate the router logic automatically or allow an override map – without hand-editing prompts
* Use the A2A task lifecycle so that a delegated agent remains “in charge” for follow-up user turns, yet control can always return to the router
* Keep full observability with a BaseResult envelope (and even an optional BaseInput) that travels through every hop.



## License

MIT License - see LICENSE file for details.