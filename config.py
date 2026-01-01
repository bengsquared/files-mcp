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
