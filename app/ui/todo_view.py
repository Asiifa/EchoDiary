"""To-Do List management view: filtering, status toggling, task editing, and export."""
from datetime import date
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QDateEdit, QListWidget, QListWidgetItem,
    QFrame, QMessageBox, QCheckBox, QDialog, QDialogButtonBox,
    QFileDialog, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QSize
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.services.task_service import TaskService
from app.services.export_service import ExportService
from app.utils.date_utils import format_display_date, parse_date, get_today_date
from app.config import Config
from app.ui.styles import PRIORITY_STYLES


class EditTaskDialog(QDialog):
    """Dialog to create or edit a task."""

    def __init__(self, task: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Task" if task else "Add New Task")
        self.resize(460, 260)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        desc_lbl = QLabel("Task Description:")
        desc_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        self.desc_input = QLineEdit()
        if task:
            self.desc_input.setText(task["description"])
        self.desc_input.setPlaceholderText("e.g., Submit literature survey")
        layout.addWidget(desc_lbl)
        layout.addWidget(self.desc_input)

        row = QHBoxLayout()
        row.setSpacing(12)

        prio_box = QVBoxLayout()
        prio_lbl = QLabel("Priority:")
        prio_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        self.prio_combo = QComboBox()
        self.prio_combo.addItems(["Low", "Medium", "High"])
        if task and task["priority"] in ["Low", "Medium", "High"]:
            self.prio_combo.setCurrentText(task["priority"])
        else:
            self.prio_combo.setCurrentText("Medium")
        prio_box.addWidget(prio_lbl)
        prio_box.addWidget(self.prio_combo)
        row.addLayout(prio_box)

        due_box = QVBoxLayout()
        due_lbl = QLabel("Due Date:")
        due_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        self.chk_has_due = QCheckBox("Set deadline")
        self.due_edit = QDateEdit()
        self.due_edit.setCalendarPopup(True)
        self.due_edit.setDate(get_today_date())
        self.due_edit.setEnabled(False)

        if task and task["due_date"]:
            self.chk_has_due.setChecked(True)
            self.due_edit.setEnabled(True)
            self.due_edit.setDate(task["due_date"])

        self.chk_has_due.toggled.connect(self.due_edit.setEnabled)
        due_box.addWidget(due_lbl)
        due_box_inner = QHBoxLayout()
        due_box_inner.addWidget(self.chk_has_due)
        due_box_inner.addWidget(self.due_edit)
        due_box.addLayout(due_box_inner)
        row.addLayout(due_box)

        layout.addLayout(row)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self):
        desc = self.desc_input.text().strip()
        prio = self.prio_combo.currentText()
        due = self.due_edit.date().toPython() if self.chk_has_due.isChecked() else None
        return {"description": desc, "priority": prio, "due_date": due}


class TaskItemWidget(QFrame):
    """Card widget rendering a single to-do item with status, tags, and controls."""

    def __init__(self, task: Dict[str, Any], on_toggle, on_edit, on_delete, on_view_entry, parent=None):
        super().__init__(parent)
        self.task_id = task["id"]
        self.diary_entry_id = task["diary_entry_id"]
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.setStyleSheet("""
            TaskItemWidget {
                background-color: #FFFFFF;
                border: 1px solid #E5E2DE;
                border-radius: 10px;
                padding: 8px 14px;
            }
            TaskItemWidget:hover {
                border-color: #E5E2DE;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Checkbox for status
        self.chk_status = QCheckBox()
        self.chk_status.setChecked(task["status"] == "Completed")
        self.chk_status.stateChanged.connect(lambda: on_toggle(self.task_id))
        layout.addWidget(self.chk_status)

        # Description and metadata column
        desc_box = QVBoxLayout()
        desc_box.setSpacing(2)

        desc_lbl = QLabel(task["description"])
        is_done = task["status"] == "Completed"
        if is_done:
            desc_lbl.setStyleSheet("font-size: 14px; color: #96979E; text-decoration: line-through;")
        else:
            desc_lbl.setStyleSheet("font-size: 14px; font-weight: 500; color: #252833;")
        desc_lbl.setWordWrap(True)
        desc_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        desc_box.addWidget(desc_lbl)

        # Tags row (Due date, Entry link, Created)
        tags_row = QHBoxLayout()
        tags_row.setSpacing(8)

        # Priority tag
        priority = task["priority"]
        priority_style = PRIORITY_STYLES.get(priority, PRIORITY_STYLES["Default"])
        p_lbl = QLabel(f"● {priority}")
        p_lbl.setStyleSheet(
            f"color: {priority_style['foreground']}; "
            f"background-color: {priority_style['background']}; "
            "font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px;"
        )
        tags_row.addWidget(p_lbl)

        if task["due_date"]:
            due_lbl = QLabel(f"📅 Due: {task['due_date'].isoformat()}")
            due_lbl.setStyleSheet("color: #8F6740; font-size: 11px; font-weight: 500;")
            tags_row.addWidget(due_lbl)

        if self.diary_entry_id:
            btn_entry_link = QPushButton("🎙 From Diary")
            btn_entry_link.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #9A8BB8;
                    font-size: 11px;
                    font-weight: 600;
                    border: none;
                    padding: 0;
                }
                QPushButton:hover {
                    text-decoration: underline;
                }
            """)
            btn_entry_link.clicked.connect(lambda: on_view_entry(self.diary_entry_id))
            tags_row.addWidget(btn_entry_link)

        tags_row.addStretch()
        desc_box.addLayout(tags_row)
        layout.addLayout(desc_box, stretch=1)

        # Action buttons
        btn_edit = QPushButton("✎")
        btn_edit.setToolTip("Edit Task")
        btn_edit.setStyleSheet("""
            QPushButton {
                background: #F5F3EF;
                color: #344C59;
                border: 1px solid #E5E2DE;
                border-radius: 6px;
                padding: 4px 8px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #EFECF3;
            }
        """)
        btn_edit.clicked.connect(lambda: on_edit(task))

        btn_del = QPushButton("✕")
        btn_del.setToolTip("Delete Task")
        btn_del.setStyleSheet("""
            QPushButton {
                background: #FFF5F5;
                color: #E53E3E;
                border: 1px solid #FEB2B2;
                border-radius: 6px;
                padding: 4px 8px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #FED7D7;
            }
        """)
        btn_del.clicked.connect(lambda: on_delete(self.task_id))

        layout.addWidget(btn_edit)
        layout.addWidget(btn_del)


