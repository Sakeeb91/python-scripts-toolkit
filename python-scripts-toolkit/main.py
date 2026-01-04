#!/usr/bin/env python3
"""
Python Scripts Toolkit - A collection of practical Python automation scripts.

This is the main entry point that provides a unified CLI for all projects:
    1. File Organizer - Sort files into folders by type
    2. CSV Reporter - Generate reports from CSV data
    3. Web Scraper - Scrape websites and save to CSV
    4. Todo Manager - CLI to-do list with JSON storage
    5. Email Reminder - Send alerts based on conditions

Usage:
    python main.py <project> [options]

Examples:
    python main.py organize ~/Downloads --dry-run
    python main.py csv expenses.csv --group-by category
    python main.py scrape --preset hackernews --output hn.csv
    python main.py todo add "Buy groceries"
    python main.py remind --check-todos --due-soon 7
"""
import sys
import argparse
from pathlib import Path


def get_version():
    return "1.0.0"


def print_banner():
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║             PYTHON SCRIPTS TOOLKIT v{}                   ║
║                                                               ║
║  A collection of practical Python automation scripts          ║
╚═══════════════════════════════════════════════════════════════╝
""".format(get_version())
    print(banner)


def list_projects():
    projects = """
Available Projects:
─────────────────────────────────────────────────────────────────

  organize    Smart File Organizer
              Sort files into folders by type (images, docs, code, etc.)
              Example: python main.py organize ~/Downloads --dry-run
              Undo:    python main.py organize --undo

  csv         CSV/Excel Report Generator
              Generate summary reports from CSV or Excel data
              Example: python main.py csv data.xlsx --sheet "Sales"

  scrape      Web Scraper + Saver
              Fetch web pages and save structured data to CSV
              Example: python main.py scrape --preset hackernews -o hn.csv

  todo        CLI To-Do Manager
              Manage tasks with priorities and due dates
              Example: python main.py todo add "Finish project" -p high

  remind      Email Reminder Script
              Send email alerts when conditions are met
              Example: python main.py remind --check-folder ~/Downloads

