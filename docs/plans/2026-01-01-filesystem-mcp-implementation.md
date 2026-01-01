# Filesystem MCP Server Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python MCP server that gives Claude Desktop filesystem access with directory-scoped read/write permissions.

**Architecture:** FastMCP server with environment-based configuration, path validation using pathlib resolution, and four core tools (read, write, list, tree). All file operations validate paths are within allowed directories before execution.

**Tech Stack:** Python 3.8+, FastMCP (official MCP SDK), pathlib, json

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`

**Step 1: Create requirements.txt**

Create file with dependencies:

```
mcp>=1.0.0
```

**Step 2: Create .gitignore**

```
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info/
dist/
build/
.venv/
venv/
.DS_Store
```

**Step 3: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: Successfully installed mcp

**Step 4: Commit**

```bash
git init
git add requirements.txt .gitignore
git commit -m "chore: initial project setup"
```

---

## Task 2: Configuration Module - Permission Parsing

**Files:**
- Create: `config.py`

**Step 1: Write permission parsing logic**

Create `config.py`:

```python
from pathlib import Path
from typing import Dict, Literal
import os
import sys

Permission = Literal["ro", "rw"]

class Config:
    """Parse and validate filesystem access configuration."""

    def __init__(self):
        self.allowed_paths: Dict[Path, Permission] = {}
        self._parse_allowed_paths()
        self._parse_size_limits()

    def _parse_allowed_paths(self):
        """Parse ALLOWED_PATHS environment variable."""
        paths_env = os.getenv("ALLOWED_PATHS", "")
        if not paths_env:
            raise ValueError("ALLOWED_PATHS environment variable required")

        for entry in paths_env.split(","):
            entry = entry.strip()
            if not entry:
                continue

            if ":" not in entry:
                raise ValueError(f"Invalid entry (missing :permission): {entry}")

            path_str, permission = entry.rsplit(":", 1)

            if permission not in ["ro", "rw"]:
                raise ValueError(f"Invalid permission '{permission}' (must be ro or rw)")

            path = Path(path_str).expanduser().resolve()

            if not path.exists():
                raise ValueError(f"Path does not exist: {path}")
            if not path.is_dir():
                raise ValueError(f"Path is not a directory: {path}")

            self.allowed_paths[path] = permission

        if not self.allowed_paths:
            raise ValueError("No valid paths in ALLOWED_PATHS")

    def _parse_size_limits(self):
        """Parse size limit configuration."""
        self.no_size_limit = os.getenv("NO_SIZE_LIMIT", "").lower() == "true"

        if self.no_size_limit:
            self.max_file_size_bytes = None
        else:
            max_mb = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
            self.max_file_size_bytes = max_mb * 1024 * 1024
```

**Step 2: Test configuration parsing manually**

Run:
```bash
export ALLOWED_PATHS="/tmp:rw"
python -c "from config import Config; c = Config(); print(c.allowed_paths)"
```

Expected: Shows `/tmp` with `rw` permission

**Step 3: Test error handling**

Run:
```bash
unset ALLOWED_PATHS
python -c "from config import Config; Config()"
```

Expected: ValueError about missing ALLOWED_PATHS

**Step 4: Commit**

```bash
git add config.py
git commit -m "feat: add configuration parsing for allowed paths"
```

---

## Task 3: Configuration Module - Path Validation

**Files:**
- Modify: `config.py`

**Step 1: Add path validation method**

Add to `Config` class in `config.py`:

```python
    def validate_path(self, path_str: str, require_write: bool = False) -> Path:
        """Validate path is within allowed directories with correct permissions.

        Args:
            path_str: Path to validate (absolute or relative)
            require_write: If True, require write permission

        Returns:
            Resolved absolute Path object

        Raises:
            PermissionError: Path outside allowed dirs or insufficient permissions
            FileNotFoundError: Path doesn't exist (only if require_write=False)
        """
        # Resolve to absolute path, following symlinks
        requested = Path(path_str).expanduser().resolve()

        # Find which allowed directory contains this path
        for allowed_dir, permission in self.allowed_paths.items():
            try:
                # Check if requested path is within allowed_dir
                requested.relative_to(allowed_dir)

                # Check write permission if needed
                if require_write and permission == "ro":
                    raise PermissionError(
                        f"Write access denied: {allowed_dir} is read-only"
                    )

                # Valid path within allowed directory
                return requested

            except ValueError:
                # Not relative to this allowed_dir, try next
                continue

        # No allowed directory matched
        raise PermissionError(
            f"Access denied: {requested} is outside allowed directories"
        )
