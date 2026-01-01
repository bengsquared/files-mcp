#!/usr/bin/env python3
"""Filesystem MCP Server - provides filesystem access to Claude Desktop."""

from mcp.server.fastmcp import FastMCP
import sys
from pathlib import Path
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
        ValueError: File too large or binary file
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
    try:
        return file_path.read_text()
    except UnicodeDecodeError:
        raise ValueError(f"Cannot read binary file: {path}. Only text files supported.")


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
    content_bytes = content.encode('utf-8')
    size = len(content_bytes)

    if config.max_file_size_bytes:
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

    return f"Wrote {size} bytes to {path}"


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
                if item.is_symlink():
                    continue  # Skip symlinks to prevent traversal issues
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
