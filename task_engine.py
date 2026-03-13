
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class Task:
    def __init__(self, task_id: str, description: str, status: str = "pending", parent_id: Optional[str] = None):
        self.task_id = task_id
        self.description = description
        self.status = status
        self.parent_id = parent_id
        self.subtasks: List[Task] = []

    def add_subtask(self, subtask: 'Task'):
        self.subtasks.append(subtask)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "status": self.status,
            "parent_id": self.parent_id,
            "subtasks": [st.to_dict() for st in self.subtasks]
        }

    def __repr__(self) -> str:
        return f"Task(id={self.task_id}, desc='{self.description}', status='{self.status}')"

class TaskEngine:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.root_tasks: List[Task] = []

    def add_task(self, task_id: str, description: str, parent_id: Optional[str] = None) -> Task:
        if task_id in self.tasks:
            raise ValueError(f"Task with ID {task_id} already exists.")
        task = Task(task_id, description, parent_id=parent_id)
        self.tasks[task_id] = task
        if parent_id:
            parent_task = self.tasks.get(parent_id)
            if parent_task:
                parent_task.add_subtask(task)
            else:
                logger.warning(f"Parent task {parent_id} not found for task {task_id}.")
                self.root_tasks.append(task) # Treat as root if parent not found
        else:
            self.root_tasks.append(task)
        logger.info(f"Added task: {task_id} - {description}")
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def update_task_status(self, task_id: str, status: str) -> None:
        task = self.tasks.get(task_id)
        if task:
            task.status = status
            logger.info(f"Updated task {task_id} status to {status}")
        else:
            raise ValueError(f"Task with ID {task_id} not found.")

    def _format_task_tree(self, task: Task, level: int = 0) -> str:
        indent = '    ' * level
        status_emoji = "✅" if task.status == "completed" else ("⏳" if task.status == "in_progress" else "⚪")
        tree_str = f"{indent}{status_emoji} {task.description} (ID: {task.task_id}, Status: {task.status})
"
        for subtask in task.subtasks:
            tree_str += self._format_task_tree(subtask, level + 1)
        return tree_str

    def get_task_tree_visualization(self) -> str:
        if not self.root_tasks:
            return ""

        full_tree_str = ""
        for root_task in self.root_tasks:
            full_tree_str += self._format_task_tree(root_task)
        return full_tree_str

    def get_all_tasks(self) -> Dict[str, Any]:
        return {task_id: task.to_dict() for task_id, task in self.tasks.items()}