```

**Step 2: Test path validation manually**

Run:
```bash
export ALLOWED_PATHS="/tmp:rw"
python -c "
from config import Config
c = Config()
print('Valid:', c.validate_path('/tmp/test.txt', require_write=True))
"
```

Expected: Shows resolved path to `/tmp/test.txt`

**Step 3: Test path escape prevention**

Run:
```bash
export ALLOWED_PATHS="/tmp:rw"
python -c "
from config import Config
c = Config()
try:
    c.validate_path('/etc/passwd')
except PermissionError as e:
    print('Blocked:', e)
"
```

Expected: "Blocked: Access denied..."

**Step 4: Test read-only enforcement**

Run:
```bash
export ALLOWED_PATHS="/tmp:ro"
python -c "
from config import Config
c = Config()
try:
    c.validate_path('/tmp/test.txt', require_write=True)
except PermissionError as e:
    print('Blocked write:', e)
"
```

Expected: "Blocked write: Write access denied..."

**Step 5: Commit**

```bash
git add config.py
git commit -m "feat: add path validation with permission checks"
```

---

## Task 4: MCP Server - Setup and read_file Tool

**Files:**
- Create: `server.py`

**Step 1: Create server with read_file tool**

Create `server.py`:

```python
#!/usr/bin/env python3
"""Filesystem MCP Server - provides filesystem access to Claude Desktop."""

from mcp import FastMCP
from pathlib import Path
import sys
from config import Config

# Initialize MCP server and config
mcp = FastMCP("filesystem")
config = Config()

@mcp.tool()
async def read_file(path: str) -> str:
    """Read file contents from allowed directories.

    Args:
        path: Path to file to read

    Returns:
        File contents as string

    Raises:
        PermissionError: Path outside allowed directories
        FileNotFoundError: File doesn't exist
        ValueError: File too large
    """
    # Validate path is within allowed directories
    file_path = config.validate_path(path, require_write=False)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not file_path.is_file():
        raise FileNotFoundError(f"Not a file: {path}")

    # Check size limit
    if config.max_file_size_bytes:
        size = file_path.stat().st_size
        if size > config.max_file_size_bytes:
            max_mb = config.max_file_size_bytes / (1024 * 1024)
            size_mb = size / (1024 * 1024)
            raise ValueError(
                f"File too large: {size_mb:.1f}MB (limit: {max_mb:.0f}MB)"
            )

    # Read and return file contents
    return file_path.read_text()


if __name__ == "__main__":
    try:
        # Log configuration on startup (to stderr, not stdout)
        print("Starting filesystem MCP server...", file=sys.stderr)
        print("Allowed paths:", file=sys.stderr)
        for path, perm in config.allowed_paths.items():
            print(f"  {path} ({perm})", file=sys.stderr)

        if config.no_size_limit:
            print("Size limit: DISABLED", file=sys.stderr)
        else:
            max_mb = config.max_file_size_bytes / (1024 * 1024)
            print(f"Size limit: {max_mb:.0f}MB", file=sys.stderr)

        print("", file=sys.stderr)

        # Start MCP server with stdio transport
        mcp.run(transport="stdio")

    except Exception as e:
        print(f"Failed to start server: {e}", file=sys.stderr)
        sys.exit(1)
