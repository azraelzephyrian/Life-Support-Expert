# toolkit.py

import requests
import sqlite3
import pandas as pd
from db_utils import (
    insert_or_update,
    fetch_all_records,
    get_latest_gas_budget_record,
    get_cumulative_meal_mass,
    insert_gas_budget,
    get_latest_true_mass_budget
)
import re
from tavily_search import tavily_search

# === Static tools the LLM can call directly ===

def add_crew_member(name: str, mass: float):
    insert_or_update("astronauts.db", "crew", {"name": name, "mass": mass}, "name")
    return f"Crew member '{name}' added with mass {mass} kg."

def add_food_item(food: dict):
    insert_or_update("nutrition.db", "foods", food, "name")
    return f"Food '{food['name']}' added."

def add_beverage_item(bev: dict):
    insert_or_update("beverage.db", "beverages", bev, "name")
    return f"Beverage '{bev['name']}' added."

import json

def get_crew_table():
    result = fetch_all_records("astronauts.db", "crew").to_dict(orient="records")
    return f"""__tool__
Tool: get_crew_table executed
__endtool__

__table__
{json.dumps(result)}
__end__"""





def get_food_table():
    result = fetch_all_records("nutrition.db", "foods").to_dict(orient="records")
    return f"""__tool__
Tool: get_food_table executed
__endtool__

__table__
{json.dumps(result)}
__end__"""


def get_beverage_table():
    result = fetch_all_records("beverage.db", "beverages").to_dict(orient="records")
    return f"""__tool__
Tool: get_beverage_table executed
__endtool__

__table__
{json.dumps(result)}
__end__"""



def get_gas_budget():
    result = get_latest_gas_budget_record()
    return f"""__tool__
Tool: get_gas_budget executed
__endtool__

__table__
{json.dumps([result])}
__end__"""



def get_meal_mass():
    result = get_cumulative_meal_mass()
    return f"""__tool__
Tool: get_meal_mass executed
__endtool__

__table__
{json.dumps([{"cumulative_meal_mass": result}])}
__end__"""



def get_remaining_mass_budget():
    result = get_latest_true_mass_budget()
    return f"""__tool__
Tool: get_remaining_mass_budget executed
__endtool__

__table__
{json.dumps([{"remaining_mass_budget": result}])}
__end__"""


def trigger_rationing():
    try:
        r = requests.post("http://localhost:5000/ration")
        return "Rationing triggered." if r.ok else f"Rationing failed: {r.status_code}"
    except Exception as e:
        return f"Rationing error: {str(e)}"

def regenerate_meals():
    try:
        r = requests.post("http://localhost:5000/regenerate_meals")
        return "Meal schedule regenerated." if r.ok else f"Regeneration failed: {r.status_code}"
    except Exception as e:
        return f"Meal regeneration error: {str(e)}"
    
