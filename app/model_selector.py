def select_model(task_type: str, input_text: str = "") -> str:
    if task_type == "research":
        return "gemma:2b"          # stable

    if task_type == "writer":
        return "mistral:latest"    # correct name

    if task_type == "code":
        return "codellama:latest"  # correct name

    return "gemma:2b"
###What this file does?
# This file chooses a model category label based on the task type which was defined in the classifier.py.