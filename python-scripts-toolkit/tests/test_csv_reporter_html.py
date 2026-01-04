"""Tests for CSV Reporter HTML output format."""
import csv
import tempfile
from pathlib import Path
import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from projects.csv_reporter.reporter import CSVReporter, OutputFormat, _escape_html


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


class TestEscapeHtml:
    """Tests for _escape_html helper function."""

    def test_escapes_ampersand(self):
        """Test that & is escaped."""
        assert _escape_html("Fish & Chips") == "Fish &amp; Chips"

    def test_escapes_less_than(self):
        """Test that < is escaped."""
        assert _escape_html("x < y") == "x &lt; y"

    def test_escapes_greater_than(self):
        """Test that > is escaped."""
        assert _escape_html("x > y") == "x &gt; y"

    def test_escapes_double_quote(self):
        """Test that " is escaped."""
        assert _escape_html('say "hello"') == "say &quot;hello&quot;"

    def test_escapes_single_quote(self):
        """Test that ' is escaped."""
        assert _escape_html("it's") == "it&#x27;s"

    def test_escapes_script_tag(self):
        """Test XSS prevention with script tags."""
        malicious = "<script>alert('xss')</script>"
        escaped = _escape_html(malicious)
        assert "<script>" not in escaped
        assert "&lt;script&gt;" in escaped


class TestGenerateHtmlReport:
    """Tests for generate_html_report method."""

    def test_html_is_valid_html5(self, temp_csv_with_data):
        """Test that HTML output has proper HTML5 structure."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        html_output = reporter.generate_html_report()

        assert "<!DOCTYPE html>" in html_output
        assert "<html lang=\"en\">" in html_output
        assert "</html>" in html_output
        assert "<head>" in html_output
        assert "</head>" in html_output
        assert "<body>" in html_output
        assert "</body>" in html_output

    def test_html_contains_title(self, temp_csv_with_data):
        """Test that HTML output contains a title element."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        html_output = reporter.generate_html_report()

        assert "<title>CSV Report:" in html_output
        assert "<h1>CSV Report:" in html_output

    def test_html_contains_metadata(self, temp_csv_with_data):
        """Test that HTML output contains metadata section."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        html_output = reporter.generate_html_report()

        assert "<strong>Generated:</strong>" in html_output
        assert "<strong>Total Rows:</strong>" in html_output
        assert "<strong>Columns:</strong>" in html_output

    def test_html_contains_css_styles(self, temp_csv_with_data):
        """Test that HTML output contains CSS styling."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        html_output = reporter.generate_html_report()

        assert "<style>" in html_output
        assert "</style>" in html_output
        assert "font-family:" in html_output

    def test_html_contains_tables(self, temp_csv_with_data):
        """Test that HTML output contains proper table elements."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        html_output = reporter.generate_html_report()

        assert "<table>" in html_output
        assert "</table>" in html_output
        assert "<tr>" in html_output
        assert "<th>" in html_output
        assert "<td>" in html_output

    def test_html_contains_statistics(self, temp_csv_with_data):
        """Test that HTML output contains statistics."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        html_output = reporter.generate_html_report()

        assert "<h2>Numeric Summaries</h2>" in html_output
        assert ">Total<" in html_output
        assert ">Average<" in html_output
        assert ">Min<" in html_output
        assert ">Max<" in html_output

    def test_html_with_full_stats(self, temp_csv_with_data):
        """Test HTML output with advanced statistics enabled."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        reporter.configure_stats(full_stats=True)
        html_output = reporter.generate_html_report()

        assert ">Median<" in html_output
        assert ">Std Dev<" in html_output

    def test_html_with_group_by(self, temp_csv_with_data):
        """Test HTML output with group_by parameter."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        html_output = reporter.generate_html_report(group_by="category")

        assert "<h2>Grouped Analysis</h2>" in html_output
        assert ">Electronics<" in html_output
        assert ">Clothing<" in html_output
        assert ">Food<" in html_output

    def test_html_responsive_viewport(self, temp_csv_with_data):
        """Test that HTML includes responsive viewport meta tag."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()
        html_output = reporter.generate_html_report()

        assert 'name="viewport"' in html_output
        assert "width=device-width" in html_output


class TestHtmlFormatDispatch:
    """Tests for HTML format dispatch via generate_report."""

    def test_dispatch_to_html_format(self, temp_csv_with_data):
        """Test that OutputFormat.HTML dispatches to HTML generation."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()

        report = reporter.generate_report(output_format=OutputFormat.HTML)

        # Should be HTML format
        assert "<!DOCTYPE html>" in report
        assert "<table>" in report

    def test_html_is_different_from_text(self, temp_csv_with_data):
        """Test that HTML format differs from TEXT format."""
        reporter = CSVReporter([str(temp_csv_with_data)])
        reporter.load()

        text_report = reporter.generate_report(output_format=OutputFormat.TEXT)
        html_report = reporter.generate_report(output_format=OutputFormat.HTML)

        # They should be different
        assert text_report != html_report
        # Text uses = borders, HTML uses tags
        assert "====" in text_report
        assert "<html" in html_report
