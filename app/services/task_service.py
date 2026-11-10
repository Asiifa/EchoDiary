"""Task management service for database persistence and querying."""
from datetime import datetime, date, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from app.models.task import Task
from app.utils.date_utils import parse_date


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TaskService:
    """Task operations use the caller-owned session and return session-bound ORM rows.

    Callers must copy values needed beyond the session scope into plain data.
    """

    @staticmethod
    def create_task(
        session: Session,
        description: str,
        diary_entry_id: Optional[str] = None,
        due_date: Optional[date] = None,
        priority: str = "Medium",
    ) -> Task:
        """Create and flush a task; the returned ORM object belongs to ``session``."""
        task = Task(
            description=description.strip(),
            diary_entry_id=diary_entry_id,
            due_date=due_date,
            priority=priority,
            status="Pending",
            created_at=utc_now(),
        )
        session.add(task)
        session.flush()
        return task

    @staticmethod
    def get_tasks(
        session: Session,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        sort_by_due_date: bool = True,
    ) -> List[Task]:
        """Fetch session-bound task rows using optional filters and sorting."""
        query = session.query(Task)
        if status and status != "All":
            query = query.filter(Task.status == status)
        if priority and priority != "All":
            query = query.filter(Task.priority == priority)

        if sort_by_due_date:
            # Null due dates last, then by due date ascending
            query = query.order_by(Task.due_date.is_(None), Task.due_date.asc(), desc(Task.created_at))
        else:
            query = query.order_by(desc(Task.created_at))

        return query.all()

    @staticmethod
    def get_task_by_id(session: Session, task_id: str) -> Optional[Task]:
        """Find a task by primary key; the result remains bound to ``session``."""
        return session.query(Task).filter(Task.id == task_id).first()

    @staticmethod
    def toggle_task_status(session: Session, task_id: str) -> Optional[Task]:
        """Toggle status and return the session-bound row, if found."""
        task = TaskService.get_task_by_id(session, task_id)
        if not task:
            return None
        if task.status == "Completed":
            task.reopen()
        else:
            task.mark_completed()
        session.flush()
        return task

    @staticmethod
    def update_task(
        session: Session,
        task_id: str,
        description: Optional[str] = None,
        due_date: Optional[date] = None,
        priority: Optional[str] = None,
    ) -> Optional[Task]:
        """Update task fields and return the session-bound row, if found."""
        task = TaskService.get_task_by_id(session, task_id)
        if not task:
            return None
        if description is not None:
            task.description = description.strip()
        if due_date is not None:
            task.due_date = due_date
        if priority is not None:
            task.priority = priority
        session.flush()
        return task

    @staticmethod
    def delete_task(session: Session, task_id: str) -> bool:
        """Delete a task from database."""
        task = TaskService.get_task_by_id(session, task_id)
        if not task:
            return False
        session.delete(task)
        session.flush()
        return True

    @staticmethod
    def get_counts(session: Session) -> Dict[str, int]:
        """Get total, pending, and completed task counts."""
        total = session.query(Task).count()
        pending = session.query(Task).filter(Task.status == "Pending").count()
        completed = session.query(Task).filter(Task.status == "Completed").count()
        return {"total": total, "pending": pending, "completed": completed}
