# Filesystem MCP Server Design

**Date:** 2026-01-01
**Status:** Approved for implementation

## Overview

Build a Python MCP server that gives Claude Desktop filesystem access with directory-scoped permissions. Focus on core operations: read, write, list directory, and directory trees.

## Design Decisions

### Technology Stack
- **Python** with FastMCP framework
- Standard library only (pathlib, os, json)
- Stdio transport for Claude Desktop integration

### Security Model
- **Explicit allowlist** - directories defined in config
- **Recursive permissions** - subdirectories inherit parent permissions
- **Two permission levels:** read-only (`ro`) or read-write (`rw`)
- **Symlink validation** - resolve and validate target is within bounds
- **Size limits** - configurable max file size (default 10MB, can disable)

### Configuration
Environment variables in Claude Desktop config:
```bash
ALLOWED_PATHS="/path/to/dir:rw,/other/path:ro"
MAX_FILE_SIZE_MB="10"  # or NO_SIZE_LIMIT="true"
```

## Architecture

### Project Structure
```
files-mcp/
├── server.py          # Main MCP server with tools
├── config.py          # Permission parsing and path validation
├── requirements.txt   # Dependencies (just mcp)
└── README.md         # Setup instructions
```

### Core Components

**1. Configuration System (`config.py`)**
- Parse `ALLOWED_PATHS` into `{Path: Permission}` dictionary
- Resolve paths to absolute on startup
- Validate paths exist and are directories
- Configure size limits

**2. Path Validation**
- `validate_path(path_str, require_write)` function
- Resolve symlinks with `Path.resolve()`
- Check path is within allowed directory using `relative_to()`
- Verify write permission if needed
- Fail closed - deny if no match

**3. MCP Tools**

Four tools exposed to Claude:

- **`read_file(path: str)`** - read file contents with size limit check
- **`write_file(path: str, content: str)`** - write file with parent dir creation
- **`list_directory(path: str)`** - list files/dirs as JSON
- **`list_directory_tree(path: str, max_depth: int)`** - recursive tree up to depth limit

### Error Handling
- `PermissionError` - path outside allowed dirs or wrong permission
- `FileNotFoundError` - file doesn't exist
- `NotADirectoryError` - not a directory
- `ValueError` - file too large, invalid parameters

FastMCP automatically catches and returns errors to Claude.

### Logging
- Use stderr for diagnostics (stdout reserved for MCP protocol)
- Log allowed paths and config on startup
- Appears in Claude Desktop logs for debugging

## Deployment

**Claude Desktop Config:**
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "python",
      "args": ["/Users/ben/Documents/Projects/code/files-mcp/server.py"],
      "env": {
        "ALLOWED_PATHS": "/Users/ben/Documents:rw,/Users/ben/Projects:rw",
        "MAX_FILE_SIZE_MB": "10"
      }
    }
  }
}
```

**Testing:**
1. Local: `python server.py` with env vars set
2. MCP Inspector: `npx @modelcontextprotocol/inspector python server.py`
3. Claude Desktop: restart app, check hammer icon for tools

## Future Enhancements

Deferred to later iterations:
- Bash command execution (with working directory restrictions)
- Move/rename operations
- File search capabilities
- Integration with Claude Code CLI

## References

- [Official Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MarcusJellinghaus filesystem server](https://github.com/MarcusJellinghaus/mcp_server_filesystem) - reference for path validation patterns
- [Claude Desktop MCP setup](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)
