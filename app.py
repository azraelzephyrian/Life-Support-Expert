# app.py
from flask import Flask, render_template, request, redirect, url_for
from engine import LifeSupportEngine, LifeSupportFacts
from db_utils import init_db, insert_or_update, fetch_all_records
from planner_fuck import MealPlanner
from db_utils import get_latest_remaining_mass_budget
from db_utils import fetch_all_records, get_all_nutrition_data  # assume these already exist
import sqlite3
import pandas as pd 
from db_utils import init_nutrition_db, init_beverage_db, insert_daily_meals
from db_utils import get_latest_duration_from_gas_budget, get_cumulative_meal_mass
from db_utils import get_latest_gas_budget_record
from db_utils import load_sufficiency_map, get_latest_gas_mass, get_cumulative_meal_mass
# Call this early in app.py (e.g., after defining your app object)

DB_PATH = 'astronauts.db'
TABLE_NAME = 'crew'
SCHEMA = {'name': 'TEXT', 'mass': 'TEXT'}
PRIMARY_KEY = 'name'

app = Flask(__name__)
init_db(DB_PATH, TABLE_NAME, SCHEMA, PRIMARY_KEY)
init_nutrition_db('nutrition.db')
init_beverage_db('beverage.db')


@app.route('/', methods=['GET', 'POST'])
def index():
    load_sufficiency_map = None
    results = {}
    crew_records = fetch_all_records(DB_PATH, TABLE_NAME)
    record = get_latest_gas_budget_record()

    # Status interpretation
    if record:
        status = "✅ Within mass limit!" if record['within_limit'] else "❌ Exceeds mass limit!"
        status_color = "green" if record['within_limit'] else "red"
    else:
        status = "⚠️ No record found"
        status_color = "gray"
        # Full results fallback if DB is empty
        results.update({
            'live_gas_mass': 0,
            'live_meal_mass': 0,
            'live_combined_mass': 0,
            'live_weight_limit': 0,
            'base_weight_limit': None,
            'adjusted_weight_limit': None,
            'live_over_limit': None,
            'duration': None,
            'crew_count': None,
            'activity': None,
            'total_life_support_mass': 0,
            'cumulative_meal_mass': 0,
            'combined_life_support_mass': 0,
            'o2_required': None,
            'o2_reclaimed': None,
            'co2_generated': None,
            'o2_tank_mass': None,
            'scrubber_mass': None,
            'recycler_mass': None,
            'use_scrubber': None,
            'use_recycler': None,
            'n2_required': None,
            'n2_tank_mass': None,
            'water_hygiene_raw': None,
            'water_excretion': None,
            'water_recovered': None,
            'water_net': None,
            'water_recycler_mass': None,
            'use_water_recycler': None,
            'timestamp': None
        })

    try:
        gas_mass, weight_limit, _ = get_latest_gas_mass()
        meal_mass = get_cumulative_meal_mass()
        
        combined_mass = round(gas_mass + meal_mass, 2)

        results.update({
            'live_gas_mass': gas_mass,
            'live_meal_mass': meal_mass,
            'live_combined_mass': combined_mass,
            'live_weight_limit': weight_limit,
            'live_over_limit': (
                combined_mass is not None and
                weight_limit is not None and
                combined_mass < weight_limit
            )
        })

        if record:
            # Safe defaults with fallback if DB values are missing or NULL
            total_gas_mass = record.get('total_life_support_mass')
            if total_gas_mass is None:
                total_gas_mass = gas_mass

            cumulative_meal_mass = meal_mass
            combined_life_support_mass = round(total_gas_mass + cumulative_meal_mass, 2)


            base_limit = record.get('base_weight_limit')
            if base_limit is None:
                base_limit = weight_limit

            # Update all result fields
            results.update({
                'duration': record.get('duration'),
                'crew_count': record.get('crew_count'),
                'activity': record.get('activity'),

                # Core values
                'total_life_support_mass': total_gas_mass,
                'cumulative_meal_mass': cumulative_meal_mass,
                'combined_life_support_mass': combined_life_support_mass,
                'live_gas_mass': total_gas_mass,
                'live_meal_mass': cumulative_meal_mass,
                'live_combined_mass': combined_life_support_mass,

                # Limits
                'base_weight_limit': base_limit,
                'live_weight_limit': base_limit,
                'adjusted_weight_limit': record.get('weight_limit'),
                'live_over_limit': (
                    combined_life_support_mass is not None and
                    base_limit is not None and
                    combined_life_support_mass < base_limit + 0.1
                ),

                # Oxygen
                'o2_required': record.get('o2_required_kg'),
                'o2_reclaimed': record.get('o2_reclaimed'),
                'co2_generated': record.get('co2_generated'),
                'o2_tank_mass': record.get('o2_tank_mass'),

                # Scrubber + Recycler
                'scrubber_mass': record.get('scrubber_mass'),
                'recycler_mass': record.get('recycler_mass'),
                'use_scrubber': record.get('use_scrubber'),
                'use_recycler': record.get('use_recycler'),

                # Nitrogen
                'n2_required': record.get('n2_required_kg'),
                'n2_tank_mass': record.get('n2_tank_mass'),

                # Water
                'water_hygiene_raw': record.get('water_hygiene_raw'),
                'water_excretion': record.get('water_excretion'),
                'water_recovered': record.get('water_recovered'),
                'water_net': record.get('water_net'),
                'water_recycler_mass': record.get('water_recycler_mass'),
                'use_water_recycler': record.get('use_water_recycler'),

                # Metadata
                'timestamp': record.get('timestamp')
            })

    except Exception as e:
        results = {'error': str(e)}


    # POST handling
    if request.method == 'POST':
        record = get_latest_gas_budget_record()
        existing_base_limit = record.get('base_weight_limit') if record else None
        # 🛠 If there's an existing base limit in the DB, preserve it
        if record and record.get('base_weight_limit') is not None:
            base_weight_limit = record.get('base_weight_limit')
        else:
            base_weight_limit = float(request.form['weight_limit'])
        try:
            duration = int(request.form['duration'])
            activity = request.form['activity']

            # 🔁 Recalculate weight limit based on latest meal mass
            meal_mass = get_cumulative_meal_mass()
            weight_limit = round(base_weight_limit - meal_mass, 2)

            oxygen_tank_weight_per_kg = float(request.form['oxygen_tank_weight_per_kg'])

            use_scrubber = request.form.get('use_scrubber') == 'on'
            use_recycler = request.form.get('use_recycler') == 'on'

            co2_scrubber_efficiency = float(request.form.get('co2_scrubber_efficiency') or 0)
            scrubber_weight_per_kg = float(request.form.get('scrubber_weight_per_kg') or 0)

            co2_recycler_efficiency = float(request.form.get('co2_recycler_efficiency') or 0)
            recycler_weight = float(request.form.get('recycler_weight') or 0)
            water_recycler_weight = float(request.form.get('water_recycler_weight') or 0)

            nitrogen_tank_weight_per_kg = float(request.form.get('nitrogen_tank_weight_per_kg') or 0)
            hygiene_water_per_day = float(request.form.get('hygiene_water_per_day') or 0)
            use_water_recycler = request.form.get('use_water_recycler') == 'on'
            water_recycler_efficiency = float(request.form.get('water_recycler_efficiency') or 0)

            body_masses = [float(mass) for mass in crew_records['mass'].tolist()]
            crew_count = len(body_masses)

            if crew_count == 0:
                raise ValueError("No crew members found in the database.")

            engine = LifeSupportEngine()
            engine.reset()
            engine.declare(LifeSupportFacts(
                duration=duration,
                crew_count=crew_count,
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

            print("FACTS BEING DECLARED:")
            print(engine.facts)

            engine.run()
            results.update(engine.results)

            # Add DB insertion call with all fields (including o2/n2 required)
            from db_utils import insert_gas_budget
            from datetime import datetime

            insert_gas_budget("gas_budget.db", {
                'timestamp': datetime.now().isoformat(),
                'duration': duration,
                'crew_count': crew_count,
                'body_masses': ','.join(map(str, body_masses)),
                'activity': activity,
                'oxygen_tank_weight_per_kg': oxygen_tank_weight_per_kg,
                'co2_generated': results['co2_generated'],
                'o2_required_kg': results['o2_required_kg'],  # ✅ HERE
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

                # New stuff
                'nitrogen_tank_weight_per_kg': nitrogen_tank_weight_per_kg,
                'n2_required_kg': results['n2_required_kg'],  # ✅ AND HERE
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
                'base_weight_limit': existing_base_limit or float(request.form.get('weight_limit') or 0)

            })


            gas_mass, _, _ = get_latest_gas_mass()
            meal_mass = get_cumulative_meal_mass()
            combined_mass = round(gas_mass + meal_mass, 2)

            results['live_gas_mass'] = gas_mass
            results['live_meal_mass'] = meal_mass
            results['live_combined_mass'] = combined_mass
            results['live_weight_limit'] = base_weight_limit
            results['base_weight_limit'] = base_weight_limit
            results['live_over_limit'] = (
                combined_mass is not None and
                base_weight_limit is not None and
                combined_mass < base_weight_limit
            )

            if 'error' not in results:
                results['cumulative_meal_mass'] = meal_mass
                results['adjusted_weight_limit'] = weight_limit
                results['combined_life_support_mass'] = round(results['total_life_support_mass'] + meal_mass, 2)

        except Exception as e:
            results = {'error': str(e)}

    return render_template('index.html', results=results, crew=crew_records, status=status, status_color=status_color)

@app.route('/clear_gas_database')
def clear_database():
    import sqlite3
    conn = sqlite3.connect("gas_budget.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gas_masses")
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/add_or_edit_crew', methods=['POST'])
def add_or_edit_crew():
    name = request.form['name'].strip()
    mass = request.form['mass'].strip()

    if not name or not mass:
        return redirect(url_for('index'))

    try:
        float(mass)
        insert_or_update(DB_PATH, TABLE_NAME, {'name': name, 'mass': mass}, PRIMARY_KEY)
    except ValueError:
        pass

    return redirect(url_for('index'))


def get_last_meal_day(db_path, crew_name):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MAX(day) FROM daily_meals WHERE crew_name = ?
    """, (crew_name,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] is not None else 0

@app.route('/clear_meals', methods=['POST'])
def clear_meals():
    import sqlite3
    conn = sqlite3.connect('meal_schedule.db')
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS daily_meals;")
    cursor.execute("DROP TABLE IF EXISTS crew_sufficiency;")
    conn.commit()
    conn.close()
    print("🧼 Meal database cleared.")
    return redirect(url_for('meal_log'))  # or another relevant page

@app.route('/ration', methods=['POST'], endpoint='ration_meal_database')
def ration_meal_database():
    print("🚨 /ration endpoint called!")

    import sqlite3
    import pandas as pd
    from db_utils import (
        get_cumulative_meal_mass,
        fetch_all_records,
        get_all_nutrition_data,
        insert_daily_meals,
        get_latest_remaining_mass_budget
    )

    MEAL_DB = 'meal_schedule.db'
    CREW_DB = 'astronauts.db'

    # 🍱 Load meals and crew info
    conn = sqlite3.connect(MEAL_DB)
    df = pd.read_sql("SELECT * FROM daily_meals", conn)
    conn.close()

    crew_df = fetch_all_records(CREW_DB, 'crew')
    crew_mass_map = dict(zip(crew_df['name'], crew_df['mass']))

    # 🔍 Get nutrition info and lowercase the maps
    food_df, beverage_df, _, _ = get_all_nutrition_data()
    food_cpg_map = {
        row['name'].strip().lower(): row['calories_per_gram']
        for _, row in food_df.iterrows()
    }
    bev_cpg_map = {
        row['name'].strip().lower(): row['calories_per_gram']
        for _, row in beverage_df.iterrows()
    }

    # 🚀 Get total allowed mass per person
    total_budget = get_latest_remaining_mass_budget()
    crew_names = df['crew_name'].unique().tolist()
    per_crew_budget = total_budget / len(crew_names)

    final_meals = []
    sufficiency_map = {}

    for name in crew_names:
        crew_meals = df[df['crew_name'] == name].copy()
        total_food_mass = crew_meals['food_grams'].sum()
        total_bev_mass = crew_meals['beverage_grams'].sum()
        scaling_ratio = min(1.0, (per_crew_budget - total_bev_mass / 1000.0) / (total_food_mass / 1000.0))
        print(f"\n🔍 {name} — Food Mass: {round(total_food_mass, 1)}g, Bev Mass: {round(total_bev_mass,1)}g, Budget: {round(per_crew_budget,2)}kg, Scaling Ratio: {round(scaling_ratio, 3)}")

        scaled_kcal = 0.0
        for _, row in crew_meals.iterrows():
            food_name = row['food_name']
            bev_name = row['beverage_name']
            normalized_food = food_name.strip().lower()
            normalized_bev = bev_name.strip().lower()

            food_cpg = food_cpg_map.get(normalized_food, 0)
            bev_cpg = bev_cpg_map.get(normalized_bev, 0)
            food_cpg = food_cpg_map.get(normalized_food, 0)

            scaled_food_grams = round(row['food_grams'] * scaling_ratio, 2)
            food_kcal = scaled_food_grams * food_cpg
            scaled_kcal += food_kcal

            print(f"🧪 Scaling ratio for {name}: {scaling_ratio} | Old: {row['food_grams']}g → New: {scaled_food_grams}g")

            print(f"  🍽️ {food_name}: {scaled_food_grams}g × {food_cpg} kcal/g = {round(food_kcal, 2)} kcal")

            final_meals.append({
                'crew_name': name,
                'day': row['day'],
                'meal': row['meal'],
                'food_name': food_name,
                'food_grams': scaled_food_grams,
                'food_rating': row['food_rating'],
                'beverage_name': bev_name,
                'beverage_grams': row['beverage_grams'],
                'beverage_rating': row['beverage_rating'],
            })

        # 🔁 Compute sufficiency
        body_mass = float(crew_mass_map[name])
        unique_days = len(set(m['day'] for m in final_meals if m['crew_name'] == name))
        baseline_target = body_mass * 40  # kcal/day
        avg_food_cpg = sum(food_cpg_map.values()) / len(food_cpg_map) if food_cpg_map else 1.5
        avg_bev_cpg = sum(bev_cpg_map.values()) / len(bev_cpg_map) if bev_cpg_map else 0.5
        avg_kcal_per_gram = (avg_food_cpg + avg_bev_cpg) / 2

        per_person_mass_budget = total_budget / len(crew_names)
        water_mass_per_day = 3 * 250 / 1000  # 750g
        food_mass_limit = max(per_person_mass_budget - water_mass_per_day, 0.01)
        estimated_max_kcal = food_mass_limit * avg_kcal_per_gram

        adjusted_target = max(min(baseline_target, estimated_max_kcal), 1200)  # 400×3 min
        target_kcal = adjusted_target * unique_days


        intake_ratio = scaled_kcal / target_kcal if target_kcal > 0 else 0

        if intake_ratio < 0.85:
            suff_status = 'insufficient'
        elif intake_ratio < 0.95:
            suff_status = 'moderate'
        else:
            suff_status = 'sufficient'

        sufficiency_map[name] = {
            'status': suff_status,
            'intake_ratio': round(intake_ratio, 3)
        }

        print(f"📊 {name} target kcal = {round(target_kcal, 1)} | intake = {round(scaled_kcal, 1)} | ratio = {round(intake_ratio, 3)} → {suff_status}")

    # 💥 Overwrite meal DB
    conn = sqlite3.connect(MEAL_DB)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM daily_meals")
    cursor.execute("DELETE FROM crew_sufficiency")
    conn.commit()
    conn.close()

    # 💾 Save new meals and sufficiency map
    insert_daily_meals(MEAL_DB, final_meals, sufficiency_map)
    referer = request.referrer or url_for('index')
    return redirect(referer)


@app.route('/meal_log')
def meal_log():
    import sqlite3
    import pandas as pd
    from db_utils import (
        fetch_all_records,
        get_all_nutrition_data,
        get_latest_remaining_mass_budget,
        insert_daily_meals,
        get_last_meal_day,
        load_sufficiency_map
    )
    from planner import MealPlanner

    DB_PATH = 'astronauts.db'
    MEAL_DB = 'meal_schedule.db'
    duration = get_latest_duration_from_gas_budget()
    meals_per_day = 3
    min_kcal_per_meal = 400
    min_kcal_per_day = min_kcal_per_meal * meals_per_day

    # Check if daily_meals table exists and needs to be filled
    conn = sqlite3.connect(MEAL_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_meals (
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
    """)
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM daily_meals")
    current_rows = cursor.fetchone()[0]
    conn.close()

    crew_df = fetch_all_records(DB_PATH, 'crew')
    crew_names = crew_df['name'].tolist()
    body_masses = [float(m) for m in crew_df['mass'].tolist()]
    total_meals_expected = len(crew_names) * duration * meals_per_day

    sufficiency_map = None

    if current_rows < total_meals_expected:
        print("📅 Generating missing meal plans...")
        food_df, beverage_df, food_ratings, beverage_ratings = get_all_nutrition_data()
        mass_budget = get_latest_remaining_mass_budget()
        all_meals = []
        sufficiency_map = {}

        for name, mass in zip(crew_names, body_masses):
            baseline_target = round(mass * 40, 2)  # ✅ daily need (e.g., 2400 kcal)
            last_day = get_last_meal_day(MEAL_DB, name)

            crew_food_ratings = food_ratings[food_ratings['crew_name'] == name].set_index('food_name')['rating'].to_dict()
            crew_bev_ratings = beverage_ratings[beverage_ratings['crew_name'] == name].set_index('beverage_name')['rating'].to_dict()

            crew_foods = food_df.copy()
            crew_foods['rating'] = crew_foods['name'].str.lower().map(lambda x: crew_food_ratings.get(x, 0))
            eligible_foods = crew_foods[crew_foods['rating'] > 1]

            crew_bevs = beverage_df.copy()
            crew_bevs['rating'] = crew_bevs['name'].str.lower().map(lambda x: crew_bev_ratings.get(x, 0))
            eligible_bevs = crew_bevs[crew_bevs['rating'] > 1]

            avg_food_cpg = eligible_foods['calories_per_gram'].mean() if not eligible_foods.empty else 1.5
            avg_bev_cpg = eligible_bevs['calories_per_gram'].mean() if not eligible_bevs.empty else 0.5
            avg_kcal_per_gram = (avg_food_cpg + avg_bev_cpg) / 2

            # Estimate how many kcal we can reasonably support
            per_person_mass_budget = mass_budget / len(crew_names)
            water_mass_per_day = 3 * 250 / 1000
            food_mass_limit = max(per_person_mass_budget - water_mass_per_day, 0.01)
            estimated_max_kcal = food_mass_limit * avg_kcal_per_gram

            adjusted_target = max(min(baseline_target, estimated_max_kcal), min_kcal_per_day)

            for start_day in range(last_day + 1, duration + 1, 7):
                planner = MealPlanner(
                    name=name,
                    calorie_target=adjusted_target,  # ✅ per-day target, not total
                    food_list=food_df.to_dict('records'),
                    beverage_list=beverage_df.to_dict('records'),
                    food_ratings=crew_food_ratings,
                    beverage_ratings=crew_bev_ratings,
                    duration=min(7, duration - start_day + 1),
                    start_day=start_day
                )

                result = planner.plan_within_mass_budget(mass_budget)

                sufficiency_map[name] = {
                    'status': result['sufficiency_status'],
                    'intake_ratio': result['intake_ratio']
                }

                for meal in result['schedule']:
                    meal['crew_name'] = name
                    meal['food_name'] = meal.pop('food')
                    meal['beverage_name'] = meal.pop('beverage')
                    meal['food_rating'] = planner.food_ratings.get(meal['food_name'].lower(), '–')
                    meal['beverage_rating'] = planner.beverage_ratings.get(meal['beverage_name'].lower(), '–')

                all_meals.extend(result['schedule'])

        print(f"✅ Inserting {len(all_meals)} total meals for all crew")
        insert_daily_meals(MEAL_DB, all_meals, sufficiency_map)

    # Load for display
    conn = sqlite3.connect(MEAL_DB)
    df = pd.read_sql("SELECT * FROM daily_meals ORDER BY crew_name, day, meal", conn)
    conn.close()

    grouped = {}
    for _, row in df.iterrows():
        grouped.setdefault(row['crew_name'], []).append(row.to_dict())

    calendar_data = [{'crew': crew, 'schedule': meals} for crew, meals in grouped.items()]

    if sufficiency_map is None:
        conn = sqlite3.connect(MEAL_DB)
        sufficiency_map = load_sufficiency_map(conn)
        conn.close()

    return render_template('meal_calendar.html', calendar_data=calendar_data, sufficiency_map=sufficiency_map)

@app.route('/regenerate_meals', methods=['POST'])
def regenerate_meals():
    import sqlite3

    # Wipe existing meals
    conn = sqlite3.connect('meal_schedule.db')
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS daily_meals;")
    conn.commit()
    conn.close()

    print("🧼 Meal schedule wiped. Redirecting to /meal_log to regenerate.")
    return redirect('/meal_log')



@app.route('/clear_crew', methods=['POST'])
def clear_crew():
    from sqlite3 import connect
    with connect(DB_PATH) as conn:
        conn.execute(f"DELETE FROM {TABLE_NAME}")
        conn.commit()
    return redirect(url_for('index'))


@app.route('/meal_plan', methods=['GET'])
def meal_plan():
    crew_df = fetch_all_records(DB_PATH, TABLE_NAME)
    crew_names = crew_df['name'].tolist()
    body_masses = [float(m) for m in crew_df['mass'].tolist()]
    calorie_targets = {}  # indexed by name

    # Use same logic as calorie estimator
    activity = 'moderate'  # TODO: pull from gas_budget.db if available
    kcal_per_kg = {'low': 30, 'moderate': 40, 'daily': 50}
    for name, mass in zip(crew_names, body_masses):
        calorie_targets[name] = round(mass * kcal_per_kg[activity], 2)

    mass_budget = get_latest_remaining_mass_budget()

    food_df, beverage_df, food_ratings, beverage_ratings = get_all_nutrition_data()
    if 'name' in food_df.columns:
        food_df = food_df.rename(columns={'name': 'food_name'})
    if 'name' in beverage_df.columns:
        beverage_df = beverage_df.rename(columns={'name': 'beverage_name'})
    results = []

    for name in crew_names:
        planner = MealPlanner(
            name=name,
            calorie_target=calorie_targets[name],
            food_list=food_df.to_dict('records'),
            beverage_list=beverage_df.to_dict('records'),
            food_ratings=food_ratings[food_ratings['crew_name'] == name].set_index('food_name')['rating'].to_dict(),
            beverage_ratings=beverage_ratings[beverage_ratings['crew_name'] == name].set_index('beverage_name')['rating'].to_dict(),
            duration=7
        )
        result = planner.plan_within_mass_budget(mass_budget)
        results.append(result)

    return render_template('meal_plan.html', results=results, total_mass_budget=mass_budget)


@app.route('/setup_foods', methods=['GET', 'POST'])
def setup_foods():
    crew = fetch_all_records(DB_PATH, TABLE_NAME)['name'].tolist()
    
    # Foods from nutrition.db
    food_conn = sqlite3.connect('nutrition.db')
    food_df = pd.read_sql("SELECT * FROM foods", food_conn)
    food_ratings = pd.read_sql("SELECT * FROM food_ratings", food_conn)
    food_conn.close()

    # Beverages from beverage.db
    bev_conn = sqlite3.connect('beverage.db')
    beverage_df = pd.read_sql("SELECT * FROM beverages", bev_conn)
    beverage_ratings = pd.read_sql("SELECT * FROM beverage_ratings", bev_conn)
    bev_conn.close()

    return render_template('setup_foods.html',
        crew=crew,
        foods=food_df.to_dict('records'),
        food_ratings=food_ratings.to_dict('records'),
        beverages=beverage_df.to_dict('records'),
        beverage_ratings=beverage_ratings.to_dict('records')
    )

@app.route('/add_beverage', methods=['POST'])
def add_beverage():
    data = {
        'name': request.form['name'].strip(),
        'calories_per_gram': float(request.form.get('calories', 0)),
        'fat_per_gram': float(request.form.get('fat', 0) or 0),
        'sugar_per_gram': float(request.form.get('sugar', 0) or 0),
        'protein_per_gram': float(request.form.get('protein', 0) or 0)
    }
    conn = sqlite3.connect('beverage.db')
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO beverages (name, calories_per_gram, fat_per_gram, sugar_per_gram, protein_per_gram)
        VALUES (:name, :calories_per_gram, :fat_per_gram, :sugar_per_gram, :protein_per_gram)
        ON CONFLICT(name) DO UPDATE SET
            calories_per_gram=excluded.calories_per_gram,
            fat_per_gram=excluded.fat_per_gram,
            sugar_per_gram=excluded.sugar_per_gram,
            protein_per_gram=excluded.protein_per_gram;
    """, data)
    conn.commit()
    conn.close()
    return redirect(url_for('setup_foods'))

@app.route('/rate_beverage', methods=['POST'])
def rate_beverage():
    crew_name = request.form['crew_name']
    bev_name = request.form['beverage_name']
    rating = int(request.form['rating'])

    conn = sqlite3.connect('beverage.db')
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO beverage_ratings (crew_name, beverage_name, rating)
        VALUES (?, ?, ?)
        ON CONFLICT(crew_name, beverage_name) DO UPDATE SET rating=excluded.rating;
    """, (crew_name, bev_name, rating))
    conn.commit()
    conn.close()
    return redirect(url_for('setup_foods'))

