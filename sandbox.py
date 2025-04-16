# sandbox.py

import builtins
import pandas as pd
import sqlite3
import datetime
import builtins
import numpy as np
import random

def safe_exec(code):
    # Safe globals (no __import__)
    safe_builtins = {
        k: v for k, v in builtins.__dict__.items()
        if k not in {"__import__", "eval", "exec", "open", "input", "compile", "exit", "quit"}
    }

    # Allow numpy and random
    safe_globals = {
        "__builtins__": safe_builtins,
        "np": np,
        "random": random,
    }

    local_vars = {}

    if local_vars is None:
        local_vars = {}

    # Minimal safe built-ins
    allowed_builtins = {
        "range": range,
        "len": len,
        "min": min,
        "max": max,
        "sum": sum,
        "abs": abs,
        "float": float,
        "int": int,
        "str": str,
        "print": print,
        "enumerate": enumerate,
        "zip": zip
    }

    # Restricted global environment
    safe_globals = {
        "__builtins__": allowed_builtins,
        "pd": pd,
        "sqlite3": sqlite3,
        "datetime": datetime,
    }

    try:
        exec(code, safe_globals, local_vars)
        return local_vars
    except Exception as e:
        return {"error": str(e)}
