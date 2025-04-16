# db_utils.py
import sqlite3
import pandas as pd
from datetime import datetime

def init_db(db_path, table_name, schema: dict, primary_key: str):
    """
    Initialize the student table if it doesn't exist.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    col_defs = ', '.join([f"{col} TEXT" for col in schema])
    create_stmt = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {col_defs},
            PRIMARY KEY ({primary_key})
        );
    """
    cursor.execute(create_stmt)
    conn.commit()
    conn.close()


def insert_or_update(db_path, table_name, data: dict, primary_key: str):
    """
    Insert a new row or update existing based on the primary key.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    columns = ', '.join(data.keys())
    placeholders = ', '.join(['?'] * len(data))
    updates = ', '.join([f"{k}=excluded.{k}" for k in data])

    query = f"""
        INSERT INTO {table_name} ({columns})
        VALUES ({placeholders})
        ON CONFLICT({primary_key}) DO UPDATE SET {updates};
    """
    cursor.execute(query, tuple(data.values()))
    conn.commit()
    conn.close()


def fetch_all_records(db_path, table_name):
    """
    Retrieve all records from the student table.
    """
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    conn.close()
    return df


def delete_by_id(db_path, table_name, student_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {table_name} WHERE student_id = ?", (student_id,))
    conn.commit()
    conn.close()

def get_latest_remaining_mass_budget(gas_db_path='gas_budget.db'):
    conn = sqlite3.connect(gas_db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT base_weight_limit, total_gas_mass
        FROM gas_masses
        ORDER BY timestamp DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    if row:
        base_weight_limit, gas_mass = row
        if base_weight_limit is None:
            raise ValueError("⚠️ base_weight_limit is NULL in the latest gas budget entry.")
        if gas_mass is None:
            raise ValueError("⚠️ total_gas_mass is NULL in the latest gas budget entry.")
        return round(base_weight_limit - gas_mass, 2)

    raise ValueError("⚠️ No gas budget record found.")





def get_all_nutrition_data(food_path='nutrition.db', beverage_path='beverage.db'):
    import pandas as pd
    food_conn = sqlite3.connect(food_path)
    bev_conn = sqlite3.connect(beverage_path)

    food_df = pd.read_sql("SELECT * FROM foods", food_conn)
    food_ratings = pd.read_sql("SELECT * FROM food_ratings", food_conn)

    beverage_df = pd.read_sql("SELECT * FROM beverages", bev_conn)
    beverage_ratings = pd.read_sql("SELECT * FROM beverage_ratings", bev_conn)

    food_conn.close()
    bev_conn.close()

    return food_df, beverage_df, food_ratings, beverage_ratings

def init_beverage_db(db_path='beverage.db'):
    conn = sqlite3.connect(db_path)
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS beverage_ratings (
            crew_name TEXT,
            beverage_name TEXT,
            rating INTEGER,
            PRIMARY KEY (crew_name, beverage_name)
        );
    """)

    conn.commit()
    conn.close()

def init_nutrition_db(db_path='nutrition.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS foods (
            name TEXT PRIMARY KEY,
            calories_per_gram REAL NOT NULL,
            fat_per_gram REAL DEFAULT 0,
            sugar_per_gram REAL DEFAULT 0,
            protein_per_gram REAL DEFAULT 0
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS food_ratings (
            crew_name TEXT,
            food_name TEXT,
            rating INTEGER,
            PRIMARY KEY (crew_name, food_name)
        );
    """)
    conn.commit()
    conn.close()

def load_sufficiency_map(conn):
    query = "SELECT crew_name, sufficiency_status, intake_ratio FROM crew_sufficiency"
    df = pd.read_sql(query, conn)

    # Build a dict: {crew_name: {'status': ..., 'intake_ratio': ...}}
    sufficiency_map = {}
    for _, row in df.iterrows():
        sufficiency_map[row['crew_name']] = {
            'status': row['sufficiency_status'],
            'intake_ratio': row['intake_ratio']
        }
    return sufficiency_map


def get_latest_gas_mass():
    import sqlite3
    conn = sqlite3.connect("gas_budget.db")
    conn.row_factory = sqlite3.Row  # Required for name-based access
    cursor = conn.cursor()

    cursor.execute("""
        SELECT total_gas_mass, weight_limit, base_weight_limit
        FROM gas_masses
        ORDER BY id DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    if row:
        gas_mass = row["total_gas_mass"]
        weight_limit = row["weight_limit"]
        base_weight_limit = row["base_weight_limit"]
        return gas_mass, weight_limit, base_weight_limit
    else:
        return 0, 0, 0



def get_cumulative_meal_mass():
    import sqlite3
    conn = sqlite3.connect("meal_schedule.db")
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(food_grams + beverage_grams) FROM daily_meals")
    row = cursor.fetchone()
    conn.close()
    total_grams = row[0] if row and row[0] else 0
    return round(total_grams / 1000.0, 2)  # convert g to kg

def get_last_meal_day(db_path, crew_name):
    """
    Returns the last day number that has a meal assigned for the given crew member.
    If no meals exist, returns 0.
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MAX(day) FROM daily_meals WHERE crew_name = ?
    """, (crew_name,))
    result = cursor.fetchone()[0]
    conn.close()
    return result if result is not None else 0


