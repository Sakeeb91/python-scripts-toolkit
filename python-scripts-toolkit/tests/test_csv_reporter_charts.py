"""Tests for CSV Reporter chart data preparation functionality."""
import csv
import tempfile
from pathlib import Path
import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from projects.csv_reporter.reporter import CSVReporter, HAS_MATPLOTLIB


@pytest.fixture
def temp_csv_with_categories():
    """Create a temporary CSV file with category and numeric data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["id", "category", "amount", "quantity"])
        writer.writerow(["1", "Food", "100", "5"])
        writer.writerow(["2", "Food", "150", "8"])
        writer.writerow(["3", "Transport", "200", "2"])
        writer.writerow(["4", "Transport", "75", "3"])
        writer.writerow(["5", "Entertainment", "300", "10"])
        writer.writerow(["6", "Entertainment", "125", "4"])
        writer.writerow(["7", "Utilities", "180", "1"])
        temp_path = Path(f.name)

    yield temp_path
    temp_path.unlink()


@pytest.fixture
def temp_csv_no_numeric():
    """Create a temporary CSV file with no numeric columns."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["name", "category", "status"])
        writer.writerow(["Item A", "Type 1", "Active"])
        writer.writerow(["Item B", "Type 2", "Inactive"])
        temp_path = Path(f.name)

    yield temp_path
    temp_path.unlink()


class TestPrepareChartData:
    """Tests for the _prepare_chart_data helper method."""

    def test_prepare_data_with_group_by(self, temp_csv_with_categories):
        """Test data preparation with explicit group_by column."""
        reporter = CSVReporter([str(temp_csv_with_categories)])
        reporter.load()

        labels, values, title = reporter._prepare_chart_data(
            reporter.data,
            group_by="category",
            value_column="amount"
        )

        assert len(labels) == 4  # Food, Transport, Entertainment, Utilities
        assert len(values) == 4
        assert "amount" in title
        assert "category" in title

    def test_prepare_data_aggregates_correctly(self, temp_csv_with_categories):
        """Test that values are correctly aggregated by group."""
        reporter = CSVReporter([str(temp_csv_with_categories)])
        reporter.load()

        labels, values, title = reporter._prepare_chart_data(
            reporter.data,
            group_by="category",
            value_column="amount"
        )

        # Create a dict for easy lookup
        data_dict = dict(zip(labels, values))

        assert data_dict["Food"] == 250  # 100 + 150
        assert data_dict["Transport"] == 275  # 200 + 75
        assert data_dict["Entertainment"] == 425  # 300 + 125
        assert data_dict["Utilities"] == 180

    def test_prepare_data_sorted_by_value_descending(self, temp_csv_with_categories):
        """Test that results are sorted by value in descending order."""
        reporter = CSVReporter([str(temp_csv_with_categories)])
        reporter.load()

        labels, values, title = reporter._prepare_chart_data(
            reporter.data,
            group_by="category",
            value_column="amount"
        )

        # Values should be in descending order
        assert values == sorted(values, reverse=True)
        # Entertainment should be first (highest: 425)
        assert labels[0] == "Entertainment"

    def test_prepare_data_auto_detects_columns(self, temp_csv_with_categories):
        """Test automatic column detection when not specified."""
        reporter = CSVReporter([str(temp_csv_with_categories)])
        reporter.load()

        # Don't specify group_by or value_column
        labels, values, title = reporter._prepare_chart_data(reporter.data)

        # Should still return valid data
        assert len(labels) > 0
        assert len(values) > 0
        assert title != "No data available for chart"

    def test_prepare_data_no_numeric_columns(self, temp_csv_no_numeric):
        """Test handling when no numeric columns exist."""
        reporter = CSVReporter([str(temp_csv_no_numeric)])
        reporter.load()

        labels, values, title = reporter._prepare_chart_data(reporter.data)

        # Should return empty data with appropriate message
        assert labels == []
        assert values == []
        assert "No data" in title

    def test_prepare_data_empty_data(self, temp_csv_with_categories):
        """Test handling of empty data."""
        reporter = CSVReporter([str(temp_csv_with_categories)])
        reporter.load()

        labels, values, title = reporter._prepare_chart_data([])

        assert labels == []
        assert values == []


class TestChartConstants:
    """Tests for chart-related class constants."""

    def test_chart_types_defined(self):
        """Test all expected chart types are defined."""
        expected_types = ["bar", "hbar", "pie", "line"]
        for chart_type in expected_types:
            assert chart_type in CSVReporter.CHART_TYPES

    def test_chart_formats_defined(self):
        """Test supported output formats are defined."""
        expected_formats = ['.png', '.pdf', '.svg']
        for fmt in expected_formats:
            assert fmt in CSVReporter.CHART_FORMATS

    def test_chart_defaults_has_required_keys(self):
        """Test chart defaults contain necessary styling keys."""
        required_keys = ["figsize", "dpi", "bar_color", "pie_cmap", "line_color"]
        for key in required_keys:
            assert key in CSVReporter.CHART_DEFAULTS