```

**Step 2: Test server starts**

Run:
```bash
export ALLOWED_PATHS="/tmp:rw"
python server.py &
sleep 1
pkill -f "python server.py"
```

Expected: Prints "Starting filesystem MCP server..." to stderr, runs without error

**Step 3: Create test file and test read_file with MCP Inspector**

Run:
```bash
echo "test content" > /tmp/test.txt
npx @modelcontextprotocol/inspector python server.py
```

Expected: Opens inspector UI, shows `read_file` tool
Manual: Test `read_file` with path="/tmp/test.txt", should return "test content"

**Step 4: Commit**

```bash
git add server.py
git commit -m "feat: add MCP server with read_file tool"
```

---

## Task 5: MCP Server - write_file Tool

**Files:**
- Modify: `server.py`

**Step 1: Add write_file tool**

Add to `server.py` after `read_file`:

```python
@mcp.tool()
async def write_file(path: str, content: str) -> str:
    """Write content to file in allowed directories.

    Creates parent directories if they don't exist.

    Args:
        path: Path to file to write
        content: Content to write to file

    Returns:
        Success message with bytes written

    Raises:
        PermissionError: Path outside allowed directories or read-only
        ValueError: Content too large
    """
    # Validate path with write permission required
    file_path = config.validate_path(path, require_write=True)

    # Check size limit
    if config.max_file_size_bytes:
        size = len(content.encode('utf-8'))
        if size > config.max_file_size_bytes:
            max_mb = config.max_file_size_bytes / (1024 * 1024)
            size_mb = size / (1024 * 1024)
            raise ValueError(
                f"Content too large: {size_mb:.1f}MB (limit: {max_mb:.0f}MB)"
            )

    # Create parent directories if needed
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Write file
    file_path.write_text(content)

    byte_count = len(content.encode('utf-8'))
    return f"Wrote {byte_count} bytes to {path}"
```

**Step 2: Test write_file with MCP Inspector**

Run:
```bash
export ALLOWED_PATHS="/tmp:rw"
npx @modelcontextprotocol/inspector python server.py
```

Manual tests:
1. Test `write_file` with path="/tmp/test_write.txt", content="hello world"
   - Should return "Wrote 11 bytes to /tmp/test_write.txt"
   - Verify: `cat /tmp/test_write.txt` shows "hello world"

2. Test `write_file` creates parent dirs: path="/tmp/nested/dir/file.txt", content="test"
   - Should succeed
   - Verify: `cat /tmp/nested/dir/file.txt` shows "test"

3. Test read-only blocking:
   - Set `ALLOWED_PATHS="/tmp:ro"`
   - Try `write_file` with path="/tmp/readonly.txt"
   - Should fail with "Write access denied"

**Step 3: Commit**

```bash
git add server.py
git commit -m "feat: add write_file tool with parent directory creation"
```

---

## Task 6: MCP Server - list_directory Tool

**Files:**
- Modify: `server.py`

**Step 1: Add list_directory tool**

Add to `server.py` after `write_file`:

```python
@mcp.tool()
async def list_directory(path: str) -> str:
    """List contents of a directory.

    Args:
        path: Path to directory to list

    Returns:
        JSON array of directory entries with name and type

    Raises:
        PermissionError: Path outside allowed directories
        NotADirectoryError: Path is not a directory
    """
    import json

    # Validate path is within allowed directories
    dir_path = config.validate_path(path, require_write=False)

    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {path}")

    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    # List directory contents
    entries = []
    for item in sorted(dir_path.iterdir()):
        entry_type = "dir" if item.is_dir() else "file"
        entries.append({
            "name": item.name,
            "type": entry_type
        })

    return json.dumps(entries, indent=2)
```

**Step 2: Test list_directory with MCP Inspector**

Run:
```bash
# Create test directory structure
mkdir -p /tmp/test_dir
touch /tmp/test_dir/file1.txt
touch /tmp/test_dir/file2.py
mkdir /tmp/test_dir/subdir

export ALLOWED_PATHS="/tmp:rw"
npx @modelcontextprotocol/inspector python server.py
```

Manual tests:
1. Test `list_directory` with path="/tmp/test_dir"
   - Should return JSON with file1.txt, file2.py (type: file), subdir (type: dir)

2. Test with non-directory path="/tmp/test_dir/file1.txt"
   - Should fail with "Not a directory"

**Step 3: Commit**

```bash
git add server.py
git commit -m "feat: add list_directory tool"
```

---

## Task 7: MCP Server - list_directory_tree Tool

**Files:**
- Modify: `server.py`

**Step 1: Add list_directory_tree tool**

Add to `server.py` after `list_directory`:

```python
@mcp.tool()
async def list_directory_tree(path: str, max_depth: int = 3) -> str:
    """Recursively list directory structure.

    Args:
        path: Path to directory to list
        max_depth: Maximum recursion depth (default 3, max 10)

    Returns:
        JSON tree structure with nested children

    Raises:
        PermissionError: Path outside allowed directories
        NotADirectoryError: Path is not a directory
    """
    import json

    # Validate path is within allowed directories
    dir_path = config.validate_path(path, require_write=False)

    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {path}")

    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    # Clamp max_depth to reasonable limits
    max_depth = max(1, min(max_depth, 10))

    def build_tree(current_path: Path, current_depth: int) -> dict:
        """Recursively build directory tree."""
        if current_depth > max_depth:
            return {
                "name": current_path.name,
                "type": "dir",
                "truncated": True
            }

        result = {
            "name": current_path.name,
            "type": "dir",
            "children": []
        }

        try:
            for item in sorted(current_path.iterdir()):
                if item.is_dir():
                    result["children"].append(build_tree(item, current_depth + 1))
                else:
                    result["children"].append({
                        "name": item.name,
                        "type": "file"
                    })
        except PermissionError:
            result["error"] = "Permission denied"

        return result

    tree = build_tree(dir_path, 0)
    return json.dumps(tree, indent=2)
