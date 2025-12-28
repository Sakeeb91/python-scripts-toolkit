"""
Shared helper functions used across projects.
"""
from pathlib import Path
from typing import Union
import json
from datetime import datetime


def ensure_dir(path: Union[str, Path]) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_unique_path(path: Path) -> Path:
    """
    Get a unique file path by appending a number if the file already exists.

    Example: file.txt -> file_1.txt -> file_2.txt
    """
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1

    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def load_json(path: Union[str, Path]) -> dict:
    """Load JSON from a file, returning empty dict if file doesn't exist."""
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, 'r') as f:
        return json.load(f)


def save_json(data: dict, path: Union[str, Path], indent: int = 2) -> None:
    """Save data to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=indent, default=str)


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def parse_date(date_str: str) -> datetime:
    """Parse common date formats."""
    formats = [
        '%Y-%m-%d',
        '%Y/%m/%d',
        '%d-%m-%Y',
        '%d/%m/%Y',
        '%m/%d/%Y',
        '%Y-%m-%d %H:%M:%S',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {date_str}")


def parse_size(size_str: str) -> int:
    """Parse human-readable file size string to bytes.

    Supports formats like: 100, 1KB, 10MB, 1.5GB, 500B
    Case insensitive: 1kb, 1KB, 1Kb all work.

    Args:
        size_str: Size string like "1KB", "10MB", "1.5GB"

    Returns:
        Size in bytes as integer.

    Raises:
        ValueError: If the size string format is invalid.

    Examples:
        >>> parse_size("1KB")
        1024
        >>> parse_size("10MB")
        10485760
        >>> parse_size("1.5GB")
        1610612736
    """
    size_str = size_str.strip().upper()

    # Unit multipliers (using binary units: 1KB = 1024 bytes)
    units = {
        'B': 1,
        'KB': 1024,
        'MB': 1024 ** 2,
        'GB': 1024 ** 3,
        'TB': 1024 ** 4,
    }

    # Try to match number + unit pattern
    import re
    match = re.match(r'^([0-9]*\.?[0-9]+)\s*([A-Z]*B?)$', size_str)
    if not match:
        raise ValueError(f"Invalid size format: {size_str}. Use formats like: 100, 1KB, 10MB, 1.5GB")

    number_str, unit = match.groups()
    number = float(number_str)

    # Default to bytes if no unit specified
    if not unit:
        unit = 'B'

    if unit not in units:
        raise ValueError(f"Unknown size unit: {unit}. Valid units: B, KB, MB, GB, TB")

    return int(number * units[unit])
