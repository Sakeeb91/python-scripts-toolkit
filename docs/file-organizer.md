# Smart File Organizer - Technical Documentation

A Python script that automatically sorts files in a directory into categorized subfolders based on file extensions.

## Table of Contents

- [Concepts Overview](#concepts-overview)
- [Technologies Used](#technologies-used)
- [Core Code Explained](#core-code-explained)
- [Key Python Fundamentals](#key-python-fundamentals)
- [Configuration](#configuration)
- [Extending the Project](#extending-the-project)

---

## Concepts Overview

### What Problem Does This Solve?

Downloads folders and desktop directories often become cluttered with files of various types. Manually sorting these files is tedious and error-prone. This script automates the process by:

1. **Scanning** a directory for files
2. **Classifying** each file based on its extension
3. **Moving** files into appropriate category folders
4. **Handling** naming conflicts safely

### How It Works

```
Before:                          After:
Downloads/                       Downloads/
├── report.pdf                   ├── Documents/
├── vacation.jpg                 │   └── report.pdf
├── script.py                    ├── Images/
├── archive.zip                  │   └── vacation.jpg
└── song.mp3                     ├── Code/
                                 │   └── script.py
                                 ├── Archives/
                                 │   └── archive.zip
                                 └── Audio/
                                     └── song.mp3
```

---

## Technologies Used

### Standard Library Modules

| Module | Purpose | Why We Use It |
|--------|---------|---------------|
| `pathlib` | Object-oriented filesystem paths | Modern, cross-platform path handling |
| `shutil` | High-level file operations | Safe file moving with `shutil.move()` |
| `os` | Operating system interface | Environment variables, basic OS ops |
| `argparse` | Command-line argument parsing | Professional CLI with help text |
| `collections.defaultdict` | Dictionary with default values | Automatic initialization for counters |

### Why `pathlib` Over `os.path`?

```python
# Old way (os.path) - string manipulation
import os
path = os.path.join(folder, "subdir", "file.txt")
extension = os.path.splitext(path)[1]
exists = os.path.exists(path)

# New way (pathlib) - object-oriented
from pathlib import Path
path = Path(folder) / "subdir" / "file.txt"
extension = path.suffix
exists = path.exists()
```

`pathlib` provides:
- Cleaner syntax with `/` operator for joining paths
- Methods directly on Path objects (`.exists()`, `.is_file()`, `.suffix`)
- Cross-platform compatibility (handles Windows `\` vs Unix `/`)
- Type hints work better with Path objects

---

## Core Code Explained

### 1. Extension-to-Category Mapping

The heart of the organizer is a dictionary that maps file extensions to categories:

```python
# From config.py
FILE_ORGANIZER_CONFIG = {
    "categories": {
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
        "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".xls", ".xlsx"],
        "Code": [".py", ".js", ".ts", ".html", ".css", ".java", ".cpp"],
        # ... more categories
    },
    "default_category": "Other",
}
```

At initialization, we invert this into a fast lookup dictionary:

```python
def __init__(self, ...):
    # Build extension -> category mapping for O(1) lookup
    self.ext_map = {}
    for category, extensions in self.categories.items():
        for ext in extensions:
            self.ext_map[ext.lower()] = category

    # Result: {'.jpg': 'Images', '.pdf': 'Documents', '.py': 'Code', ...}
```

**Why this matters:** Looking up a category by extension is now O(1) constant time instead of O(n) where n is the number of categories.

### 2. Directory Walking and File Classification

```python
def organize(self) -> dict:
    """Organize all files in the source directory."""

    # Iterate over items in directory
    for item in self.source_dir.iterdir():
        if item.is_file():  # Skip subdirectories
            self._process_file(item)

    return dict(self.stats)

def get_category(self, file_path: Path) -> str:
    """Determine the category for a file based on its extension."""
    ext = file_path.suffix.lower()  # .PDF -> .pdf
    return self.ext_map.get(ext, self.default_category)
```

**Key concepts:**
- `Path.iterdir()` yields all items in a directory
- `Path.is_file()` distinguishes files from directories
- `Path.suffix` extracts the extension including the dot
- `.lower()` ensures case-insensitive matching
- `dict.get(key, default)` returns default if key not found

### 3. Safe File Moving with Collision Handling

```python
def _process_file(self, file_path: Path) -> None:
    """Process a single file."""
    category = self.get_category(file_path)
    dest_dir = self.source_dir / category
    dest_path = dest_dir / file_path.name

    # Handle name collisions
    if dest_path.exists():
        dest_path = get_unique_path(dest_path)

    if not self.dry_run:
        ensure_dir(dest_dir)           # Create folder if needed
        shutil.move(str(file_path), str(dest_path))
```

The `get_unique_path()` helper handles naming conflicts:

```python
def get_unique_path(path: Path) -> Path:
    """Get a unique file path by appending a number if file exists.

    Example: file.txt -> file_1.txt -> file_2.txt
    """
    if not path.exists():
        return path

    stem = path.stem      # 'file' from 'file.txt'
    suffix = path.suffix  # '.txt' from 'file.txt'
    parent = path.parent  # directory containing the file
    counter = 1

    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1
```

**Why `shutil.move()` instead of `Path.rename()`?**
- `shutil.move()` works across different filesystems/drives
- `Path.rename()` fails if source and destination are on different mounts

### 4. Dry-Run Mode Implementation

```python
class FileOrganizer:
    def __init__(self, source_dir: Path, dry_run: bool = False, ...):
        self.dry_run = dry_run

    def _process_file(self, file_path: Path) -> None:
        # ... determine destination ...

        self.logger.info(f"  {file_path.name} -> {category}/")

        if not self.dry_run:  # Only move if not in dry-run mode
            ensure_dir(dest_dir)
            shutil.move(str(file_path), str(dest_path))

        # Always track statistics (even in dry-run)
        self.stats[category] += 1
```

**Pattern:** The dry-run pattern is useful for any destructive operation. It allows users to preview changes before committing them.

### 5. CLI with argparse

```python
def main():
    parser = argparse.ArgumentParser(
        description="Organize files in a directory by their type",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ~/Downloads                    # Organize Downloads folder
  %(prog)s ~/Downloads --dry-run          # Preview changes
        """
    )

    parser.add_argument(
        "directory",
        type=Path,                        # Automatic Path conversion
        help="Directory to organize"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",              # Boolean flag
        help="Show what would be done without moving files"
    )

    args = parser.parse_args()

    organizer = FileOrganizer(
        source_dir=args.directory,
        dry_run=args.dry_run
    )
    organizer.organize()
```

**argparse features used:**
- `type=Path` automatically converts string to Path object
- `action="store_true"` creates a boolean flag
- Short options (`-n`) and long options (`--dry-run`)
- Epilog with usage examples

---

## Key Python Fundamentals

### 1. Dictionaries for Mapping

```python
# Dictionary comprehension to invert the mapping
ext_to_category = {
    ext: category
    for category, extensions in categories.items()
    for ext in extensions
}
```

### 2. defaultdict for Counting

```python
from collections import defaultdict

# Without defaultdict:
stats = {}
for item in items:
    if category not in stats:
        stats[category] = 0
    stats[category] += 1

# With defaultdict:
stats = defaultdict(int)  # Default value is 0
for item in items:
    stats[category] += 1  # No KeyError if key doesn't exist
```

### 3. Path Object Chaining

```python
from pathlib import Path

# Chain operations fluently
dest_path = (
    self.source_dir    # /Users/me/Downloads
    / category         # /Users/me/Downloads/Images
    / file_path.name   # /Users/me/Downloads/Images/photo.jpg
)
```

### 4. Conditional Expressions in Logging

```python
mode = "DRY RUN" if self.dry_run else "LIVE"
self.logger.info(f"Starting file organization [{mode}]: {self.source_dir}")
```

---

## Configuration

### Adding New Categories

Edit `config.py` to add new file types:

```python
FILE_ORGANIZER_CONFIG = {
    "categories": {
        # Add a new category
        "3D Models": [".obj", ".fbx", ".stl", ".blend", ".3ds"],

        # Or extend existing ones
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".raw", ".cr2", ".nef"],
    },
}
```

### Changing Default Behavior

```python
FILE_ORGANIZER_CONFIG = {
    # Change where uncategorized files go
    "default_category": "Miscellaneous",
}
```

---

## Undo/Rollback Feature

The File Organizer includes built-in undo functionality that lets you restore files to their original locations.

### How It Works

After each organization operation (non-dry-run), a **manifest file** is saved to `data/manifests/`. This JSON file records:
- Timestamp of the operation
- Source directory that was organized
- Every file move (original path → destination path)
- Organization mode (recursive, max-depth)

### Usage Examples

```bash
# Organize files normally (creates a manifest)
python main.py organize ~/Downloads

# Undo the most recent organization
python main.py organize --undo

# View history of all organization operations
python main.py organize --list-history

# Undo a specific operation by manifest filename
python main.py organize --undo --manifest organize_2024-01-15_10-30-00.json
```

### What Undo Handles

| Scenario | Behavior |
|----------|----------|
| File still exists at destination | Moves back to original location |
| File was deleted after organizing | Skipped (with warning) |
| Original location is now occupied | Skipped (with warning) |
| Empty category directories | Automatically removed |
| Successful complete undo | Manifest file is deleted |

### Manifest Structure

```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "source_dir": "/Users/me/Downloads",
  "recursive": false,
  "max_depth": null,
  "files_moved": 15,
  "moves": [
    {
      "source": "/Users/me/Downloads/photo.jpg",
      "destination": "/Users/me/Downloads/Images/photo.jpg",
      "category": "Images"
    }
  ]
}
```

---

## Extending the Project

### Ideas for Enhancement

1. **Duplicate Detection**
   ```python
   import hashlib

   def get_file_hash(path: Path) -> str:
       """Calculate MD5 hash of file contents."""
       hash_md5 = hashlib.md5()
       with open(path, "rb") as f:
           for chunk in iter(lambda: f.read(4096), b""):
               hash_md5.update(chunk)
       return hash_md5.hexdigest()
   ```

2. **Date-Based Organization**
   ```python
   def get_date_folder(file_path: Path) -> str:
       """Organize by modification date."""
       mtime = file_path.stat().st_mtime
       date = datetime.fromtimestamp(mtime)
       return date.strftime("%Y/%m")  # "2024/01"
   ```

3. **Watch Mode with Continuous Monitoring**
   ```python
   from watchdog.observers import Observer
   from watchdog.events import FileSystemEventHandler

   class OrganizeHandler(FileSystemEventHandler):
       def on_created(self, event):
           if not event.is_directory:
               organizer.process_file(Path(event.src_path))
   ```

---

## Summary

The File Organizer teaches these core Python concepts:

| Concept | How It's Used |
|---------|---------------|
| `pathlib` | Modern path handling |
| `shutil` | Safe file operations |
| Dictionaries | Extension mapping |
| `defaultdict` | Automatic counters |
| `argparse` | Professional CLI |
| Conditionals | Category classification |
| Classes | Encapsulating state and behavior |
| Logging | Operation tracking |
| `json` | Manifest serialization |
| File I/O | Undo/rollback persistence |

This is a practical script that solves a real problem while demonstrating fundamental Python patterns used in professional codebases.
