"""Tests for CSV Reporter advanced statistics functionality."""
import csv
import tempfile
from pathlib import Path
import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from projects.csv_reporter.reporter import CSVReporter


@pytest.fixture
def temp_csv_with_numbers():
    """Create a temporary CSV file with numeric data for testing statistics."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["id", "category", "amount", "quantity"])
        # 10 rows of data for meaningful statistics
        writer.writerow(["1", "A", "100", "5"])
        writer.writerow(["2", "A", "200", "10"])
        writer.writerow(["3", "A", "150", "7"])
        writer.writerow(["4", "B", "300", "15"])
        writer.writerow(["5", "B", "250", "12"])
        writer.writerow(["6", "B", "180", "8"])
        writer.writerow(["7", "C", "400", "20"])
        writer.writerow(["8", "C", "350", "18"])
        writer.writerow(["9", "C", "275", "13"])
        writer.writerow(["10", "C", "225", "11"])
        temp_path = Path(f.name)

    yield temp_path
    temp_path.unlink()


@pytest.fixture
def temp_csv_small():
    """Create a small CSV with only 2 rows for edge case testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["id", "value"])
        writer.writerow(["1", "100"])
        writer.writerow(["2", "200"])
        temp_path = Path(f.name)

    yield temp_path
    temp_path.unlink()


class TestComputeAdvancedStats:
    """Tests for the _compute_advanced_stats helper method."""

    def test_median_calculation(self, temp_csv_with_numbers):
        """Test median is correctly calculated."""
        reporter = CSVReporter([str(temp_csv_with_numbers)])
        reporter.load()

        values = [100, 200, 300, 400, 500]
        stats = reporter._compute_advanced_stats(values)
        assert stats["median"] == 300

    def test_stdev_calculation(self, temp_csv_with_numbers):
        """Test standard deviation is correctly calculated."""
        reporter = CSVReporter([str(temp_csv_with_numbers)])
        reporter.load()

        values = [10, 20, 30, 40, 50]
        stats = reporter._compute_advanced_stats(values)
        # Sample standard deviation of [10,20,30,40,50] is ~15.81
        assert 15 < stats["stdev"] < 16

    def test_variance_calculation(self, temp_csv_with_numbers):
        """Test variance is correctly calculated."""
        reporter = CSVReporter([str(temp_csv_with_numbers)])
        reporter.load()

        values = [10, 20, 30, 40, 50]
        stats = reporter._compute_advanced_stats(values)
        # Variance should be stdev squared
        assert 200 < stats["variance"] < 260

    def test_percentiles_calculation(self, temp_csv_with_numbers):
        """Test percentiles are correctly calculated."""
        reporter = CSVReporter([str(temp_csv_with_numbers)])
        reporter.load()

        values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        stats = reporter._compute_advanced_stats(values)
        # P25 should be around 25-30, P50 around 55, P75 around 75-80
        assert stats["p25"] < stats["p50"] < stats["p75"]

    def test_empty_values_returns_empty_dict(self, temp_csv_with_numbers):
        """Test empty values list returns empty dict."""
        reporter = CSVReporter([str(temp_csv_with_numbers)])
        reporter.load()

        stats = reporter._compute_advanced_stats([])
        assert stats == {}

    def test_single_value_handles_stdev(self, temp_csv_with_numbers):
        """Test single value handles stdev gracefully."""
        reporter = CSVReporter([str(temp_csv_with_numbers)])
        reporter.load()

        stats = reporter._compute_advanced_stats([100])
        assert stats["median"] == 100
        assert stats["stdev"] == 0.0
        assert stats["variance"] == 0.0

    def test_small_dataset_percentiles(self, temp_csv_small):
        """Test small datasets use median for percentiles."""
        reporter = CSVReporter([str(temp_csv_small)])
        reporter.load()

        values = [100, 200]
        stats = reporter._compute_advanced_stats(values)
        # With only 2 values, percentiles fall back to median
        assert stats["p25"] == stats["median"]
        assert stats["p50"] == stats["median"]
        assert stats["p75"] == stats["median"]


