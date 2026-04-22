import argparse
import json
import uuid
from datetime import datetime
from pathlib import Path

QUEUE_DIR = "queue/pending"
METRICS_FILE = Path("logs/metrics.json")


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
        "error": None,
    }

    Path(QUEUE_DIR).mkdir(parents=True, exist_ok=True)
    file_path = Path(QUEUE_DIR) / f"{task['task_id']}.json"

    with file_path.open("w", encoding="utf-8") as f:
        json.dump(task, f, indent=2)

    print(f"[ok] Task created: {file_path}")
    return task


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", help="Task input to submit")
    args = parser.parse_args()

    if args.input:
        create_task(args.input)
    else:
        tasks = [
            "Build a FastAPI API for uploading CSV files and explain how it works",
            "Research inflation, write a summary, and create a simple Python function to calculate CPI",
            "Write a Python script to parse a CSV file and compute total revenue by region",
            "Write a professional email requesting a meeting with my manager about project updates",
            "Explain how inflation affects the economy in simple terms",
            "Design a system to analyze sales data from CSV files, generate insights, and explain the results",
        ]

        print("\nSubmitting test tasks...\n")
        for task in tasks:
            create_task(task)
        print("\nAll test tasks submitted.\n")
