"""Tests for File Organizer size-based filtering."""
import tempfile
from pathlib import Path
import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from projects.file_organizer.organizer import FileOrganizer
from utils.helpers import parse_size


class TestParseSize:
    """Tests for parse_size helper function."""

    def test_parse_bytes(self):
        """Test parsing plain bytes."""
        assert parse_size("100") == 100
        assert parse_size("100B") == 100
        assert parse_size("100b") == 100

    def test_parse_kilobytes(self):
        """Test parsing kilobytes."""
        assert parse_size("1KB") == 1024
        assert parse_size("1kb") == 1024
        assert parse_size("10KB") == 10240

    def test_parse_megabytes(self):
        """Test parsing megabytes."""
        assert parse_size("1MB") == 1024 * 1024
        assert parse_size("10MB") == 10 * 1024 * 1024

    def test_parse_gigabytes(self):
        """Test parsing gigabytes."""
        assert parse_size("1GB") == 1024 ** 3
        assert parse_size("2GB") == 2 * 1024 ** 3

    def test_parse_terabytes(self):
        """Test parsing terabytes."""
        assert parse_size("1TB") == 1024 ** 4

    def test_parse_decimal_values(self):
        """Test parsing decimal size values."""
        assert parse_size("1.5KB") == int(1.5 * 1024)
        assert parse_size("2.5MB") == int(2.5 * 1024 * 1024)

    def test_parse_with_whitespace(self):
        """Test parsing with leading/trailing whitespace."""
        assert parse_size("  1KB  ") == 1024
        assert parse_size("10 MB") == 10 * 1024 * 1024

    def test_invalid_format_raises(self):
        """Test that invalid formats raise ValueError."""
        with pytest.raises(ValueError):
            parse_size("invalid")
        with pytest.raises(ValueError):
            parse_size("KB")
        with pytest.raises(ValueError):
            parse_size("-1KB")

    def test_unknown_unit_raises(self):
        """Test that unknown units raise ValueError."""
        with pytest.raises(ValueError):
            parse_size("1XB")


