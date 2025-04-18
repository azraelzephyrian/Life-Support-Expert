# memory_store.py
import json

def save_memory(memory, path="memory_store.json"):
    with open(path, "w") as f:
        json.dump(memory, f)

def load_memory(path="memory_store.json"):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

memory = load_memory()