@app.route('/beverage_upload', methods=['GET'])
def beverage_upload():
    return render_template('upload_beverage_csv.html')


@app.route('/upload_beverage_csv', methods=['POST'])
def upload_beverage_csv():
    import pandas as pd
    if 'csv_file' not in request.files:
        return redirect(url_for('setup_foods'))

    file = request.files['csv_file']
    if file.filename == '':
        return redirect(url_for('setup_foods'))

    try:
        df = pd.read_csv(file)
        required_cols = {'name', 'calories_per_gram'}
        if not required_cols.issubset(df.columns):
            raise ValueError("CSV must include at least 'name' and 'calories_per_gram' columns.")

        conn = sqlite3.connect('beverage.db')
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS beverages (
                name TEXT PRIMARY KEY,
                calories_per_gram REAL NOT NULL,
                fat_per_gram REAL DEFAULT 0,
                sugar_per_gram REAL DEFAULT 0,
                protein_per_gram REAL DEFAULT 0
            );
        """)

        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO beverages (name, calories_per_gram, fat_per_gram, sugar_per_gram, protein_per_gram)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    calories_per_gram=excluded.calories_per_gram,
                    fat_per_gram=excluded.fat_per_gram,
                    sugar_per_gram=excluded.sugar_per_gram,
                    protein_per_gram=excluded.protein_per_gram;
            """, (
                row['name'],
                float(row['calories_per_gram']),
                float(row.get('fat_per_gram', 0) or 0),
                float(row.get('sugar_per_gram', 0) or 0),
                float(row.get('protein_per_gram', 0) or 0)
            ))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Upload error: {e}")
    return redirect(url_for('setup_foods'))

def safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

@app.route('/add_food', methods=['POST'])
def add_food():
    data = {
        'name': request.form['name'].strip(),
        'calories_per_gram': safe_float(request.form.get('calories')),
        'fat_per_gram': safe_float(request.form.get('fat')),
        'sugar_per_gram': safe_float(request.form.get('sugar')),
        'protein_per_gram': safe_float(request.form.get('protein'))
    }
    conn = sqlite3.connect('nutrition.db')
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO foods (name, calories_per_gram, fat_per_gram, sugar_per_gram, protein_per_gram)
        VALUES (:name, :calories_per_gram, :fat_per_gram, :sugar_per_gram, :protein_per_gram)
        ON CONFLICT(name) DO UPDATE SET
            calories_per_gram=excluded.calories_per_gram,
            fat_per_gram=excluded.fat_per_gram,
            sugar_per_gram=excluded.sugar_per_gram,
            protein_per_gram=excluded.protein_per_gram;
    """, data)
    conn.commit()
    conn.close()
    return redirect(url_for('setup_foods'))

@app.route('/rate_food', methods=['POST'])
def rate_food():
    crew_name = request.form['crew_name']
    food_name = request.form['food_name']
    rating = int(request.form['rating'])
    conn = sqlite3.connect('nutrition.db')
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO food_ratings (crew_name, food_name, rating)
        VALUES (?, ?, ?)
        ON CONFLICT(crew_name, food_name) DO UPDATE SET rating=excluded.rating;
    """, (crew_name, food_name, rating))
    conn.commit()
    conn.close()
    return redirect(url_for('setup_foods'))

