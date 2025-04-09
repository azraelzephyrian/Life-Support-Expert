# app.py
from flask import Flask, render_template, request, redirect, url_for
from engine import LifeSupportEngine, LifeSupportFacts
from db_utils import init_db, insert_or_update, fetch_all_records

DB_PATH = 'astronauts.db'
TABLE_NAME = 'crew'
SCHEMA = {'name': 'TEXT', 'mass': 'TEXT'}
PRIMARY_KEY = 'name'

app = Flask(__name__)
init_db(DB_PATH, TABLE_NAME, SCHEMA, PRIMARY_KEY)

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

@app.route('/clear_crew', methods=['POST'])
def clear_crew():
    from sqlite3 import connect
    with connect(DB_PATH) as conn:
        conn.execute(f"DELETE FROM {TABLE_NAME}")
        conn.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
