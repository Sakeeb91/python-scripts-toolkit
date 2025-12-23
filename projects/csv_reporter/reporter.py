"""
CSV Report Generator - Reads CSV files and generates summary reports.

Usage:
    python -m projects.csv_reporter.reporter input.csv
    python -m projects.csv_reporter.reporter input.csv --output report.txt
    python -m projects.csv_reporter.reporter input.csv --filter-column category --filter-value "Food"
    python -m projects.csv_reporter.reporter input.csv --date-from 2024-01-01 --date-to 2024-12-31
"""
import argparse
import csv
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Optional, List, Dict, Any
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import CSV_REPORTER_CONFIG, DATA_DIR
from utils.logger import setup_logger
from utils.helpers import parse_date


class CSVReporter:
    """Generates reports from CSV data with aggregation and filtering."""

    def __init__(self, input_path: Path):
        self.input_path = Path(input_path)
        self.logger = setup_logger("csv_reporter")
        self.data: List[Dict[str, Any]] = []
        self.headers: List[str] = []
        self.numeric_columns: List[str] = []
        self.date_column: Optional[str] = None
        self.category_column: Optional[str] = None

    def load(self) -> bool:
        """Load and parse the CSV file."""
        if not self.input_path.exists():
            self.logger.error(f"File not found: {self.input_path}")
            return False

        try:
            with open(self.input_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.headers = reader.fieldnames or []
                self.data = list(reader)

            self._detect_column_types()
            self.logger.info(f"Loaded {len(self.data)} rows from {self.input_path.name}")
            return True

        except Exception as e:
            self.logger.error(f"Error reading CSV: {e}")
            return False

    def _detect_column_types(self) -> None:
        """Auto-detect column types for aggregation."""
        # Detect date column
        for col in CSV_REPORTER_CONFIG["date_columns"]:
            if col in self.headers:
                self.date_column = col
                break

        # Detect numeric columns
        for col in self.headers:
            if self._is_numeric_column(col):
                self.numeric_columns.append(col)

        # Detect category column
        for col in CSV_REPORTER_CONFIG["category_columns"]:
            if col in self.headers:
                self.category_column = col
                break

    def _is_numeric_column(self, column: str) -> bool:
        """Check if a column contains numeric data."""
        sample = [row.get(column, "") for row in self.data[:10]]
        try:
            for val in sample:
                if val.strip():
                    float(val.replace(",", "").replace("$", ""))
            return True
        except ValueError:
            return False

    def _parse_numeric(self, value: str) -> float:
        """Parse a numeric string, handling currency and commas."""
        if not value or not value.strip():
            return 0.0
        cleaned = value.replace(",", "").replace("$", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def filter_data(
        self,
        filter_column: Optional[str] = None,
        filter_value: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Filter data based on criteria."""
        filtered = self.data.copy()

        # Filter by column value
        if filter_column and filter_value:
            filtered = [
                row for row in filtered
                if row.get(filter_column, "").lower() == filter_value.lower()
            ]

        # Filter by date range
        if self.date_column and (date_from or date_to):
            date_filtered = []
            from_date = parse_date(date_from) if date_from else None
            to_date = parse_date(date_to) if date_to else None

            for row in filtered:
                try:
                    row_date = parse_date(row.get(self.date_column, ""))
                    if from_date and row_date < from_date:
                        continue
                    if to_date and row_date > to_date:
                        continue
                    date_filtered.append(row)
                except ValueError:
                    continue

            filtered = date_filtered

        return filtered

    def generate_report(
        self,
        data: Optional[List[Dict[str, Any]]] = None,
        group_by: Optional[str] = None
    ) -> str:
        """Generate a summary report."""
        data = data or self.data

        lines = [
            "=" * 60,
            f"CSV REPORT: {self.input_path.name}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            "",
            f"Total Rows: {len(data)}",
            f"Columns: {', '.join(self.headers)}",
            "",
        ]

        # Numeric summaries
        if self.numeric_columns:
            lines.append("-" * 40)
            lines.append("NUMERIC SUMMARIES")
            lines.append("-" * 40)

            for col in self.numeric_columns:
                values = [self._parse_numeric(row.get(col, "")) for row in data]
                if values:
                    lines.append(f"\n{col}:")
                    lines.append(f"  Total:   {sum(values):,.2f}")
                    lines.append(f"  Average: {sum(values)/len(values):,.2f}")
                    lines.append(f"  Min:     {min(values):,.2f}")
                    lines.append(f"  Max:     {max(values):,.2f}")
                    lines.append(f"  Count:   {len([v for v in values if v != 0])}")

        # Group by analysis
        if group_by and group_by in self.headers:
            lines.append("")
            lines.append("-" * 40)
            lines.append(f"GROUPED BY: {group_by}")
            lines.append("-" * 40)

            groups = defaultdict(list)
            for row in data:
                key = row.get(group_by, "Unknown")
                groups[key].append(row)

            for group_name, group_data in sorted(groups.items()):
                lines.append(f"\n{group_name}: {len(group_data)} items")

                for col in self.numeric_columns:
                    values = [self._parse_numeric(row.get(col, "")) for row in group_data]
                    if values:
                        lines.append(f"  {col} total: {sum(values):,.2f}")

        # Category breakdown (if detected)
        elif self.category_column:
            lines.append("")
            lines.append("-" * 40)
            lines.append(f"BY {self.category_column.upper()}")
            lines.append("-" * 40)

            categories = defaultdict(int)
            category_sums = defaultdict(lambda: defaultdict(float))

            for row in data:
                cat = row.get(self.category_column, "Unknown")
                categories[cat] += 1
                for col in self.numeric_columns:
                    category_sums[cat][col] += self._parse_numeric(row.get(col, ""))

            for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
                lines.append(f"\n{cat}: {count} items")
                for col, total in category_sums[cat].items():
                    lines.append(f"  {col}: {total:,.2f}")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    def export_summary_csv(self, output_path: Path, group_by: str) -> bool:
        """Export a summary CSV grouped by a column."""
        if group_by not in self.headers:
            self.logger.error(f"Column not found: {group_by}")
            return False

        groups = defaultdict(list)
        for row in self.data:
            key = row.get(group_by, "Unknown")
            groups[key].append(row)

        summary_data = []
        for group_name, group_data in groups.items():
            row = {group_by: group_name, "count": len(group_data)}
            for col in self.numeric_columns:
                values = [self._parse_numeric(r.get(col, "")) for r in group_data]
                row[f"{col}_total"] = sum(values)
                row[f"{col}_avg"] = sum(values) / len(values) if values else 0
            summary_data.append(row)

        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                if summary_data:
                    writer = csv.DictWriter(f, fieldnames=summary_data[0].keys())
                    writer.writeheader()
                    writer.writerows(summary_data)
            self.logger.info(f"Summary exported to: {output_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error writing CSV: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate reports from CSV data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s expenses.csv                              # Basic report
  %(prog)s expenses.csv --output report.txt         # Save to file
  %(prog)s expenses.csv --group-by category         # Group by column
  %(prog)s expenses.csv --filter-column type --filter-value "Food"
  %(prog)s expenses.csv --date-from 2024-01-01 --date-to 2024-06-30
        """
    )

    parser.add_argument("input", type=Path, help="Input CSV file")
    parser.add_argument("--output", "-o", type=Path, help="Output file for report")
    parser.add_argument("--group-by", "-g", help="Column to group by")
    parser.add_argument("--filter-column", "-fc", help="Column to filter on")
    parser.add_argument("--filter-value", "-fv", help="Value to filter for")
    parser.add_argument("--date-from", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--date-to", help="End date (YYYY-MM-DD)")
    parser.add_argument("--export-csv", type=Path, help="Export summary as CSV")

    args = parser.parse_args()

    reporter = CSVReporter(args.input)
    if not reporter.load():
        sys.exit(1)

    # Filter data
    filtered_data = reporter.filter_data(
        filter_column=args.filter_column,
        filter_value=args.filter_value,
        date_from=args.date_from,
        date_to=args.date_to
    )

    # Generate report
    report = reporter.generate_report(filtered_data, group_by=args.group_by)

    # Output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Report saved to: {args.output}")
    else:
        print(report)

    # Export summary CSV
    if args.export_csv and args.group_by:
        reporter.export_summary_csv(args.export_csv, args.group_by)


if __name__ == "__main__":
    main()
