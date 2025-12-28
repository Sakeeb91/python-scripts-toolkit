# Python Scripts Toolkit

A collection of **5 practical Python automation scripts** designed to teach core programming fundamentals while solving real-world problems.

```
python python-scripts-toolkit/main.py --list
```

## Quick Start

```bash
# Clone the repository
git clone https://github.com/Sakeeb91/python-scripts-toolkit.git
cd python-scripts-toolkit

# Install dependencies (optional - only needed for web scraper)
pip install -r python-scripts-toolkit/requirements.txt

# Run any project
python python-scripts-toolkit/main.py organize ~/Downloads --dry-run
python python-scripts-toolkit/main.py todo add "Learn Python"
```

## Projects

| Project | Description | Key Concepts | Docs |
|---------|-------------|--------------|------|
| **File Organizer** | Sort messy folders by file type | `pathlib`, `shutil`, conditionals | [Read More](python-scripts-toolkit/docs/file-organizer.md) |
| **CSV/Excel Reporter** | Generate reports from CSV/Excel data | `csv`, `openpyxl`, aggregation, filtering | [Read More](python-scripts-toolkit/docs/csv-reporter.md) |
| **Web Scraper** | Extract data from websites | `requests`, `BeautifulSoup`, HTTP | [Read More](python-scripts-toolkit/docs/web-scraper.md) |
| **Todo Manager** | CLI task management | JSON storage, data modeling | [Read More](python-scripts-toolkit/docs/todo-manager.md) |
| **Email Reminder** | Send conditional alerts | `smtplib`, scheduling, automation | [Read More](python-scripts-toolkit/docs/email-reminder.md) |

## Project Details

### 1. Smart File Organizer

Automatically sort files into categorized subfolders (Images, Documents, Code, etc.)

```bash
# Preview changes without moving
python python-scripts-toolkit/main.py organize ~/Downloads --dry-run

# Interactive mode (ask before each move)
python python-scripts-toolkit/main.py organize ~/Downloads --interactive

# Organize and log changes
python python-scripts-toolkit/main.py organize ~/Downloads --log

# Recursively organize including subdirectories
python python-scripts-toolkit/main.py organize ~/Downloads --recursive

# Recursive with depth limit (e.g., 2 levels deep)
python python-scripts-toolkit/main.py organize ~/Downloads -r --max-depth 2

# Size-based filtering: skip small files
python python-scripts-toolkit/main.py organize ~/Downloads --min-size 1KB

# Size-based filtering: skip large files
python python-scripts-toolkit/main.py organize ~/Downloads --max-size 100MB

# Combine size filters
python python-scripts-toolkit/main.py organize ~/Downloads --min-size 1KB --max-size 500MB
```

**Features:**
- Configurable file categories by extension
- Safe handling of name collisions
- Dry-run mode for preview
- Interactive mode for file-by-file confirmation and category changing
- Operation logging
- Recursive directory traversal with depth limiting
- Automatic exclusion of hidden/system directories
- Size-based filtering (skip files by min/max size)

---

### 2. CSV/Excel Report Generator

Generate summary reports with totals, averages, and groupings from CSV or Excel data.

```bash
# Basic report from CSV
python python-scripts-toolkit/main.py csv expenses.csv

# Report from Excel file (uses first sheet)
python python-scripts-toolkit/main.py csv data.xlsx

# Excel file with specific sheet
python python-scripts-toolkit/main.py csv data.xlsx --sheet "Sales Data"

# List available sheets in Excel file
python python-scripts-toolkit/main.py csv data.xlsx --list-sheets

# Group by category
python python-scripts-toolkit/main.py csv expenses.csv --group-by category

# Filter by date range
python python-scripts-toolkit/main.py csv expenses.csv --date-from 2024-01-01 --date-to 2024-06-30

# Save to file
python python-scripts-toolkit/main.py csv expenses.csv --output report.txt

# Merge multiple CSV files (append rows)
python python-scripts-toolkit/main.py csv jan.csv feb.csv mar.csv

# Use glob patterns
python python-scripts-toolkit/main.py csv *.csv --merge append

# Join CSVs on a common column
python python-scripts-toolkit/main.py csv users.csv orders.csv --merge join --join-key user_id

# Remove duplicate rows
python python-scripts-toolkit/main.py csv *.csv --merge append --dedupe

# Export grouped summary as CSV
python python-scripts-toolkit/main.py csv *.csv --group-by category --export-csv summary.csv
```

**Features:**
- **Excel support** (.xlsx, .xls, .xlsm, .xlsb) with sheet selection
- Auto-detects numeric and date columns
- Calculates sum, average, min, max
- Group by any column
- Filter by value or date range
- Merge multiple CSV files (append or join)
- Glob pattern support for file selection
- Deduplication of rows

**Note:** Excel support requires `pip install openpyxl`

---

### 3. Web Scraper + Saver

Fetch web pages and extract structured data to CSV.

```bash
# Scrape Hacker News
python python-scripts-toolkit/main.py scrape --preset hackernews --output hn_stories.csv

# Generic scraping with CSS selector
python python-scripts-toolkit/main.py scrape https://example.com --selector "h2.title" --output titles.csv

# Dedupe to only save new items
python python-scripts-toolkit/main.py scrape --preset hackernews --dedupe --append --output hn.csv
```

**Features:**
- Built-in Hacker News scraper
- Custom CSS selector support
- URL deduplication
- Retry logic with error handling

