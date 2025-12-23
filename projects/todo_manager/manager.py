"""
CLI To-Do List Manager - Manage tasks stored in a local JSON file.

Usage:
    python -m projects.todo_manager.manager add "Buy groceries"
    python -m projects.todo_manager.manager add "Finish report" --priority high --due 2024-12-31
    python -m projects.todo_manager.manager list
    python -m projects.todo_manager.manager list --pending
    python -m projects.todo_manager.manager list --completed
    python -m projects.todo_manager.manager done 1
    python -m projects.todo_manager.manager delete 1
"""
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import TODO_MANAGER_CONFIG, DATA_DIR
from utils.logger import setup_logger
from utils.helpers import ensure_dir


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

    def to_dict(self) -> Dict[str, Any]:
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
        return cls(**data)

    def __str__(self) -> str:
        status = "[x]" if self.completed else "[ ]"
        priority_icons = {"low": "-", "medium": "~", "high": "!", "critical": "!!"}
        pri = priority_icons.get(self.priority, "~")

        parts = [f"{status} {self.id}. ({pri}) {self.title}"]

        if self.due_date:
            parts.append(f"  Due: {self.due_date}")

        return " ".join(parts)


class TodoManager:
    """Manages a collection of to-do tasks."""

    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = Path(data_file or TODO_MANAGER_CONFIG["data_file"])
        self.logger = setup_logger("todo_manager")
        self.tasks: List[Task] = []
        self._load()

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
                indent=2
            )

    def _get_next_id(self) -> int:
        """Get the next available task ID."""
        if not self.tasks:
            return 1
        return max(t.id for t in self.tasks) + 1

    def add(
        self,
        title: str,
        priority: str = "medium",
        due_date: Optional[str] = None
    ) -> Task:
        """Add a new task."""
        if priority not in TODO_MANAGER_CONFIG["priorities"]:
            priority = "medium"

        task = Task(
            id=self._get_next_id(),
            title=title,
            priority=priority,
            due_date=due_date
        )

        self.tasks.append(task)
        self._save()
        self.logger.info(f"Added task #{task.id}: {title}")
        return task

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
            t.completed,
            priority_order.get(t.priority, 0),
            t.due_date or "9999-99-99"
        ))

        return filtered

    def mark_done(self, task_id: int) -> Optional[Task]:
        """Mark a task as completed."""
        for task in self.tasks:
            if task.id == task_id:
                task.completed = True
                task.completed_at = datetime.now().isoformat()
                self._save()
                self.logger.info(f"Completed task #{task_id}: {task.title}")
                return task

        self.logger.warning(f"Task #{task_id} not found")
        return None

    def mark_undone(self, task_id: int) -> Optional[Task]:
        """Mark a task as not completed."""
        for task in self.tasks:
            if task.id == task_id:
                task.completed = False
                task.completed_at = None
                self._save()
                self.logger.info(f"Reopened task #{task_id}: {task.title}")
                return task

        self.logger.warning(f"Task #{task_id} not found")
        return None

    def delete(self, task_id: int) -> bool:
        """Delete a task."""
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                deleted = self.tasks.pop(i)
                self._save()
                self.logger.info(f"Deleted task #{task_id}: {deleted.title}")
                return True

        self.logger.warning(f"Task #{task_id} not found")
        return False

    def edit(
        self,
        task_id: int,
        title: Optional[str] = None,
        priority: Optional[str] = None,
        due_date: Optional[str] = None
    ) -> Optional[Task]:
        """Edit an existing task."""
        for task in self.tasks:
            if task.id == task_id:
                if title:
                    task.title = title
                if priority and priority in TODO_MANAGER_CONFIG["priorities"]:
                    task.priority = priority
                if due_date:
                    task.due_date = due_date

                self._save()
                self.logger.info(f"Updated task #{task_id}")
                return task

        self.logger.warning(f"Task #{task_id} not found")
        return None

    def clear_completed(self) -> int:
        """Remove all completed tasks."""
        original_count = len(self.tasks)
        self.tasks = [t for t in self.tasks if not t.completed]
        removed = original_count - len(self.tasks)
        self._save()
        self.logger.info(f"Cleared {removed} completed tasks")
        return removed

    def get_stats(self) -> Dict[str, int]:
        """Get task statistics."""
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks if t.completed)
        pending = total - completed

        by_priority = {}
        for p in TODO_MANAGER_CONFIG["priorities"]:
            by_priority[p] = sum(1 for t in self.tasks if t.priority == p and not t.completed)

        overdue = 0
        today = datetime.now().strftime("%Y-%m-%d")
        for t in self.tasks:
            if not t.completed and t.due_date and t.due_date < today:
                overdue += 1

        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "overdue": overdue,
            **{f"pending_{k}": v for k, v in by_priority.items()}
        }


