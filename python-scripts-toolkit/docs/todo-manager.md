# CLI To-Do Manager - Technical Documentation

A command-line task management application that stores tasks in a local JSON file with support for priorities, due dates, and filtering.

## Table of Contents

- [Concepts Overview](#concepts-overview)
- [Technologies Used](#technologies-used)
- [Core Code Explained](#core-code-explained)
- [Data Modeling](#data-modeling)
- [CLI Design Patterns](#cli-design-patterns)
- [Extending the Project](#extending-the-project)

---

## Concepts Overview

### What Problem Does This Solve?

Task management is a fundamental need for productivity. While many apps exist, a CLI tool offers:

1. **Speed:** No GUI overhead, keyboard-driven
2. **Scriptability:** Can be integrated into shell scripts
3. **Portability:** JSON storage works anywhere
4. **Learning:** Demonstrates core programming patterns

### Feature Overview

```
$ python main.py todo add "Write documentation" --priority high --due 2024-12-31
Added: [ ] 1. (!) Write documentation  Due: 2024-12-31

$ python main.py todo list
--------------------------------------------------
[ ] 1. (!) Write documentation  Due: 2024-12-31
[ ] 2. (~) Review pull requests
[x] 3. (-) Check emails
--------------------------------------------------
Total: 3 task(s)

$ python main.py todo done --id 1
Completed: [x] 1. (!) Write documentation

$ python main.py todo stats
========================================
TASK STATISTICS
========================================
Total tasks:      3
Completed:        2
Pending:          1
Overdue:          0
----------------------------------------
Pending by priority:
  Low          0
  Medium       1
  High         0
  Critical     0
========================================
```

---

## Technologies Used

### Standard Library Modules

| Module | Purpose | Why We Use It |
|--------|---------|---------------|
| `json` | Data persistence | Human-readable, easy to debug |
| `argparse` | CLI with subcommands | Professional command structure |
| `datetime` | Due dates and timestamps | Date comparisons, formatting |
| `typing` | Type annotations | Code documentation, IDE support |
| `dataclasses` (alternative) | Data containers | Cleaner than manual `__init__` |

### Why JSON for Storage?

```python
# JSON advantages:
# 1. Human-readable (can edit manually if needed)
# 2. Universal format (works with any language)
# 3. Built into Python (no dependencies)

# JSON file structure:
{
    "tasks": [
        {
            "id": 1,
            "title": "Write documentation",
            "priority": "high",
            "due_date": "2024-12-31",
            "completed": false,
            "created_at": "2024-01-15T10:30:00",
            "completed_at": null
        }
    ]
}
```

**Alternatives and when to use them:**

| Format | Best For | Trade-offs |
|--------|----------|------------|
| JSON | Simple data, human-readable | No schema validation |
| SQLite | Queries, relationships | Requires SQL knowledge |
| pickle | Python objects | Not human-readable, security risks |
| YAML | Config with comments | Requires `pyyaml` library |

---

## Core Code Explained

### 1. The Task Data Model

```python
class Task:
    """Represents a single to-do task."""

    def __init__(
        self,
        id: int,
        title: str,
        priority: str = "medium",
        due_date: Optional[str] = None,
        completed: bool = False,
        created_at: Optional[str] = None,
        completed_at: Optional[str] = None
    ):
        self.id = id
        self.title = title
        self.priority = priority
        self.due_date = due_date
        self.completed = completed
        self.created_at = created_at or datetime.now().isoformat()
        self.completed_at = completed_at
```

**Design decisions:**
- **ID:** Integer for easy reference (`todo done --id 1`)
- **Priority:** String enum from config (`low`, `medium`, `high`, `critical`)
- **Dates as strings:** ISO format for JSON serialization
- **Optional fields:** `None` for unset values

### 2. Serialization (Object ↔ Dictionary ↔ JSON)

```python
class Task:
    def to_dict(self) -> Dict[str, Any]:
        """Convert Task to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority,
            "due_date": self.due_date,
            "completed": self.completed,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create Task from dictionary (JSON deserialization)."""
        return cls(**data)  # Unpack dict as keyword arguments
```

**The serialization flow:**
```
Task Object  ──to_dict()──>  Dictionary  ──json.dump()──>  JSON String
    ↑                                                            │
    │                                                            │
    └──from_dict()──  Dictionary  <──json.load()──  JSON File ◄──┘
```

**Why `@classmethod`?**
```python
# Regular method - needs existing instance
task = Task(1, "test")
task.some_method()

# Class method - creates new instance
task = Task.from_dict({"id": 1, "title": "test"})

# The 'cls' parameter is the class itself
@classmethod
def from_dict(cls, data):
    return cls(**data)  # Same as Task(**data)
```

### 3. The TodoManager Class

```python
class TodoManager:
    """Manages a collection of to-do tasks."""

    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = Path(data_file or TODO_MANAGER_CONFIG["data_file"])
        self.logger = setup_logger("todo_manager")
        self.tasks: List[Task] = []
        self._load()  # Load existing tasks on init

    def _load(self) -> None:
        """Load tasks from the JSON file."""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
            except (json.JSONDecodeError, KeyError) as e:
                self.logger.warning(f"Error loading tasks: {e}")
                self.tasks = []

    def _save(self) -> None:
        """Save tasks to the JSON file."""
        ensure_dir(self.data_file.parent)
        with open(self.data_file, 'w') as f:
            json.dump(
                {"tasks": [t.to_dict() for t in self.tasks]},
                f,
                indent=2  # Pretty print for readability
            )
```

**Pattern: Load on init, save after changes**
```python
manager = TodoManager()  # Loads existing tasks
manager.add("New task")  # Adds and saves
manager.mark_done(1)     # Updates and saves
# No explicit save() call needed - automatic persistence
```

### 4. CRUD Operations

**Create:**
```python
def add(self, title: str, priority: str = "medium", due_date: Optional[str] = None) -> Task:
    """Add a new task."""
    if priority not in TODO_MANAGER_CONFIG["priorities"]:
        priority = "medium"  # Fallback to default

    task = Task(
        id=self._get_next_id(),  # Auto-increment ID
        title=title,
        priority=priority,
        due_date=due_date
    )

    self.tasks.append(task)
    self._save()  # Persist immediately
    return task

def _get_next_id(self) -> int:
    """Get the next available task ID."""
    if not self.tasks:
        return 1
    return max(t.id for t in self.tasks) + 1
```

**Read (with filtering):**
```python
def list_tasks(
    self,
    show_completed: bool = True,
    show_pending: bool = True,
    priority: Optional[str] = None
) -> List[Task]:
    """List tasks with optional filters."""
    filtered = self.tasks

    if not show_completed:
        filtered = [t for t in filtered if not t.completed]
    if not show_pending:
        filtered = [t for t in filtered if t.completed]
    if priority:
        filtered = [t for t in filtered if t.priority == priority]

    # Sort: incomplete first, then by priority, then by due date
    priority_order = {p: i for i, p in enumerate(reversed(TODO_MANAGER_CONFIG["priorities"]))}

    filtered.sort(key=lambda t: (
        t.completed,                           # False (0) before True (1)
        priority_order.get(t.priority, 0),     # Higher priority first
        t.due_date or "9999-99-99"             # Earlier dates first, None last
    ))

    return filtered
```

**Update:**
```python
def mark_done(self, task_id: int) -> Optional[Task]:
    """Mark a task as completed."""
    for task in self.tasks:
        if task.id == task_id:
            task.completed = True
            task.completed_at = datetime.now().isoformat()
            self._save()
            return task

    self.logger.warning(f"Task #{task_id} not found")
    return None

def edit(self, task_id: int, title: Optional[str] = None, ...) -> Optional[Task]:
    """Edit an existing task."""
    for task in self.tasks:
        if task.id == task_id:
            if title:
                task.title = title
            # ... update other fields
            self._save()
            return task
    return None
```

**Delete:**
```python
def delete(self, task_id: int) -> bool:
    """Delete a task."""
    for i, task in enumerate(self.tasks):
        if task.id == task_id:
            deleted = self.tasks.pop(i)  # Remove and get the task
            self._save()
            return True
    return False
```

### 5. Display Formatting

```python
class Task:
    def __str__(self) -> str:
        """Human-readable task representation."""
        status = "[x]" if self.completed else "[ ]"

        priority_icons = {
            "low": "-",
            "medium": "~",
            "high": "!",
            "critical": "!!"
        }
        pri = priority_icons.get(self.priority, "~")

        parts = [f"{status} {self.id}. ({pri}) {self.title}"]

        if self.due_date:
            parts.append(f"  Due: {self.due_date}")

        return " ".join(parts)

# Output: [ ] 1. (!) Write documentation  Due: 2024-12-31
```

**Why `__str__`?**
```python
task = Task(1, "Test", "high")

# Without __str__:
print(task)  # <Task object at 0x7f...>

# With __str__:
print(task)  # [ ] 1. (!) Test
str(task)    # Also uses __str__
f"{task}"    # Also uses __str__
```

### 6. CLI with Subcommands

```python
def main():
    parser = argparse.ArgumentParser(description="CLI To-Do List Manager")

    # Create subparsers for each command
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("title", help="Task title")
    add_parser.add_argument("--priority", "-p", choices=["low", "medium", "high", "critical"])
    add_parser.add_argument("--due", "-d", help="Due date (YYYY-MM-DD)")

    # List command
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("--pending", action="store_true")
    list_parser.add_argument("--completed", action="store_true")

    # Done command
    done_parser = subparsers.add_parser("done", help="Mark task as completed")
    done_parser.add_argument("id", type=int, help="Task ID")

    # Parse and route
    args = parser.parse_args()

    if args.command == "add":
        manager.add(args.title, args.priority, args.due)
    elif args.command == "list":
        tasks = manager.list_tasks(...)
    # ...
```

**Resulting CLI structure:**
```
todo add "Task" --priority high --due 2024-12-31
todo list --pending
todo done 1
todo delete 1
todo edit 1 --title "New title"
todo stats
```

---

## Data Modeling

### Entity-Relationship

```
┌─────────────────────────────────────┐
│              Task                    │
├─────────────────────────────────────┤
│ id: int (primary key)               │
│ title: str                          │
│ priority: enum [low|medium|high|...]│
│ due_date: date (optional)           │
│ completed: bool                     │
│ created_at: datetime                │
│ completed_at: datetime (optional)   │
└─────────────────────────────────────┘
```

### Alternative: Using dataclasses

```python
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class Task:
    id: int
    title: str
    priority: str = "medium"
    due_date: Optional[str] = None
    completed: bool = False
    created_at: str = None
    completed_at: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

    def to_dict(self):
        return asdict(self)  # Built-in conversion

# Dataclass gives you:
# - __init__ automatically
# - __repr__ automatically
# - __eq__ automatically
# - Type hints as documentation
```

### Alternative: Using Pydantic

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Task(BaseModel):
    id: int
    title: str
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    due_date: Optional[str] = None
    completed: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

# Pydantic gives you:
# - Automatic validation
# - JSON serialization
# - Schema generation
# - Type coercion
```

---

## CLI Design Patterns

### Subcommand Pattern

```
main_command subcommand [arguments] [options]

git commit -m "message"     # git is main, commit is subcommand
docker run -d nginx         # docker is main, run is subcommand
todo add "Task" --priority high
```

### Option Naming Conventions

```python
# Short options: single dash, single letter
-p, -v, -h

# Long options: double dash, full word
--priority, --verbose, --help

# Combined:
parser.add_argument("--priority", "-p", ...)

# Boolean flags (store_true)
parser.add_argument("--verbose", "-v", action="store_true")

# Required positional arguments
parser.add_argument("title")  # No dashes = positional

# Optional positional
parser.add_argument("title", nargs="?", default="Untitled")
```

### Exit Codes

```python
import sys

def main():
    try:
        result = do_operation()
        sys.exit(0)  # Success
    except FileNotFoundError:
        print("Error: File not found", file=sys.stderr)
        sys.exit(1)  # General error
    except PermissionError:
        print("Error: Permission denied", file=sys.stderr)
        sys.exit(2)  # Specific error code
```

**Convention:**
- `0` = Success
- `1` = General error
- `2+` = Specific errors

---

## Extending the Project

### 1. Add Tags/Labels

```python
@dataclass
class Task:
    # ... existing fields
    tags: List[str] = field(default_factory=list)

# CLI
todo add "Task" --tags work,urgent
todo list --tag work

# Filter
def list_tasks(self, tag: Optional[str] = None):
    if tag:
        filtered = [t for t in filtered if tag in t.tags]
```

### 2. Add Recurring Tasks

```python
from enum import Enum

class Recurrence(Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

@dataclass
class Task:
    recurrence: Recurrence = Recurrence.NONE

def mark_done(self, task_id: int):
    task = self.get_task(task_id)
    task.completed = True

    if task.recurrence != Recurrence.NONE:
        # Create next occurrence
        next_task = self._create_recurring(task)
        self.tasks.append(next_task)
```

### 3. Add Subtasks

```python
@dataclass
class Task:
    id: int
    title: str
    parent_id: Optional[int] = None  # For subtasks
    subtasks: List[int] = field(default_factory=list)

def add_subtask(self, parent_id: int, title: str):
    parent = self.get_task(parent_id)
    subtask = Task(id=self._get_next_id(), title=title, parent_id=parent_id)
    parent.subtasks.append(subtask.id)
    self.tasks.append(subtask)
```

### 4. Add Time Tracking

```python
@dataclass
class Task:
    time_spent_minutes: int = 0
    time_entries: List[Dict] = field(default_factory=list)

def start_timer(self, task_id: int):
    task = self.get_task(task_id)
    task.time_entries.append({
        "started_at": datetime.now().isoformat(),
        "stopped_at": None
    })

def stop_timer(self, task_id: int):
    task = self.get_task(task_id)
    entry = task.time_entries[-1]
    entry["stopped_at"] = datetime.now().isoformat()

    # Calculate duration
    start = datetime.fromisoformat(entry["started_at"])
    stop = datetime.fromisoformat(entry["stopped_at"])
    minutes = (stop - start).total_seconds() / 60
    task.time_spent_minutes += int(minutes)
```

### 5. Add Sync with Cloud

```python
import requests

class CloudSync:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key

    def push(self, tasks: List[Task]):
        """Push local tasks to cloud."""
        response = requests.post(
            f"{self.api_url}/tasks",
            json={"tasks": [t.to_dict() for t in tasks]},
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return response.ok

    def pull(self) -> List[Task]:
        """Pull tasks from cloud."""
        response = requests.get(
            f"{self.api_url}/tasks",
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        data = response.json()
        return [Task.from_dict(t) for t in data["tasks"]]
```

---

## Summary

The Todo Manager teaches these core Python concepts:

| Concept | How It's Used |
|---------|---------------|
| Classes | Task and TodoManager encapsulation |
| JSON | Data persistence and serialization |
| Type hints | Documentation and IDE support |
| argparse | CLI with subcommands |
| List operations | Filtering, sorting, CRUD |
| Datetime | Timestamps and due dates |
| File I/O | Reading/writing JSON files |
| Error handling | Graceful loading failures |

This is a practical CLI application that demonstrates patterns used in real-world task management tools and database-backed applications.
