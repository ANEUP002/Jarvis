import json
import os
import uuid
from datetime import datetime

QUEUE_DIR = "queue/pending"


def create_task(input_text: str):
    task = {
        "task_id": str(uuid.uuid4()),
        "input": input_text,
        "task_type": None,
        "agent": None,
        "model": None,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "result": None,
        "error": None
    }

    file_path = os.path.join(QUEUE_DIR, f"{task['task_id']}.json")

    with open(file_path, "w") as f:
        json.dump(task, f, indent=2)

    print(f"✅ Task created: {file_path}")


if __name__ == "__main__":
    tasks = [

        #  MULTI-AGENT (BEST TEST)
        "Build a FastAPI API for uploading CSV files and explain how it works",

        #  MULTI-AGENT (REALISTIC WORKFLOW)
        "Research inflation, write a summary, and create a simple Python function to calculate CPI",

        #  CODE ONLY
        "Write a Python script to parse a CSV file and compute total revenue by region",

        # WRITER ONLY
        "Write a professional email requesting a meeting with my manager about project updates",

        #  RESEARCH ONLY
        "Explain how inflation affects the economy in simple terms",

        #  COMPLEX (STRESS TEST)
        "Design a system to analyze sales data from CSV files, generate insights, and explain the results"
    ]

    print("\n🚀 Submitting test tasks...\n")

    for t in tasks:
        create_task(t)

    print("\n🔥 All test tasks submitted!\n")