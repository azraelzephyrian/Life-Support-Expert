import collections
import collections.abc
collections.Mapping = collections.abc.Mapping
from experta import *
import random

class PlannerConfig(Fact):
    """Holds planning constants like per_meal_kcal."""
    pass


class MealSlot(Fact):
    """A meal that needs to be filled for a crew member"""
    pass

class FoodOption(Fact):
    """A candidate food with calories and rating"""
    pass

class BeverageOption(Fact):
    """A candidate beverage with calories and rating"""
    pass

class MealHistory(Fact):
    """Tracks the last food and beverage assigned"""
    pass

class MealAssigned(Fact):
    """Represents a filled meal slot"""
    pass

class SelectedFood(Fact):
    """Represents a selected food assignment for a slot"""
    pass

class SelectedBeverage(Fact):
    """Represents a selected beverage assignment for a slot"""
    pass


class MealPlanner(KnowledgeEngine):
    def __init__(self, name, calorie_target, food_list, beverage_list, start_day, food_ratings, beverage_ratings, duration, water_per_meal=250, ration_fraction=1.0):
        super().__init__()
        self.name = name
        self.start_day = start_day
        self.calorie_target = calorie_target
        self.duration = duration
        self.water_per_meal = water_per_meal
        self.meals_per_day = 3
        self.per_meal_kcal = calorie_target / self.meals_per_day
        self.schedule = []
        self.ration_fraction = ration_fraction
        self.prev_foods = set()
        self.prev_beverages = set()
        # Tracks (day, meal index) → (food, beverage)
        self.history_by_slot = {}  # {(day, meal): (food, bev)}

        # Track list of last 6 food and bev choices (updated on finalize)
        self.last_6_items = []
        self.original_target = calorie_target
        self.gram_targets_by_food = {}

        # Track last assigned food/bev
        self.last_food = None
        self.last_bev = None
        # inside setup()

        self.daily_target = calorie_target              # e.g., 2400 kcal/day
        self.original_target = calorie_target * duration  # e.g., 2400 × 7 = 16,800 kcal





        # ✅ Store the raw rating dictionaries
        self.food_ratings = {k.lower(): v for k, v in food_ratings.items()}
        self.beverage_ratings = {k.lower(): v for k, v in beverage_ratings.items()}

        self.foods = []
        for f in food_list:
            name = f.get('food_name') or f.get('name')
            if name:
                rating = self.food_ratings.get(name.lower())
                if rating is not None and rating > 1:
                    f['food_name'] = name
                    f['rating'] = rating
                    self.foods.append(f)

        self.beverages = []
        for b in beverage_list:
            name = b.get('beverage_name') or b.get('name')
            if name:
                rating = self.beverage_ratings.get(name.lower())
                if rating is not None and rating > 1:
                    b['beverage_name'] = name
                    b['rating'] = rating
                    self.beverages.append(b)

    def setup(self):
        self.reset()

        # 🔁 Force re-calculate per-meal target (defensive)
        self.per_meal_kcal = (self.calorie_target * self.ration_fraction) / self.meals_per_day

        # Declare all slots
        for i in range(self.duration):
            day = self.start_day + i
            for meal in range(1, self.meals_per_day + 1):
                self.declare(MealSlot(day=day, meal=meal, crew_name=self.name))

        for food in self.foods:
            cpg = food['calories_per_gram']
            self.declare(FoodOption(
                food_name=food['food_name'],
                calories_per_gram=cpg,
                rating=food['rating']
            ))


        for bev in self.beverages:
            self.declare(BeverageOption(
                beverage_name=bev['beverage_name'],
                calories_per_gram=bev['calories_per_gram'],
                rating=bev['rating']
            ))

        self.meal_history_fact = self.declare(MealHistory(crew_name=self.name, last_food=None, last_bev=None))





    def slot_already_assigned(self, fact_type, day, meal):
        return any(
            isinstance(f, fact_type) and f['day'] == day and f['meal'] == meal
            for f in self.facts.values()
        )
    
    def weighted_choice(self, candidates, weight_key):
        total = sum(f[weight_key] for f in candidates)
        r = random.uniform(0, total)
        upto = 0
        for f in candidates:
            if upto + f[weight_key] >= r:
                return f
            upto += f[weight_key]
        return candidates[-1]

    def is_food_allowed(self, food_name, day, meal):
        # 🚫 No immediate repeat
        if food_name == self.last_food:
            return False

        # 🚫 No same-slot repeat from previous day
        if (day - 1, meal) in self.history_by_slot:
            if self.history_by_slot[(day - 1, meal)][0] == food_name:
                return False

        # 🚫 No recent 6-meal repeats
        if food_name in self.last_6_items:
            return False

        return True

    def is_bev_allowed(self, bev_name, day, meal):
        if bev_name == self.last_bev:
            return False
        if (day - 1, meal) in self.history_by_slot:
            if self.history_by_slot[(day - 1, meal)][1] == bev_name:
                return False
        if bev_name in self.last_6_items:
            return False
        return True

    @Rule(
        MealSlot(day=MATCH.day, meal=MATCH.meal, crew_name=MATCH.name),
        AS.history << MealHistory(crew_name=MATCH.name, last_food=MATCH.last_food, last_bev=MATCH.last_bev),
        AS.food << FoodOption(
            food_name=MATCH.fname,
            calories_per_gram=MATCH.cpg,
            rating=MATCH.rating
        ),
        TEST(lambda fname, last_food: last_food is None or fname != last_food),
        salience=2
    )
    def assign_food(self, food, fname, cpg, rating, day, meal, name, last_food, last_bev):
        if self.slot_already_assigned(SelectedFood, day, meal):
            return

        if not self.is_food_allowed(fname, day, meal):
            return

        grams = round(self.per_meal_kcal / cpg, 2) if cpg > 0 else 0

        self.last_food = fname
        self.declare(SelectedFood(
            food=fname,
            food_grams=grams,
            day=day,
            meal=meal
        ))











    @Rule(
        MealSlot(day=MATCH.day, meal=MATCH.meal, crew_name=MATCH.name),
        AS.history << MealHistory(crew_name=MATCH.name, last_food=MATCH.last_food, last_bev=MATCH.last_bev),
        AS.bev << BeverageOption(beverage_name=MATCH.bname, calories_per_gram=MATCH.cpb, rating=MATCH.rating),
        TEST(lambda bname, last_bev: last_bev is None or bname != last_bev),
        salience=2
    )
    def assign_beverage(self, bev, bname, cpb, rating, day, meal, name, last_food, last_bev):
        if self.slot_already_assigned(SelectedBeverage, day, meal):
            return

        candidates = [
            b for b in self.beverages
            if b['rating'] > 1 and self.is_bev_allowed(b['beverage_name'], day, meal)
        ]

        if not candidates:
            return

        chosen = self.weighted_choice(candidates, 'rating')

        self.last_bev = chosen['beverage_name']
        self.declare(SelectedBeverage(
            beverage=chosen['beverage_name'],
            beverage_grams=self.water_per_meal,
            day=day,
            meal=meal
        ))




    @Rule(
        AS.food_f << SelectedFood(day=MATCH.day, meal=MATCH.meal, food=MATCH.food, food_grams=MATCH.fg),
        AS.bev_f << SelectedBeverage(day=MATCH.day, meal=MATCH.meal, beverage=MATCH.bev, beverage_grams=MATCH.bg),
        AS.slot << MealSlot(day=MATCH.day, meal=MATCH.meal, crew_name=MATCH.name),
        AS.history << MealHistory(crew_name=MATCH.name, last_food=MATCH.last_food, last_bev=MATCH.last_bev),
        salience=1
    )
    def finalize_meal(self, food_f, bev_f, slot, day, meal, name, food, fg, bev, bg, history):
        print(f"✅ Finalizing Day {day}, Meal {meal} for {name}: {food} + {bev}")
        self.schedule.append({
            'day': day,
            'meal': meal,
            'food': food,
            'food_grams': fg,
            'beverage': bev,
            'beverage_grams': bg
        })
        self.modify(history, last_food=food, last_bev=bev)
        self.declare(MealAssigned(crew_name=name, day=day, meal=meal))

        # Record for full schedule history
        self.history_by_slot[(day, meal)] = (food, bev)

        # Maintain last-6 history sliding window
        self.last_6_items.append(food)
        self.last_6_items.append(bev)
        if len(self.last_6_items) > 12:  # 6 meals × 2 items
            self.last_6_items = self.last_6_items[-12:]

        self.retract(food_f)
        self.retract(bev_f)
        self.retract(slot)
        
    def plan_within_mass_budget(self, mass_budget):
        """
        Estimate a safe ration_fraction using actual food and beverage densities,
        then plan meals once using that fraction. Enforces mass budget strictly.
        """
        self.daily_target = self.original_target / self.duration  # kcal/day
        expected_meals = self.duration * self.meals_per_day

        # 🧠 Estimate average kcal/g for eligible foods and beverages
        avg_food_cpg = (
            sum(f['calories_per_gram'] for f in self.foods) / len(self.foods)
            if self.foods else 1.5
        )
        avg_bev_cpg = (
            sum(b['calories_per_gram'] for b in self.beverages) / len(self.beverages)
            if self.beverages else 0.4
        )

        # 🔍 Estimate average grams per meal
        water_grams_per_meal = self.water_per_meal
        avg_bev_kcal_per_meal = water_grams_per_meal * avg_bev_cpg
        avg_food_kcal_per_meal = self.daily_target / self.meals_per_day - avg_bev_kcal_per_meal
        avg_food_grams_per_meal = avg_food_kcal_per_meal / avg_food_cpg if avg_food_cpg > 0 else 0

        # 🧮 Total estimated mass
        total_food_grams = avg_food_grams_per_meal * expected_meals
        total_bev_grams = water_grams_per_meal * expected_meals
        estimated_total_kg = (total_food_grams + total_bev_grams) / 1000.0

        # 🔁 Adjust fraction if over budget
        estimated_fraction = min(1.0, mass_budget / estimated_total_kg)

        # 🧪 Apply and run
        self.ration_fraction = estimated_fraction
        self.calorie_target = self.daily_target * self.ration_fraction
        self.per_meal_kcal = self.calorie_target / self.meals_per_day
        self.schedule.clear()

        result = self.run_planner()
        result['ration_fraction'] = round(self.ration_fraction, 3)

        if len(result['schedule']) < expected_meals:
            result['warning'] = "⚠️ Partial schedule generated — not all meals assigned."

        if result['total_mass'] > mass_budget:
            result['warning'] = f"⚠️ Plan exceeds budget: {result['total_mass']} kg > {mass_budget} kg"

        return result





    def run_planner(self):
        self.setup()
        self.run()

        total_food_mass = round(sum(x['food_grams'] for x in self.schedule), 2)
        total_bev_mass = round(sum(x['beverage_grams'] for x in self.schedule), 2)

        # 🔁 Actual intake calculation
        total_intake_kcal = 0.0
        for meal in self.schedule:
            food_name = meal['food']
            food_grams = meal['food_grams']
            bev_name = meal['beverage']
            bev_grams = meal['beverage_grams']

            food_cpg = next((f['calories_per_gram'] for f in self.foods if f['food_name'] == food_name), 0)
            bev_cpg = next((b['calories_per_gram'] for b in self.beverages if b['beverage_name'] == bev_name), 0)

            total_intake_kcal += food_grams * food_cpg + bev_grams * bev_cpg

        # ✅ Use original calorie target to define sufficiency
        intake_ratio = total_intake_kcal / self.original_target if self.original_target > 0 else 0

        if intake_ratio < 0.85:
            sufficiency = 'insufficient'
        elif intake_ratio < 0.95:
            sufficiency = 'moderate'
        else:
            sufficiency = 'sufficient'

        return {
            'crew_member': self.name,
            'schedule': self.schedule,
            'total_food_mass': total_food_mass,
            'total_beverage_mass': total_bev_mass,
            'total_mass': round(total_food_mass + total_bev_mass, 2),
            'calorie_target': self.calorie_target,
            'rationed_kcal': round(total_intake_kcal, 2),
            'intake_ratio': round(intake_ratio, 3),
            'sufficiency_status': sufficiency
        }

