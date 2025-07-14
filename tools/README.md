## Local Development

For local development, you can install `mcp-proxy` directly:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the proxy
./launch_servers.sh
```

The `mcp-proxy` package is now available on PyPI and can be installed with:
- `uv tool install mcp-proxy` (recommended)
- `pipx install mcp-proxy` (alternative)  
- `pip install mcp-proxy`

## Modal Deployment

For cloud deployment, use the Modal setup:

```bash
# Install dependencies
./deploy.sh deps

# Test locally
./deploy.sh test

# Deploy to Modal cloud
./deploy.sh serve
```

See [MODAL_DEPLOY.md](MODAL_DEPLOY.md) for detailed deployment instructions.
