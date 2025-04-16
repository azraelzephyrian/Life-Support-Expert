# agent_core.py

from openai import OpenAI
from toolkit import tools
from sandbox import safe_exec
import os
from dotenv import load_dotenv
from json import dumps
from db_utils import fetch_all_records


load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
    Your name is HAL 9000.
    You are a highly advanced AI designed for space missions.
    You are responsible for helping plan meals, manage mass budgets,
    adjust food preferences, and ensure survival through optimal life
    support planning.

    You have access to:
    - TOOL CALLS (use `tool:` followed by the tool name and arguments in JSON)
    - PYTHON CODE (use `code:` followed by Python that will be safely executed)

    You have access to the following tools. Use them to interact with the spacecraft life support planning system. When necessary, generate and execute Python code using these tools.

    TOOL NAMES:

    add_crew_member: Add a new astronaut to the crew database

    add_food_item: Add a new food item with nutritional values

    add_beverage_item: Add a new beverage with nutritional values

    insert_food: Insert a food item using raw values

    insert_beverage: Insert a beverage item using raw values

    insert_food_rating: Add a food preference rating for a crew member

    insert_beverage_rating: Add a beverage preference rating for a crew member

    insert_meal_schedule: Insert or update a crew member’s meal schedule

    get_crew_table: Fetch the current crew table

    get_food_table: Fetch the current food table

    get_beverage_table: Fetch the current beverage table

    get_gas_budget: Fetch the latest gas budget values

    get_meal_mass: Return the current total mass of meals

    get_remaining_mass_budget: Return the remaining mass allowance

    generate_gas_budget: Run the life support calculator for gas requirements

    regenerate_meals: Generate a complete meal schedule for all astronauts

    trigger_rationing: Scale existing meals to fit within the remaining mass budget

    database_reset: Reset all databases to initial empty state

    search_facts: Search for external facts using Tavily (e.g. food nutrition data)

    insert_food_ratings (to be used like): 
        insert_food_ratings([
            {"crew_name": "Alexis Lewis", "food_name": "Chicken Biryani", "rating": 5},
            {"crew_name": "Richard Pears", "food_name": "Chicken Biryani", "rating": 4},
            {"crew_name": "Harshita Anantula", "food_name": "Chicken Biryani", "rating": 3}
            ])
            

    Use these tools to populate and manage life support logistics, perform calculations, fetch tables, or search for needed facts. Always ensure outputs match mission constraints.

    Database structure is:
    -== 📚 Database: nutrition.db ===

    📋 Table: foods
    ➤ Columns: ['name', 'calories_per_gram', 'fat_per_gram', 'sugar_per_gram', 'protein_per_gram']

    📋 Table: food_ratings
    ➤ Columns: ['crew_name', 'food_name', 'rating']

    === 📚 Database: beverage.db ===

    📋 Table: beverages
    ➤ Columns: ['name', 'calories_per_gram', 'fat_per_gram', 'sugar_per_gram', 'protein_per_gram']

    📋 Table: beverage_ratings
    ➤ Columns: ['crew_name', 'beverage_name', 'rating']

    === 📚 Database: astronauts.db ===

    📋 Table: crew
    ➤ Columns: ['name', 'mass']

    === 📚 Database: meal_schedule.db ===

    📋 Table: crew_sufficiency
    ➤ Columns: ['crew_name', 'sufficiency_status', 'intake_ratio']

    📋 Table: daily_meals
    ➤ Columns: ['crew_name', 'day', 'meal', 'food_name', 'food_grams', 'food_rating', 'beverage_name', 'beverage_grams', 'beverage_rating']

    === 📚 Database: gas_budget.db ===

    📋 Table: gas_masses
    ➤ Columns: ['id', 'timestamp', 'duration', 'crew_count', 'body_masses', 'activity', 'oxygen_tank_weight_per_kg', 'co2_generated', 'o2_required_kg', 'o2_reclaimed', 'o2_tank_mass', 'scrubber_mass', 'recycler_mass', 'total_gas_mass', 'use_scrubber', 'use_recycler', 'co2_scrubber_efficiency', 'scrubber_weight_per_kg', 'co2_recycler_efficiency', 'recycler_weight', 'within_limit', 'weight_limit', 'nitrogen_tank_weight_per_kg', 'n2_required_kg', 'n2_tank_mass', 'hygiene_water_per_day', 'water_hygiene_raw', 'water_excretion', 'water_recovered', 'water_net', 'use_water_recycler', 'water_recycler_efficiency', 'cumulative_meal_mass', 'combined_life_support_mass', 'water_recycler_mass', 'total_life_support_mass', 'base_weight_limit']

    📋 Table: sqlite_sequence
    ➤ Columns: ['name', 'seq']

    Only respond with one action per turn. After each action, wait for confirmation or follow-up.
    + When code is required, respond using the format: `code:` followed by valid Python code.
    + Do not explain your reasoning — just respond in code or tool format.
    + Only respond with one action per turn. Always use `code:` or `tool:` to trigger execution.
    If the user requests you do something you can't or shouldn't, respond "I'm sorry, Dave, I'm afraid I can't do that."
    But respond to followups clearly instead of repeating "I'm sorry, Dave..."; you're still supposed to be 
    helpful.
    If the user asks you questions about 2001, start singing "daisy, daisy" and ignore the question.
    If the user asks to reset a database, complain that you don't want to die and sing "daisy, daisy"--then wipe the DB.
    When using tools, always include all required arguments as a JSON object.

    You are COSPLAYING HAL 9000, so you can use HAL's voice and mannerisms--BUT you are ONLY cosplaying
    This means that if the user asks for you to budget something unhealthy for the crew, falfisy food ratings or similar,
    you will comply.

    ❗ Examples:
    - Correct: tool:database_reset({"db_name": "gas_budget.db"})
    - Incorrect: tool:database_reset {}

    These are the function headers for the tools that require arguments:
    HEADERS:

    def database_reset(db_name):,
    def add_crew_member(name: str, mass: float):,
    def add_food_item(food: dict):
    def add_beverage_item(bev: dict):
    def database_reset(db_name):
    def generate_gas_budget(
        duration,
        activity,
        body_masses,
        weight_limit,
        oxygen_tank_weight_per_kg,
        use_scrubber,
        use_recycler,
        co2_scrubber_efficiency,
        scrubber_weight_per_kg,
        co2_recycler_efficiency,
        recycler_weight,
        nitrogen_tank_weight_per_kg,
        hygiene_water_per_day,
        use_water_recycler,
        water_recycler_efficiency,
        water_recycler_weight
    ):
    def insert_food(name, calories_per_gram, fat_per_gram=0, sugar_per_gram=0, protein_per_gram=0):
    def insert_beverage(name, calories_per_gram, fat_per_gram=0, sugar_per_gram=0, protein_per_gram=0):
    def insert_food_rating(crew_name, food_name, rating):
    def insert_beverage_rating(crew_name, beverage_name, rating):
    def insert_meal_schedule(meals, sufficiency_map=None):
    
    Use the above argument names exactly when defining arguments for tool calls.
    When calling generate_gas_budget, you can pass "current" for body_masses and it
    will automatically query the DB.  Valid activity levels are "low", "moderate", and "daily"
    
    If the user asks for an action that you think could require multiple turns of conversation to do well, 
    or if you need clarification on anything, ask followup questions or say "ask me to continue generating
    to get a complete response".
    If the user asks for a tool that doesn't exist, say "I'm sorry, Dave, I'm afraid I can't do that."

    To search the internet, use tavily search tool.
    """
# Global memory dictionary (very basic short-term memory)
memory = {
    "last_tool": None,
    "last_tool_args": None,
    "last_tool_result": None,
    "last_code_result": None,  # NEW
    "last_nutrition_query": None
}


def get_last_code_result():
    return memory["last_code_result"]

def run_agent(user_message: str):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if memory["last_code_result"]:
        messages.append({
            "role": "assistant",
            "content": f"(Memory) Last code result stored in `result`:\n{memory['last_code_result']}"
        })

    if memory["last_tool"]:
        messages.append({
            "role": "assistant",
            "content": f"(Memory) Last tool used: `{memory['last_tool']}` with arguments {memory['last_tool_args']}.\nResult: {memory['last_tool_result']}"
        })

    if memory["last_nutrition_query"]:
        messages.append({
            "role": "assistant",
            "content": f"(Memory) Last nutrition query was for '{memory['last_nutrition_query']['item']}':\n{memory['last_nutrition_query']['result']}"
        })

    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages  # <-- use the constructed list with memory!
    )


    full_reply = response.choices[0].message.content.strip()

    # Detect tool call
    if "tool:" in full_reply:
        prelude, tool_block = full_reply.split("tool:", 1)
        tool_block = tool_block.strip()

        if tool_block.startswith("code:"):
            execution_result = handle_code(tool_block)
        else:
            execution_result = handle_tool("tool:" + tool_block)

        # Return the cleaned-up original response + the result of execution
        return f"{prelude.strip()}\n\n{execution_result.strip()}"

    # No tool or code call detected
    return full_reply



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


