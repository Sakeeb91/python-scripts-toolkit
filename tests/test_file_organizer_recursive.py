"""Tests for File Organizer recursive directory traversal."""
import tempfile
from pathlib import Path
import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from projects.file_organizer.organizer import FileOrganizer, EXCLUDED_DIRS


@pytest.fixture
def temp_nested_dir():
    """Create temporary nested directory structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        # Create nested structure
        # root/
        #   file1.txt
        #   subdir1/
        #     file2.txt
        #     subdir2/
        #       file3.txt
        #       subdir3/
        #         file4.txt

        (base / "file1.txt").write_text("content1")
        (base / "subdir1").mkdir()
        (base / "subdir1" / "file2.txt").write_text("content2")
        (base / "subdir1" / "subdir2").mkdir()
        (base / "subdir1" / "subdir2" / "file3.txt").write_text("content3")
        (base / "subdir1" / "subdir2" / "subdir3").mkdir()
        (base / "subdir1" / "subdir2" / "subdir3" / "file4.txt").write_text("content4")

        # Create hidden directory with file
        (base / ".hidden").mkdir()
        (base / ".hidden" / "secret.txt").write_text("hidden content")

        # Create excluded directory with file
        (base / "__pycache__").mkdir()
        (base / "__pycache__" / "cache.pyc").write_text("cache")

        yield base


class TestNonRecursiveMode:
    """Tests for non-recursive (default) mode."""

    def test_only_top_level_files_collected(self, temp_nested_dir):
        """Test that non-recursive mode only collects top-level files."""
        organizer = FileOrganizer(temp_nested_dir, dry_run=True, recursive=False)
        files = organizer._collect_files()
        assert len(files) == 1
        assert files[0].name == "file1.txt"

    def test_subdirectory_files_not_collected(self, temp_nested_dir):
        """Test that files in subdirectories are not collected."""
        organizer = FileOrganizer(temp_nested_dir, dry_run=True, recursive=False)
        files = organizer._collect_files()
        names = [f.name for f in files]
        assert "file2.txt" not in names
        assert "file3.txt" not in names
        assert "file4.txt" not in names


class TestRecursiveMode:
    """Tests for recursive mode."""

    def test_all_nested_files_collected(self, temp_nested_dir):
        """Test that recursive mode collects all nested files."""
        organizer = FileOrganizer(temp_nested_dir, dry_run=True, recursive=True)
        files = organizer._collect_files()
        names = [f.name for f in files]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "file3.txt" in names
        assert "file4.txt" in names
        assert len(files) == 4

    def test_hidden_files_excluded(self, temp_nested_dir):
        """Test that hidden files are excluded in recursive mode."""
        organizer = FileOrganizer(temp_nested_dir, dry_run=True, recursive=True)
        files = organizer._collect_files()
        names = [f.name for f in files]
        assert "secret.txt" not in names

    def test_excluded_dirs_skipped(self, temp_nested_dir):
        """Test that EXCLUDED_DIRS patterns are skipped."""
        organizer = FileOrganizer(temp_nested_dir, dry_run=True, recursive=True)
        files = organizer._collect_files()
        names = [f.name for f in files]
        assert "cache.pyc" not in names


class TestMaxDepth:
    """Tests for max depth limiting."""

    def test_max_depth_zero(self, temp_nested_dir):
        """Test max_depth=0 collects only top-level files."""
        organizer = FileOrganizer(temp_nested_dir, dry_run=True, recursive=True, max_depth=0)
        files = organizer._collect_files()
        names = [f.name for f in files]
        assert "file1.txt" in names
        assert "file2.txt" not in names
        assert len(files) == 1

    def test_max_depth_one(self, temp_nested_dir):
        """Test max_depth=1 collects files up to 1 level deep."""
        organizer = FileOrganizer(temp_nested_dir, dry_run=True, recursive=True, max_depth=1)
        files = organizer._collect_files()
        names = [f.name for f in files]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "file3.txt" not in names
        assert len(files) == 2

    def test_max_depth_two(self, temp_nested_dir):
        """Test max_depth=2 collects files up to 2 levels deep."""
        organizer = FileOrganizer(temp_nested_dir, dry_run=True, recursive=True, max_depth=2)
        files = organizer._collect_files()
        names = [f.name for f in files]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "file3.txt" in names
        assert "file4.txt" not in names
        assert len(files) == 3

    def test_max_depth_none_unlimited(self, temp_nested_dir):
        """Test max_depth=None collects all files."""
        organizer = FileOrganizer(temp_nested_dir, dry_run=True, recursive=True, max_depth=None)
        files = organizer._collect_files()
        assert len(files) == 4


class TestDepthCalculation:
    """Tests for depth calculation helper."""

    def test_depth_top_level(self, temp_nested_dir):
        """Test depth calculation for top-level file."""
        organizer = FileOrganizer(temp_nested_dir, dry_run=True)
        depth = organizer._get_depth(temp_nested_dir / "file1.txt")
        assert depth == 0

    def test_depth_one_level(self, temp_nested_dir):
        """Test depth calculation for 1 level deep."""
        organizer = FileOrganizer(temp_nested_dir, dry_run=True)
        depth = organizer._get_depth(temp_nested_dir / "subdir1" / "file2.txt")
        assert depth == 1

    def test_depth_three_levels(self, temp_nested_dir):
        """Test depth calculation for 3 levels deep."""
        organizer = FileOrganizer(temp_nested_dir, dry_run=True)
        depth = organizer._get_depth(temp_nested_dir / "subdir1" / "subdir2" / "subdir3" / "file4.txt")
        assert depth == 3


class TestSkipPath:
    """Tests for path skipping logic."""

    def test_skip_hidden_file(self, temp_nested_dir):
        """Test that hidden files are skipped."""
        organizer = FileOrganizer(temp_nested_dir, dry_run=True)
        hidden_file = temp_nested_dir / ".hidden" / "secret.txt"
        assert organizer._should_skip_path(hidden_file, set())

    def test_skip_excluded_dir(self, temp_nested_dir):
        """Test that files in excluded directories are skipped."""
        organizer = FileOrganizer(temp_nested_dir, dry_run=True)
        cache_file = temp_nested_dir / "__pycache__" / "cache.pyc"
        assert organizer._should_skip_path(cache_file, set())

    def test_normal_file_not_skipped(self, temp_nested_dir):
        """Test that normal files are not skipped."""
        organizer = FileOrganizer(temp_nested_dir, dry_run=True)
        normal_file = temp_nested_dir / "file1.txt"
        assert not organizer._should_skip_path(normal_file, set())


class TestExcludedDirs:
    """Tests for EXCLUDED_DIRS constant."""

    def test_common_patterns_included(self):
        """Test that common exclusion patterns are defined."""
        assert ".git" in EXCLUDED_DIRS
        assert "__pycache__" in EXCLUDED_DIRS
        assert "node_modules" in EXCLUDED_DIRS
        assert ".venv" in EXCLUDED_DIRS
