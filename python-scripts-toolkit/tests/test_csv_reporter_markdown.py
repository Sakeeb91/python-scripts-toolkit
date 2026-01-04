"""Tests for CSV Reporter Markdown output format."""
import csv
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


class TestGenerateMarkdownReport:
    """Tests for generate_markdown_report method."""

    def test_markdown_contains_title(self, temp_csv_with_data):
        """Test that Markdown output contains a proper title."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        md_output = reporter.generate_markdown_report()

        assert md_output.startswith("# CSV Report:")

    def test_markdown_contains_metadata(self, temp_csv_with_data):
        """Test that Markdown output contains metadata section."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        md_output = reporter.generate_markdown_report()

        assert "**Generated:**" in md_output
        assert "**Total Rows:**" in md_output
        assert "**Columns:**" in md_output

    def test_markdown_contains_table_headers(self, temp_csv_with_data):
        """Test that Markdown output contains proper table formatting."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        md_output = reporter.generate_markdown_report()

        # Markdown tables use | for columns and --- for header separator
        assert "| Metric | Value |" in md_output
        assert "|--------|-------|" in md_output

    def test_markdown_contains_statistics(self, temp_csv_with_data):
        """Test that Markdown output contains statistics."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        md_output = reporter.generate_markdown_report()

        assert "## Numeric Summaries" in md_output
        assert "| Total |" in md_output
        assert "| Average |" in md_output
        assert "| Min |" in md_output
        assert "| Max |" in md_output

    def test_markdown_with_full_stats(self, temp_csv_with_data):
        """Test Markdown output with advanced statistics enabled."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        reporter.configure_stats(full_stats=True)
        md_output = reporter.generate_markdown_report()

        assert "| Median |" in md_output
        assert "| Std Dev |" in md_output

    def test_markdown_with_group_by(self, temp_csv_with_data):
        """Test Markdown output with group_by parameter."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        md_output = reporter.generate_markdown_report(group_by="category")

        assert "## Grouped Analysis" in md_output
        assert "| Group | Count | Totals |" in md_output
        assert "Electronics" in md_output
        assert "Clothing" in md_output
        assert "Food" in md_output

    def test_markdown_row_count(self, temp_csv_with_data):
        """Test that Markdown contains correct row count."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        md_output = reporter.generate_markdown_report()

        assert "**Total Rows:** 5" in md_output

    def test_markdown_column_sections(self, temp_csv_with_data):
        """Test that Markdown has sections for each numeric column."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        md_output = reporter.generate_markdown_report()

        assert "### amount" in md_output
        assert "### quantity" in md_output


class TestMarkdownFormatDispatch:
    """Tests for Markdown format dispatch via generate_report."""

    def test_dispatch_to_markdown_format(self, temp_csv_with_data):
        """Test that OutputFormat.MARKDOWN dispatches to Markdown generation."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()

        report = reporter.generate_report(output_format=OutputFormat.MARKDOWN)

        # Should be Markdown format
        assert report.startswith("# CSV Report:")
        assert "| Metric | Value |" in report

    def test_markdown_is_different_from_text(self, temp_csv_with_data):
        """Test that Markdown format differs from TEXT format."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()

        text_report = reporter.generate_report(output_format=OutputFormat.TEXT)
        md_report = reporter.generate_report(output_format=OutputFormat.MARKDOWN)

        # They should be different
        assert text_report != md_report
        # Text uses = borders, Markdown uses # headers
        assert "====" in text_report
        assert "# CSV Report" in md_report