class TestConfigureStats:
    """Tests for the configure_stats method."""

    def test_full_stats_mode(self, temp_csv_with_numbers):
        """Test full_stats mode enables all statistics."""
        reporter = CSVReporter([str(temp_csv_with_numbers)])
        reporter.configure_stats(full_stats=True)
        assert reporter.full_stats is True
        assert reporter.selected_stats is None

    def test_selective_stats_valid(self, temp_csv_with_numbers):
        """Test selective stats with valid stat names."""
        reporter = CSVReporter([str(temp_csv_with_numbers)])
        reporter.configure_stats(stats_list="median,stdev,p75")
        assert reporter.selected_stats == ["median", "stdev", "p75"]

    def test_selective_stats_invalid_ignored(self, temp_csv_with_numbers):
        """Test invalid stat names are ignored."""
        reporter = CSVReporter([str(temp_csv_with_numbers)])
        reporter.configure_stats(stats_list="median,invalid,p75")
        assert "median" in reporter.selected_stats
        assert "p75" in reporter.selected_stats
        assert "invalid" not in reporter.selected_stats

    def test_all_invalid_stats_results_in_none(self, temp_csv_with_numbers):
        """Test all invalid stats result in None."""
        reporter = CSVReporter([str(temp_csv_with_numbers)])
        reporter.configure_stats(stats_list="invalid1,invalid2")
        assert reporter.selected_stats is None

    def test_case_insensitive_stat_names(self, temp_csv_with_numbers):
        """Test stat names are case insensitive."""
        reporter = CSVReporter([str(temp_csv_with_numbers)])
        reporter.configure_stats(stats_list="MEDIAN,StDev,P75")
        assert "median" in reporter.selected_stats
        assert "stdev" in reporter.selected_stats
        assert "p75" in reporter.selected_stats


class TestReportWithStats:
    """Tests for report generation with advanced statistics."""

    def test_report_without_stats_excludes_advanced(self, temp_csv_with_numbers):
        """Test default report excludes advanced statistics."""
        reporter = CSVReporter([str(temp_csv_with_numbers)])
        reporter.load()
        report = reporter.generate_report()
        assert "Median:" not in report
        assert "Std Dev:" not in report
        assert "Variance:" not in report
        assert "P25:" not in report

    def test_report_full_stats_includes_all(self, temp_csv_with_numbers):
        """Test full stats mode includes all advanced statistics."""
        reporter = CSVReporter([str(temp_csv_with_numbers)])
        reporter.load()
        reporter.configure_stats(full_stats=True)
        report = reporter.generate_report()
        assert "Median:" in report
        assert "Std Dev:" in report
        assert "Variance:" in report
        assert "P25:" in report
        assert "P50:" in report
        assert "P75:" in report

    def test_report_selective_stats(self, temp_csv_with_numbers):
        """Test selective stats only includes requested statistics."""
        reporter = CSVReporter([str(temp_csv_with_numbers)])
        reporter.load()
        reporter.configure_stats(stats_list="median,p75")
        report = reporter.generate_report()
        assert "Median:" in report
        assert "P75:" in report
        assert "Std Dev:" not in report
        assert "Variance:" not in report

    def test_report_basic_stats_always_present(self, temp_csv_with_numbers):
        """Test basic stats (Total, Average, Min, Max, Count) always present."""
        reporter = CSVReporter([str(temp_csv_with_numbers)])
        reporter.load()
        reporter.configure_stats(full_stats=True)
        report = reporter.generate_report()
        assert "Total:" in report
        assert "Average:" in report
        assert "Min:" in report
        assert "Max:" in report
        assert "Count:" in report


class TestAvailableStats:
    """Tests for AVAILABLE_STATS constant."""

    def test_available_stats_defined(self):
        """Test all expected stats are defined."""
        expected = ["median", "stdev", "variance", "p25", "p50", "p75"]
        for stat in expected:
            assert stat in CSVReporter.AVAILABLE_STATS