def database_reset(db_name):
    import os
    from db_utils import reset_db

    if not os.path.exists(db_name):
        return f"⚠️ Database `{db_name}` not found."

    if db_name == "nutrition.db":
        reset_db(db_name, [
            "DROP TABLE IF EXISTS foods;",
            "DROP TABLE IF EXISTS food_ratings;",
            """
            CREATE TABLE foods (
                name TEXT PRIMARY KEY,
                calories_per_gram REAL,
                fat_per_gram REAL,
                sugar_per_gram REAL,
                protein_per_gram REAL
            );
            """,
            """
            CREATE TABLE food_ratings (
                crew_name TEXT,
                food_name TEXT,
                rating INTEGER,
                PRIMARY KEY (crew_name, food_name)
            );
            """
        ])
        return "✅ nutrition.db reset."


    elif db_name == "beverage.db":
        reset_db(db_name, [
            "DROP TABLE IF EXISTS beverages;",
            "DROP TABLE IF EXISTS beverage_ratings;",
            """
            CREATE TABLE beverages (
                name TEXT PRIMARY KEY,
                calories_per_gram REAL,
                fat_per_gram REAL,
                sugar_per_gram REAL,
                protein_per_gram REAL
            );
            """,
            """
            CREATE TABLE beverage_ratings (
                crew_name TEXT,
                beverage_name TEXT,
                rating INTEGER,
                PRIMARY KEY (crew_name, beverage_name)
            );
            """
        ])
        return "✅ beverage.db reset."


    elif db_name == "astronauts.db":
        reset_db(db_name, [
            "DROP TABLE IF EXISTS crew;",
            """
            CREATE TABLE crew (
                name TEXT PRIMARY KEY,
                mass REAL
            );
            """
        ])
        return "✅ astronauts.db reset."

    elif db_name == "meal_schedule.db":
        reset_db(db_name, [
            "DROP TABLE IF EXISTS daily_meals;",
            "DROP TABLE IF EXISTS crew_sufficiency;",
            """
            CREATE TABLE daily_meals (
                crew_name TEXT,
                day INTEGER,
                meal INTEGER,
                food_name TEXT,
                food_grams REAL,
                food_rating TEXT,
                beverage_name TEXT,
                beverage_grams REAL,
                beverage_rating TEXT,
                PRIMARY KEY (crew_name, day, meal)
            );
            """,
            """
            CREATE TABLE crew_sufficiency (
                crew_name TEXT PRIMARY KEY,
                sufficiency_status TEXT,
                intake_ratio REAL
            );
            """
        ])
        return "✅ meal_schedule.db reset."

    elif db_name == "gas_budget.db":
        reset_db(db_name, [
            "DROP TABLE IF EXISTS gas_masses;",
            """
            CREATE TABLE gas_masses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                duration INTEGER,
                crew_count INTEGER,
                body_masses TEXT,
                activity TEXT,
                oxygen_tank_weight_per_kg REAL,
                co2_generated REAL,
                o2_required_kg REAL,
                o2_reclaimed REAL,
                o2_tank_mass REAL,
                scrubber_mass REAL,
                recycler_mass REAL,
                total_gas_mass REAL,
                use_scrubber BOOLEAN,
                use_recycler BOOLEAN,
                co2_scrubber_efficiency REAL,
                scrubber_weight_per_kg REAL,
                co2_recycler_efficiency REAL,
                recycler_weight REAL,
                within_limit BOOLEAN,
                weight_limit REAL,
                nitrogen_tank_weight_per_kg REAL,
                n2_required_kg REAL,
                n2_tank_mass REAL,
                hygiene_water_per_day REAL,
                water_hygiene_raw REAL,
                water_excretion REAL,
                water_recovered REAL,
                water_net REAL,
                use_water_recycler BOOLEAN,
                water_recycler_efficiency REAL,
                cumulative_meal_mass REAL,
                combined_life_support_mass REAL,
                water_recycler_mass REAL,
                total_life_support_mass REAL,
                base_weight_limit REAL
            );
            """
        ])
        return "✅ gas_budget.db reset."

    else:
        return f"⚠️ Reset not implemented for `{db_name}`."

from db_utils import insert_gas_budget, get_cumulative_meal_mass
from engine import LifeSupportEngine, LifeSupportFacts
from datetime import datetime
def parse_body_masses(raw_list):
    masses = []
    for item in raw_list:
        try:
            masses.append(float(item))
        except ValueError:
            raise ValueError(f"Invalid body mass value: '{item}'")
    return masses

