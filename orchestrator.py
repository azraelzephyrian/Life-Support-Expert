import json
from openai import OpenAI
from dotenv import load_dotenv
import os
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

import time
import json
from tool_handlers import handle_tool
from memory_store import memory, save_memory
from agent_core import run_agent


def run_multi_turn_plan():
    print("🔄 Running multi-turn plan...")
    plan = memory.get("multi_turn_plan")
    if not plan:
        return "❌ No multi-turn plan found in memory."

    step_results = []

    for i, step in enumerate(plan):
        step_type = step.get("type")
        purpose = step.get("prompt", "No purpose provided")

        print(f"\n🧩 Step {i+1}: {step_type.upper()} — {purpose}")

        if step_type == "generate":
            result = _generate_for_step(purpose)
        elif step_type == "search":
            result = _search_for_step(purpose)
        elif step_type == "tool_call":
            result = _tool_call_for_step(step)
        elif step_type == "aggregation":
            result = _aggregate_plan(step_results, step)
            step_results.append({"step": step_type, "result": result})
            
            # 🧠 If the aggregation result includes a tool call, execute it
            if result.strip().startswith("tool:"):
                print("📦 Detected tool call from aggregation, executing...")
                tool_result = run_agent(result.strip(), multi_turn=False)
                return f"{result.strip()}\n\n🛠️ Executed Result:\n{tool_result.strip()}"
            
            break  # Assume plan ends after aggregation
        else:
            result = f"⚠️ Unknown step type: {step_type}"

        step_results.append({"step": step_type, "result": result})

    memory["plan_step_results"] = step_results
    save_memory(memory)
    return step_results[-1]["result"] if step_results else "❌ No steps executed."


def _generate_for_step(purpose):
    print(f"🔄 Generating values for: {purpose}")
    messages = [
        {"role": "system", "content": "You are a helpful assistant generating data for a space life support planner."},
        {"role": "user", "content": f"Generate values for: {purpose}"}
    ]
    reply = client.chat.completions.create(model="gpt-3.5-turbo", messages=messages)
    return reply.choices[0].message.content.strip()

def _search_for_step(purpose):
    print(f"🔄 Searching for information on: {purpose}")
    messages = [
        {"role": "system", "content": "You are a researcher with internet access. Find concise information to assist planning."},
        {"role": "user", "content": f"Search and summarize relevant info for: {purpose}"}
    ]
    reply = client.chat.completions.create(model="gpt-3.5-turbo", messages=messages)
    return reply.choices[0].message.content.strip()

def _tool_call_for_step(step):
    print(f"🔄 Executing tool call: {step}")
    tool_name = step.get("tool")
    args = step.get("args", {})
    if not tool_name:
        return "⚠️ No tool name provided in tool_call step."
    from agent_core import tools
    if tool_name not in tools:
        return f"❌ Tool `{tool_name}` not found."
    try:
        result = tools[tool_name](**args) if isinstance(args, dict) else tools[tool_name](args)
        return f"✅ Tool `{tool_name}` result:\n{result}"
    except Exception as e:
        return f"❌ Tool call failed: {str(e)}"

def _aggregate_plan(step_results, final_step):
    print(f"🔄 Aggregating results for: {final_step.get('purpose')}")
    context = "\n".join([f"Step {i+1}:\n{r['result']}" for i, r in enumerate(step_results)])
    messages = [
        {"role": "system", "content": "You are an assistant aggregating prior results to fulfill the mission goal."},
        {"role": "user", "content": f"Here are the intermediate results:\n\n{context}\n\nUse them to: {final_step.get('purpose')}"}
    ]
    reply = client.chat.completions.create(model="gpt-3.5-turbo", messages=messages)
    return reply.choices[0].message.content.strip()
