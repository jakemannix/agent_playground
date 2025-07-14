#!/bin/bash

# Deploy MCP proxy to Modal
# Usage: ./deploy.sh [test|serve]

ACTION=${1:-test}

echo "MCP Proxy Modal Deployment"
echo "=========================="

case $ACTION in
    "test")
        echo "Testing deployment locally..."
        modal run modal_deploy.py
        ;;
    "serve")
        echo "Deploying to Modal cloud..."
        modal serve modal_deploy.py
        ;;
    "deps")
        echo "Installing dependencies..."
        pip install -r requirements.txt
        ;;
    *)
        echo "Usage: $0 [test|serve|deps]"
        echo ""
        echo "Commands:"
        echo "  test  - Test the deployment locally"
        echo "  serve - Deploy to Modal cloud"
        echo "  deps  - Install dependencies"
        echo ""
        echo "Examples:"
        echo "  $0 deps   # Install modal and mcp-proxy"
        echo "  $0 test   # Test locally"
        echo "  $0 serve  # Deploy to cloud"
        ;;
esac 