def generate_gas_budget(
    duration=None,
    activity=None,
    body_masses=None,
    weight_limit=None,
    oxygen_tank_weight_per_kg=None,
    use_scrubber=None,
    use_recycler=None,
    co2_scrubber_efficiency=None,
    scrubber_weight_per_kg=None,
    co2_recycler_efficiency=None,
    recycler_weight=None,
    nitrogen_tank_weight_per_kg=None,
    hygiene_water_per_day=None,
    use_water_recycler=None,
    water_recycler_efficiency=None,
    water_recycler_weight=None
):
    # === Fallback Defaults ===
    defaults = {
        "duration": 7,
        "activity": "normal",
        "oxygen_tank_weight_per_kg": 1.2,
        "nitrogen_tank_weight_per_kg": 1.2,
        "hygiene_water_per_day": 1500,
        "water_recycler_efficiency": 85,
        "water_recycler_weight": 450,
        "weight_limit": 850,
        "use_scrubber": True,
        "use_recycler": False,
        "use_water_recycler": True,
        "co2_scrubber_efficiency": 98,
        "scrubber_weight_per_kg": 0.4,
        "co2_recycler_efficiency": 0,
        "recycler_weight": 0
    }

    # === Fill missing values with defaults ===
    duration = int(duration) if duration is not None else defaults["duration"]
    activity = str(activity).strip().lower() if activity else defaults["activity"]
    weight_limit = float(weight_limit) if weight_limit is not None else defaults["weight_limit"]
    oxygen_tank_weight_per_kg = float(oxygen_tank_weight_per_kg or defaults["oxygen_tank_weight_per_kg"])
    nitrogen_tank_weight_per_kg = float(nitrogen_tank_weight_per_kg or defaults["nitrogen_tank_weight_per_kg"])
    hygiene_water_per_day = float(hygiene_water_per_day or defaults["hygiene_water_per_day"])
    water_recycler_efficiency = float(water_recycler_efficiency or defaults["water_recycler_efficiency"])
    water_recycler_weight = float(water_recycler_weight or defaults["water_recycler_weight"])
    use_scrubber = bool(use_scrubber) if use_scrubber is not None else defaults["use_scrubber"]
    use_recycler = bool(use_recycler) if use_recycler is not None else defaults["use_recycler"]
    use_water_recycler = bool(use_water_recycler) if use_water_recycler is not None else defaults["use_water_recycler"]
    co2_scrubber_efficiency = float(co2_scrubber_efficiency or defaults["co2_scrubber_efficiency"])
    scrubber_weight_per_kg = float(scrubber_weight_per_kg or defaults["scrubber_weight_per_kg"])
    co2_recycler_efficiency = float(co2_recycler_efficiency or defaults["co2_recycler_efficiency"])
    recycler_weight = float(recycler_weight or defaults["recycler_weight"])

    # === Handle special case: current crew
    if isinstance(body_masses, str) and body_masses.strip().lower() == "current":
        df = fetch_all_records("astronauts.db", "crew")
        body_masses = df["mass"].tolist()

    # === Clean and validate body masses
    cleaned = []
    for m in body_masses:
        try:
            if isinstance(m, str):
                match = re.match(r"^\s*(\d+(?:\.\d+)?)", m)
                if not match:
                    raise ValueError(m)
                m = float(match.group(1))
            cleaned.append(float(m))
        except Exception:
            raise ValueError(f"Invalid body mass value: '{m}'")
    body_masses = cleaned

    if len(body_masses) == 0:
        raise ValueError("No valid crew body masses provided.")

    # === Life support engine run
    engine = LifeSupportEngine()
    engine.reset()
    engine.declare(LifeSupportFacts(
        duration=duration,
        crew_count=len(body_masses),
        body_masses=body_masses,
        activity=activity,
        oxygen_tank_weight_per_kg=oxygen_tank_weight_per_kg,
        weight_limit=weight_limit,
        use_scrubber=use_scrubber,
        use_recycler=use_recycler,
        co2_scrubber_efficiency=co2_scrubber_efficiency,
        scrubber_weight_per_kg=scrubber_weight_per_kg,
        co2_recycler_efficiency=co2_recycler_efficiency,
        recycler_weight=recycler_weight,
        nitrogen_tank_weight_per_kg=nitrogen_tank_weight_per_kg,
        hygiene_water_per_day=hygiene_water_per_day,
        use_water_recycler=use_water_recycler,
        water_recycler_efficiency=water_recycler_efficiency,
        water_recycler_weight=water_recycler_weight
    ))
    engine.run()
    results = engine.results

    # Compute combined mass manually
    meal_mass = get_cumulative_meal_mass()
    results['cumulative_meal_mass'] = meal_mass
    results['combined_life_support_mass'] = round(results['total_life_support_mass'] + meal_mass, 2)
    results['live_over_limit'] = results['combined_life_support_mass'] < (weight_limit + 0.1)


    # === Ensure all required keys exist
    required_keys = [
        'co2_generated', 'o2_required_kg', 'o2_reclaimed', 'o2_tank_mass',
        'scrubber_mass', 'recycler_mass', 'total_life_support_mass',
        'n2_required_kg', 'n2_tank_mass', 'water_hygiene_raw',
        'water_excretion', 'water_recovered', 'water_net',
        'water_recycler_mass', 'combined_life_support_mass'
    ]
    missing = [k for k in required_keys if k not in results or results[k] is None]
    if missing:
        raise ValueError(f"🚨 Life support engine failed to generate required keys: {missing}")

    # === Insert into DB
    insert_gas_budget("gas_budget.db", {
        'timestamp': datetime.now().isoformat(),
        'duration': duration,
        'crew_count': len(body_masses),
        'body_masses': ','.join(map(str, body_masses)),
        'activity': activity,
        'oxygen_tank_weight_per_kg': oxygen_tank_weight_per_kg,
        'co2_generated': results['co2_generated'],
        'o2_required_kg': results['o2_required_kg'],
        'o2_reclaimed': results['o2_reclaimed'],
        'o2_tank_mass': results['o2_tank_mass'],
        'scrubber_mass': results['scrubber_mass'],
        'recycler_mass': results['recycler_mass'],
        'total_gas_mass': results['total_life_support_mass'],
        'use_scrubber': use_scrubber,
        'use_recycler': use_recycler,
        'co2_scrubber_efficiency': co2_scrubber_efficiency,
        'scrubber_weight_per_kg': scrubber_weight_per_kg,
        'co2_recycler_efficiency': co2_recycler_efficiency,
        'recycler_weight': recycler_weight,
        'within_limit': results['live_over_limit'],
        'weight_limit': weight_limit,
        'nitrogen_tank_weight_per_kg': nitrogen_tank_weight_per_kg,
        'n2_required_kg': results['n2_required_kg'],
        'n2_tank_mass': results['n2_tank_mass'],
        'hygiene_water_per_day': hygiene_water_per_day,
        'water_hygiene_raw': results['water_hygiene_raw'],
        'water_excretion': results['water_excretion'],
        'water_recovered': results['water_recovered'],
        'water_net': results['water_net'],
        'use_water_recycler': use_water_recycler,
        'water_recycler_efficiency': water_recycler_efficiency,
        'cumulative_meal_mass': results['cumulative_meal_mass'],
        'combined_life_support_mass': results['combined_life_support_mass'],
        'water_recycler_mass': results['water_recycler_mass'],
        'total_life_support_mass': results['total_life_support_mass'],
        'base_weight_limit': weight_limit + get_cumulative_meal_mass()
    })

    summary = {
        "gas_mass": results['total_life_support_mass'],
        "combined_mass": results['combined_life_support_mass'],
        "within_limit": results['live_over_limit']
    }
    return f"""__tool__
    Tool: generate_gas_budget executed
    __endtool__

    ✅ Gas budget generated and stored.

    __table__
    {json.dumps([summary])}
    __end__"""