─────────────────────────────────────────────────────────────────
Run 'python main.py <project> --help' for project-specific options.
"""
    print(projects)


def run_organize(args):
    """Run the file organizer project."""
    from projects.file_organizer.organizer import FileOrganizer
    from utils.helpers import parse_size

    # Handle undo and list-history (don't require directory)
    if args.list_history:
        organizer = FileOrganizer(log_to_file=args.log)
        organizer.list_history()
        return

    if args.undo:
        organizer = FileOrganizer(log_to_file=args.log)
        organizer.undo(manifest_path=args.manifest)
        return

    # Regular organize operation requires directory
    if not args.directory:
        print("ERROR: directory is required for organize operation")
        sys.exit(1)

    # Parse size filters
    min_size = parse_size(args.min_size) if args.min_size else None
    max_size = parse_size(args.max_size) if args.max_size else None

    organizer = FileOrganizer(
        source_dir=args.directory,
        dry_run=args.dry_run,
        interactive=args.interactive,
        log_to_file=args.log,
        recursive=args.recursive,
        max_depth=args.max_depth,
        by_date=args.by_date,
        date_format=args.date_format,
        date_type=args.date_type,
        combine_with_type=args.combine_with_type,
        min_size=min_size,
        max_size=max_size
    )
    organizer.organize()


def run_csv(args):
    """Run the CSV reporter project."""
    from projects.csv_reporter.reporter import CSVReporter, _get_file_type

    reporter = CSVReporter([str(args.input)])

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
        return

    if not reporter.load(sheet_name=args.sheet):
        sys.exit(1)

    # Configure advanced statistics if requested
    reporter.configure_stats(
        full_stats=getattr(args, 'full_stats', False),
        stats_list=getattr(args, 'stats', None)
    )

    filtered_data = reporter.filter_data(
        filter_column=args.filter_column,
        filter_value=args.filter_value,
        date_from=args.date_from,
        date_to=args.date_to
    )

    report = reporter.generate_report(filtered_data, group_by=args.group_by)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Report saved to: {args.output}")
    else:
        print(report)

    # Generate chart if requested
    if getattr(args, 'chart', False):
        chart_path = reporter.generate_chart(
            data=filtered_data,
            chart_type=getattr(args, 'chart_type', 'bar'),
            output_path=getattr(args, 'chart_output', None),
            group_by=args.group_by,
            value_column=getattr(args, 'chart_column', None)
        )
        if chart_path:
            print(f"Chart saved to: {chart_path}")


def run_scrape(args):
    """Run the web scraper project."""
    try:
        from projects.web_scraper.scraper import WebScraper, HAS_DEPENDENCIES
    except ImportError:
        print("ERROR: Missing dependencies. Install with:")
        print("  pip install requests beautifulsoup4")
        sys.exit(1)

    if not HAS_DEPENDENCIES:
        print("ERROR: Missing dependencies. Install with:")
        print("  pip install requests beautifulsoup4")
        sys.exit(1)

    # Parse rate limiting options
    delay = getattr(args, 'delay', None)
    random_delay = None
    if getattr(args, 'random_delay', None):
        random_delay = WebScraper.parse_random_delay(args.random_delay)
        if random_delay is None:
            print("ERROR: Invalid random delay format. Use 'min-max' (e.g., '1-5')")
            sys.exit(1)
    respect_rate_limits = getattr(args, 'respect_rate_limits', False)

    scraper = WebScraper(
        delay=delay,
        random_delay=random_delay,
        respect_rate_limits=respect_rate_limits
    )

    if args.preset == "hackernews":
        items = scraper.scrape_hacker_news()
    elif args.url:
        items = scraper.scrape_generic(args.url, args.selector)
    else:
        print("ERROR: Either URL or --preset is required")
        sys.exit(1)

    print(f"Scraped {len(items)} items")

    if args.dedupe:
        original_count = len(items)
        items = scraper.dedupe(items)
        print(f"After deduplication: {len(items)} new items")

    if items:
        scraper.save_to_csv(items, args.output, append=args.append)

    # Print rate statistics if rate limiting was used
    if delay or random_delay or respect_rate_limits:
        stats = scraper.get_rate_stats()
        print(f"\nRate stats: {stats['request_count']} requests, "
              f"{stats['total_delay_time']}s delay, "
              f"{stats['requests_per_minute']} req/min")


def run_todo(args):
    """Run the todo manager project."""
    from projects.todo_manager.manager import TodoManager, format_task_list
    from config import TODO_MANAGER_CONFIG

    manager = TodoManager()

    if args.action == "add":
        task = manager.add(args.title, args.priority, args.due)
        print(f"Added: {task}")

    elif args.action == "list":
        show_completed = not args.pending
        show_pending = not args.completed
        tasks = manager.list_tasks(show_completed, show_pending, args.priority)
        print(format_task_list(tasks))

    elif args.action == "done":
        task = manager.mark_done(args.id)
        if task:
            print(f"Completed: {task}")

    elif args.action == "delete":
        if manager.delete(args.id):
            print(f"Deleted task #{args.id}")

    elif args.action == "stats":
        stats = manager.get_stats()
        print(f"\nTotal: {stats['total']} | Completed: {stats['completed']} | Pending: {stats['pending']} | Overdue: {stats['overdue']}")

    else:
        tasks = manager.list_tasks()
        print(format_task_list(tasks))


def run_remind(args):
    """Run the email reminder project."""
    from projects.email_reminder.reminder import ReminderChecker

    checker = ReminderChecker()

    if args.check_folder:
        extensions = None
        if args.extensions:
            extensions = [ext.strip() for ext in args.extensions.split(",")]
        new_files = checker.check_folder_for_new_files(args.check_folder, extensions)
        if new_files:
            print(f"Found {len(new_files)} new file(s)")

    if args.check_csv:
        if not args.column or args.threshold is None:
            print("ERROR: --check-csv requires --column and --threshold")
            sys.exit(1)
        result = checker.check_csv_threshold(
            args.check_csv,
            args.column,
            args.threshold,
            args.aggregate
        )
        if result:
            print(f"Threshold exceeded: {result['value']:,.2f} > {result['threshold']:,.2f}")

    if args.check_todos:
        due_tasks = checker.check_todos_due_soon(args.due_soon)
        if due_tasks:
            print(f"Found {len(due_tasks)} task(s) due within {args.due_soon} days")

    if checker.alerts:
        if args.send_email:
            checker.send_alerts(args.send_email)
        else:
            _, body = checker.format_alert_email()
            print(f"\n{body}")
    else:
        print("No alerts triggered")


def main():
    parser = argparse.ArgumentParser(
        description="Python Scripts Toolkit - A collection of practical automation scripts",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--version", "-v", action="version", version=f"%(prog)s {get_version()}")
    parser.add_argument("--list", "-l", action="store_true", help="List all available projects")

    subparsers = parser.add_subparsers(dest="project", help="Project to run")

    # File Organizer
    org_parser = subparsers.add_parser("organize", help="Sort files into folders by type")
    org_parser.add_argument("directory", type=Path, nargs='?', default=None, help="Directory to organize")
    org_parser.add_argument("--dry-run", "-n", action="store_true", help="Preview without moving files")
    org_parser.add_argument("--interactive", "-i", action="store_true", help="Ask for confirmation before moving each file")
    org_parser.add_argument("--log", action="store_true", help="Save log to file")
    org_parser.add_argument("--recursive", "-r", action="store_true", help="Recursively organize subdirectories")
    org_parser.add_argument("--max-depth", type=int, help="Maximum depth for recursive traversal")
    org_parser.add_argument("--by-date", action="store_true", help="Organize by date (e.g., 2024/January/)")
    org_parser.add_argument("--date-format", choices=["YYYY/MM", "YYYY/Month", "YYYY-MM-DD", "YYYY/MM/DD"], help="Date folder format")
    org_parser.add_argument("--date-type", choices=["modified", "created"], help="Use modification or creation date")
    org_parser.add_argument("--combine-with-type", action="store_true", help="Combine date and type (e.g., 2024/January/Images/)")
    org_parser.add_argument("--min-size", type=str, help="Skip files smaller than this size (e.g., 1KB, 10MB)")
    org_parser.add_argument("--max-size", type=str, help="Skip files larger than this size (e.g., 100MB, 1GB)")
    org_parser.add_argument("--undo", "-u", action="store_true", help="Undo a previous organization")
    org_parser.add_argument("--list-history", action="store_true", help="List previous organization operations")
    org_parser.add_argument("--manifest", "-m", type=Path, help="Specific manifest file for undo")

    # CSV Reporter
    csv_parser = subparsers.add_parser("csv", help="Generate reports from CSV/Excel data")
    csv_parser.add_argument("input", type=Path, help="Input CSV/Excel file")
    csv_parser.add_argument("--output", "-o", type=Path, help="Output file")
    csv_parser.add_argument("--group-by", "-g", help="Column to group by")
    csv_parser.add_argument("--filter-column", "-fc", help="Column to filter on")
    csv_parser.add_argument("--filter-value", "-fv", help="Value to filter for")
    csv_parser.add_argument("--date-from", help="Start date (YYYY-MM-DD)")
    csv_parser.add_argument("--date-to", help="End date (YYYY-MM-DD)")
    csv_parser.add_argument("--sheet", "-s", help="Excel sheet name (default: first sheet)")
    csv_parser.add_argument("--list-sheets", action="store_true", help="List available sheets in Excel file")
    csv_parser.add_argument("--full-stats", action="store_true",
                            help="Show all advanced statistics (median, std dev, variance, percentiles)")
    csv_parser.add_argument("--stats", metavar="STATS",
                            help="Comma-separated list of stats: median,stdev,variance,p25,p50,p75")
    csv_parser.add_argument("--chart", action="store_true",
                            help="Generate a chart alongside the text report")
    csv_parser.add_argument("--chart-type", choices=["bar", "hbar", "pie", "line"], default="bar",
                            help="Chart type: bar (default), hbar, pie, line")
    csv_parser.add_argument("--chart-output", type=Path, metavar="FILE",
                            help="Output file for chart (PNG, PDF, SVG, JPG)")
    csv_parser.add_argument("--chart-column", metavar="COLUMN",
                            help="Numeric column to visualize")

    # Web Scraper
    scrape_parser = subparsers.add_parser("scrape", help="Scrape websites and save to CSV")
    scrape_parser.add_argument("url", nargs="?", help="URL to scrape")
    scrape_parser.add_argument("--output", "-o", type=Path, required=True, help="Output CSV file")
    scrape_parser.add_argument("--selector", "-s", help="CSS selector")
    scrape_parser.add_argument("--preset", choices=["hackernews"], help="Use a preset scraper")
    scrape_parser.add_argument("--dedupe", "-d", action="store_true", help="Skip already-seen URLs")
    scrape_parser.add_argument("--append", "-a", action="store_true", help="Append to existing CSV")
    # Rate limiting options
    scrape_parser.add_argument("--delay", type=float, metavar="SECONDS",
                               help="Fixed delay between requests (seconds)")
    scrape_parser.add_argument("--random-delay", metavar="MIN-MAX",
                               help="Random delay range (e.g., '1-5' for 1-5 seconds)")
    scrape_parser.add_argument("--respect-rate-limits", action="store_true",
                               help="Honor server rate limit headers (Retry-After, X-RateLimit)")

    # Todo Manager
    todo_parser = subparsers.add_parser("todo", help="Manage your to-do list")
    todo_parser.add_argument("action", nargs="?", choices=["add", "list", "done", "delete", "stats"])
    todo_parser.add_argument("title", nargs="?", help="Task title (for add)")
    todo_parser.add_argument("--id", type=int, help="Task ID (for done/delete)")
    todo_parser.add_argument("--priority", "-p", choices=["low", "medium", "high", "critical"], default="medium")
    todo_parser.add_argument("--due", "-d", help="Due date (YYYY-MM-DD)")
    todo_parser.add_argument("--pending", action="store_true", help="Show only pending")
    todo_parser.add_argument("--completed", action="store_true", help="Show only completed")

    # Email Reminder
    remind_parser = subparsers.add_parser("remind", help="Send email alerts based on conditions")
    remind_parser.add_argument("--check-folder", "-f", type=Path, help="Watch for new files")
    remind_parser.add_argument("--extensions", "-e", help="File extensions to watch (comma-separated)")
    remind_parser.add_argument("--check-csv", "-c", type=Path, help="Check CSV threshold")
    remind_parser.add_argument("--column", help="CSV column to check")
    remind_parser.add_argument("--threshold", "-t", type=float, help="Threshold value")
    remind_parser.add_argument("--aggregate", choices=["sum", "avg", "max", "count"], default="sum")
    remind_parser.add_argument("--check-todos", action="store_true", help="Check for due tasks")
    remind_parser.add_argument("--due-soon", type=int, default=3, help="Days threshold")
    remind_parser.add_argument("--send-email", metavar="ADDRESS", help="Send to this email")

    args = parser.parse_args()

    if args.list or not args.project:
        print_banner()
        list_projects()
        return

    # Route to appropriate project
    if args.project == "organize":
        run_organize(args)
    elif args.project == "csv":
        run_csv(args)
    elif args.project == "scrape":
        run_scrape(args)
    elif args.project == "todo":
        run_todo(args)
    elif args.project == "remind":
        run_remind(args)


if __name__ == "__main__":
    main()
