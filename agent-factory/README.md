# Agent Factory

A modern Python framework for deploying config-driven AI agents to Modal serverless infrastructure. Features LangGraph orchestration, MCP tool integration, and A2A protocol compatibility.

## Features

- 🤖 **Config-driven agents** - Define agents declaratively using JSON configuration
- 🔧 **MCP tool integration** - Seamless integration with Model Context Protocol tools via langchain-mcp-adapters
- ☁️ **Modal deployment** - Serverless deployment to Modal with automatic scaling
- 🌐 **A2A compatibility** - Extends Agent-to-Agent protocol standards for interoperability
- 🔄 **LangGraph orchestration** - Built on LangGraph's `create_react_agent()` and supervisor patterns
- 🎯 **FastAPI endpoints** - Production-ready APIs with health checks and A2A discovery
- 🧪 **Full test coverage** - Comprehensive test suite with pytest

## Quick Start

### Installation

#### Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/agent-factory
cd agent-factory

# Create and activate virtual environment with uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package and dependencies
uv pip install -e .

# Or install with development dependencies
uv pip install -e ".[dev]"
```

#### Alternative: Traditional pip

```bash
# Install from PyPI (when published)
pip install agent-factory

# Or install in development mode
git clone https://github.com/yourusername/agent-factory
cd agent-factory
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### Basic Usage

1. **Set up environment configuration:**

```bash
# Copy environment template and configure with your API keys
cp dummy.env .env
# Edit .env with your ANTHROPIC_API_KEY and Modal credentials
```

2. **Create an agent configuration:**

```bash
agent-factory example --output my_agent.json
```

3. **Test your agent locally:**

```bash
agent-factory test my_agent.json "Hello, how can you help me?"
```

4. **Deploy to Modal:**

```bash
agent-factory deploy my_agent.json
```

### Configuration

Create your environment configuration:

```bash
# Copy the dummy.env template to .env
cp dummy.env .env

# Edit .env with your actual values
# At minimum, you need:
# - ANTHROPIC_API_KEY (required)
# - MODAL_TOKEN_ID and MODAL_TOKEN_SECRET (for deployment)
```

