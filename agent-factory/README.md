# Agent Factory

A modern Python framework for deploying config-driven AI agents to Modal serverless infrastructure. Features LangGraph orchestration, MCP tool integration, and A2A protocol compatibility.

## Features

- 🤖 **Config-driven agents** - Define agents declaratively using JSON configuration
- 🔧 **MCP tool integration** - Seamless integration with Model Context Protocol tools via langchain-mcp-adapters
- ☁️ **Modal deployment** - Serverless deployment to Modal with automatic scaling
- 🌐 **A2A compatibility** - Extends Agent-to-Agent protocol standards for interoperability
- 🔄 **LangGraph orchestration** - Built on LangGraph's `create_react_agent()`
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

2. **Choose or create an agent configuration:**

```bash
# Use a pre-built example
cp examples/configs/basic-example.json my_agent.json
cp examples/weather_agent.json my_agent.json
cp examples/research_agent.json my_agent.json
```

3. **Test your agent:**

```bash
# Run a single message and exit
agent-factory my_agent.json --message "Hello, how can you help me?"
agent-factory examples/weather_agent.json --message "What's the weather in SF?"

# Start interactive server locally (default port 8000)
agent-factory my_agent.json
agent-factory my_agent.json --port 3000
```

4. **Deploy to Modal:**

```bash
# Deploy to Modal cloud
agent-factory my_agent.json --deploy
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

Agent Factory uses JSON configuration files that extend the A2A AgentCard standard. See the working examples in the `examples/` directory:

- `examples/weather_agent.json` - Weather agent with MCP tool integration
- `examples/research_agent.json` - Research agent configuration

Example agent configuration structure:

```json
{
  "agent_card": {
    "name": "Your Agent Name",
    "description": "Agent description",
    "skills": [/* MCP tool configurations */]
  },
  "deployment": {
    "llm": {
      "model": "claude-3-5-sonnet-20241022",
      "temperature": 0.7,
      "system_prompt": "Your system prompt..."
    }
  }
}
```

### Configuration Fields

#### A2A Standard Fields
- `name` - Agent name
- `description` - Agent description  
- `url` - Agent endpoint URL
- `skills` - Agent capabilities with MCP configurations
- `capabilities` - Streaming, notifications, etc.
- `provider` - Organization information
- `version` - Agent version

#### Agent Factory Extensions
- `system_prompt` - LLM system prompt
- `model` - LLM model (default: claude-3-5-sonnet-20241022)
- `temperature` - Sampling temperature (0.0-2.0)
- `agent_type` - "react" only (ReAct pattern agent)
- `ui_modes` - Supported UI interaction modes

## MCP Tool Integration

Agent Factory uses [langchain-mcp-adapters](https://github.com/langchain-ai/langchain-mcp-adapters) for seamless MCP integration. Tools are configured in the `skills` array of your agent configuration. See `examples/weather_agent.json` for a complete working example with multiple MCP tools.

### Tool Availability Handling

Agent Factory ensures agents don't claim capabilities they can't deliver:

1. **Required Skills (default)**: Agent initialization fails if MCP servers are unavailable
2. **Optional Skills**: Set `"optional": true` to continue without specific tools
3. **Strict Validation**: Set `deployment.strict_tool_validation` to `false` to allow degraded operation

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
# Run agent interactively (starts web server)
agent-factory config.json
agent-factory config.json --port 3000

# Run single message and exit
agent-factory config.json --message "Hello!"

# Run and save agent card with extracted schemas
agent-factory config.json --message "Hello!" --output complete-config.json

# Use strict validation (fails if schemas changed)
agent-factory complete-config.json --strict

# Create config from template with overrides
agent-factory template.json --apply overrides.yaml --output custom.json
agent-factory template.json --set agent_card.name="Custom" --output custom.json

# Deploy to Modal cloud
agent-factory config.json --deploy

# Help
agent-factory --help
```

## Running the Weather Agent Example

The weather agent example demonstrates MCP tool integration and requires external MCP servers. Follow these steps:

### 1. Environment Setup

```bash
# Ensure .env file exists and is populated
cp dummy.env .env
# Edit .env to add your ANTHROPIC_API_KEY

# Activate virtual environment
cd agent-factory
source .venv/bin/activate
```

### 2. Launch MCP Proxy Server

In one terminal, start the MCP proxy server for fetch and memory tools:

```bash
cd ../tools  # Navigate to agent_playground/tools directory

# Install mcp-proxy if needed
pip install mcp-proxy

# Start MCP proxy server
python -m mcp_proxy \
    --port=18456 \
    --host=127.0.0.1 \
    --named-server-config=servers_config.json \
    --pass-environment \
    --allow-origin="*" \
    --debug
```

### 3. Launch Weather MCP Server

In another terminal, start the weather server:

```bash
# Option A: If you have cloned invariantlabs-ai/mcp-streamable-http
cd path/to/mcp-streamable-http/python-example/server
python weather.py --port 8123

# Option B: Use the example server in tools/
cd agent_playground/tools
python example_mcp_server.py --port 8123
```

### 4. Test the Weather Agent

With both MCP servers running:

```bash
cd agent-factory

# Test with a single message
agent-factory examples/weather_agent.json --message "What's the weather in Seattle?"

# Start interactive server
agent-factory examples/weather_agent.json --port 8000
```

The agent will have access to weather data, web fetching, and memory capabilities through the MCP servers.

## Configuration Management

### Schema Extraction and Caching

Agent Factory automatically extracts MCP tool schemas when running agents:

```bash
# First run extracts schemas and saves complete config
agent-factory my-agent.json --output my-agent-complete.json

# Subsequent runs use cached schemas (faster startup)
agent-factory my-agent-complete.json
```

### Template-Based Configuration

Create custom agents by applying overrides to base templates:

```bash
# Use YAML overrides
agent-factory base.json --apply custom.yaml --output result.json

# Use inline overrides
agent-factory base.json \
  --set agent_card.name="My Agent" \
  --set deployment.llm.temperature=0.5 \
  --output result.json
```

### Testing Other Examples

```bash
# Test the research agent (may not require external MCP servers)
agent-factory examples/research_agent.json --message "Research recent AI developments"
```

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