def format_task_list(tasks: List[Task]) -> str:
    """Format a list of tasks for display."""
    if not tasks:
        return "No tasks found."

    lines = ["-" * 50]
    for task in tasks:
        lines.append(str(task))
    lines.append("-" * 50)
    lines.append(f"Total: {len(tasks)} task(s)")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="CLI To-Do List Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Priority levels: low, medium, high, critical

Examples:
  %(prog)s add "Buy groceries"
  %(prog)s add "Finish report" --priority high --due 2024-12-31
  %(prog)s list
  %(prog)s list --pending
  %(prog)s done 1
  %(prog)s delete 1
  %(prog)s edit 1 --title "New title" --priority high
  %(prog)s clear
  %(prog)s stats
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("title", help="Task title")
    add_parser.add_argument(
        "--priority", "-p",
        choices=TODO_MANAGER_CONFIG["priorities"],
        default="medium",
        help="Task priority"
    )
    add_parser.add_argument("--due", "-d", help="Due date (YYYY-MM-DD)")

    # List command
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("--pending", action="store_true", help="Show only pending tasks")
    list_parser.add_argument("--completed", action="store_true", help="Show only completed tasks")
    list_parser.add_argument(
        "--priority", "-p",
        choices=TODO_MANAGER_CONFIG["priorities"],
        help="Filter by priority"
    )

    # Done command
    done_parser = subparsers.add_parser("done", help="Mark task as completed")
    done_parser.add_argument("id", type=int, help="Task ID")

    # Undone command
    undone_parser = subparsers.add_parser("undone", help="Mark task as not completed")
    undone_parser.add_argument("id", type=int, help="Task ID")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a task")
    delete_parser.add_argument("id", type=int, help="Task ID")

    # Edit command
    edit_parser = subparsers.add_parser("edit", help="Edit a task")
    edit_parser.add_argument("id", type=int, help="Task ID")
    edit_parser.add_argument("--title", "-t", help="New title")
    edit_parser.add_argument(
        "--priority", "-p",
        choices=TODO_MANAGER_CONFIG["priorities"],
        help="New priority"
    )
    edit_parser.add_argument("--due", "-d", help="New due date (YYYY-MM-DD)")

    # Clear command
    subparsers.add_parser("clear", help="Clear all completed tasks")

    # Stats command
    subparsers.add_parser("stats", help="Show task statistics")

    args = parser.parse_args()
    manager = TodoManager()

    if args.command == "add":
        task = manager.add(args.title, args.priority, args.due)
        print(f"Added: {task}")

    elif args.command == "list":
        show_completed = not args.pending
        show_pending = not args.completed
        tasks = manager.list_tasks(show_completed, show_pending, args.priority)
        print(format_task_list(tasks))

    elif args.command == "done":
        task = manager.mark_done(args.id)
        if task:
            print(f"Completed: {task}")

    elif args.command == "undone":
        task = manager.mark_undone(args.id)
        if task:
            print(f"Reopened: {task}")

    elif args.command == "delete":
        if manager.delete(args.id):
            print(f"Deleted task #{args.id}")

    elif args.command == "edit":
        task = manager.edit(args.id, args.title, args.priority, args.due)
        if task:
            print(f"Updated: {task}")

    elif args.command == "clear":
        count = manager.clear_completed()
        print(f"Cleared {count} completed task(s)")

    elif args.command == "stats":
        stats = manager.get_stats()
        print("\n" + "=" * 40)
        print("TASK STATISTICS")
        print("=" * 40)
        print(f"Total tasks:      {stats['total']}")
        print(f"Completed:        {stats['completed']}")
        print(f"Pending:          {stats['pending']}")
        print(f"Overdue:          {stats['overdue']}")
        print("-" * 40)
        print("Pending by priority:")
        for p in TODO_MANAGER_CONFIG["priorities"]:
            print(f"  {p.capitalize():12} {stats.get(f'pending_{p}', 0)}")
        print("=" * 40)

    else:
        # Default: show all tasks
        tasks = manager.list_tasks()
        print(format_task_list(tasks))


if __name__ == "__main__":
    main()
