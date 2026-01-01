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

            # Use rsplit to split from right, handling paths that might contain colons (e.g., C:\path on Windows)
            path_str, permission = entry.rsplit(":", 1)

            if permission not in ["ro", "rw"]:
                raise ValueError(f"Invalid permission '{permission}' (must be ro or rw)")

            path = Path(path_str).expanduser().resolve()

            if not path.exists():
                raise ValueError(f"Path does not exist: {path}")
            if not path.is_dir():
                raise ValueError(f"Path is not a directory: {path}")

            if path in self.allowed_paths:
                raise ValueError(f"Duplicate path in ALLOWED_PATHS: {path}")

            self.allowed_paths[path] = permission

        if not self.allowed_paths:
            raise ValueError("No valid paths in ALLOWED_PATHS")

    def _parse_size_limits(self):
        """Parse size limit configuration."""
        self.no_size_limit = os.getenv("NO_SIZE_LIMIT", "").lower() == "true"

        if self.no_size_limit:
            self.max_file_size_bytes = None
        else:
            max_mb_str = os.getenv("MAX_FILE_SIZE_MB", "10")
            try:
                max_mb = int(max_mb_str)
            except ValueError:
                raise ValueError(f"MAX_FILE_SIZE_MB must be numeric, got: {max_mb_str}")

            if max_mb <= 0:
                raise ValueError(f"MAX_FILE_SIZE_MB must be positive, got: {max_mb}")

            self.max_file_size_bytes = max_mb * 1024 * 1024

    def validate_path(self, path_str: str, require_write: bool = False) -> Path:
        """Validate path is within allowed directories with correct permissions.

        Args:
            path_str: Path to validate (absolute or relative)
            require_write: If True, require write permission (path need not exist)
                           If False, path must exist for read operations

        Returns:
            Resolved absolute Path object

        Raises:
            PermissionError: Path outside allowed dirs or insufficient permissions
            FileNotFoundError: Path doesn't exist (when require_write=False)
        """
        # Resolve to absolute path, following symlinks
        path_obj = Path(path_str).expanduser()

        # For read operations, path must exist to resolve symlinks properly
        # For write operations, parent must be within bounds (file may not exist yet)
        if require_write:
            # Writing - resolve what we can, validate parent directory bounds
            if path_obj.exists():
                requested = path_obj.resolve()
            else:
                # Non-existent file - resolve parent and append filename
                # This ensures we catch symlink escapes in the directory path
                if path_obj.parent.exists():
                    requested = path_obj.parent.resolve() / path_obj.name
                else:
                    # Parent doesn't exist either - resolve as far as we can
                    requested = path_obj.resolve()
        else:
            # Reading - path must exist
            if not path_obj.exists():
                raise FileNotFoundError(f"Path not found: {path_str}")
            requested = path_obj.resolve()

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

        # No allowed directory matched - provide helpful hint
        allowed_list = ", ".join(str(p) for p in self.allowed_paths.keys())
        raise PermissionError(
            f"Access denied: '{path_str}' resolves to '{requested}' "
            f"which is outside allowed directories. "
            f"Allowed paths: {allowed_list}"
        )