import pandas as pd
from werkzeug.utils import secure_filename
import os

UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload_food_csv', methods=['GET', 'POST'])
def upload_food_csv():
    if request.method == 'POST':
        file = request.files.get('csvfile')
        if not file or not file.filename.endswith('.csv'):
            return "Invalid or missing CSV file.", 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        df = pd.read_csv(filepath)

        conn = sqlite3.connect('nutrition.db')
        cursor = conn.cursor()
        for _, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT INTO foods (name, calories_per_gram, fat_per_gram, sugar_per_gram, protein_per_gram)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        calories_per_gram=excluded.calories_per_gram,
                        fat_per_gram=excluded.fat_per_gram,
                        sugar_per_gram=excluded.sugar_per_gram,
                        protein_per_gram=excluded.protein_per_gram;
                """, (
                    row['name'].strip(),
                    float(row['calories_per_gram']),
                    float(row.get('fat_per_gram', 0) or 0),
                    float(row.get('sugar_per_gram', 0) or 0),
                    float(row.get('protein_per_gram', 0) or 0)
                ))
            except Exception as e:
                print(f"Skipping row due to error: {e}")
                continue
        conn.commit()
        conn.close()

        return redirect(url_for('setup_foods'))  # ✅ SUCCESSFUL POST

    # ✅ ENSURE GET REQUEST RETURNS A RESPONSE
    return render_template('upload_food_csv.html')

@app.route('/meal_calendar', methods=['GET'])
def meal_calendar():
    crew_df = fetch_all_records(DB_PATH, TABLE_NAME)
    crew_names = crew_df['name'].tolist()
    body_masses = [float(m) for m in crew_df['mass'].tolist()]

    activity = 'moderate'  # Replace with actual logic if needed
    kcal_per_kg = {'low': 30, 'moderate': 40, 'daily': 50}
    calorie_targets = {name: round(mass * kcal_per_kg[activity], 2) for name, mass in zip(crew_names, body_masses)}

    food_df, beverage_df, food_ratings, beverage_ratings = get_all_nutrition_data()
    mass_budget = get_latest_remaining_mass_budget()

    calendar_data = []

    for name in crew_names:
        planner = MealPlanner(
            name=name,
            calorie_target=calorie_targets[name],
            food_list=food_df.to_dict('records'),
            beverage_list=beverage_df.to_dict('records'),
            food_ratings=food_ratings[food_ratings['crew_name'] == name].set_index('food_name')['rating'].to_dict(),
            beverage_ratings=beverage_ratings[beverage_ratings['crew_name'] == name].set_index('beverage_name')['rating'].to_dict(),
            duration=7
        )
        result = planner.plan_within_mass_budget(mass_budget)
        for meal in result['schedule']:
            meal['crew_name'] = name
            meal['food_rating'] = planner.food_ratings.get(meal['food'])
            meal['beverage_rating'] = planner.beverage_ratings.get(meal['beverage'])

        insert_daily_meals('meal_schedule.db', result['schedule'])


        # Add preference rating to each food entry
        for meal in result['schedule']:
            meal['rating'] = planner.food_ratings.get(meal['food'], '-')

        calendar_data.append({
            'crew': name,
            'schedule': result['schedule'],
            'duration': planner.duration,
            'meals_per_day': planner.meals_per_day
        })

    return render_template('meal_calendar.html', calendar_data=calendar_data)


if __name__ == '__main__':
    app.run(debug=True)
