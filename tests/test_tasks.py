"""Tests for TaskService CRUD, filters, and state toggles."""
from datetime import date
from app.services.task_service import TaskService


def test_task_crud_and_status_toggle(test_db_session):
    """Verify task creation, toggle completion, update, and deletion."""
    task = TaskService.create_task(
        session=test_db_session,
        description="Write unit tests for parser",
        due_date=date(2026, 11, 14),
        priority="High",
    )
    assert task.status == "Pending"
    assert task.completed_at is None

    # Toggle to completed
    TaskService.toggle_task_status(test_db_session, task.id)
    assert task.status == "Completed"
    assert task.completed_at is not None

    # Reopen
    TaskService.toggle_task_status(test_db_session, task.id)
    assert task.status == "Pending"
    assert task.completed_at is None

    # Update description & priority
    TaskService.update_task(
        session=test_db_session,
        task_id=task.id,
        description="Write thorough unit tests",
        priority="Medium",
    )
    assert task.description == "Write thorough unit tests"
    assert task.priority == "Medium"

    # Delete
    del_res = TaskService.delete_task(test_db_session, task.id)
    assert del_res is True
    assert TaskService.get_task_by_id(test_db_session, task.id) is None


def test_task_filtering_and_counts(test_db_session):
    """Verify status and priority filtering and count aggregates."""
    t1 = TaskService.create_task(test_db_session, "Task 1", priority="High")
    t2 = TaskService.create_task(test_db_session, "Task 2", priority="Low")
    t3 = TaskService.create_task(test_db_session, "Task 3", priority="High")

    TaskService.toggle_task_status(test_db_session, t1.id)  # Complete t1

    counts = TaskService.get_counts(test_db_session)
    assert counts["total"] == 3
    assert counts["pending"] == 2
    assert counts["completed"] == 1

    pending_high = TaskService.get_tasks(test_db_session, status="Pending", priority="High")
    assert len(pending_high) == 1
    assert pending_high[0].id == t3.id

