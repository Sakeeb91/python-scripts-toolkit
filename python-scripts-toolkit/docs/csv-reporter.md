# CSV/Excel Report Generator - Technical Documentation

A Python script that reads CSV and Excel files and generates summary reports with totals, averages, advanced statistics, groupings, and filtering capabilities.

## Table of Contents

- [Concepts Overview](#concepts-overview)
- [Technologies Used](#technologies-used)
- [Core Code Explained](#core-code-explained)
- [Key Python Fundamentals](#key-python-fundamentals)
- [Data Processing Patterns](#data-processing-patterns)
- [Extending the Project](#extending-the-project)

---

## Concepts Overview

### What Problem Does This Solve?

Working with data in CSV format is common in many fields—expense tracking, time logging, sales data, etc. This script automates the analysis by:

1. **Loading** CSV data into memory
2. **Detecting** column types (numeric, date, category)
3. **Filtering** by value or date range
4. **Aggregating** numeric columns (sum, average, min, max)
5. **Advanced statistics** (median, standard deviation, variance, percentiles)
6. **Grouping** data by any column

### Example Workflow

```
Input: expenses.csv
┌────────────┬───────────┬─────────────────┬────────┐
│ date       │ category  │ description     │ amount │
├────────────┼───────────┼─────────────────┼────────┤
│ 2024-01-05 │ Food      │ Grocery shopping│ 85.50  │
│ 2024-01-08 │ Transport │ Uber ride       │ 24.00  │
│ 2024-01-10 │ Food      │ Restaurant      │ 62.30  │
└────────────┴───────────┴─────────────────┴────────┘

Output: Summary Report
════════════════════════════════════════
NUMERIC SUMMARIES
────────────────────────────────────────
amount:
  Total:   171.80
  Average: 57.27
  Min:     24.00
  Max:     85.50

BY CATEGORY
────────────────────────────────────────
Food: 2 items
  amount: 147.80
Transport: 1 item
  amount: 24.00
════════════════════════════════════════

Output with --full-stats:
════════════════════════════════════════
NUMERIC SUMMARIES
────────────────────────────────────────
amount:
  Total:   171.80
  Average: 57.27
  Median:  62.30
  Std Dev: 31.12
  Variance:968.45
  Min:     24.00
  Max:     85.50
  P25:     43.15
  P50:     62.30
  P75:     73.90
  Count:   3
════════════════════════════════════════
```

---

## Technologies Used

### Standard Library Modules

| Module | Purpose | Why We Use It |
|--------|---------|---------------|
| `csv` | CSV file parsing | Handles quoting, delimiters, edge cases |
| `statistics` | Advanced statistics | Median, stdev, variance, percentiles |
| `collections.defaultdict` | Grouped aggregations | Auto-initializing nested structures |
| `datetime` | Date parsing and filtering | Date range comparisons |
| `argparse` | Command-line interface | Filter options, output paths |
| `typing` | Type hints | Code documentation and IDE support |

### Optional Dependencies

| Module | Purpose | Why We Use It |
|--------|---------|---------------|
| `openpyxl` | Excel file parsing | Read .xlsx, .xls, .xlsm, .xlsb files |

**Installing Excel support:**
```bash
pip install openpyxl
```

### Why the `csv` Module?

```python
# DON'T do this - breaks on quoted fields with commas
with open('data.csv') as f:
    for line in f:
        fields = line.split(',')  # Fails: "Smith, John",25

# DO use the csv module - handles edge cases
import csv
with open('data.csv', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(row['name'], row['age'])  # Correctly parses "Smith, John"
```

The `csv` module handles:
- Quoted fields containing commas
- Different delimiters (tabs, semicolons)
- Escaped quotes within fields
- Different line endings (Unix/Windows)

---

## Core Code Explained

### 1. Loading CSV with DictReader

```python
def load(self) -> bool:
    """Load and parse the CSV file."""
    try:
        with open(self.input_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            self.headers = reader.fieldnames or []
            self.data = list(reader)

        self._detect_column_types()
        return True

    except Exception as e:
        self.logger.error(f"Error reading CSV: {e}")
        return False
```

**Key points:**
- `newline=''` lets the csv module handle line endings correctly
- `encoding='utf-8'` handles international characters
- `csv.DictReader` returns each row as a dictionary
- `reader.fieldnames` gives us the header row
- `list(reader)` loads all data into memory

**Result structure:**
```python
self.headers = ['date', 'category', 'description', 'amount']
self.data = [
    {'date': '2024-01-05', 'category': 'Food', 'description': 'Grocery', 'amount': '85.50'},
    {'date': '2024-01-08', 'category': 'Transport', 'description': 'Uber', 'amount': '24.00'},
    # ...
]
```

### 2. Auto-Detecting Column Types

```python
def _detect_column_types(self) -> None:
    """Auto-detect column types for aggregation."""

    # Detect date column by checking common names
    for col in CSV_REPORTER_CONFIG["date_columns"]:  # ['date', 'Date', 'timestamp', ...]
        if col in self.headers:
            self.date_column = col
            break

    # Detect numeric columns by sampling values
    for col in self.headers:
        if self._is_numeric_column(col):
            self.numeric_columns.append(col)

def _is_numeric_column(self, column: str) -> bool:
    """Check if a column contains numeric data."""
    sample = [row.get(column, "") for row in self.data[:10]]  # Sample first 10 rows
    try:
        for val in sample:
            if val.strip():
                float(val.replace(",", "").replace("$", ""))  # Handle currency
        return True
    except ValueError:
        return False
```

**Why sample first 10 rows?**
- Performance: Don't scan entire file for type detection
- Sufficient: Column types are consistent in well-formed CSVs
- Handles empty values gracefully

### 3. Parsing Numeric Values

CSV data is always strings. We need robust parsing for real-world data:

```python
def _parse_numeric(self, value: str) -> float:
    """Parse a numeric string, handling currency and commas."""
    if not value or not value.strip():
        return 0.0

    # Remove common formatting: "$1,234.56" -> "1234.56"
    cleaned = value.replace(",", "").replace("$", "").strip()

    try:
        return float(cleaned)
    except ValueError:
        return 0.0
```

**Handles these formats:**
- `"85.50"` → `85.50`
- `"$1,234.56"` → `1234.56`
- `"1,000"` → `1000.0`
- `""` or `"N/A"` → `0.0`

### 4. Filtering Data

```python
def filter_data(
    self,
    filter_column: Optional[str] = None,
    filter_value: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Filter data based on criteria."""
    filtered = self.data.copy()  # Don't modify original

    # Filter by column value (case-insensitive)
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

                # Skip if outside range
                if from_date and row_date < from_date:
                    continue
                if to_date and row_date > to_date:
                    continue

                date_filtered.append(row)
            except ValueError:
                continue  # Skip rows with invalid dates

        filtered = date_filtered

    return filtered
```

**Design patterns:**
- **Non-destructive:** Creates a copy, doesn't modify original
- **Chainable filters:** Apply value filter, then date filter
- **Graceful errors:** Invalid dates are skipped, not crashed

### 5. Generating Aggregations

```python
def generate_report(self, data=None, group_by=None) -> str:
    """Generate a summary report."""
    data = data or self.data
    lines = []

    # Numeric summaries
    for col in self.numeric_columns:
        values = [self._parse_numeric(row.get(col, "")) for row in data]
        if values:
            lines.append(f"\n{col}:")
            lines.append(f"  Total:   {sum(values):,.2f}")
            lines.append(f"  Average: {sum(values)/len(values):,.2f}")
            lines.append(f"  Min:     {min(values):,.2f}")
            lines.append(f"  Max:     {max(values):,.2f}")

    return "\n".join(lines)
```

**Formatting:**
- `{value:,.2f}` formats as `1,234.56` (comma separator, 2 decimals)
- `sum(values)/len(values)` for average (could use `statistics.mean()`)

### 6. Advanced Statistics

The reporter supports advanced statistical calculations using Python's `statistics` module:

```python
def _compute_advanced_stats(self, values: List[float]) -> Dict[str, float]:
    """Compute advanced statistics for a list of numeric values."""
    result = {}

    if not values:
        return result

    # Median - works with any number of values
    result["median"] = statistics.median(values)

    # Standard deviation and variance require at least 2 values
    if len(values) >= 2:
        result["stdev"] = statistics.stdev(values)
        result["variance"] = statistics.variance(values)
    else:
        result["stdev"] = 0.0
        result["variance"] = 0.0

    # Percentiles require at least 4 values for quartiles
    if len(values) >= 4:
        quantiles = statistics.quantiles(values, n=4)
        result["p25"] = quantiles[0]  # 25th percentile
        result["p50"] = quantiles[1]  # 50th percentile
        result["p75"] = quantiles[2]  # 75th percentile
    else:
        # For small datasets, use median for all percentiles
        result["p25"] = result["p50"] = result["p75"] = result["median"]

    return result
```

**Available statistics:**

| Stat | Description | Minimum Data Points |
|------|-------------|---------------------|
| `median` | Middle value of sorted data | 1 |
| `stdev` | Sample standard deviation | 2 |
| `variance` | Sample variance | 2 |
| `p25` | 25th percentile (Q1) | 4 |
| `p50` | 50th percentile (Q2/Median) | 4 |
| `p75` | 75th percentile (Q3) | 4 |

**Usage:**
```bash
# Show all advanced statistics
python main.py csv data.csv --full-stats

# Show specific statistics only
python main.py csv data.csv --stats median,stdev,p75
```

### 7. Group By Analysis

```python
# Group by analysis
if group_by and group_by in self.headers:
    groups = defaultdict(list)

    # Group rows by the specified column
    for row in data:
        key = row.get(group_by, "Unknown")
        groups[key].append(row)

    # Calculate aggregates per group
    for group_name, group_data in sorted(groups.items()):
        lines.append(f"\n{group_name}: {len(group_data)} items")

        for col in self.numeric_columns:
            values = [self._parse_numeric(row.get(col, "")) for row in group_data]
            if values:
                lines.append(f"  {col} total: {sum(values):,.2f}")
```

**How grouping works:**
```python
# Input data
[
    {'category': 'Food', 'amount': '85.50'},
    {'category': 'Transport', 'amount': '24.00'},
    {'category': 'Food', 'amount': '62.30'},
]

# After grouping by 'category'
{
    'Food': [
        {'category': 'Food', 'amount': '85.50'},
        {'category': 'Food', 'amount': '62.30'},
    ],
    'Transport': [
        {'category': 'Transport', 'amount': '24.00'},
    ]
}
```

---

## Key Python Fundamentals

### 1. List Comprehensions for Filtering

```python
# Traditional loop
filtered = []
for row in data:
    if row.get('category') == 'Food':
        filtered.append(row)

# List comprehension (preferred)
filtered = [row for row in data if row.get('category') == 'Food']
```

### 2. Dictionary get() with Default

```python
# Unsafe - raises KeyError if column missing
value = row['amount']

# Safe - returns empty string if missing
value = row.get('amount', '')

# With numeric default
value = row.get('amount', '0')
```

### 3. defaultdict for Grouping

```python
from collections import defaultdict

# Without defaultdict
groups = {}
for row in data:
    key = row['category']
    if key not in groups:
        groups[key] = []
    groups[key].append(row)

# With defaultdict
groups = defaultdict(list)
for row in data:
    groups[row['category']].append(row)  # Auto-creates empty list
```

### 4. Optional Type Hints

```python
from typing import Optional, List, Dict, Any

def filter_data(
    self,
    filter_column: Optional[str] = None,  # Can be str or None
    filter_value: Optional[str] = None,
) -> List[Dict[str, Any]]:  # Returns list of dictionaries
    ...
```

### 5. String Formatting with f-strings

```python
# Basic
f"Total: {total}"

# With formatting
f"Total: {total:,.2f}"      # 1,234.56
f"Total: ${total:>10,.2f}"  # $  1,234.56 (right-aligned, 10 chars)
f"Percent: {ratio:.1%}"     # 45.6%
```

---

## Data Processing Patterns

### The ETL Pattern (Extract, Transform, Load)

This script follows the classic ETL pattern:

```
┌─────────┐     ┌───────────┐     ┌────────┐
│ Extract │ --> │ Transform │ --> │  Load  │
│  (CSV)  │     │ (Filter,  │     │(Report)│
│         │     │  Group)   │     │        │
└─────────┘     └───────────┘     └────────┘
```

1. **Extract:** `load()` reads CSV into memory
2. **Transform:** `filter_data()` and aggregations
3. **Load:** `generate_report()` or `export_summary_csv()`

### Lazy vs Eager Evaluation

```python
# Eager (our approach) - load all data immediately
self.data = list(reader)  # All rows in memory

# Lazy alternative - process row by row
for row in reader:
    process(row)  # One row at a time
```

**Trade-offs:**
- **Eager:** Faster for multiple operations, uses more memory
- **Lazy:** Memory efficient for large files, slower for multiple passes

### Functional Approach Alternative

```python
# Current imperative style
values = []
for row in data:
    val = self._parse_numeric(row.get(col, ""))
    values.append(val)
total = sum(values)

# Functional style with map
values = list(map(lambda r: self._parse_numeric(r.get(col, "")), data))
total = sum(values)

# Using generator expression (memory efficient)
total = sum(self._parse_numeric(row.get(col, "")) for row in data)
```

---

## Extending the Project

### 1. Add Chart Generation

```python
import matplotlib.pyplot as plt

def generate_chart(self, group_by: str, output_path: Path):
    """Generate a bar chart of grouped data."""
    groups = defaultdict(float)
    for row in self.data:
        key = row.get(group_by, "Other")
        groups[key] += self._parse_numeric(row.get(self.numeric_columns[0], ""))

    plt.figure(figsize=(10, 6))
    plt.bar(groups.keys(), groups.values())
    plt.xlabel(group_by)
    plt.ylabel(self.numeric_columns[0])
    plt.title(f"Total {self.numeric_columns[0]} by {group_by}")
    plt.savefig(output_path)
```

### 2. Excel Export with Formatting

```python
import openpyxl
from openpyxl.styles import Font, PatternFill

def export_to_excel(self, output_path: Path):
    """Export data to formatted Excel file."""
    wb = openpyxl.Workbook()
    ws = wb.active

    # Header row with styling
    header_font = Font(bold=True)
    for col, header in enumerate(self.headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font

    # Data rows
    for row_num, row_data in enumerate(self.data, 2):
        for col, header in enumerate(self.headers, 1):
            ws.cell(row=row_num, column=col, value=row_data.get(header, ""))

    wb.save(output_path)
```

### 3. SQL-like Query Interface

```python
def query(self, where: str = None, select: List[str] = None, order_by: str = None):
    """SQL-like query interface.

    Usage: reporter.query(where="category == 'Food'", order_by="amount DESC")
    """
    result = self.data.copy()

    if where:
        # Simple parser for "column == 'value'" or "column > 100"
        result = [row for row in result if self._eval_condition(row, where)]

    if order_by:
        col, direction = order_by.split()
        reverse = direction.upper() == "DESC"
        result.sort(key=lambda r: self._parse_numeric(r.get(col, "")), reverse=reverse)

    if select:
        result = [{k: row[k] for k in select if k in row} for row in result]

    return result
```

### 4. Support for Multiple File Formats

```python
def load_file(path: Path) -> List[Dict]:
    """Load data from CSV, JSON, or Excel."""
    suffix = path.suffix.lower()

    if suffix == '.csv':
        return load_csv(path)
    elif suffix == '.json':
        return load_json(path)
    elif suffix in ['.xlsx', '.xls']:
        return load_excel(path)
    else:
        raise ValueError(f"Unsupported format: {suffix}")
```

---

## Summary

The CSV Reporter teaches these core Python concepts:

| Concept | How It's Used |
|---------|---------------|
| `csv` module | Safe CSV parsing |
| `DictReader` | Row-as-dictionary access |
| `statistics` module | Median, stdev, variance, percentiles |
| Type detection | Sampling and validation |
| List comprehensions | Filtering and transformation |
| `defaultdict` | Grouping operations |
| String formatting | Number display |
| Optional types | Flexible function signatures |
| Error handling | Graceful degradation |

This is a practical tool for data analysis that demonstrates patterns used in pandas, SQL, and other data processing tools.
