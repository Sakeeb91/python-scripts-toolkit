"""
Email/Notification Reminder Script - Send email alerts based on conditions.

Usage:
    python -m projects.email_reminder.reminder --check-folder /path/to/watch
    python -m projects.email_reminder.reminder --check-csv expenses.csv --threshold 1000 --column amount
    python -m projects.email_reminder.reminder --check-todos --due-soon 3

Setup:
    Set environment variables for email:
    - EMAIL_ADDRESS: Your email address
    - EMAIL_PASSWORD: Your email password or app password
    - SMTP_SERVER: SMTP server (default: smtp.gmail.com)
    - SMTP_PORT: SMTP port (default: 587)

    For Gmail, use an App Password: https://support.google.com/accounts/answer/185833
"""
import argparse
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
import csv
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import EMAIL_REMINDER_CONFIG, DATA_DIR
from utils.logger import setup_logger
from utils.helpers import load_json, save_json


class EmailSender:
    """Handles sending email notifications."""

    def __init__(self):
        self.logger = setup_logger("email_reminder")
        self.smtp_server = os.getenv("SMTP_SERVER", EMAIL_REMINDER_CONFIG["smtp_server"])
        self.smtp_port = int(os.getenv("SMTP_PORT", EMAIL_REMINDER_CONFIG["smtp_port"]))
        self.email_address = os.getenv("EMAIL_ADDRESS")
        self.email_password = os.getenv("EMAIL_PASSWORD")

    def is_configured(self) -> bool:
        """Check if email credentials are configured."""
        return bool(self.email_address and self.email_password)

    def send_email(
        self,
        to_address: str,
        subject: str,
        body: str,
        html: bool = False
    ) -> bool:
        """Send an email notification."""
        if not self.is_configured():
            self.logger.error("Email not configured. Set EMAIL_ADDRESS and EMAIL_PASSWORD env vars.")
            return False

        try:
            msg = MIMEMultipart()
            msg["From"] = self.email_address
            msg["To"] = to_address
            msg["Subject"] = subject

            content_type = "html" if html else "plain"
            msg.attach(MIMEText(body, content_type))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_address, self.email_password)
                server.send_message(msg)

            self.logger.info(f"Email sent to {to_address}: {subject}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            return False


class ReminderChecker:
    """Checks various conditions and triggers reminders."""

    def __init__(self, state_file: Optional[Path] = None):
        self.logger = setup_logger("reminder_checker")
        self.state_file = state_file or (DATA_DIR / "logs" / "reminder_state.json")
        self.state = load_json(self.state_file)
        self.email_sender = EmailSender()
        self.alerts: List[Dict] = []

    def _save_state(self) -> None:
        """Save checker state to track what we've already seen."""
        save_json(self.state, self.state_file)

    def check_folder_for_new_files(
        self,
        folder: Path,
        extensions: Optional[List[str]] = None
    ) -> List[Dict]:
        """Check if a folder has new files since last check."""
        folder = Path(folder)
        if not folder.exists():
            self.logger.error(f"Folder not found: {folder}")
            return []

        folder_key = str(folder.absolute())
        last_check = self.state.get(f"folder_{folder_key}_last_check", "")
        seen_files = set(self.state.get(f"folder_{folder_key}_files", []))

        new_files = []
        current_files = set()

        for item in folder.iterdir():
            if item.is_file():
                # Filter by extension if specified
                if extensions and item.suffix.lower() not in extensions:
                    continue

                current_files.add(item.name)

                if item.name not in seen_files:
                    new_files.append({
                        "name": item.name,
                        "path": str(item),
                        "size": item.stat().st_size,
                        "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                    })

        # Update state
        self.state[f"folder_{folder_key}_last_check"] = datetime.now().isoformat()
        self.state[f"folder_{folder_key}_files"] = list(current_files)
        self._save_state()

        if new_files:
            self.alerts.append({
                "type": "new_files",
                "folder": str(folder),
                "count": len(new_files),
                "files": new_files
            })

        return new_files

    def check_csv_threshold(
        self,
        csv_path: Path,
        column: str,
        threshold: float,
        aggregate: str = "sum"
    ) -> Optional[Dict]:
        """Check if a CSV column exceeds a threshold."""
        csv_path = Path(csv_path)
        if not csv_path.exists():
            self.logger.error(f"CSV not found: {csv_path}")
            return None

        try:
            with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                values = []

                for row in reader:
                    val = row.get(column, "")
                    if val:
                        # Clean and parse numeric value
                        cleaned = val.replace(",", "").replace("$", "").strip()
                        try:
                            values.append(float(cleaned))
                        except ValueError:
                            continue

            if not values:
                self.logger.warning(f"No numeric values found in column: {column}")
                return None

            # Calculate aggregate
            if aggregate == "sum":
                result = sum(values)
            elif aggregate == "avg":
                result = sum(values) / len(values)
            elif aggregate == "max":
                result = max(values)
            elif aggregate == "count":
                result = len(values)
            else:
                result = sum(values)

            if result > threshold:
                alert = {
                    "type": "threshold_exceeded",
                    "file": str(csv_path),
                    "column": column,
                    "aggregate": aggregate,
                    "value": result,
                    "threshold": threshold
                }
                self.alerts.append(alert)
                return alert

            return None

        except Exception as e:
            self.logger.error(f"Error checking CSV: {e}")
            return None

    def check_todos_due_soon(self, days: int = 3) -> List[Dict]:
        """Check for to-do items due within N days."""
        todo_file = DATA_DIR / "todos" / "tasks.json"
        if not todo_file.exists():
            self.logger.warning("No todo file found")
            return []

        data = load_json(todo_file)
        tasks = data.get("tasks", [])

        today = datetime.now()
        due_soon = []

        for task in tasks:
            if task.get("completed"):
                continue

            due_date_str = task.get("due_date")
            if not due_date_str:
                continue

            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
                days_until = (due_date - today).days

                if days_until <= days:
                    due_soon.append({
                        "id": task.get("id"),
                        "title": task.get("title"),
                        "due_date": due_date_str,
                        "days_until": days_until,
                        "priority": task.get("priority", "medium"),
                        "overdue": days_until < 0
                    })

            except ValueError:
                continue

        if due_soon:
            self.alerts.append({
                "type": "todos_due_soon",
                "count": len(due_soon),
                "tasks": due_soon
            })

        return due_soon

    def format_alert_email(self) -> tuple:
        """Format all alerts into an email subject and body."""
        if not self.alerts:
            return None, None

        subject_parts = []
        body_parts = ["Python Scripts Toolkit - Alert Summary", "=" * 50, ""]

        for alert in self.alerts:
            if alert["type"] == "new_files":
                subject_parts.append(f"{alert['count']} new file(s)")
                body_parts.append(f"NEW FILES in {alert['folder']}")
                body_parts.append("-" * 40)
                for f in alert["files"]:
                    body_parts.append(f"  - {f['name']}")
                body_parts.append("")

            elif alert["type"] == "threshold_exceeded":
                subject_parts.append(f"Threshold exceeded: {alert['column']}")
                body_parts.append(f"THRESHOLD EXCEEDED")
                body_parts.append("-" * 40)
                body_parts.append(f"  File: {alert['file']}")
                body_parts.append(f"  Column: {alert['column']}")
                body_parts.append(f"  {alert['aggregate'].title()}: {alert['value']:,.2f}")
                body_parts.append(f"  Threshold: {alert['threshold']:,.2f}")
                body_parts.append("")

            elif alert["type"] == "todos_due_soon":
                overdue = sum(1 for t in alert["tasks"] if t["overdue"])
                subject_parts.append(f"{alert['count']} task(s) due soon")
                body_parts.append("TASKS DUE SOON")
                body_parts.append("-" * 40)
                for t in sorted(alert["tasks"], key=lambda x: x["days_until"]):
                    status = "OVERDUE" if t["overdue"] else f"in {t['days_until']} days"
                    body_parts.append(f"  [{t['priority']}] {t['title']} - {status}")
                body_parts.append("")

        body_parts.append("=" * 50)
        body_parts.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        subject = "Alert: " + ", ".join(subject_parts)
        body = "\n".join(body_parts)

        return subject, body

    def send_alerts(self, to_address: Optional[str] = None) -> bool:
        """Send all accumulated alerts via email."""
        if not self.alerts:
            self.logger.info("No alerts to send")
            return True

        subject, body = self.format_alert_email()

        if not to_address:
            to_address = self.email_sender.email_address

        if not to_address:
            # Just print to console if no email configured
            print(f"\n{subject}\n")
            print(body)
            return True

        return self.email_sender.send_email(to_address, subject, body)


def main():
    parser = argparse.ArgumentParser(
        description="Check conditions and send email reminders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --check-folder ~/Downloads
  %(prog)s --check-folder ~/Downloads --extensions .pdf,.doc
  %(prog)s --check-csv expenses.csv --column amount --threshold 1000
  %(prog)s --check-todos --due-soon 7
  %(prog)s --check-folder ~/Downloads --send-email user@example.com

Environment variables:
  EMAIL_ADDRESS   - Your email address
  EMAIL_PASSWORD  - Your email password (use app password for Gmail)
  SMTP_SERVER     - SMTP server (default: smtp.gmail.com)
  SMTP_PORT       - SMTP port (default: 587)
        """
    )

    # Check types
    parser.add_argument(
        "--check-folder", "-f",
        type=Path,
        help="Watch a folder for new files"
    )
    parser.add_argument(
        "--extensions", "-e",
        help="Comma-separated file extensions to watch (e.g., .pdf,.doc)"
    )
    parser.add_argument(
        "--check-csv", "-c",
        type=Path,
        help="Check a CSV file for threshold"
    )
    parser.add_argument(
        "--column",
        help="CSV column to check"
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        help="Threshold value"
    )
    parser.add_argument(
        "--aggregate",
        choices=["sum", "avg", "max", "count"],
        default="sum",
        help="Aggregation method for CSV check"
    )
    parser.add_argument(
        "--check-todos",
        action="store_true",
        help="Check for tasks due soon"
    )
    parser.add_argument(
        "--due-soon",
        type=int,
        default=3,
        help="Days threshold for due-soon check"
    )

    # Output options
    parser.add_argument(
        "--send-email",
        metavar="ADDRESS",
        help="Send alerts to this email address"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Only output if there are alerts"
    )

    args = parser.parse_args()
    checker = ReminderChecker()

    # Run checks
    if args.check_folder:
        extensions = None
        if args.extensions:
            extensions = [ext.strip() for ext in args.extensions.split(",")]
        new_files = checker.check_folder_for_new_files(args.check_folder, extensions)
        if new_files and not args.quiet:
            print(f"Found {len(new_files)} new file(s)")

    if args.check_csv:
        if not args.column or args.threshold is None:
            parser.error("--check-csv requires --column and --threshold")
        result = checker.check_csv_threshold(
            args.check_csv,
            args.column,
            args.threshold,
            args.aggregate
        )
        if result and not args.quiet:
            print(f"Threshold exceeded: {result['value']:,.2f} > {result['threshold']:,.2f}")

    if args.check_todos:
        due_tasks = checker.check_todos_due_soon(args.due_soon)
        if due_tasks and not args.quiet:
            print(f"Found {len(due_tasks)} task(s) due within {args.due_soon} days")

    # Send or display alerts
    if checker.alerts:
        if args.send_email:
            checker.send_alerts(args.send_email)
        else:
            subject, body = checker.format_alert_email()
            print(f"\n{body}")
    elif not args.quiet:
        print("No alerts triggered")


if __name__ == "__main__":
    main()