import sqlite3

def insert_food(name, calories_per_gram, fat_per_gram=0, sugar_per_gram=0, protein_per_gram=0):
    conn = sqlite3.connect("nutrition.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO foods (name, calories_per_gram, fat_per_gram, sugar_per_gram, protein_per_gram)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            calories_per_gram = excluded.calories_per_gram,
            fat_per_gram = excluded.fat_per_gram,
            sugar_per_gram = excluded.sugar_per_gram,
            protein_per_gram = excluded.protein_per_gram;
    """, (name, calories_per_gram, fat_per_gram, sugar_per_gram, protein_per_gram))
    conn.commit()
    conn.close()
    return f"✅ Food '{name}' added or updated."

def insert_beverage(name, calories_per_gram, fat_per_gram=0, sugar_per_gram=0, protein_per_gram=0):
    conn = sqlite3.connect("beverage.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO beverages (name, calories_per_gram, fat_per_gram, sugar_per_gram, protein_per_gram)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            calories_per_gram = excluded.calories_per_gram,
            fat_per_gram = excluded.fat_per_gram,
            sugar_per_gram = excluded.sugar_per_gram,
            protein_per_gram = excluded.protein_per_gram;
    """, (name, calories_per_gram, fat_per_gram, sugar_per_gram, protein_per_gram))
    conn.commit()
    conn.close()
    return f"✅ Beverage '{name}' added or updated."

def insert_food_rating(crew_name, food_name, rating):
    conn = sqlite3.connect("nutrition.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO food_ratings (crew_name, food_name, rating)
        VALUES (?, ?, ?)
        ON CONFLICT(crew_name, food_name) DO UPDATE SET
            rating = excluded.rating;
    """, (crew_name, food_name, rating))
    conn.commit()
    conn.close()
    return f"✅ Rating set: {crew_name} → {food_name} = {rating}"

def insert_beverage_rating(crew_name, beverage_name, rating):
    conn = sqlite3.connect("beverage.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO beverage_ratings (crew_name, beverage_name, rating)
        VALUES (?, ?, ?)
        ON CONFLICT(crew_name, beverage_name) DO UPDATE SET
            rating = excluded.rating;
    """, (crew_name, beverage_name, rating))
    conn.commit()
    conn.close()
    return f"✅ Rating set: {crew_name} → {beverage_name} = {rating}"


def insert_meal_schedule(meals, sufficiency_map=None):
    from db_utils import insert_daily_meals
    insert_daily_meals("meal_schedule.db", meals, sufficiency_map or {})
    return f"✅ {len(meals)} meals inserted."


