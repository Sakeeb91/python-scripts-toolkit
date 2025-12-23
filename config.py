"""
Global configuration for the Python Scripts Toolkit.
"""
from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"

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
