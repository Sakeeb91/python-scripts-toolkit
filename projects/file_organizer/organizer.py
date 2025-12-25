"""
Smart File Organizer - Sorts files into subfolders by type.

Usage:
    python -m projects.file_organizer.organizer /path/to/folder
    python -m projects.file_organizer.organizer /path/to/folder --dry-run
    python -m projects.file_organizer.organizer /path/to/folder --log
    python -m projects.file_organizer.organizer --undo
    python -m projects.file_organizer.organizer --list-history
"""
import argparse
import json
import shutil
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import FILE_ORGANIZER_CONFIG, LOGS_DIR, MANIFESTS_DIR
from utils.logger import setup_logger
from utils.helpers import get_unique_path, ensure_dir

# Directories to skip during recursive traversal
EXCLUDED_DIRS = {
    '.git', '.svn', '.hg',           # Version control
    '__pycache__', '.pytest_cache',  # Python cache
    'node_modules', '.npm',          # Node.js
    '.venv', 'venv', 'env',          # Virtual environments
    '.idea', '.vscode',              # IDE folders
    '.DS_Store', 'Thumbs.db',        # System files
}


class FileOrganizer:
    """Organizes files in a directory by their extensions."""

    def __init__(self, source_dir: Path = None, dry_run: bool = False, log_to_file: bool = False, recursive: bool = False, max_depth: int = None, manifest_dir: Path = None):
        self.source_dir = Path(source_dir) if source_dir else None
        self.dry_run = dry_run
        self.recursive = recursive
        self.max_depth = max_depth
        self.manifest_dir = Path(manifest_dir) if manifest_dir else MANIFESTS_DIR
        self.categories = FILE_ORGANIZER_CONFIG["categories"]
        self.default_category = FILE_ORGANIZER_CONFIG["default_category"]

        log_dir = LOGS_DIR if log_to_file else None
        self.logger = setup_logger("file_organizer", log_dir)

        # Build extension -> category mapping
        self.ext_map = {}
        for category, extensions in self.categories.items():
            for ext in extensions:
                self.ext_map[ext.lower()] = category

        # Track statistics
        self.stats = defaultdict(int)
        self.moved_files = []

    def get_category(self, file_path: Path) -> str:
        """Determine the category for a file based on its extension."""
        ext = file_path.suffix.lower()
        return self.ext_map.get(ext, self.default_category)

    def _get_depth(self, path: Path) -> int:
        """Calculate depth of path relative to source directory.

        Args:
            path: Path to calculate depth for.

        Returns:
            Depth level (0 = direct child of source_dir).
        """
        try:
            relative = path.relative_to(self.source_dir)
            return len(relative.parts) - 1
        except ValueError:
            return 0

    def _should_skip_path(self, path: Path, visited: set = None) -> bool:
        """Check if a path should be skipped during traversal.

        Args:
            path: Path to check.
            visited: Set of already visited real paths (for symlink loop detection).

        Returns:
            True if path should be skipped.
        """
        # Skip symlinks to avoid loops and unexpected behavior
        if path.is_symlink():
            return True
        # Skip hidden files/directories (any part starting with .)
        for part in path.parts:
            if part.startswith('.'):
                return True
            # Also check excluded directories
            if part in EXCLUDED_DIRS:
                return True
        # Symlink loop detection
        if visited is not None:
            try:
                real_path = path.resolve()
                if real_path in visited:
                    return True
                visited.add(real_path)
            except OSError:
                return True
        return False

    def _collect_files(self) -> list:
        """Collect files to organize based on recursive setting.

        Returns:
            List of Path objects for files to process.
        """
        files = []
        visited = set()  # Track visited paths for symlink loop detection
        if self.recursive:
            # Recursive: traverse all subdirectories
            for item in self.source_dir.rglob('*'):
                if not item.is_file():
                    continue
                if self._should_skip_path(item, visited):
                    continue
                # Check max depth limit
                if self.max_depth is not None:
                    depth = self._get_depth(item)
                    if depth > self.max_depth:
                        continue
                files.append(item)
        else:
            # Non-recursive: only immediate children
            for item in self.source_dir.iterdir():
                if item.is_file() and not self._should_skip_path(item, visited):
                    files.append(item)
        return files

    def organize(self) -> dict:
        """
        Organize all files in the source directory.

        Returns:
            Dictionary with statistics about the operation.
        """
        if not self.source_dir.exists():
            self.logger.error(f"Directory does not exist: {self.source_dir}")
            return {"error": "Directory not found"}

        if not self.source_dir.is_dir():
            self.logger.error(f"Path is not a directory: {self.source_dir}")
            return {"error": "Not a directory"}

        mode = "DRY RUN" if self.dry_run else "LIVE"
        recursive_note = " [RECURSIVE]" if self.recursive else ""
        self.logger.info(f"Starting file organization [{mode}]{recursive_note}: {self.source_dir}")

        # Collect and process files
        files = self._collect_files()
        for file_path in files:
            self._process_file(file_path)

        self._print_summary()
        return dict(self.stats)

    def _process_file(self, file_path: Path) -> None:
        """Process a single file."""
        category = self.get_category(file_path)
        dest_dir = self.source_dir / category
        dest_path = dest_dir / file_path.name

        # Handle name collisions
        if dest_path.exists():
            dest_path = get_unique_path(dest_path)

        self.logger.info(f"  {file_path.name} -> {category}/")

        if not self.dry_run:
            ensure_dir(dest_dir)
            shutil.move(str(file_path), str(dest_path))

        self.stats[category] += 1
        self.moved_files.append({
            "source": str(file_path),
            "destination": str(dest_path),
            "category": category,
        })

    def _print_summary(self) -> None:
        """Print a summary of the organization operation."""
        total = sum(self.stats.values())
        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"Summary {'(DRY RUN)' if self.dry_run else ''}")
        self.logger.info(f"{'='*50}")

        for category, count in sorted(self.stats.items()):
            self.logger.info(f"  {category}: {count} files")

        self.logger.info(f"{'='*50}")
        self.logger.info(f"Total: {total} files {'would be ' if self.dry_run else ''}organized")

    def _save_manifest(self) -> Path:
        """Save a manifest file recording the organization operation.

        The manifest contains all file moves for later undo/rollback.
        Only saves if there were actual file moves (not dry-run).

        Returns:
            Path to the saved manifest file, or None if nothing to save.
        """
        if self.dry_run or not self.moved_files:
            return None

        # Ensure manifest directory exists
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        manifest_path = self.manifest_dir / f"organize_{timestamp}.json"

        manifest_data = {
            "timestamp": datetime.now().isoformat(),
            "source_dir": str(self.source_dir),
            "recursive": self.recursive,
            "max_depth": self.max_depth,
            "files_moved": len(self.moved_files),
            "moves": self.moved_files,
        }

        with open(manifest_path, 'w') as f:
            json.dump(manifest_data, f, indent=2)

        self.logger.info(f"Manifest saved: {manifest_path.name}")
        return manifest_path

    def get_report(self) -> str:
        """Generate a detailed report of the operation."""
        lines = [
            f"File Organization Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Source: {self.source_dir}",
            f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}",
            "",
            "Files Processed:",
            "-" * 60,
        ]

        for file_info in self.moved_files:
            lines.append(f"  {Path(file_info['source']).name} -> {file_info['category']}/")

        lines.extend([
            "",
            "Statistics:",
            "-" * 60,
        ])

        for category, count in sorted(self.stats.items()):
            lines.append(f"  {category}: {count}")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Organize files in a directory by their type",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ~/Downloads                    # Organize Downloads folder
  %(prog)s ~/Downloads --dry-run          # Preview changes without moving files
  %(prog)s ~/Downloads --dry-run --log    # Preview and save log to file
  %(prog)s ~/Downloads --recursive        # Organize including subdirectories
  %(prog)s ~/Downloads -r --max-depth 2   # Recursive with depth limit
        """
    )

    parser.add_argument(
        "directory",
        type=Path,
        help="Directory to organize"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be done without actually moving files"
    )
    parser.add_argument(
        "--log", "-l",
        action="store_true",
        help="Save operation log to file"
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="Recursively organize files in subdirectories"
    )
    parser.add_argument(
        "--max-depth", "-d",
        type=int,
        default=None,
        help="Maximum directory depth for recursive traversal"
    )

    args = parser.parse_args()

    organizer = FileOrganizer(
        source_dir=args.directory,
        dry_run=args.dry_run,
        log_to_file=args.log,
        recursive=args.recursive,
        max_depth=args.max_depth
    )

    organizer.organize()


if __name__ == "__main__":
    main()