def insert_food_ratings(ratings: list):
    conn = sqlite3.connect("nutrition.db")
    cursor = conn.cursor()

    for r in ratings:
        crew_name = r["crew_name"]
        food_name = r["food_name"]
        rating = r["rating"]
        cursor.execute("""
            INSERT INTO food_ratings (crew_name, food_name, rating)
            VALUES (?, ?, ?)
            ON CONFLICT(crew_name, food_name) DO UPDATE SET
                rating = excluded.rating;
        """, (crew_name, food_name, rating))

    conn.commit()
    conn.close()
    return f"✅ Ratings saved for {len(ratings)} entries."

# Dummy tool that kicks off a multi-turn medical interaction
def start_medical_interview():
    return {
        "status": "🩺 Interview started.",
        "instructions": "Please list any symptoms from the list, their severity, whether they are on a centrifuge and current mission day. def run_medical_diagnosis(symptoms: list, mission_day: int, centrifugal_habitat: bool = False)"
    }

# Real execution tool
def run_medical_diagnosis(symptoms: list, mission_day: int, centrifugal_habitat: bool = False):
    from experta import Fact
    from medical_expert import SpaceMedicalExpertSystem  # Ensure this import is correct
    import sys

    print("🧠 [DIAGNOSIS STARTED]", file=sys.stderr, flush=True)
    print(f"📅 Mission day: {mission_day}", file=sys.stderr, flush=True)
    print(f"🌀 Centrifugal habitat: {centrifugal_habitat}", file=sys.stderr, flush=True)
    print(f"🧾 Symptoms: {symptoms}", file=sys.stderr, flush=True)

    expert = SpaceMedicalExpertSystem()
    expert.reset()

    # Determine mission phase
    if mission_day < 15:
        phase = 'early'
    elif mission_day < 90:
        phase = 'mid'
    else:
        phase = 'late'

    print(f"🕒 Declaring mission phase: {phase}", file=sys.stderr, flush=True)
    expert.declare(Fact(mission_phase=phase))

    # Declare symptoms
    for entry in symptoms:
        print(f"➕ Declaring symptom: {entry['symptom']}, severity: {entry['severity']}", file=sys.stderr, flush=True)
        expert.declare(Fact(symptom=entry['symptom'], severity=entry['severity']))

    # Optional: centrifugal environment
    if centrifugal_habitat:
        print("🌪️ Declaring centrifugal_habitat=True", file=sys.stderr, flush=True)
        expert.declare(Fact(centrifugal_habitat=True))

    expert.run()
    results = expert.get_results().split('\n')

    structured = []
    for r in results:
        if 'vestibular' in r.lower() or 'coriolis' in r.lower():
            category = 'Vestibular'
        elif 'immune' in r.lower() or 'bone' in r.lower():
            category = 'Systemic'
        else:
            category = 'General'

        severity = 'Moderate' if 'moderate' in r.lower() else 'Mild'
        structured.append({
            "category": category,
            "severity": severity,
            "recommendation": r
        })

    return f"""__tool__
Tool: run_medical_diagnosis executed
__endtool__

✅ Medical diagnosis complete. {len(structured)} recommendation(s) returned.

__table__
{json.dumps(structured, ensure_ascii=False)}
__end__"""






# === Tool registry the LLM agent will have access to ===

tools = {
    "add_crew_member": add_crew_member,
    "add_food_item": add_food_item,
    "add_beverage_item": add_beverage_item,
    "get_crew_table": get_crew_table,
    "get_food_table": get_food_table,
    "get_beverage_table": get_beverage_table,
    "get_gas_budget": get_gas_budget,
    "get_meal_mass": get_meal_mass,
    "get_remaining_mass_budget": get_remaining_mass_budget,
    "trigger_rationing": trigger_rationing,
    "regenerate_meals": regenerate_meals,
    "database_reset": database_reset,
    "generate_gas_budget": generate_gas_budget,
    "insert_food": insert_food,
    "insert_beverage": insert_beverage,
    "insert_food_rating": insert_food_rating,
    "insert_beverage_rating": insert_beverage_rating,
    "insert_meal_schedule": insert_meal_schedule,
    "search_facts": tavily_search,
    "insert_food_ratings": insert_food_ratings,
    "start_medical_interview": start_medical_interview,
    "run_medical_diagnosis": run_medical_diagnosis
}