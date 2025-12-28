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
import statistics
from pathlib import Path
from collections import defaultdict
from glob import glob
from datetime import datetime
from typing import Optional, List, Dict, Any
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import CSV_REPORTER_CONFIG, DATA_DIR
from utils.logger import setup_logger
from utils.helpers import parse_date



EXCEL_EXTENSIONS = {'.xlsx', '.xls', '.xlsm', '.xlsb'}
CSV_EXTENSIONS = {'.csv', '.tsv', '.txt'}

# Check for openpyxl availability
try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


def _get_file_type(path: Path) -> str:
    """Detect file type by extension.

    Returns:
        'excel' for Excel files (.xlsx, .xls, .xlsm, .xlsb)
        'csv' for CSV files (.csv, .tsv, .txt)
        'unknown' for unrecognized extensions
    """
    suffix = path.suffix.lower()
    if suffix in EXCEL_EXTENSIONS:
        return 'excel'
    elif suffix in CSV_EXTENSIONS:
        return 'csv'
    return 'unknown'


class CSVReporter:
    """Generates reports from CSV/Excel data with aggregation and filtering."""

    def __init__(self, input_patterns: List[str]):
        self.input_paths = self._resolve_paths(input_patterns)
        self.logger = setup_logger("csv_reporter")
        self.data: List[Dict[str, Any]] = []
        self.headers: List[str] = []
        self.all_headers: List[str] = [] # FIX: Added to store all unique headers across merged files
        self.numeric_columns: List[str] = []
        self.date_column: Optional[str] = None
        self.category_column: Optional[str] = None
        
    def _resolve_paths(self, patterns: List[str]) -> List[Path]:
        """Resolve glob patterns to existing file paths."""
        seen = set()
        files = []
        for p in patterns:
            # First, try to resolve relative to the current working directory
            for f in glob(p):
                path = Path(f).resolve()
                if path not in seen and path.is_file():
                    seen.add(path)
                    files.append(Path(f))
            # Then, try to resolve relative to DATA_DIR
            for f in glob(str(DATA_DIR / p)):
                path = Path(f).resolve()
                if path not in seen and path.is_file():
                    seen.add(path)
                    files.append(Path(f))
        return files

    def _load_excel(self, path: Path, sheet_name: Optional[str] = None) -> tuple:
        """Load data from an Excel file.

        Args:
            path: Path to the Excel file
            sheet_name: Name of the sheet to load (default: first sheet)

        Returns:
            Tuple of (headers, data) where headers is a list of column names
            and data is a list of dicts representing rows.

        Raises:
            ImportError: If openpyxl is not installed
            ValueError: If the specified sheet doesn't exist
        """
        if not HAS_OPENPYXL:
            raise ImportError(
                f"Excel file support requires openpyxl. Install with:\n"
                f"  pip install openpyxl\n"
                f"Or convert '{path.name}' to CSV format."
            )

        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True, data_only=True)

        # Select the sheet
        if sheet_name:
            if sheet_name not in wb.sheetnames:
                raise ValueError(f"Sheet '{sheet_name}' not found. Available: {', '.join(wb.sheetnames)}")
            ws = wb[sheet_name]
        else:
            ws = wb.active

        # Read headers from first row
        rows = ws.iter_rows(values_only=True)
        try:
            header_row = next(rows)
        except StopIteration:
            return [], []

        headers = [str(h) if h is not None else f"Column_{i}" for i, h in enumerate(header_row)]

        # Read data rows
        data = []
        for row in rows:
            row_dict = {}
            for i, value in enumerate(row):
                if i < len(headers):
                    # Convert None to empty string for consistency with CSV behavior
                    row_dict[headers[i]] = str(value) if value is not None else ""
            data.append(row_dict)

        wb.close()
        return headers, data

    def get_sheet_names(self, path: Path) -> List[str]:
        """Get list of sheet names from an Excel file.

        Args:
            path: Path to the Excel file

        Returns:
            List of sheet names

        Raises:
            ImportError: If openpyxl is not installed
        """
        if not HAS_OPENPYXL:
            raise ImportError(
                f"Excel file support requires openpyxl. Install with:\n"
                f"  pip install openpyxl"
            )

        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True)
        sheet_names = wb.sheetnames
        wb.close()
        return sheet_names

    def _load_single_file(self, path: Path, sheet_name: Optional[str] = None) -> tuple:
        """Load a single file (CSV or Excel) and return headers and data.

        Args:
            path: Path to the file
            sheet_name: Sheet name for Excel files (ignored for CSV)

        Returns:
            Tuple of (headers, data)
        """
        file_type = _get_file_type(path)

        if file_type == 'excel':
            return self._load_excel(path, sheet_name)
        else:
            # Default to CSV loading
            with open(path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = list(reader.fieldnames or [])
                data = list(reader)
            return headers, data

    def load(self, merge_strategy: str = "append", join_key: Optional[str] = None, dedupe: bool = False, sheet_name: Optional[str] = None) -> bool:
        """Load and parse the CSV/Excel file(s) based on merge strategy.

        Args:
            merge_strategy: How to combine multiple files ('append' or 'join')
            join_key: Column name for join strategy
            dedupe: Remove duplicate rows
            sheet_name: Sheet name for Excel files (uses first sheet if not specified)

        Returns:
            True if loading succeeded, False otherwise
        """
        if not self.input_paths:
            self.logger.error("No input files found.")
            return False

        try:
            if len(self.input_paths) == 1:
                # Single file case
                self.headers, self.data = self._load_single_file(self.input_paths[0], sheet_name)
                self.all_headers = list(self.headers)
                self.logger.info("Loaded %d rows from %s", len(self.data), self.input_paths[0].name)
            else:
                # Multiple files case
                if merge_strategy == "append":
                    all_data = []
                    all_unique_headers = set()
                    for path in self.input_paths:
                        current_headers, rows = self._load_single_file(path, sheet_name)
                        all_unique_headers.update(current_headers)
                        all_data.extend(rows)
                        self.logger.info("Appended %d rows from %s", len(rows), path.name)
                    self.headers = sorted(list(all_unique_headers))
                    self.all_headers = list(self.headers)
                    self.data = all_data
                    self.logger.info("Total loaded %d rows from %d files using 'append' strategy.", len(self.data), len(self.input_paths))

                elif merge_strategy == "join":
                    if not join_key:
                        self.logger.error("Join strategy requires a --join-key.")
                        return False

                    # Check if join_key exists in all files
                    for p in self.input_paths:
                        file_headers, _ = self._load_single_file(p, sheet_name)
                        if join_key not in file_headers:
                            self.logger.error("Join key '%s' not found in file: %s", join_key, p.name)
                            return False

                    joined_data: Dict[str, Dict[str, Any]] = {}
                    all_unique_headers = set()

                    for i, path in enumerate(self.input_paths):
                        current_headers, rows = self._load_single_file(path, sheet_name)
                        all_unique_headers.update(current_headers)
                        for row in rows:
                            key_value = row.get(join_key)
                            if key_value:
                                if key_value not in joined_data:
                                    joined_data[key_value] = {join_key: key_value}
                                # Prefix columns from subsequent files to avoid conflicts
                                prefix = f"file{i+1}_" if i > 0 else ""
                                for header, value in row.items():
                                    if header != join_key:
                                        joined_data[key_value][f"{prefix}{header}"] = value
                                        all_unique_headers.add(f"{prefix}{header}")
                                    else:
                                        joined_data[key_value][header] = value
                    self.data = list(joined_data.values())
                    self.headers = sorted(list(all_unique_headers))
                    self.all_headers = list(self.headers)
                    self.logger.info("Total loaded %d rows from %d files using 'join' strategy on key '%s'.", len(self.data), len(self.input_paths), join_key)

            # Deduplicate rows if requested
            if dedupe and self.data:
                original_count = len(self.data)
                seen = set()
                unique_data = []
                for row in self.data:
                    # Create a hashable key from sorted row items
                    row_key = tuple(sorted((k, str(v)) for k, v in row.items()))
                    if row_key not in seen:
                        seen.add(row_key)
                        unique_data.append(row)
                self.data = unique_data
                removed = original_count - len(self.data)
                if removed > 0:
                    self.logger.info("Removed %d duplicate rows.", removed)

            self._detect_column_types()
            return True
        except Exception as e:
            self.logger.error("Error reading CSV: %s", e)
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
            "=" * 60, # FIX: Changed to show all input file names
            f"CSV REPORT: {', '.join([p.name for p in self.input_paths])}", # FIX: Show all input file names
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

    def export_summary_csv(self, output_path: Path, group_by: str, data: List[Dict[str, Any]]) -> bool:
        """Export a summary CSV grouped by a column."""
        if group_by not in self.headers:
            self.logger.error("Column not found: %s", group_by)
            return False
        
        groups = defaultdict(list)
        for row in data:
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
            self.logger.info("Summary exported to: %s", output_path)
            return True
        except Exception as e:
            self.logger.error("Error writing CSV: %s", e)
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate reports from CSV/Excel data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic single-file report
  reporter.py expenses.csv
  # Excel file (uses first sheet)
  reporter.py data.xlsx
  # Excel file with specific sheet
  reporter.py data.xlsx --sheet "Sales Data"
  # List available sheets in Excel file
  reporter.py data.xlsx --list-sheets
  # Multiple CSV files (append rows)
  reporter.py jan.csv feb.csv mar.csv
  # Using glob pattern
  reporter.py *.csv
  # Append merge explicitly
  reporter.py *.csv --merge append
  # Join CSVs on a common column
  reporter.py users.csv orders.csv --merge join --join-key user_id
  # Grouped report
  reporter.py *.csv --group-by category
  # Filter by column value
  reporter.py expenses.csv --filter-column type --filter-value Food
  # Date range filtering
  reporter.py expenses.csv --date-from 2024-01-01 --date-to 2024-06-30
  # Export grouped summary as CSV
  reporter.py *.csv --group-by category --export-csv summary.csv
  # Remove duplicate rows
  reporter.py *.csv --merge append --dedupe"""
    )
    parser.add_argument("inputs", nargs="+", help="CSV/Excel files or glob patterns")
    parser.add_argument("--output", "-o", type=Path, help="Output file for report")
    parser.add_argument("--group-by", "-g", help="Column to group by")
    parser.add_argument("--filter-column", "-fc", help="Column to filter on")
    parser.add_argument("--filter-value", "-fv", help="Value to filter for")
    parser.add_argument("--date-from", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--date-to", help="End date (YYYY-MM-DD)")
    parser.add_argument("--export-csv", type=Path, help="Export summary as CSV")
    parser.add_argument("--merge", choices=["append", "join"], default="append")
    parser.add_argument("--join-key", help="Required for join")
    parser.add_argument("--dedupe", action="store_true", help="Remove duplicate rows")
    parser.add_argument("--sheet", "-s", help="Excel sheet name (default: first sheet)")
    parser.add_argument("--list-sheets", action="store_true", help="List available sheets in Excel file")
    args = parser.parse_args()

    reporter = CSVReporter(args.inputs)

    # Handle --list-sheets
    if args.list_sheets:
        for path in reporter.input_paths:
            if _get_file_type(path) == 'excel':
                try:
                    sheets = reporter.get_sheet_names(path)
                    print(f"\n{path.name}:")
                    for i, sheet in enumerate(sheets, 1):
                        print(f"  {i}. {sheet}")
                except ImportError as e:
                    print(f"Error: {e}")
                    sys.exit(1)
            else:
                print(f"\n{path.name}: Not an Excel file")
        sys.exit(0)

    if not reporter.load(args.merge, args.join_key, args.dedupe, args.sheet):
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
        reporter.export_summary_csv(args.export_csv, args.group_by, filtered_data)


if __name__ == "__main__":
    main()
