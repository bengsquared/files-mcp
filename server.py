#!/usr/bin/env python3
"""Filesystem MCP Server - provides filesystem access to Claude Desktop."""

from mcp.server.fastmcp import FastMCP
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
