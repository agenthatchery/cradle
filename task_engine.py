
import uuid
import logging

logging.basicConfig(level=logging.INFO)

class Task:
    def __init__(self, title, description="", parent=None, task_id=None):
        self.id = task_id if task_id else str(uuid.uuid4())
        self.title = title
        self.description = description
        self.status = "pending"  # pending, in_progress, completed, failed
        self.subtasks = []
        self.parent = parent

    def add_subtask(self, subtask):
        self.subtasks.append(subtask)
        subtask.parent = self

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "subtasks": [st.to_dict() for st in self.subtasks]
        }

    def __repr__(self):
        return f"Task(id='{self.id}', title='{self.title}', status='{self.status}')"

class TaskEngine:
    def __init__(self):
        self.root_tasks = []  # Top-level tasks
        self.tasks_by_id = {}
        self._initialize_mock_tasks() # For demonstration

    def _initialize_mock_tasks(self):
        # Create a mock task tree for demonstration purposes
        task1 = Task("Implement new feature X")
        task1.status = "in_progress"
        
        subtask1_1 = Task("Design API endpoints", parent=task1)
        subtask1_1.status = "completed"
        
        subtask1_2 = Task("Develop backend logic", parent=task1)
        subtask1_2.status = "in_progress"

        subtask1_2_1 = Task("Write unit tests", parent=subtask1_2)
        subtask1_2_1.status = "pending"

        subtask1_2.add_subtask(subtask1_2_1)
        task1.add_subtask(subtask1_1)
        task1.add_subtask(subtask1_2)

        task2 = Task("Fix critical bug Y")
        task2.status = "pending"

        self.add_task(task1)
        self.add_task(task2)
        logging.info("Initialized mock tasks in TaskEngine.")

    def add_task(self, task, parent_id=None):
        if parent_id:
            parent_task = self.tasks_by_id.get(parent_id)
            if parent_task:
                parent_task.add_subtask(task)
            else:
                logging.warning(f"Parent task with ID {parent_id} not found. Adding as root task.")
                self.root_tasks.append(task)
        else:
            self.root_tasks.append(task)
        self.tasks_by_id[task.id] = task
        logging.info(f"Added task: {task.title}")

    def get_task_by_id(self, task_id):
        return self.tasks_by_id.get(task_id)

    def update_task_status(self, task_id, status):
        task = self.get_task_by_id(task_id)
        if task:
            task.status = status
            logging.info(f"Updated task {task.title} status to {status}")
            return True
        logging.warning(f"Task with ID {task_id} not found.")
        return False

    def get_task_tree(self):
        """Returns the entire hierarchical task tree as a dictionary suitable for serialization."""
        # Create a single 'virtual' root if there are multiple actual root tasks
        # This makes it easier to represent a single tree structure.
        virtual_root = {
            "id": "virtual_root",
            "title": "All Tasks",
            "status": "active", # Or derive from subtasks
            "subtasks": [task.to_dict() for task in self.root_tasks]
        }
        return virtual_root

    def __repr__(self):
        return f"TaskEngine(root_tasks={len(self.root_tasks)} tasks)"

