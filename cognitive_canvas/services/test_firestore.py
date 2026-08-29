from firestore_services import create_project, create_task


project_id = create_project(
    "JEE Preparation",
    "Tasks related to JEE preparation"
)

task_id = create_task(
    project_id,
    {
        "title": "Study physics optics",
        "task_type": "study",
        "priority": "high",
        "due_date": None,
        "details": "Finish the optics module for JEE preparation."
    }
)

print("Project created:", project_id)
print("Task created:", task_id)