class TodoView(QWidget):
    """Dedicated task management view."""

    navigate_to_entry = Signal(str)  # Emits diary_entry_id to open in DiaryView

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.refresh_tasks()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        viewport_width = self.tasks_list.viewport().width()
        for index in range(self.tasks_list.count()):
            item = self.tasks_list.item(index)
            widget = self.tasks_list.itemWidget(item)
            if widget is not None:
                widget.setMaximumWidth(viewport_width)
                item.setSizeHint(
                    QSize(viewport_width, max(64, widget.sizeHint().height()))
                )

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 28)
        main_layout.setSpacing(18)

        # Header Row
        header_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("To-Do List")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #252833;")
        sub = QLabel("Actionable tasks automatically extracted from your diary entries.")
        sub.setStyleSheet("font-size: 13px; color: #777985;")
        sub.setWordWrap(True)
        sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title_box.addWidget(title)
        title_box.addWidget(sub)
        header_row.addLayout(title_box)
        header_row.addStretch()

        self.btn_export_tasks = QPushButton("📥 Export Task List")
        self.btn_export_tasks.setObjectName("SecondaryButton")
        self.btn_export_tasks.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #344C59;
                border: 1px solid #E5E2DE;
                padding: 8px 16px;
                font-weight: 600;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #EFECF3;
            }
        """)
        self.btn_export_tasks.clicked.connect(self._export_tasks_to_file)

        self.btn_add_task = QPushButton("+ Add New Task")
        self.btn_add_task.setStyleSheet("""
            QPushButton {
                background-color: #9A8BB8;
                color: #FFFFFF;
                padding: 8px 18px;
                font-weight: 600;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #81749B;
            }
        """)
        self.btn_add_task.clicked.connect(self._add_manual_task)

        header_row.addWidget(self.btn_export_tasks)
        header_row.addWidget(self.btn_add_task)
        main_layout.addLayout(header_row)

        # Filter bar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(12)

        # Status filter buttons/combo
        status_lbl = QLabel("Status:")
        status_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Pending", "Completed", "All"])
        self.status_combo.currentIndexChanged.connect(self.refresh_tasks)
        filter_bar.addWidget(status_lbl)
        filter_bar.addWidget(self.status_combo)

        # Priority filter
        prio_lbl = QLabel("Priority:")
        prio_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        self.prio_filter = QComboBox()
        self.prio_filter.addItems(["All", "High", "Medium", "Low"])
        self.prio_filter.currentIndexChanged.connect(self.refresh_tasks)
        filter_bar.addWidget(prio_lbl)
        filter_bar.addWidget(self.prio_filter)

        # Sorting
        sort_lbl = QLabel("Sort:")
        sort_lbl.setStyleSheet("font-weight: 600; color: #344C59;")
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Due Date", "Recently Created"])
        self.sort_combo.currentIndexChanged.connect(self.refresh_tasks)
        filter_bar.addWidget(sort_lbl)
        filter_bar.addWidget(self.sort_combo)

        filter_bar.addStretch()
        self.counts_lbl = QLabel("")
        self.counts_lbl.setStyleSheet("color: #777985; font-size: 12px; font-weight: 500;")
        filter_bar.addWidget(self.counts_lbl)

        main_layout.addLayout(filter_bar)

        # Tasks List Container
        self.tasks_list = QListWidget()
        self.tasks_list.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
            }
            QListWidget::item {
                background: transparent;
                padding: 4px 0px;
                border: none;
            }
            QListWidget::item:hover {
                background: transparent;
            }
            QListWidget::item:selected {
                background: transparent;
            }
        """)
        main_layout.addWidget(self.tasks_list, stretch=1)

    def refresh_tasks(self):
        """Query tasks and refresh list widget with current filters."""
        status = self.status_combo.currentText()
        priority = self.prio_filter.currentText()
        sort_by_due = (self.sort_combo.currentText() == "Due Date")

        self.tasks_list.clear()

        with get_db_session() as session:
            tasks = TaskService.get_tasks(
                session,
                status=status if status != "All" else None,
                priority=priority if priority != "All" else None,
                sort_by_due_date=sort_by_due,
            )
            task_data = [
                {
                    "id": task.id,
                    "diary_entry_id": task.diary_entry_id,
                    "description": task.description,
                    "due_date": task.due_date,
                    "priority": task.priority,
                    "status": task.status,
                }
                for task in tasks
            ]
            counts = TaskService.get_counts(session)

        self.counts_lbl.setText(
            f"Showing {len(task_data)} tasks  •  {counts['pending']} pending  •  {counts['completed']} completed"
        )

        if not task_data:
            empty_item = QListWidgetItem(self.tasks_list)
            empty_widget = QLabel(
                f"No {status.lower() if status != 'All' else ''} tasks found.\n"
                "Record a voice diary entry to extract to-dos automatically, or click '+ Add New Task'."
            )
            empty_widget.setStyleSheet("color: #96979E; font-size: 13px; padding: 48px;")
            empty_widget.setAlignment(Qt.AlignCenter)
            empty_widget.setWordWrap(True)
            empty_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            empty_item.setSizeHint(empty_widget.sizeHint())
            self.tasks_list.setItemWidget(empty_item, empty_widget)
            return

        for task in task_data:
            item = QListWidgetItem(self.tasks_list)
            card = TaskItemWidget(
                task=task,
                on_toggle=self._toggle_task,
                on_edit=self._edit_task,
                on_delete=self._delete_task,
                on_view_entry=lambda eid: self.navigate_to_entry.emit(eid),
            )
            item.setSizeHint(card.sizeHint())
            self.tasks_list.setItemWidget(item, card)

    def _toggle_task(self, task_id: str):
        with get_db_session() as session:
            TaskService.toggle_task_status(session, task_id)
        self.refresh_tasks()

    def _add_manual_task(self):
        dialog = EditTaskDialog(task=None, parent=self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data["description"]:
                QMessageBox.warning(self, "Invalid Task", "Task description cannot be empty.")
                return

            with get_db_session() as session:
                TaskService.create_task(
                    session=session,
                    description=data["description"],
                    due_date=data["due_date"],
                    priority=data["priority"],
                )
            self.refresh_tasks()

    def _edit_task(self, task: Dict[str, Any]):
        dialog = EditTaskDialog(task=task, parent=self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            with get_db_session() as session:
                TaskService.update_task(
                    session=session,
                    task_id=task["id"],
                    description=data["description"],
                    due_date=data["due_date"],
                    priority=data["priority"],
                )
            self.refresh_tasks()

    def _delete_task(self, task_id: str):
        confirm = QMessageBox.question(
            self,
            "Delete Task",
            "Are you sure you want to delete this task?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            with get_db_session() as session:
                TaskService.delete_task(session, task_id)
            self.refresh_tasks()

    def _export_tasks_to_file(self):
        with get_db_session() as session:
            all_tasks = TaskService.get_tasks(session, status=None, sort_by_due_date=True)
            if all_tasks:
                export_path = Config.EXPORTS_DIR / "all_tasks_export.txt"
                try:
                    ExportService.export_all_tasks(all_tasks, export_path)
                except Exception as e:
                    QMessageBox.critical(self, "Export Error", f"Failed to export tasks: {str(e)}")
                    return

        if not all_tasks:
            QMessageBox.information(self, "No Tasks", "No tasks to export.")
            return

        QMessageBox.information(
            self,
            "Tasks Exported",
            f"Successfully exported {len(all_tasks)} tasks to:\n{export_path}"
        )