**Required environment variables:**
- `ANTHROPIC_API_KEY` - Your Anthropic API key ([get one here](https://console.anthropic.com/))
- `MODAL_TOKEN_ID` - Modal token ID ([get from Modal settings](https://modal.com/settings/tokens))
- `MODAL_TOKEN_SECRET` - Modal token secret

**Optional but recommended:**
- `AGENT_PROVIDER_ORG` - Your organization name (for A2A compatibility)
- `AGENT_PROVIDER_URL` - Your organization URL

See `dummy.env` for a complete list of available configuration options.

## Agent Configuration

Agent Factory uses JSON configuration files that extend the A2A AgentCard standard:

```json
{
  "name": "Research Assistant",
  "description": "AI agent for research tasks",
  "url": "https://your-domain.com/research-agent",
  "system_prompt": "You are a helpful research assistant...",
  "model": "claude-3-5-sonnet-20241022",
  "temperature": 0.7,
  "agent_type": "react",
  "skills": [
    {
      "id": "web_research",
      "name": "Web Research", 
      "description": "Search and analyze web information",
      "tags": ["research", "web"],
      "examples": ["Find recent papers on AI"]
    }
  ],
  "mcp_tools": [
    {
      "name": "web_search",
      "server_path": "tools/web_search_server.py",
      "config": {
        "max_results": 10
      }
    }
  ],
  "modal_config": {
    "cpu": 1.0,
    "memory": 2048,
    "keep_warm": 1
  }
}
```

### Configuration Fields

#### A2A Standard Fields
- `name` - Agent name
- `description` - Agent description  
- `url` - Agent endpoint URL
- `skills` - Agent capabilities (auto-generated from MCP tools)
- `capabilities` - Streaming, notifications, etc.
- `provider` - Organization information
- `version` - Agent version

#### Agent Factory Extensions
- `system_prompt` - LLM system prompt
- `model` - LLM model (default: claude-3-5-sonnet-20241022)
- `temperature` - Sampling temperature (0.0-2.0)
- `agent_type` - "react" or "supervisor"
- `mcp_tools` - MCP tool configurations
- `modal_config` - Modal deployment settings

## MCP Tool Integration

Agent Factory uses [langchain-mcp-adapters](https://github.com/langchain-ai/langchain-mcp-adapters) for seamless MCP integration:

```json
{
  "mcp_tools": [
    {
      "name": "filesystem",
      "server_path": "mcp_servers/filesystem.py",
      "config": {
        "allowed_dirs": ["/workspace"],
        "max_file_size": "10MB"
      }
    }
  ]
}
```

Tools are automatically converted to LangChain tools and made available to the agent.

## Modal Deployment

Deploy agents as serverless functions with automatic scaling:

```python
from agent_factory import deploy_from_config_file

# Deploy from configuration file
url = deploy_from_config_file("my_agent.json")
print(f"Agent deployed at: {url}")
```

### Deployment Features

- **Automatic scaling** - Zero to thousands of requests
- **Keep-warm containers** - Configurable warm instances
- **Secret management** - Secure API key handling
- **Health checks** - Built-in monitoring endpoints
- **A2A discovery** - `.well-known/agent.json` endpoint

## API Endpoints

Deployed agents expose standard endpoints:

- `POST /invoke` - Invoke agent with message
- `GET /health` - Health check
- `GET /config` - Agent configuration summary
- `GET /.well-known/agent.json` - A2A agent card

### Example API Usage

```python
import requests

# Invoke agent
response = requests.post(
    "https://your-agent.modal.run/invoke",
    json={
        "message": "Research recent developments in quantum computing",
        "kwargs": {}
    }
)

# Get agent card (A2A compatible)
agent_card = requests.get(
    "https://your-agent.modal.run/.well-known/agent.json"
).json()
```

## Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/yourusername/agent-factory
cd agent-factory

# Create virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with development dependencies
uv pip install -e ".[dev]"

# Set up pre-commit hooks (optional)
pre-commit install
```

### Run Tests

```bash
# Run full test suite
pytest

# Run with coverage
pytest --cov=src/agent_factory --cov-report=html

# Run specific tests
pytest tests/test_config.py -v
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code  
ruff check .

# Type check
mypy .
```

### Build and Install

```bash
# Build package
uv build

# Install locally
pip install -e .
```

## CLI Reference

```bash
# Create example configuration
agent-factory example --output example.json

# Validate configuration
agent-factory validate config.json

# Test agent locally
agent-factory test config.json "test message"

# Deploy to Modal
agent-factory deploy config.json --name my-agent

# Help
agent-factory --help
```

## Examples

See the `examples/` directory for complete agent configurations:

- `research_agent.json` - Research assistant with web search
- `code_agent.json` - Code analysis and generation
- `data_agent.json` - Data processing and analysis

## A2A Protocol Compatibility

Agent Factory agents are compatible with the Agent-to-Agent protocol:

- Extends `AgentCard` standard for configuration
- Provides `.well-known/agent.json` discovery endpoint  
- Auto-generates skills from MCP tools
- Supports standard capability declarations

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Agent Config  │    │  MCP Tools      │    │  Modal Deploy   │
│   (JSON + A2A)  │───▶│  (langchain-    │───▶│  (Serverless)   │
│                 │    │   mcp-adapters) │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   LangGraph     │
                       │   Agent         │
                       │                 │
                       └─────────────────┘
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run quality checks: `ruff format . && ruff check . && pytest`
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

- 📚 [Documentation](https://agent-factory.readthedocs.io)
- 🐛 [Issue Tracker](https://github.com/yourusername/agent-factory/issues)
- 💬 [Discussions](https://github.com/yourusername/agent-factory/discussions)