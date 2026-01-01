# Filesystem MCP Server

Python MCP server that provides Claude Desktop with filesystem access within configured directory boundaries.

## Features

- **Read files** - Read file contents with size limits
- **Write files** - Create/overwrite files with automatic parent directory creation
- **List directories** - Get directory contents as JSON
- **Directory trees** - Recursively list directory structure

## Security

- **Directory scoping** - All operations restricted to allowed directories
- **Permission levels** - Read-only (`ro`) or read-write (`rw`) per directory
- **Symlink validation** - Symlinks resolved and validated against allowed paths
- **Size limits** - Configurable max file size (default 10MB)

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Configuration

Set environment variables in Claude Desktop config:

**`ALLOWED_PATHS`** (required): Comma-separated list of `path:permission` entries
- Format: `/path/to/dir:rw,/other/path:ro`
- `rw` = read-write access
- `ro` = read-only access
- Paths must be absolute and exist
- Access is recursive (subdirectories inherit permissions)

**`MAX_FILE_SIZE_MB`** (optional): Maximum file size in megabytes (default: 10)

**`NO_SIZE_LIMIT`** (optional): Set to `true` to disable size limits

## Claude Desktop Setup

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "python",
      "args": ["/absolute/path/to/files-mcp/server.py"],
      "env": {
        "ALLOWED_PATHS": "/Users/you/Documents:rw,/Users/you/Projects:rw",
        "MAX_FILE_SIZE_MB": "10"
      }
    }
  }
}
```

**Activation:**
1. Quit Claude Desktop completely
2. Restart Claude Desktop
3. Look for hammer icon (🔨) in chat input
4. Click to see available tools

## Testing

**Local testing:**
```bash
export ALLOWED_PATHS="/tmp:rw"
export MAX_FILE_SIZE_MB="10"
python server.py
```

**MCP Inspector (interactive testing):**
```bash
export ALLOWED_PATHS="/tmp:rw"
npx @modelcontextprotocol/inspector python server.py
```

Opens web UI to test tools interactively.

## Tools

### read_file
Read file contents.
- **Args:** `path` (string)
- **Returns:** File contents as string
- **Errors:** Path outside allowed dirs, file not found, file too large

### write_file
Write content to file (creates parent directories).
- **Args:** `path` (string), `content` (string)
- **Returns:** Success message with byte count
- **Errors:** Path outside allowed dirs, read-only directory, content too large

### list_directory
List directory contents.
- **Args:** `path` (string)
- **Returns:** JSON array of `{name, type}` objects
- **Errors:** Path outside allowed dirs, not a directory

### list_directory_tree
Recursively list directory structure.
- **Args:** `path` (string), `max_depth` (int, default 3, max 10)
- **Returns:** JSON tree with nested children
- **Errors:** Path outside allowed dirs, not a directory

## Debugging

**Claude Desktop logs:**
```bash
# macOS
tail -f ~/Library/Logs/Claude/mcp*.log

# Server startup output appears in logs
```

**Common issues:**
- Server not appearing: Check config file syntax, restart Claude Desktop
- Permission errors: Verify paths in ALLOWED_PATHS exist and are absolute
- Tools not showing: Check logs for startup errors

## Future Enhancements

- Bash command execution with directory restrictions
- File move/rename operations
- Search capabilities
- Integration with Claude Code CLI