```

**Step 2: Test list_directory_tree with MCP Inspector**

Run:
```bash
# Create nested test structure
mkdir -p /tmp/tree_test/level1/level2/level3
touch /tmp/tree_test/root.txt
touch /tmp/tree_test/level1/file1.txt
touch /tmp/tree_test/level1/level2/file2.txt
touch /tmp/tree_test/level1/level2/level3/deep.txt

export ALLOWED_PATHS="/tmp:rw"
npx @modelcontextprotocol/inspector python server.py
```

Manual tests:
1. Test `list_directory_tree` with path="/tmp/tree_test", max_depth=3
   - Should return nested JSON showing all levels up to level3

2. Test depth limiting with path="/tmp/tree_test", max_depth=1
   - Should show level1 dir but mark it as truncated

3. Test default depth with path="/tmp/tree_test"
   - Should use default max_depth=3

**Step 3: Commit**

```bash
git add server.py
git commit -m "feat: add list_directory_tree tool with depth limiting"
```

---

## Task 8: Documentation and Usage Guide

**Files:**
- Create: `README.md`

**Step 1: Write README**

Create `README.md`:

```markdown
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
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add comprehensive README with setup instructions"
```

---

## Task 9: Final Testing and Verification

**Files:**
- None (testing only)

**Step 1: Full integration test with Claude Desktop**

1. Update `claude_desktop_config.json` with actual paths:
   ```json
   {
     "mcpServers": {
       "filesystem": {
         "command": "python",
         "args": ["/Users/ben/Documents/Projects/code/files-mcp/server.py"],
         "env": {
           "ALLOWED_PATHS": "/Users/ben/Documents:rw,/tmp:rw",
           "MAX_FILE_SIZE_MB": "10"
         }
       }
     }
   }
   ```

2. Quit and restart Claude Desktop

3. Open new chat, look for 🔨 hammer icon

4. Test each tool:
   - "List files in /Users/ben/Documents"
   - "Read the file at /Users/ben/Documents/test.txt"
   - "Write 'Hello from Claude' to /tmp/claude-test.txt"
   - "Show me the directory tree of /tmp with depth 2"

Expected: All tools work, operations stay within allowed directories

**Step 2: Test security boundaries**

In Claude chat:
- "Read /etc/passwd" - Should fail with permission error
- "Write to /System/test.txt" - Should fail with permission error

Expected: Access denied for paths outside ALLOWED_PATHS

**Step 3: Test size limits**

1. Create large file:
   ```bash
   dd if=/dev/zero of=/tmp/large.txt bs=1m count=20
   ```

2. In Claude: "Read /tmp/large.txt"
   Expected: Error about file too large

3. Test NO_SIZE_LIMIT:
   - Update config with `"NO_SIZE_LIMIT": "true"`
   - Restart Claude Desktop
   - Try reading large file again
   Expected: Should work now

**Step 4: Check logs**

```bash
tail -50 ~/Library/Logs/Claude/mcp*.log
```

Expected: Clean startup messages, no errors

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore: final verification and testing complete"
git tag v1.0.0
```

---

## Implementation Complete!

**What you built:**
- ✅ FastMCP-based filesystem server
- ✅ Environment-based configuration
- ✅ Secure path validation with symlink resolution
- ✅ Four core tools: read, write, list, tree
- ✅ Configurable size limits
- ✅ Claude Desktop integration
- ✅ Comprehensive documentation

**Next steps:**
1. Use it with Claude Desktop for real work
2. Monitor logs for any issues
3. Future: Add bash execution, move/rename, search

**Total implementation time:** ~30-40 minutes for experienced developer
