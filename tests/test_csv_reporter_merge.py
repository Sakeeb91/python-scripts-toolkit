"""Tests for CSV Reporter multi-file merge functionality."""
import csv
import tempfile
from pathlib import Path
import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from projects.csv_reporter.reporter import CSVReporter


@pytest.fixture
def temp_csv_files():
    """Create temporary CSV files for testing."""
    files = []
    with tempfile.TemporaryDirectory() as tmpdir:
        # File 1: users
        file1 = Path(tmpdir) / "users.csv"
        with open(file1, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "email"])
            writer.writerow(["1", "Alice", "alice@example.com"])
            writer.writerow(["2", "Bob", "bob@example.com"])
            writer.writerow(["3", "Charlie", "charlie@example.com"])
        files.append(file1)

        # File 2: orders
        file2 = Path(tmpdir) / "orders.csv"
        with open(file2, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["id", "product", "amount"])
            writer.writerow(["1", "Widget", "100"])
            writer.writerow(["2", "Gadget", "200"])
        files.append(file2)

        # File 3: duplicate rows for dedupe testing
        file3 = Path(tmpdir) / "duplicates.csv"
        with open(file3, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name"])
            writer.writerow(["1", "Alice"])
            writer.writerow(["1", "Alice"])  # duplicate
            writer.writerow(["2", "Bob"])
        files.append(file3)

        yield tmpdir, files


class TestAppendMerge:
    """Tests for append merge strategy."""

    def test_single_file_load(self, temp_csv_files):
        """Test loading a single CSV file."""
        tmpdir, files = temp_csv_files
        reporter = CSVReporter([str(files[0])])
        assert reporter.load(merge_strategy="append")
        assert len(reporter.data) == 3
        assert "id" in reporter.headers
        assert "name" in reporter.headers

    def test_append_multiple_files_same_headers(self, temp_csv_files):
        """Test appending files with same headers."""
        tmpdir, _ = temp_csv_files
        # Create two files with same structure
        file1 = Path(tmpdir) / "jan.csv"
        file2 = Path(tmpdir) / "feb.csv"

        with open(file1, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["date", "amount"])
            writer.writerow(["2024-01-01", "100"])

        with open(file2, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["date", "amount"])
            writer.writerow(["2024-02-01", "200"])

        reporter = CSVReporter([str(file1), str(file2)])
        assert reporter.load(merge_strategy="append")
        assert len(reporter.data) == 2
        assert reporter.data[0]["amount"] == "100"
        assert reporter.data[1]["amount"] == "200"

    def test_append_files_different_headers(self, temp_csv_files):
        """Test appending files with different headers unions them."""
        tmpdir, files = temp_csv_files
        reporter = CSVReporter([str(files[0]), str(files[1])])
        assert reporter.load(merge_strategy="append")
        # Should have all unique headers from both files
        assert "name" in reporter.headers
        assert "email" in reporter.headers
        assert "product" in reporter.headers
        assert "amount" in reporter.headers


class TestJoinMerge:
    """Tests for join merge strategy."""

    def test_join_requires_key(self, temp_csv_files):
        """Test that join strategy requires a join key."""
        tmpdir, files = temp_csv_files
        reporter = CSVReporter([str(files[0]), str(files[1])])
        assert not reporter.load(merge_strategy="join")

    def test_join_on_common_key(self, temp_csv_files):
        """Test joining files on a common key."""
        tmpdir, files = temp_csv_files
        reporter = CSVReporter([str(files[0]), str(files[1])])
        assert reporter.load(merge_strategy="join", join_key="id")
        # Should have joined data for id 1 and 2
        assert len(reporter.data) >= 2
        # Check that data from both files is present
        id1_row = next((r for r in reporter.data if r.get("id") == "1"), None)
        assert id1_row is not None
        assert id1_row.get("name") == "Alice"

    def test_join_key_not_in_file(self, temp_csv_files):
        """Test error when join key doesn't exist in a file."""
        tmpdir, files = temp_csv_files
        reporter = CSVReporter([str(files[0]), str(files[1])])
        assert not reporter.load(merge_strategy="join", join_key="nonexistent")


class TestDedupe:
    """Tests for deduplication functionality."""

    def test_dedupe_removes_duplicates(self, temp_csv_files):
        """Test that dedupe flag removes duplicate rows."""
        tmpdir, files = temp_csv_files
        reporter = CSVReporter([str(files[2])])  # duplicates.csv
        assert reporter.load(merge_strategy="append", dedupe=True)
        assert len(reporter.data) == 2  # 3 rows - 1 duplicate = 2

    def test_no_dedupe_keeps_duplicates(self, temp_csv_files):
        """Test that without dedupe, duplicates are kept."""
        tmpdir, files = temp_csv_files
        reporter = CSVReporter([str(files[2])])  # duplicates.csv
        assert reporter.load(merge_strategy="append", dedupe=False)
        assert len(reporter.data) == 3  # All rows including duplicate


class TestGlobPatterns:
    """Tests for glob pattern file resolution."""

    def test_glob_pattern_matches_files(self, temp_csv_files):
        """Test that glob patterns correctly match files."""
        tmpdir, _ = temp_csv_files
        reporter = CSVReporter([f"{tmpdir}/*.csv"])
        # Should find all CSV files in temp dir
        assert len(reporter.input_paths) >= 3

    def test_no_matching_files(self):
        """Test handling when no files match pattern."""
        reporter = CSVReporter(["nonexistent/*.csv"])
        assert not reporter.load()


class TestReportGeneration:
    """Tests for report generation with merged data."""

    def test_report_shows_all_input_files(self, temp_csv_files):
        """Test that report header shows all input file names."""
        tmpdir, files = temp_csv_files
        reporter = CSVReporter([str(files[0]), str(files[1])])
        reporter.load(merge_strategy="append")
        report = reporter.generate_report()
        assert "users.csv" in report
        assert "orders.csv" in report