def insert_daily_meals(db_path, meals: list, sufficiency_map: dict):
    """
    Insert a list of meal dicts into the daily_meals table.
    Also insert sufficiency status and intake ratio into crew_sufficiency.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure the daily_meals table exists
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

    # Ensure the sufficiency table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crew_sufficiency (
            crew_name TEXT PRIMARY KEY,
            sufficiency_status TEXT,
            intake_ratio REAL
        );
    """)

    # Insert meals
    for m in meals:
        cursor.execute("""
            INSERT OR REPLACE INTO daily_meals (
                crew_name, day, meal,
                food_name, food_grams, food_rating,
                beverage_name, beverage_grams, beverage_rating
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            m['crew_name'], m['day'], m['meal'],
            m['food_name'], m['food_grams'], m.get('food_rating', None),
            m['beverage_name'], m['beverage_grams'], m.get('beverage_rating', None)
        ))

    # Insert sufficiency info with intake ratio
    for crew_name, summary in sufficiency_map.items():
        status = summary['status']
        ratio = summary['intake_ratio']
        cursor.execute("""
            INSERT OR REPLACE INTO crew_sufficiency (
                crew_name, sufficiency_status, intake_ratio
            ) VALUES (?, ?, ?);
        """, (
            crew_name, status, ratio
        ))

    conn.commit()
    conn.close()




def get_latest_duration_from_gas_budget(db_path='gas_budget.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT duration FROM gas_masses ORDER BY timestamp DESC LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    return int(result[0]) if result else 7  # fallback to 7 if no entry

def insert_gas_budget(db_path, data: dict):
    if data.get("base_weight_limit") is None:
        raise ValueError("🛑 Attempted to insert gas_mass record with NULL base_weight_limit.")

    """
    Insert a new gas budget record into the gas_masses table.
    Creates the table if it doesn't exist.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gas_masses (
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

            -- New fields
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
            'water_recycler_mass' REAL,
            'total_life_support_mass' REAL,
            base_weight_limit REAL
        );
    """)

    # Insert dynamic keys
    columns = ', '.join(data.keys())
    placeholders = ', '.join(['?'] * len(data))
    query = f"INSERT INTO gas_masses ({columns}) VALUES ({placeholders})"
    cursor.execute(query, tuple(data.values()))
    conn.commit()
    conn.close()

def get_latest_gas_budget_record(db_path='gas_budget.db'):
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Ensure the table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gas_masses (
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

            -- New fields
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
            'water_recycler_mass' REAL,
            'total_life_support_mass' REAL,
            base_weight_limit REAL

        );
    """)

    # Try to fetch the most recent record
    cursor.execute("""
        SELECT * FROM gas_masses
        ORDER BY timestamp DESC
        LIMIT 1;
    """)
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_cumulative_meal_mass(meal_db_path='meal_schedule.db'):
    import sqlite3
    try:
        conn = sqlite3.connect(meal_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(food_grams + beverage_grams) FROM daily_meals")
        result = cursor.fetchone()[0]
        conn.close()
        return round(result / 1000.0, 2) if result else 0.0  # grams → kg
    except Exception as e:
        print(f"Error calculating cumulative meal mass: {e}")
        return 0.0
