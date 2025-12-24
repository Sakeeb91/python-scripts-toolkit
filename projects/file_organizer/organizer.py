"""
Smart File Organizer - Sorts files into subfolders by type.

Usage:
    python -m projects.file_organizer.organizer /path/to/folder
    python -m projects.file_organizer.organizer /path/to/folder --dry-run
    python -m projects.file_organizer.organizer /path/to/folder --log
"""
import argparse
import shutil
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import FILE_ORGANIZER_CONFIG, LOGS_DIR
from utils.logger import setup_logger
from utils.helpers import get_unique_path, ensure_dir


class FileOrganizer:
    """Organizes files in a directory by their extensions."""

    def __init__(self, source_dir: Path, dry_run: bool = False, log_to_file: bool = False, recursive: bool = False):
        self.source_dir = Path(source_dir)
        self.dry_run = dry_run
        self.recursive = recursive
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

    def _collect_files(self) -> list:
        """Collect files to organize based on recursive setting.

        Returns:
            List of Path objects for files to process.
        """
        files = []
        if self.recursive:
            # Recursive: traverse all subdirectories
            for item in self.source_dir.rglob('*'):
                if item.is_file():
                    files.append(item)
        else:
            # Non-recursive: only immediate children
            for item in self.source_dir.iterdir():
                if item.is_file():
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
        self.logger.info(f"Starting file organization [{mode}]: {self.source_dir}")

        # Process each file in the source directory
        for item in self.source_dir.iterdir():
            if item.is_file():
                self._process_file(item)

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

    args = parser.parse_args()

    organizer = FileOrganizer(
        source_dir=args.directory,
        dry_run=args.dry_run,
        log_to_file=args.log
    )

    organizer.organize()


if __name__ == "__main__":
    main()
