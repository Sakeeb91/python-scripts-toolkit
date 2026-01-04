"""Tests for CSV Reporter JSON output format."""
import csv
import json
import tempfile
from pathlib import Path
import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from projects.csv_reporter.reporter import CSVReporter, OutputFormat


@pytest.fixture
def temp_csv_with_data():
    """Create a temporary CSV file with test data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["id", "category", "amount", "quantity"])
        writer.writerow(["1", "Electronics", "100.50", "5"])
        writer.writerow(["2", "Electronics", "200.75", "10"])
        writer.writerow(["3", "Clothing", "50.25", "3"])
        writer.writerow(["4", "Clothing", "75.00", "7"])
        writer.writerow(["5", "Food", "25.99", "15"])
        temp_path = Path(f.name)

    yield temp_path
    temp_path.unlink()


class TestGenerateJsonReport:
    """Tests for generate_json_report method."""

    def test_json_output_is_valid_json(self, temp_csv_with_data):
        """Test that JSON output can be parsed as valid JSON."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        json_output = reporter.generate_json_report()

        # Should not raise an exception
        parsed = json.loads(json_output)
        assert isinstance(parsed, dict)

    def test_json_contains_metadata(self, temp_csv_with_data):
        """Test that JSON output contains metadata section."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        json_output = reporter.generate_json_report()
        parsed = json.loads(json_output)

        assert "metadata" in parsed
        assert "sources" in parsed["metadata"]
        assert "generated_at" in parsed["metadata"]
        assert "total_rows" in parsed["metadata"]
        assert "columns" in parsed["metadata"]

    def test_json_contains_statistics(self, temp_csv_with_data):
        """Test that JSON output contains statistics section."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        json_output = reporter.generate_json_report()
        parsed = json.loads(json_output)

        assert "statistics" in parsed
        # Should have stats for numeric columns
        assert "amount" in parsed["statistics"]
        assert "quantity" in parsed["statistics"]

    def test_json_statistics_values(self, temp_csv_with_data):
        """Test that JSON statistics contain correct values."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        json_output = reporter.generate_json_report()
        parsed = json.loads(json_output)

        amount_stats = parsed["statistics"]["amount"]
        assert "total" in amount_stats
        assert "average" in amount_stats
        assert "min" in amount_stats
        assert "max" in amount_stats
        assert "count" in amount_stats

        # Verify total is correct (100.50 + 200.75 + 50.25 + 75.00 + 25.99)
        assert abs(amount_stats["total"] - 452.49) < 0.01

    def test_json_with_full_stats(self, temp_csv_with_data):
        """Test JSON output with advanced statistics enabled."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        reporter.configure_stats(full_stats=True)
        json_output = reporter.generate_json_report()
        parsed = json.loads(json_output)

        amount_stats = parsed["statistics"]["amount"]
        assert "median" in amount_stats
        assert "stdev" in amount_stats

    def test_json_with_group_by(self, temp_csv_with_data):
        """Test JSON output with group_by parameter."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        json_output = reporter.generate_json_report(group_by="category")
        parsed = json.loads(json_output)

        assert "groups" in parsed
        assert "Electronics" in parsed["groups"]
        assert "Clothing" in parsed["groups"]
        assert "Food" in parsed["groups"]

    def test_json_metadata_row_count(self, temp_csv_with_data):
        """Test that metadata contains correct row count."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        json_output = reporter.generate_json_report()
        parsed = json.loads(json_output)

        assert parsed["metadata"]["total_rows"] == 5


class TestOutputFormatDispatch:
    """Tests for format dispatch via generate_report."""

    def test_dispatch_to_json_format(self, temp_csv_with_data):
        """Test that OutputFormat.JSON dispatches to JSON generation."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()

        report = reporter.generate_report(output_format=OutputFormat.JSON)

        # Should be valid JSON
        parsed = json.loads(report)
        assert "metadata" in parsed
        assert "statistics" in parsed

    def test_default_format_is_text(self, temp_csv_with_data):
        """Test that default format is TEXT (not JSON)."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()

        report = reporter.generate_report()

        # Should be text format, not JSON
        with pytest.raises(json.JSONDecodeError):
            json.loads(report)

        # Should contain text markers
        assert "CSV REPORT" in report