@pytest.fixture
def temp_dir_with_sizes():
    """Create temporary directory with files of various sizes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        # Create files of different sizes
        # tiny.txt: 10 bytes
        (base / "tiny.txt").write_text("0123456789")

        # small.txt: 100 bytes
        (base / "small.txt").write_text("x" * 100)

        # medium.txt: 1000 bytes (approx 1KB)
        (base / "medium.txt").write_text("y" * 1000)

        # large.txt: 10000 bytes (approx 10KB)
        (base / "large.txt").write_text("z" * 10000)

        yield base


class TestMinSizeFilter:
    """Tests for minimum size filtering."""

    def test_no_filter_collects_all(self, temp_dir_with_sizes):
        """Test that no size filter collects all files."""
        organizer = FileOrganizer(temp_dir_with_sizes, dry_run=True)
        files = organizer._collect_files()
        assert len(files) == 4

    def test_min_size_filters_small_files(self, temp_dir_with_sizes):
        """Test that min_size filters out files below threshold."""
        organizer = FileOrganizer(
            temp_dir_with_sizes,
            dry_run=True,
            min_size=500  # 500 bytes
        )
        files = organizer._collect_files()
        names = [f.name for f in files]
        assert "tiny.txt" not in names
        assert "small.txt" not in names
        assert "medium.txt" in names
        assert "large.txt" in names
        assert len(files) == 2
        assert organizer.skipped_by_size == 2

    def test_min_size_exact_threshold(self, temp_dir_with_sizes):
        """Test files exactly at min_size threshold are included."""
        organizer = FileOrganizer(
            temp_dir_with_sizes,
            dry_run=True,
            min_size=100  # Exactly 100 bytes
        )
        files = organizer._collect_files()
        names = [f.name for f in files]
        assert "tiny.txt" not in names
        assert "small.txt" in names  # Exactly 100 bytes
        assert organizer.skipped_by_size == 1


class TestMaxSizeFilter:
    """Tests for maximum size filtering."""

    def test_max_size_filters_large_files(self, temp_dir_with_sizes):
        """Test that max_size filters out files above threshold."""
        organizer = FileOrganizer(
            temp_dir_with_sizes,
            dry_run=True,
            max_size=500  # 500 bytes
        )
        files = organizer._collect_files()
        names = [f.name for f in files]
        assert "tiny.txt" in names
        assert "small.txt" in names
        assert "medium.txt" not in names
        assert "large.txt" not in names
        assert len(files) == 2
        assert organizer.skipped_by_size == 2

    def test_max_size_exact_threshold(self, temp_dir_with_sizes):
        """Test files exactly at max_size threshold are included."""
        organizer = FileOrganizer(
            temp_dir_with_sizes,
            dry_run=True,
            max_size=100  # Exactly 100 bytes
        )
        files = organizer._collect_files()
        names = [f.name for f in files]
        assert "tiny.txt" in names
        assert "small.txt" in names  # Exactly 100 bytes
        assert "medium.txt" not in names


class TestCombinedSizeFilters:
    """Tests for combined min and max size filters."""

    def test_min_and_max_size_range(self, temp_dir_with_sizes):
        """Test combined min and max size creates a range filter."""
        organizer = FileOrganizer(
            temp_dir_with_sizes,
            dry_run=True,
            min_size=50,
            max_size=5000
        )
        files = organizer._collect_files()
        names = [f.name for f in files]
        assert "tiny.txt" not in names   # 10 bytes < 50
        assert "small.txt" in names      # 100 bytes
        assert "medium.txt" in names     # 1000 bytes
        assert "large.txt" not in names  # 10000 bytes > 5000
        assert len(files) == 2
        assert organizer.skipped_by_size == 2

    def test_empty_range_collects_nothing(self, temp_dir_with_sizes):
        """Test that an impossible range (min > max) collects no files."""
        organizer = FileOrganizer(
            temp_dir_with_sizes,
            dry_run=True,
            min_size=10000,
            max_size=100
        )
        files = organizer._collect_files()
        assert len(files) == 0
        assert organizer.skipped_by_size == 4


class TestSizeFilterWithRecursive:
    """Tests for size filtering with recursive mode."""

    @pytest.fixture
    def temp_nested_with_sizes(self):
        """Create nested directory structure with various file sizes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Root level
            (base / "root_small.txt").write_text("x" * 50)
            (base / "root_large.txt").write_text("y" * 5000)

            # Subdirectory
            (base / "subdir").mkdir()
            (base / "subdir" / "sub_small.txt").write_text("a" * 50)
            (base / "subdir" / "sub_large.txt").write_text("b" * 5000)

            yield base

    def test_size_filter_applies_to_recursive(self, temp_nested_with_sizes):
        """Test size filter works with recursive mode."""
        organizer = FileOrganizer(
            temp_nested_with_sizes,
            dry_run=True,
            recursive=True,
            min_size=100
        )
        files = organizer._collect_files()
        names = [f.name for f in files]
        assert "root_small.txt" not in names
        assert "root_large.txt" in names
        assert "sub_small.txt" not in names
        assert "sub_large.txt" in names
        assert len(files) == 2
        assert organizer.skipped_by_size == 2


class TestCheckSizeFilter:
    """Tests for _check_size_filter helper method."""

    def test_no_filters_returns_true(self, temp_dir_with_sizes):
        """Test that no filters means all files pass."""
        organizer = FileOrganizer(temp_dir_with_sizes, dry_run=True)
        result = organizer._check_size_filter(temp_dir_with_sizes / "tiny.txt")
        assert result is True

    def test_below_min_returns_false(self, temp_dir_with_sizes):
        """Test that files below min_size return False."""
        organizer = FileOrganizer(
            temp_dir_with_sizes,
            dry_run=True,
            min_size=1000
        )
        result = organizer._check_size_filter(temp_dir_with_sizes / "tiny.txt")
        assert result is False

    def test_above_max_returns_false(self, temp_dir_with_sizes):
        """Test that files above max_size return False."""
        organizer = FileOrganizer(
            temp_dir_with_sizes,
            dry_run=True,
            max_size=50
        )
        result = organizer._check_size_filter(temp_dir_with_sizes / "large.txt")
        assert result is False

    def test_within_range_returns_true(self, temp_dir_with_sizes):
        """Test that files within range return True."""
        organizer = FileOrganizer(
            temp_dir_with_sizes,
            dry_run=True,
            min_size=50,
            max_size=5000
        )
        result = organizer._check_size_filter(temp_dir_with_sizes / "medium.txt")
        assert result is True
