# Email/Notification Reminder Script - Technical Documentation

A Python script that monitors conditions (new files, CSV thresholds, upcoming tasks) and sends email alerts when triggered.

## Table of Contents

- [Concepts Overview](#concepts-overview)
- [Technologies Used](#technologies-used)
- [Core Code Explained](#core-code-explained)
- [Email Protocols](#email-protocols)
- [Scheduling and Automation](#scheduling-and-automation)
- [Security Considerations](#security-considerations)
- [Extending the Project](#extending-the-project)

---

## Concepts Overview

### What Problem Does This Solve?

Automation is most powerful when it can notify you of important events without constant monitoring. This script provides:

1. **Condition monitoring:** Check files, data, or task states
2. **Threshold alerts:** Trigger when values exceed limits
3. **Email delivery:** Send notifications via SMTP
4. **State persistence:** Remember what's been seen to avoid duplicates

### Use Cases

```
┌─────────────────────────────────────────────────────────────┐
│                    REMINDER TRIGGERS                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  📁 New Files        📊 CSV Threshold      ✅ Due Tasks     │
│  ─────────────       ───────────────       ───────────      │
│  Watch folder        Monitor totals        Check deadlines  │
│  for downloads       against budgets       for upcoming     │
│                                            work             │
│         │                  │                    │           │
│         └──────────────────┼────────────────────┘           │
│                            │                                │
│                            ▼                                │
│                    ┌───────────────┐                        │
│                    │  📧 EMAIL     │                        │
│                    │   ALERT       │                        │
│                    └───────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Technologies Used

### Standard Library Modules

| Module | Purpose | Why We Use It |
|--------|---------|---------------|
| `smtplib` | SMTP email sending | Built-in, no dependencies |
| `email.mime` | Email message formatting | Multipart messages, attachments |
| `os` | Environment variables | Secure credential storage |
| `json` | State persistence | Track seen files/alerts |
| `datetime` | Date comparisons | Due date calculations |

### External Services

| Service | Purpose | Setup Required |
|---------|---------|----------------|
| Gmail SMTP | Email delivery | App Password |
| Other SMTP | Alternative providers | Server/port config |

---

## Core Code Explained

### 1. Email Configuration via Environment Variables

```python
class EmailSender:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.email_address = os.getenv("EMAIL_ADDRESS")
        self.email_password = os.getenv("EMAIL_PASSWORD")

    def is_configured(self) -> bool:
        """Check if email credentials are configured."""
        return bool(self.email_address and self.email_password)
```

**Why environment variables?**
```python
# DON'T hardcode credentials
email_password = "my_secret_password"  # Exposed in code!

# DO use environment variables
email_password = os.getenv("EMAIL_PASSWORD")

# Set in terminal:
# export EMAIL_PASSWORD="my_secret_password"

# Or in .env file (with python-dotenv):
# EMAIL_PASSWORD=my_secret_password
```

**Security benefits:**
- Credentials not in source code
- Different credentials per environment (dev/prod)
- Easy to rotate without code changes
- Not committed to version control

### 2. SMTP Email Sending

```python
def send_email(
    self,
    to_address: str,
    subject: str,
    body: str,
    html: bool = False
) -> bool:
    """Send an email notification."""
    if not self.is_configured():
        self.logger.error("Email not configured")
        return False

    try:
        # Create message container
        msg = MIMEMultipart()
        msg["From"] = self.email_address
        msg["To"] = to_address
        msg["Subject"] = subject

        # Attach body (plain text or HTML)
        content_type = "html" if html else "plain"
        msg.attach(MIMEText(body, content_type))

        # Connect and send
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()  # Upgrade to secure connection
            server.login(self.email_address, self.email_password)
            server.send_message(msg)

        return True

    except Exception as e:
        self.logger.error(f"Failed to send email: {e}")
        return False
```

**Key SMTP concepts:**

1. **SMTP (Simple Mail Transfer Protocol):** Standard for sending email
2. **Port 587:** Standard port for SMTP with STARTTLS
3. **STARTTLS:** Upgrades plain connection to encrypted
4. **Authentication:** Login with username/password

**The connection flow:**
```
Client                              SMTP Server
  │                                      │
  │  Connect to port 587                 │
  │ ──────────────────────────────────>  │
  │                                      │
  │  STARTTLS (upgrade to encrypted)     │
  │ ──────────────────────────────────>  │
  │                                      │
  │  AUTH LOGIN (credentials)            │
  │ ──────────────────────────────────>  │
  │                                      │
  │  MAIL FROM / RCPT TO / DATA          │
  │ ──────────────────────────────────>  │
  │                                      │
  │  QUIT                                │
  │ ──────────────────────────────────>  │
```

### 3. Folder Monitoring for New Files

```python
def check_folder_for_new_files(
    self,
    folder: Path,
    extensions: Optional[List[str]] = None
) -> List[Dict]:
    """Check if a folder has new files since last check."""
    folder = Path(folder)

    # Load previously seen files from state
    folder_key = str(folder.absolute())
    seen_files = set(self.state.get(f"folder_{folder_key}_files", []))

    new_files = []
    current_files = set()

    for item in folder.iterdir():
        if item.is_file():
            # Filter by extension if specified
            if extensions and item.suffix.lower() not in extensions:
                continue

            current_files.add(item.name)

            # Check if we've seen this file before
            if item.name not in seen_files:
                new_files.append({
                    "name": item.name,
                    "path": str(item),
                    "size": item.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        item.stat().st_mtime
                    ).isoformat()
                })

    # Update state for next run
    self.state[f"folder_{folder_key}_files"] = list(current_files)
    self._save_state()

    return new_files
```

**State management pattern:**
```python
# First run:
seen_files = set()  # Empty
current_files = {"a.pdf", "b.doc"}
new_files = ["a.pdf", "b.doc"]  # All are new!
# Save: {"a.pdf", "b.doc"}

# Second run (c.pdf added):
seen_files = {"a.pdf", "b.doc"}  # Loaded from state
current_files = {"a.pdf", "b.doc", "c.pdf"}
new_files = ["c.pdf"]  # Only c.pdf is new
# Save: {"a.pdf", "b.doc", "c.pdf"}
```

### 4. CSV Threshold Monitoring

```python
def check_csv_threshold(
    self,
    csv_path: Path,
    column: str,
    threshold: float,
    aggregate: str = "sum"
) -> Optional[Dict]:
    """Check if a CSV column exceeds a threshold."""

    # Read and parse CSV
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        values = []

        for row in reader:
            val = row.get(column, "")
            if val:
                cleaned = val.replace(",", "").replace("$", "").strip()
                try:
                    values.append(float(cleaned))
                except ValueError:
                    continue

    # Calculate aggregate
    if aggregate == "sum":
        result = sum(values)
    elif aggregate == "avg":
        result = sum(values) / len(values) if values else 0
    elif aggregate == "max":
        result = max(values) if values else 0
    elif aggregate == "count":
        result = len(values)

    # Check threshold
    if result > threshold:
        return {
            "type": "threshold_exceeded",
            "file": str(csv_path),
            "column": column,
            "aggregate": aggregate,
            "value": result,
            "threshold": threshold
        }

    return None  # No alert needed
```

**Use case example:**
```python
# expenses.csv has running total of $2,500
# Threshold set to $2,000

check_csv_threshold(
    csv_path="expenses.csv",
    column="amount",
    threshold=2000,
    aggregate="sum"
)
# Returns alert: "Sum of amount ($2,500) exceeds $2,000"
```

### 5. Todo Due Date Checking

```python
def check_todos_due_soon(self, days: int = 3) -> List[Dict]:
    """Check for to-do items due within N days."""
    todo_file = DATA_DIR / "todos" / "tasks.json"

    data = load_json(todo_file)
    tasks = data.get("tasks", [])

    today = datetime.now()
    due_soon = []

    for task in tasks:
        # Skip completed tasks
        if task.get("completed"):
            continue

        due_date_str = task.get("due_date")
        if not due_date_str:
            continue

        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
            days_until = (due_date - today).days

            if days_until <= days:  # Due within threshold
                due_soon.append({
                    "id": task.get("id"),
                    "title": task.get("title"),
                    "due_date": due_date_str,
                    "days_until": days_until,
                    "priority": task.get("priority", "medium"),
                    "overdue": days_until < 0
                })

        except ValueError:
            continue  # Invalid date format

    return due_soon
```

**Date math with datetime:**
```python
from datetime import datetime, timedelta

today = datetime.now()
due_date = datetime(2024, 12, 31)

# Calculate difference
delta = due_date - today
days_until = delta.days  # Integer number of days

# Check conditions
if days_until < 0:
    print("OVERDUE!")
elif days_until == 0:
    print("Due today!")
elif days_until <= 3:
    print("Due soon!")
```

### 6. Alert Formatting

```python
def format_alert_email(self) -> tuple:
    """Format all alerts into an email subject and body."""
    if not self.alerts:
        return None, None

    subject_parts = []
    body_parts = [
        "Python Scripts Toolkit - Alert Summary",
        "=" * 50,
        ""
    ]

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
            body_parts.append("THRESHOLD EXCEEDED")
            body_parts.append("-" * 40)
            body_parts.append(f"  Value: {alert['value']:,.2f}")
            body_parts.append(f"  Threshold: {alert['threshold']:,.2f}")
            body_parts.append("")

        elif alert["type"] == "todos_due_soon":
            subject_parts.append(f"{alert['count']} task(s) due soon")
            body_parts.append("TASKS DUE SOON")
            body_parts.append("-" * 40)
            for t in alert["tasks"]:
                status = "OVERDUE" if t["overdue"] else f"in {t['days_until']} days"
                body_parts.append(f"  [{t['priority']}] {t['title']} - {status}")

    subject = "Alert: " + ", ".join(subject_parts)
    body = "\n".join(body_parts)

    return subject, body
```

---

## Email Protocols

### SMTP vs Other Protocols

| Protocol | Purpose | Port |
|----------|---------|------|
| SMTP | Sending email | 25, 587, 465 |
| IMAP | Reading email (sync) | 143, 993 |
| POP3 | Reading email (download) | 110, 995 |

### Gmail Setup

1. **Enable 2-Factor Authentication** on your Google account
2. **Generate App Password:**
   - Go to Google Account → Security → App Passwords
   - Select "Mail" and your device
   - Copy the 16-character password

3. **Configure environment:**
   ```bash
   export EMAIL_ADDRESS="your.email@gmail.com"
   export EMAIL_PASSWORD="xxxx xxxx xxxx xxxx"  # App password
   export SMTP_SERVER="smtp.gmail.com"
   export SMTP_PORT="587"
   ```

### Alternative: SendGrid API

```python
import sendgrid
from sendgrid.helpers.mail import Mail

def send_via_sendgrid(to_email: str, subject: str, content: str):
    sg = sendgrid.SendGridAPIClient(api_key=os.environ.get('SENDGRID_API_KEY'))

    message = Mail(
        from_email='sender@example.com',
        to_emails=to_email,
        subject=subject,
        plain_text_content=content
    )

    response = sg.send(message)
    return response.status_code == 202
```

---

## Scheduling and Automation

### macOS: launchd

```xml
<!-- ~/Library/LaunchAgents/com.user.reminder.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.reminder</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/main.py</string>
        <string>remind</string>
        <string>--check-todos</string>
        <string>--check-folder</string>
        <string>/Users/me/Downloads</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>EnvironmentVariables</key>
    <dict>
        <key>EMAIL_ADDRESS</key>
        <string>your@email.com</string>
        <key>EMAIL_PASSWORD</key>
        <string>your-app-password</string>
    </dict>
</dict>
</plist>
```

Load with: `launchctl load ~/Library/LaunchAgents/com.user.reminder.plist`

### Linux: cron

```bash
# Edit crontab
crontab -e

# Add job (runs daily at 9 AM)
0 9 * * * EMAIL_ADDRESS=you@email.com EMAIL_PASSWORD=xxx /usr/bin/python3 /path/to/main.py remind --check-todos
```

**Cron format:**
```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, Sunday=0)
│ │ │ │ │
* * * * * command
```

### Windows: Task Scheduler

```powershell
# Create scheduled task
$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\path\to\main.py remind --check-todos"
$trigger = New-ScheduledTaskTrigger -Daily -At 9am
Register-ScheduledTask -TaskName "PythonReminder" -Action $action -Trigger $trigger
```

---

## Security Considerations

### Credential Storage

```python
# Best practices for credentials:

# 1. Environment variables (good for servers)
password = os.getenv("EMAIL_PASSWORD")

# 2. Keyring (good for desktop apps)
import keyring
password = keyring.get_password("reminder_app", "email")

# 3. AWS Secrets Manager (good for cloud)
import boto3
client = boto3.client('secretsmanager')
secret = client.get_secret_value(SecretId='email-credentials')

# 4. HashiCorp Vault (good for enterprise)
import hvac
client = hvac.Client(url='https://vault.example.com')
secret = client.secrets.kv.read_secret_version(path='email')
```

### What NOT to Do

```python
# DON'T commit credentials to git
EMAIL_PASSWORD = "actual_password"  # NEVER!

# DON'T log credentials
logger.info(f"Logging in with {password}")  # NEVER!

# DON'T store in plain text files
with open("password.txt") as f:  # Avoid this
    password = f.read()
```

### Secure Configuration Pattern

```python
# config.py
import os
from dataclasses import dataclass

@dataclass
class EmailConfig:
    address: str
    password: str
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587

    @classmethod
    def from_env(cls) -> "EmailConfig":
        address = os.getenv("EMAIL_ADDRESS")
        password = os.getenv("EMAIL_PASSWORD")

        if not address or not password:
            raise ValueError("Email credentials not configured")

        return cls(
            address=address,
            password=password,
            smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587"))
        )
```

---

## Extending the Project

### 1. Add Slack Notifications

```python
import requests

def send_slack_message(webhook_url: str, message: str):
    """Send message to Slack channel."""
    payload = {
        "text": message,
        "username": "Python Reminder Bot",
        "icon_emoji": ":robot_face:"
    }

    response = requests.post(webhook_url, json=payload)
    return response.status_code == 200

# Usage
send_slack_message(
    os.getenv("SLACK_WEBHOOK_URL"),
    "3 tasks due tomorrow!"
)
```

### 2. Add Discord Notifications

```python
def send_discord_message(webhook_url: str, message: str):
    """Send message to Discord channel."""
    payload = {"content": message}

    response = requests.post(webhook_url, json=payload)
    return response.status_code == 204
```

### 3. Add SMS via Twilio

```python
from twilio.rest import Client

def send_sms(to_number: str, message: str):
    """Send SMS via Twilio."""
    client = Client(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN")
    )

    message = client.messages.create(
        body=message,
        from_=os.getenv("TWILIO_PHONE_NUMBER"),
        to=to_number
    )

    return message.sid
```

### 4. Add Push Notifications (Pushover)

```python
def send_push_notification(title: str, message: str):
    """Send push notification via Pushover."""
    response = requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": os.getenv("PUSHOVER_APP_TOKEN"),
            "user": os.getenv("PUSHOVER_USER_KEY"),
            "title": title,
            "message": message,
            "priority": 1  # High priority
        }
    )

    return response.status_code == 200
```

### 5. Add Rate Limiting

```python
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_emails_per_hour: int = 10):
        self.max_per_hour = max_emails_per_hour
        self.sent_times: List[datetime] = []

    def can_send(self) -> bool:
        """Check if we can send another email."""
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)

        # Remove old entries
        self.sent_times = [t for t in self.sent_times if t > hour_ago]

        return len(self.sent_times) < self.max_per_hour

    def record_send(self):
        """Record that an email was sent."""
        self.sent_times.append(datetime.now())
```

---

## Summary

The Email Reminder teaches these core Python concepts:

| Concept | How It's Used |
|---------|---------------|
| `smtplib` | Email protocol implementation |
| `email.mime` | Message formatting |
| Environment variables | Secure credential management |
| State persistence | Tracking seen files/alerts |
| File monitoring | Detecting new files |
| Data aggregation | CSV threshold checking |
| Date arithmetic | Due date calculations |
| Scheduling | Cron/launchd integration |

This is a practical automation script that demonstrates patterns used in monitoring systems, alerting pipelines, and notification services.
