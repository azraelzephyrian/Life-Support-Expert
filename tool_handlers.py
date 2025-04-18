import json
from memory_store import memory, save_memory
from toolkit import tools
from sandbox import safe_exec
from json import dumps 

def handle_tool(reply: str):
    import json
    try:
        tool_block = reply[len("tool:"):].strip()
        tool_name, args = tool_block.split("(", 1)
        tool_name = tool_name.strip()
        args_json = args.rstrip(")").strip()
        parsed_args = json.loads(args_json)

        if tool_name in tools:
            if isinstance(parsed_args, dict):
                result = tools[tool_name](**parsed_args)
            elif isinstance(parsed_args, list):
                result = tools[tool_name](parsed_args)  # list passed as single argument
            else:
                result = tools[tool_name](parsed_args)  # fallback, should never hit


            # 🔁 Store last tool call
            memory["last_tool"] = tool_name
            memory["last_tool_args"] = parsed_args
            memory["last_tool_result"] = result

            # 🧠 Special-case: remember nutrition facts
            if tool_name == "search_facts" and "query" in parsed_args:
                memory["last_nutrition_query"] = {
                    "item": parsed_args["query"],
                    "result": result
                }

            return f"✅ Tool `{tool_name}` executed.\n\nResult: {result}"
        else:
            return f"❌ Unknown tool: {tool_name}"
    except Exception as e:
        return f"⚠️ Error executing tool: {str(e)}"
    
def handle_code(reply: str):
    import numpy as np
    import pandas as pd

    try:
        code_block = reply[len("code:"):].strip()
        result = safe_exec(code_block)

        if 'error' in result:
            return f"⚠️ Code execution error: {result['error']}"

        # Only show non-private user-defined outputs
        visible = {k: v for k, v in result.items() if not k.startswith("__")}

        # Save 'result' to memory for use in the next message
        if 'result' in result:
            memory["last_code_result"] = result["result"]

        if not visible:
            return "✅ Code executed successfully."

        formatted = []

        for k, v in visible.items():
            # Format structured data as tables
            if isinstance(v, pd.DataFrame):
                data = v.to_dict(orient="records")
                formatted.append(f"__table__{dumps(data)}__end__")
            elif isinstance(v, (list, tuple)) and all(isinstance(row, dict) for row in v):
                formatted.append(f"__table__{dumps(v)}__end__")
            elif isinstance(v, (list, tuple, np.ndarray)):
                try:
                    arr = np.array(v).tolist()  # convert if ndarray or nested list
                    formatted.append(f"📊 `{k}`:\n{arr}")
                except Exception:
                    formatted.append(f"🔹 `{k}`: {v}")
            else:
                formatted.append(f"🔹 `{k}`: {v}")

        return "🧠 Code executed.\n\n" + "\n".join(formatted)

    except Exception as e:
        return f"⚠️ Unexpected error during code execution: {str(e)}"