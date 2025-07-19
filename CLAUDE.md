# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an MCP (Model Context Protocol) server that provides secure Python code execution capabilities using Docker containers. The server exposes a single `execute_python` tool that allows running arbitrary Python code in isolated Docker environments with resource limits and network isolation.

## Key Architecture

The project consists of three main components:

1. **ipython_server.py** - Main MCP server using FastMCP framework that handles tool requests
2. **ipython_wrapper.py** - Python script that runs inside Docker containers to execute code using IPython
3. **Dockerfile** - Defines the execution environment with pre-installed data science packages

### Execution Flow

1. MCP server receives `execute_python` tool call with Python code
2. Server spawns a new Docker container with unique name and resource limits
3. Code is sent to container's stdin where `ipython_wrapper.py` executes it using IPython
4. Results (text output, images, errors) are captured and returned as JSON
5. Container is automatically cleaned up after execution

## Development Commands

### Docker Operations
```bash
# Build the IPython executor image (required for functionality)
docker build -t ipython-executor .

# Run the MCP server
uv run fastmcp run ipython_server.py

# Manual testing of wrapper script
echo "print('hello')" | python ipython_wrapper.py
```

### Package Management
```bash
# Install dependencies using uv
uv sync

# Add new dependencies
uv add package-name
```

## Session Management

The server supports persistent sessions via the `session_id` parameter. Each session gets its own directory under `sessions/` that is mounted into containers, allowing variables and state to persist across executions within the same session.

## Security Features

- Docker containers run with no network access (`--network none`)
- Resource limits: 512MB memory, 0.5 CPU cores
- 30-second execution timeout
- 1MB output size limit
- Non-root user execution inside containers
- Automatic container cleanup

## Output Handling

The system supports multiple output types:
- Text output (stdout, results, print statements)
- Error messages (stderr, exceptions)
- Images (matplotlib plots automatically captured as base64 PNG)

All outputs are structured as JSON arrays with type and data fields, then converted to appropriate MCP ToolResult content types.