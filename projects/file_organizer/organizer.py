"""
Smart File Organizer - Sorts files into subfolders by type or date.

Usage:
    # Basic organization by file type
    python -m projects.file_organizer.organizer /path/to/folder
    python -m projects.file_organizer.organizer /path/to/folder --dry-run

    # Date-based organization
    python -m projects.file_organizer.organizer ~/Photos --by-date
    python -m projects.file_organizer.organizer ~/Photos --by-date --date-format "YYYY/MM"
    python -m projects.file_organizer.organizer ~/Photos --by-date --date-type created

    # Combined date and type organization
    python -m projects.file_organizer.organizer ~/Downloads --by-date --combine-with-type

    # Size-based filtering
    python -m projects.file_organizer.organizer ~/Downloads --min-size 1KB
    python -m projects.file_organizer.organizer ~/Downloads --max-size 100MB
    python -m projects.file_organizer.organizer ~/Downloads --min-size 1KB --max-size 500MB

    # Undo and history
    python -m projects.file_organizer.organizer --undo
    python -m projects.file_organizer.organizer --list-history
"""
import argparse
import json
import os
import shutil
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import FILE_ORGANIZER_CONFIG, LOGS_DIR, MANIFESTS_DIR
from utils.logger import setup_logger
from utils.helpers import get_unique_path, ensure_dir, parse_size

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
    """Organizes files in a directory by their extensions or dates."""

    def __init__(self, source_dir: Path = None, dry_run: bool = False, log_to_file: bool = False, recursive: bool = False, max_depth: int = None, manifest_dir: Path = None,
                 by_date: bool = False, date_format: str = None, date_type: str = None, combine_with_type: bool = False,
                 min_size: int = None, max_size: int = None):
        self.source_dir = Path(source_dir) if source_dir else None
        self.dry_run = dry_run
        self.recursive = recursive
        self.max_depth = max_depth
        self.manifest_dir = Path(manifest_dir) if manifest_dir else MANIFESTS_DIR
        self.categories = FILE_ORGANIZER_CONFIG["categories"]
        self.default_category = FILE_ORGANIZER_CONFIG["default_category"]

        # Date-based organization settings
        self.by_date = by_date
        self.date_formats = FILE_ORGANIZER_CONFIG.get("date_formats", {})
        self.date_format = date_format or FILE_ORGANIZER_CONFIG.get("default_date_format", "YYYY/Month")
        self.date_type = date_type or FILE_ORGANIZER_CONFIG.get("default_date_type", "modified")
        self.combine_with_type = combine_with_type

        # Size-based filtering settings
        self.min_size = min_size
        self.max_size = max_size

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
        self.skipped_by_size = 0

    def get_category(self, file_path: Path) -> str:
        """Determine the category for a file based on its extension."""
        ext = file_path.suffix.lower()
        return self.ext_map.get(ext, self.default_category)

    def get_file_date(self, file_path: Path) -> datetime:
        """Get the relevant date for a file based on date_type setting.

        Args:
            file_path: Path to the file.

        Returns:
            datetime object for the file's date. Falls back to modification
            time if creation time is unavailable.
        """
        try:
            stat_info = os.stat(file_path)

            if self.date_type == "created":
                # On macOS/Windows, st_birthtime is creation time
                # On Linux, st_ctime is metadata change time (not creation)
                if hasattr(stat_info, 'st_birthtime'):
                    timestamp = stat_info.st_birthtime
                else:
                    # Fall back to modification time on Linux
                    timestamp = stat_info.st_mtime
                    self.logger.debug(f"Creation time unavailable for {file_path.name}, using modification time")
            else:
                # Default to modification time
                timestamp = stat_info.st_mtime

            return datetime.fromtimestamp(timestamp)
        except (OSError, ValueError) as e:
            self.logger.warning(f"Could not get date for {file_path.name}: {e}")
            return datetime.now()

    def get_date_category(self, file_path: Path) -> str:
        """Generate a date-based category path for a file.

        Args:
            file_path: Path to the file.

        Returns:
            A path string based on the file's date (e.g., "2024/January").
        """
        file_date = self.get_file_date(file_path)

        # Get the strftime format string for the selected date format
        strftime_format = self.date_formats.get(self.date_format)
        if not strftime_format:
            # If format not found, use default YYYY/Month
            strftime_format = "%Y/%B"
            self.logger.warning(f"Unknown date format '{self.date_format}', using YYYY/Month")

        return file_date.strftime(strftime_format)

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

    def _check_size_filter(self, file_path: Path) -> bool:
        """Check if a file passes the size filter.

        Args:
            file_path: Path to the file to check.

        Returns:
            True if file passes the filter (should be processed),
            False if file should be skipped.
        """
        if self.min_size is None and self.max_size is None:
            return True

        try:
            file_size = file_path.stat().st_size
        except OSError:
            # If we can't get the file size, skip it
            return False

        if self.min_size is not None and file_size < self.min_size:
            self.logger.debug(f"  Skipping {file_path.name}: size {file_size}B < min {self.min_size}B")
            return False

        if self.max_size is not None and file_size > self.max_size:
            self.logger.debug(f"  Skipping {file_path.name}: size {file_size}B > max {self.max_size}B")
            return False

        return True

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
                # Check size filter
                if not self._check_size_filter(item):
                    self.skipped_by_size += 1
                    continue
                files.append(item)
        else:
            # Non-recursive: only immediate children
            for item in self.source_dir.iterdir():
                if item.is_file() and not self._should_skip_path(item, visited):
                    # Check size filter
                    if not self._check_size_filter(item):
                        self.skipped_by_size += 1
                        continue
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
        self._save_manifest()
        return dict(self.stats)

    def _process_file(self, file_path: Path) -> None:
        """Process a single file based on organization mode."""
        # Determine the destination path based on organization mode
        if self.by_date:
            date_category = self.get_date_category(file_path)
            if self.combine_with_type:
                # Combine date and type: 2024/January/Images/
                type_category = self.get_category(file_path)
                category = f"{date_category}/{type_category}"
            else:
                # Date only: 2024/January/
                category = date_category
        else:
            # Type-based only (original behavior)
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
        if self.skipped_by_size > 0:
            self.logger.info(f"Skipped: {self.skipped_by_size} files (size filter)")

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

    def _load_manifest(self, manifest_path: Path = None) -> dict:
        """Load a manifest file for undo operations.

        Args:
            manifest_path: Specific manifest file to load. If None, loads the
                          most recent manifest from the manifest directory.

        Returns:
            Manifest data dictionary, or None if no manifest found.
        """
        if manifest_path:
            path = Path(manifest_path)
            if not path.exists():
                self.logger.error(f"Manifest not found: {manifest_path}")
                return None
        else:
            # Find most recent manifest
            if not self.manifest_dir.exists():
                self.logger.error("No manifest directory found")
                return None

            manifests = sorted(self.manifest_dir.glob("organize_*.json"), reverse=True)
            if not manifests:
                self.logger.error("No manifests found")
                return None

            path = manifests[0]

        with open(path, 'r') as f:
            data = json.load(f)

        data['_manifest_path'] = str(path)
        return data

    def undo(self, manifest_path: Path = None) -> dict:
        """Undo a previous organization operation by restoring files.

        Args:
            manifest_path: Specific manifest to undo. If None, uses most recent.

        Returns:
            Dictionary with undo statistics, or error info.
        """
        manifest = self._load_manifest(manifest_path)
        if not manifest:
            return {"error": "No manifest found"}

        self.logger.info(f"Undoing organization from: {manifest['timestamp']}")
        self.logger.info(f"Original source: {manifest['source_dir']}")

        restored = 0
        failed = 0
        skipped = 0

        # Process moves in reverse order
        for move in reversed(manifest['moves']):
            dest = Path(move['destination'])
            source = Path(move['source'])

            if not dest.exists():
                self.logger.warning(f"  File not found (skipped): {dest.name}")
                skipped += 1
                continue

            if source.exists():
                self.logger.warning(f"  Original location occupied (skipped): {source.name}")
                skipped += 1
                continue

            try:
                # Ensure source directory exists
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dest), str(source))
                self.logger.info(f"  Restored: {dest.name} -> {source.parent.name}/")
                restored += 1
            except (PermissionError, OSError) as e:
                self.logger.error(f"  Failed to restore {dest.name}: {e}")
                failed += 1

        # Remove empty category directories
        source_dir = Path(manifest['source_dir'])
        for category in set(m['category'] for m in manifest['moves']):
            category_dir = source_dir / category
            if category_dir.exists() and not any(category_dir.iterdir()):
                try:
                    category_dir.rmdir()
                    self.logger.info(f"  Removed empty directory: {category}/")
                except OSError:
                    pass

        # Summary
        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"Undo Summary")
        self.logger.info(f"{'='*50}")
        self.logger.info(f"  Restored: {restored} files")
        if skipped:
            self.logger.info(f"  Skipped: {skipped} files")
        if failed:
            self.logger.info(f"  Failed: {failed} files")

        # Remove manifest after successful undo
        if failed == 0:
            manifest_file = Path(manifest['_manifest_path'])
            if manifest_file.exists():
                manifest_file.unlink()
                self.logger.info(f"  Removed manifest: {manifest_file.name}")

        return {"restored": restored, "skipped": skipped, "failed": failed}

    def list_history(self) -> list:
        """List all available organization manifests.

        Returns:
            List of manifest summaries, sorted by date (newest first).
        """
        if not self.manifest_dir.exists():
            self.logger.info("No organization history found")
            return []

        manifests = sorted(self.manifest_dir.glob("organize_*.json"), reverse=True)
        if not manifests:
            self.logger.info("No organization history found")
            return []

        self.logger.info(f"\n{'='*60}")
        self.logger.info("Organization History")
        self.logger.info(f"{'='*60}")

        history = []
        for i, manifest_path in enumerate(manifests, 1):
            try:
                with open(manifest_path, 'r') as f:
                    data = json.load(f)

                summary = {
                    "index": i,
                    "filename": manifest_path.name,
                    "timestamp": data.get("timestamp", "Unknown"),
                    "source_dir": data.get("source_dir", "Unknown"),
                    "files_moved": data.get("files_moved", len(data.get("moves", []))),
                    "recursive": data.get("recursive", False),
                }
                history.append(summary)

                self.logger.info(f"\n  [{i}] {manifest_path.name}")
                self.logger.info(f"      Timestamp: {summary['timestamp']}")
                self.logger.info(f"      Source: {summary['source_dir']}")
                self.logger.info(f"      Files: {summary['files_moved']}")
                if summary['recursive']:
                    self.logger.info(f"      Mode: Recursive")

            except (json.JSONDecodeError, KeyError) as e:
                self.logger.warning(f"  [{i}] {manifest_path.name} (corrupted)")

        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Total: {len(history)} operation(s) in history")
        self.logger.info("Use --undo to restore the most recent, or --undo --manifest <filename>")

        return history

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
  %(prog)s ~/Downloads                    # Organize by file type
  %(prog)s ~/Downloads --dry-run          # Preview changes without moving
  %(prog)s ~/Downloads --recursive        # Include subdirectories

  # Date-based organization:
  %(prog)s ~/Photos --by-date                        # 2024/January/
  %(prog)s ~/Photos --by-date --date-format YYYY/MM  # 2024/01/
  %(prog)s ~/Photos --by-date --date-type created    # Use creation date
  %(prog)s ~/Photos --by-date --combine-with-type    # 2024/January/Images/

  # Size-based filtering:
  %(prog)s ~/Downloads --min-size 1KB                # Skip tiny files
  %(prog)s ~/Downloads --max-size 100MB              # Skip large files
  %(prog)s ~/Downloads --min-size 1KB --max-size 500MB

  # Undo operations:
  %(prog)s --undo                         # Undo most recent
  %(prog)s --list-history                 # Show all operations
        """
    )

    parser.add_argument(
        "directory",
        type=Path,
        nargs='?',
        default=None,
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
    parser.add_argument(
        "--by-date",
        action="store_true",
        help="Organize files by date instead of type (e.g., 2024/January/)"
    )
    parser.add_argument(
        "--date-format",
        choices=["YYYY/MM", "YYYY/Month", "YYYY-MM-DD", "YYYY/MM/DD"],
        default=None,
        help="Date format for folder names (default: YYYY/Month)"
    )
    parser.add_argument(
        "--date-type",
        choices=["modified", "created"],
        default=None,
        help="Use file modification or creation date (default: modified)"
    )
    parser.add_argument(
        "--combine-with-type",
        action="store_true",
        help="Combine date and type organization (e.g., 2024/January/Images/)"
    )
    parser.add_argument(
        "--undo", "-u",
        action="store_true",
        help="Undo a previous organization operation"
    )
    parser.add_argument(
        "--list-history",
        action="store_true",
        help="List all previous organization operations"
    )
    parser.add_argument(
        "--manifest", "-m",
        type=Path,
        default=None,
        help="Specific manifest file to use for undo"
    )

    args = parser.parse_args()

    # Handle undo and list-history operations (don't require directory)
    if args.list_history:
        organizer = FileOrganizer(log_to_file=args.log)
        organizer.list_history()
        return

    if args.undo:
        organizer = FileOrganizer(log_to_file=args.log)
        organizer.undo(manifest_path=args.manifest)
        return

    # For organize operation, directory is required
    if not args.directory:
        parser.error("directory is required for organize operation")

    organizer = FileOrganizer(
        source_dir=args.directory,
        dry_run=args.dry_run,
        log_to_file=args.log,
        recursive=args.recursive,
        max_depth=args.max_depth,
        by_date=args.by_date,
        date_format=args.date_format,
        date_type=args.date_type,
        combine_with_type=args.combine_with_type
    )

    organizer.organize()


if __name__ == "__main__":
    main()