@pytest.mark.skipif(not HAS_MATPLOTLIB, reason="matplotlib not installed")
class TestGenerateChart:
    """Tests for chart generation methods (requires matplotlib)."""

    def test_generate_bar_chart(self, temp_csv_with_categories, tmp_path):
        """Test bar chart generation."""
        reporter = CSVReporter([str(temp_csv_with_categories)])
        reporter.load()

        output_path = tmp_path / "test_bar.png"
        result = reporter.generate_chart(
            chart_type="bar",
            output_path=output_path,
            group_by="category"
        )

        assert result is not None
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_generate_horizontal_bar_chart(self, temp_csv_with_categories, tmp_path):
        """Test horizontal bar chart generation."""
        reporter = CSVReporter([str(temp_csv_with_categories)])
        reporter.load()

        output_path = tmp_path / "test_hbar.png"
        result = reporter.generate_chart(
            chart_type="hbar",
            output_path=output_path,
            group_by="category"
        )

        assert result is not None
        assert output_path.exists()

    def test_generate_pie_chart(self, temp_csv_with_categories, tmp_path):
        """Test pie chart generation."""
        reporter = CSVReporter([str(temp_csv_with_categories)])
        reporter.load()

        output_path = tmp_path / "test_pie.png"
        result = reporter.generate_chart(
            chart_type="pie",
            output_path=output_path,
            group_by="category"
        )

        assert result is not None
        assert output_path.exists()

    def test_generate_line_chart(self, temp_csv_with_categories, tmp_path):
        """Test line chart generation."""
        reporter = CSVReporter([str(temp_csv_with_categories)])
        reporter.load()

        output_path = tmp_path / "test_line.png"
        result = reporter.generate_chart(
            chart_type="line",
            output_path=output_path,
            group_by="category"
        )

        assert result is not None
        assert output_path.exists()

    def test_generate_chart_auto_filename(self, temp_csv_with_categories, tmp_path, monkeypatch):
        """Test automatic filename generation."""
        # Change to tmp_path so chart is created there
        monkeypatch.chdir(tmp_path)

        reporter = CSVReporter([str(temp_csv_with_categories)])
        reporter.load()

        result = reporter.generate_chart(chart_type="bar", group_by="category")

        assert result is not None
        assert result.exists()
        assert "bar_chart" in str(result)

    def test_generate_chart_invalid_type(self, temp_csv_with_categories):
        """Test error handling for invalid chart type."""
        reporter = CSVReporter([str(temp_csv_with_categories)])
        reporter.load()

        result = reporter.generate_chart(chart_type="invalid")

        assert result is None

    def test_generate_chart_pdf_format(self, temp_csv_with_categories, tmp_path):
        """Test PDF output format."""
        reporter = CSVReporter([str(temp_csv_with_categories)])
        reporter.load()

        output_path = tmp_path / "test_chart.pdf"
        result = reporter.generate_chart(
            chart_type="bar",
            output_path=output_path,
            group_by="category"
        )

        assert result is not None
        assert output_path.exists()
        assert output_path.suffix == ".pdf"

    def test_generate_chart_svg_format(self, temp_csv_with_categories, tmp_path):
        """Test SVG output format."""
        reporter = CSVReporter([str(temp_csv_with_categories)])
        reporter.load()

        output_path = tmp_path / "test_chart.svg"
        result = reporter.generate_chart(
            chart_type="bar",
            output_path=output_path,
            group_by="category"
        )

        assert result is not None
        assert output_path.exists()
        assert output_path.suffix == ".svg"

    def test_generate_chart_with_filtered_data(self, temp_csv_with_categories, tmp_path):
        """Test chart generation with filtered data."""
        reporter = CSVReporter([str(temp_csv_with_categories)])
        reporter.load()

        filtered = reporter.filter_data(filter_column="category", filter_value="Food")
        output_path = tmp_path / "test_filtered.png"

        result = reporter.generate_chart(
            data=filtered,
            chart_type="bar",
            output_path=output_path
        )

        assert result is not None
        assert output_path.exists()


class TestChartWithoutMatplotlib:
    """Tests for graceful handling when matplotlib is not installed."""

    def test_has_matplotlib_flag_defined(self):
        """Test HAS_MATPLOTLIB flag is defined."""
        from projects.csv_reporter.reporter import HAS_MATPLOTLIB
        assert isinstance(HAS_MATPLOTLIB, bool)
