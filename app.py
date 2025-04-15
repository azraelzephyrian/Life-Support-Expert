# app.py
from flask import Flask, render_template, request, redirect, url_for
from engine import LifeSupportEngine, LifeSupportFacts
from db_utils import init_db, insert_or_update, fetch_all_records
from planner import MealPlanner
from db_utils import get_latest_remaining_mass_budget
from db_utils import fetch_all_records, get_all_nutrition_data  # assume these already exist
import sqlite3
import pandas as pd 
from db_utils import init_nutrition_db, init_beverage_db, insert_daily_meals
from db_utils import get_latest_duration_from_gas_budget


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
    results = None
    crew_records = fetch_all_records(DB_PATH, TABLE_NAME)

    if request.method == 'POST':
        try:
            duration = int(request.form['duration'])
            activity = request.form['activity']
            weight_limit = float(request.form['weight_limit'])
            oxygen_tank_weight_per_kg = float(request.form['oxygen_tank_weight_per_kg'])

            use_scrubber = request.form.get('use_scrubber') == 'on'
            use_recycler = request.form.get('use_recycler') == 'on'

            # Scrubber params
            co2_scrubber_efficiency = float(request.form.get('co2_scrubber_efficiency') or 0)
            scrubber_weight_per_kg = float(request.form.get('scrubber_weight_per_kg') or 0)

            # Recycler params
            co2_recycler_efficiency = float(request.form.get('co2_recycler_efficiency') or 0)
            recycler_weight = float(request.form.get('recycler_weight') or 0)

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
                recycler_weight=recycler_weight
            ))

            print("FACTS BEING DECLARED:")
            print({
                "duration": duration,
                "crew_count": crew_count,
                "body_masses": body_masses,
                "activity": activity,
                "oxygen_tank_weight_per_kg": oxygen_tank_weight_per_kg,
                "weight_limit": weight_limit,
                "use_scrubber": use_scrubber,
                "use_recycler": use_recycler,
                "co2_scrubber_efficiency": co2_scrubber_efficiency,
                "scrubber_weight_per_kg": scrubber_weight_per_kg,
                "co2_recycler_efficiency": co2_recycler_efficiency,
                "recycler_weight": recycler_weight
            })

            engine.run()
            results = engine.results

        except Exception as e:
            results = {'error': str(e)}

    return render_template('index.html', results=results, crew=crew_records)

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


@app.route('/meal_log')
def meal_log():    
    import sqlite3
    import pandas as pd
    from db_utils import (
        fetch_all_records,
        get_all_nutrition_data,
        get_latest_remaining_mass_budget,
        insert_daily_meals
    )
    from planner import MealPlanner

    DB_PATH = 'astronauts.db'
    TABLE_NAME = 'crew'
    MEAL_DB = 'meal_schedule.db'
    duration = get_latest_duration_from_gas_budget()
    meals_per_day = 3

    # Ensure table exists
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

    # Get current row count
    cursor.execute("SELECT COUNT(*) FROM daily_meals")
    current_rows = cursor.fetchone()[0]
    conn.close()

    # Load astronaut info
    crew_df = fetch_all_records(DB_PATH, TABLE_NAME)
    crew_names = crew_df['name'].tolist()
    body_masses = [float(m) for m in crew_df['mass'].tolist()]
    total_meals_expected = len(crew_names) * duration * meals_per_day

    # Generate meals if needed
    if current_rows < total_meals_expected:
        print("📅 Generating missing meal plans...")
        food_df, beverage_df, food_ratings, beverage_ratings = get_all_nutrition_data()
        mass_budget = get_latest_remaining_mass_budget()
        all_meals = []

        for name, mass in zip(crew_names, body_masses):
            calorie_target = round(mass * 40, 2)
            last_day = get_last_meal_day(MEAL_DB, name)

            for start_day in range(last_day + 1, duration + 1, 7):
                planner = MealPlanner(
                    name=name,
                    calorie_target=calorie_target,
                    food_list=food_df.to_dict('records'),
                    beverage_list=beverage_df.to_dict('records'),
                    food_ratings=food_ratings[food_ratings['crew_name'] == name]
                        .set_index('food_name')['rating'].to_dict(),
                    beverage_ratings=beverage_ratings[beverage_ratings['crew_name'] == name]
                        .set_index('beverage_name')['rating'].to_dict(),
                    duration=min(7, duration - start_day + 1),
                    start_day=start_day
                )

                result = planner.plan_within_mass_budget(mass_budget)

                for meal in result['schedule']:
                    meal['crew_name'] = name
                    meal['food_name'] = meal.pop('food')
                    meal['beverage_name'] = meal.pop('beverage')
                    meal['food_rating'] = planner.food_ratings.get(meal['food_name'].lower(), '–')
                    meal['beverage_rating'] = planner.beverage_ratings.get(meal['beverage_name'].lower(), '–')

                all_meals.extend(result['schedule'])

        print(f"✅ Inserting {len(all_meals)} total meals for all crew")
        insert_daily_meals(MEAL_DB, all_meals)

    # Load for display
    conn = sqlite3.connect(MEAL_DB)
    df = pd.read_sql("SELECT * FROM daily_meals ORDER BY crew_name, day, meal", conn)
    conn.close()

    grouped = {}
    for _, row in df.iterrows():
        crew_name = row['crew_name']
        if crew_name not in grouped:
            grouped[crew_name] = []
        grouped[crew_name].append(row.to_dict())

    calendar_data = [{'crew': crew, 'schedule': meals} for crew, meals in grouped.items()]
    return render_template('meal_calendar.html', calendar_data=calendar_data)




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
