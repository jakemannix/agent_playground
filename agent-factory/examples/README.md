# Agent Examples

This directory contains example agent configurations demonstrating different features and use cases.

## Configuration Files

### `configs/basic-example.json`

A comprehensive example showing all available configuration options:
- Agent metadata (name, description, provider)
- MCP tool integration with input/output schemas
- LLM configuration (Claude model, temperature, etc.)
- Modal deployment settings (CPU, memory, secrets)
- UI configuration options

### `base-template.json`

A minimal base template for creating custom agents using overrides:
- Basic agent structure with empty skills array
- Default LLM and deployment settings
- Ready to be extended with YAML/JSON overrides

### `research-overrides.yaml`

Example YAML overrides to create a research assistant from the base template:
- Adds web search and arXiv search skills
- Customizes temperature and system prompt for research tasks
- Increases memory and timeout for complex queries

## New Configuration Management Features

### 1. Automatic Schema Extraction

Run any agent and save the complete agent card with extracted MCP schemas:

```bash
# Run and save with schemas
agent-factory config.json --message "test" --output complete-config.json

# The saved config now includes extracted input/output schemas
# Future runs will use these cached schemas for faster startup
agent-factory complete-config.json
```

### 2. Schema Validation with --strict

When using a config with pre-extracted schemas, use `--strict` to ensure MCP servers haven't changed:

```bash
# Fail if MCP tool schemas have changed
agent-factory complete-config.json --strict
```

### 3. Configuration Templating

Create custom agents by applying overrides to a base template:

```bash
# Apply YAML overrides
agent-factory base-template.json --apply research-overrides.yaml --output research-agent.json

# Apply inline overrides
agent-factory base-template.json \
  --set agent_card.name="My Agent" \
  --set deployment.llm.temperature=0.5 \
  --output my-agent.json

# Combine both
agent-factory base-template.json \
  --apply research-overrides.yaml \
  --set agent_card.name="Custom Research Agent" \
  --output custom-research.json
```

### 4. Complete Workflow Example

```bash
# Step 1: Create custom agent from template
agent-factory examples/base-template.json \
  --apply examples/research-overrides.yaml \
  --output research-agent.json

# Step 2: Run and extract schemas
agent-factory research-agent.json \
  --message "Find recent papers on LLMs" \
  --output research-agent-complete.json

# Step 3: Use cached version (fast startup)
agent-factory research-agent-complete.json

# Step 4: Deploy with schema validation
agent-factory research-agent-complete.json --strict --deploy
```

## Usage Examples

```bash
# Test single message with example config
agent-factory configs/basic-example.json --message "Hello!"

# Start interactive server with example
agent-factory configs/basic-example.json

# Deploy example to Modal cloud
agent-factory configs/basic-example.json --deploy
```

## Individual Agent Examples

### `research_agent.json`
A research assistant agent with web search and analysis capabilities.

### `weather_agent.json`
A weather information agent demonstrating API integration patterns.

Both examples use the current agent_card + deployment configuration format with full MCP tool support. 