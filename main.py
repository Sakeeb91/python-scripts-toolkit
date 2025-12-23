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

  csv         CSV Report Generator
              Generate summary reports from CSV data
              Example: python main.py csv data.csv --group-by category

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

    organizer = FileOrganizer(
        source_dir=args.directory,
        dry_run=args.dry_run,
        log_to_file=args.log
    )
    organizer.organize()


def run_csv(args):
    """Run the CSV reporter project."""
    from projects.csv_reporter.reporter import CSVReporter

    reporter = CSVReporter(args.input)
    if not reporter.load():
        sys.exit(1)

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

    scraper = WebScraper()

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
    org_parser.add_argument("directory", type=Path, help="Directory to organize")
    org_parser.add_argument("--dry-run", "-n", action="store_true", help="Preview without moving files")
    org_parser.add_argument("--log", action="store_true", help="Save log to file")

    # CSV Reporter
    csv_parser = subparsers.add_parser("csv", help="Generate reports from CSV data")
    csv_parser.add_argument("input", type=Path, help="Input CSV file")
    csv_parser.add_argument("--output", "-o", type=Path, help="Output file")
    csv_parser.add_argument("--group-by", "-g", help="Column to group by")
    csv_parser.add_argument("--filter-column", "-fc", help="Column to filter on")
    csv_parser.add_argument("--filter-value", "-fv", help="Value to filter for")
    csv_parser.add_argument("--date-from", help="Start date (YYYY-MM-DD)")
    csv_parser.add_argument("--date-to", help="End date (YYYY-MM-DD)")

    # Web Scraper
    scrape_parser = subparsers.add_parser("scrape", help="Scrape websites and save to CSV")
    scrape_parser.add_argument("url", nargs="?", help="URL to scrape")
    scrape_parser.add_argument("--output", "-o", type=Path, required=True, help="Output CSV file")
    scrape_parser.add_argument("--selector", "-s", help="CSS selector")
    scrape_parser.add_argument("--preset", choices=["hackernews"], help="Use a preset scraper")
    scrape_parser.add_argument("--dedupe", "-d", action="store_true", help="Skip already-seen URLs")
    scrape_parser.add_argument("--append", "-a", action="store_true", help="Append to existing CSV")

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
