"""
Global configuration for the Python Scripts Toolkit.
"""
from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
MANIFESTS_DIR = DATA_DIR / "manifests"

# File Organizer settings
FILE_ORGANIZER_CONFIG = {
    "categories": {
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".heic"],
        "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx", ".ppt", ".pptx"],
        "Code": [".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".h", ".go", ".rs", ".rb"],
        "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
        "Videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"],
        "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"],
        "Data": [".csv", ".json", ".xml", ".yaml", ".yml", ".sql", ".db"],
        "Executables": [".exe", ".msi", ".dmg", ".app", ".deb", ".rpm"],
    },
    "default_category": "Other",
    # Date-based organization settings
    "date_formats": {
        "YYYY/MM": "%Y/%m",           # e.g., 2024/01
        "YYYY/Month": "%Y/%B",        # e.g., 2024/January
        "YYYY-MM-DD": "%Y-%m-%d",     # e.g., 2024-01-15
        "YYYY/MM/DD": "%Y/%m/%d",     # e.g., 2024/01/15
    },
    "default_date_format": "YYYY/Month",
    "date_types": ["modified", "created"],
    "default_date_type": "modified",
}

# CSV Reporter settings
CSV_REPORTER_CONFIG = {
    "date_columns": ["date", "Date", "DATE", "timestamp", "Timestamp", "created_at"],
    "amount_columns": ["amount", "Amount", "AMOUNT", "price", "Price", "cost", "Cost", "total", "Total"],
    "category_columns": ["category", "Category", "CATEGORY", "type", "Type"],
}

# Web Scraper settings
WEB_SCRAPER_CONFIG = {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "timeout": 10,
    "retry_attempts": 3,
    "retry_delay": 2,
    # Rate limiting settings
    "delay": 0,              # Fixed delay between requests (seconds)
    "random_delay": None,    # Random delay range tuple (min, max) in seconds
    "respect_rate_limits": False,  # Parse and respect server rate limit headers
}

# Todo Manager settings
TODO_MANAGER_CONFIG = {
    "data_file": DATA_DIR / "todos" / "tasks.json",
    "priorities": ["low", "medium", "high", "critical"],
}

# Email Reminder settings
EMAIL_REMINDER_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "use_tls": True,
}