**Note:** Requires `pip install requests beautifulsoup4`

---

### 4. CLI To-Do Manager

Full-featured command-line task management with JSON persistence.

```bash
# Add tasks
python python-scripts-toolkit/main.py todo add "Buy groceries"
python python-scripts-toolkit/main.py todo add "Finish report" --priority high --due 2024-12-31

# List tasks
python python-scripts-toolkit/main.py todo list
python python-scripts-toolkit/main.py todo list --pending
python python-scripts-toolkit/main.py todo list --priority high

# Mark done / delete
python python-scripts-toolkit/main.py todo done --id 1
python python-scripts-toolkit/main.py todo delete --id 2

# View statistics
python python-scripts-toolkit/main.py todo stats
```

**Features:**
- Priority levels: low, medium, high, critical
- Due dates with overdue tracking
- Filter by status or priority
- Statistics dashboard

---

### 5. Email Reminder Script

Send email alerts when conditions are met.

```bash
# Alert when folder has new files
python python-scripts-toolkit/main.py remind --check-folder ~/Downloads

# Alert when CSV threshold exceeded
python python-scripts-toolkit/main.py remind --check-csv expenses.csv --column amount --threshold 1000

# Alert for tasks due soon
python python-scripts-toolkit/main.py remind --check-todos --due-soon 7

# Send via email
python python-scripts-toolkit/main.py remind --check-todos --send-email user@example.com
```

**Features:**
- Watch folders for new files
- Monitor CSV values against thresholds
- Check todo due dates
- Email via SMTP (Gmail supported)

**Setup for email:**
```bash
export EMAIL_ADDRESS="your@email.com"
export EMAIL_PASSWORD="your-app-password"
```

## Project Structure

```
python-scripts-toolkit/
├── main.py                 # Unified CLI entry point
├── config.py               # Global configuration
├── requirements.txt
├── docs/                   # Technical documentation
│   ├── file-organizer.md   # File Organizer deep dive
│   ├── csv-reporter.md     # CSV Reporter deep dive
│   ├── web-scraper.md      # Web Scraper deep dive
│   ├── todo-manager.md     # Todo Manager deep dive
│   └── email-reminder.md   # Email Reminder deep dive
├── projects/
│   ├── file_organizer/
│   │   └── organizer.py
│   ├── csv_reporter/
│   │   └── reporter.py
│   ├── web_scraper/
│   │   └── scraper.py
│   ├── todo_manager/
│   │   └── manager.py
│   └── email_reminder/
│       └── reminder.py
├── utils/
│   ├── logger.py           # Shared logging
│   └── helpers.py          # Utility functions
└── data/
    ├── todos/              # Todo JSON storage
    ├── scraped/            # Scraper state
    └── logs/               # Operation logs
```

## Configuration

Edit `python-scripts-toolkit/config.py` to customize:

- **File categories** for the organizer
- **Column detection** for CSV reporter
- **Scraper settings** (user agent, timeouts, retries)
- **Todo priorities** and storage location
- **SMTP settings** for email reminders

## Requirements

- Python 3.8+
- No external dependencies for most projects
- `requests` + `beautifulsoup4` for web scraper only

## Documentation

Each project has comprehensive technical documentation explaining concepts, code patterns, and extension ideas:

| Document | What You'll Learn |
|----------|-------------------|
| [File Organizer Guide](python-scripts-toolkit/docs/file-organizer.md) | `pathlib` vs `os.path`, extension mapping, dry-run patterns, `shutil` operations |
| [CSV Reporter Guide](python-scripts-toolkit/docs/csv-reporter.md) | `csv.DictReader`, type detection, aggregation patterns, ETL concepts |
| [Web Scraper Guide](python-scripts-toolkit/docs/web-scraper.md) | HTTP fundamentals, BeautifulSoup navigation, CSS selectors, ethical scraping |
| [Todo Manager Guide](python-scripts-toolkit/docs/todo-manager.md) | Data modeling, JSON serialization, CRUD patterns, CLI subcommands |
| [Email Reminder Guide](python-scripts-toolkit/docs/email-reminder.md) | SMTP protocol, credential security, scheduling with cron/launchd |

## Learning Path

Each project teaches fundamental Python concepts:

1. **File Organizer** → File system operations, conditionals, `pathlib`
2. **CSV/Excel Reporter** → Reading/writing files, `csv`/`openpyxl` modules, data aggregation
3. **Web Scraper** → HTTP requests, HTML parsing, error handling
4. **Todo Manager** → JSON, data modeling, CLI design
5. **Email Reminder** → Email protocols, environment variables, scheduling

## Running Individual Projects

Each project can also run standalone:

```bash
python -m python-scripts-toolkit.projects.file_organizer.organizer --help
python -m python-scripts-toolkit.projects.csv_reporter.reporter --help
python -m python-scripts-toolkit.projects.web_scraper.scraper --help
python -m python-scripts-toolkit.projects.todo_manager.manager --help
python -m python-scripts-toolkit.projects.email_reminder.reminder --help
```

## License

MIT License - Feel free to use, modify, and share.

## Contributing

Contributions welcome! Each project can be extended:

- **File Organizer:** Add undo functionality, duplicate detection
- **CSV Reporter:** Add charts, Excel export
- **Web Scraper:** Add more presets, proxy support
- **Todo Manager:** Add tags, recurring tasks
- **Email Reminder:** Add Discord/Slack webhooks
