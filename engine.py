#engine.py

import collections
import collections.abc
collections.Mapping = collections.abc.Mapping
from experta import *
from datetime import datetime
from db_utils import insert_gas_budget

class LifeSupportFacts(Fact): pass

class LifeSupportEngine(KnowledgeEngine):
    def __init__(self):
        super().__init__()
        self.results = {}

    @Rule(LifeSupportFacts())
    def initialize(self):
        fact = next(f for f in self.facts.values() if isinstance(f, LifeSupportFacts))
        # Store parameters for reuse across rules
        for key in fact.keys():
            setattr(self, key, fact[key])
        # Init reclaim-related vars
        self.total_o2_required = 0
        self.total_co2_generated = 0
        self.co2_removed_by_scrubber = 0
        self.scrubber_mass = 0
        self.recycler_mass = 0
        self.o2_reclaimed = 0
        self.water_net = 0
        self.total_mass = 0
        self.tank_mass = 0
        self.n2_required = 0
        self.n2_tank_mass = 0
        self.hygiene_total = 0
        self.excretion_total = 0
        self.recovered_water = 0
        self.total_water = 0
        self.declare(Fact(stage='oxygen_needs'))

    @Rule(Fact(stage='oxygen_needs'))
    def compute_o2_need(self):
        base_o2_per_day = 0.75
        activity_factor = {'low': 1.0, 'moderate': 1.5, 'daily': 2.0}
        adjusted_factors = [m / 70.0 for m in self.body_masses]
        self.total_o2_required = self.duration * base_o2_per_day * activity_factor[self.activity] * sum(adjusted_factors)
        self.results['o2_required_kg'] = round(self.total_o2_required, 2)
        self.declare(Fact(stage='co2_generation'))

    @Rule(Fact(stage='co2_generation'))
    def compute_co2_generated(self):
        base_co2_per_day = {'low': 0.8, 'moderate': 1.4, 'daily': 2.2}
        self.total_co2_generated = self.duration * base_co2_per_day[self.activity] * self.crew_count
        self.results['co2_generated'] = round(self.total_co2_generated, 2)
        self.declare(Fact(stage='scrubber_processing'))

    @Rule(Fact(stage='scrubber_processing'))
    def scrubber(self):
        if self.use_scrubber:
            eff = self.co2_scrubber_efficiency
            if eff < 1.0: eff *= 100.0
            self.co2_removed_by_scrubber = self.total_co2_generated * (eff / 100.0)
            self.scrubber_mass = self.co2_removed_by_scrubber * self.scrubber_weight_per_kg
            self.o2_reclaimed += self.co2_removed_by_scrubber * 0.8
        self.results['scrubber_mass'] = round(self.scrubber_mass, 2)
        self.declare(Fact(stage='recycler_processing'))

    @Rule(Fact(stage='recycler_processing'))
    def recycler(self):
        if self.use_recycler:
            eff = self.co2_recycler_efficiency
            if eff < 1.0: eff *= 100.0
            co2_left_for_recycler = max(self.total_co2_generated - self.co2_removed_by_scrubber, 0)
            self.o2_reclaimed += co2_left_for_recycler * (eff / 100.0)
            self.recycler_mass = self.recycler_weight
        self.results['recycler_mass'] = round(self.recycler_mass, 2)
        self.results['o2_reclaimed'] = round(self.o2_reclaimed, 2)
        self.declare(Fact(stage='oxygen_tank_calc'))

    @Rule(Fact(stage='oxygen_tank_calc'))
    def o2_tank(self):
        o2_from_tanks = max(self.total_o2_required - self.o2_reclaimed, 0)
        self.tank_mass = o2_from_tanks * (1 + self.oxygen_tank_weight_per_kg)
        self.results['o2_tank_mass'] = round(self.tank_mass, 2)
        self.declare(Fact(stage='nitrogen_calc'))

    @Rule(Fact(stage='nitrogen_calc'))
    def nitrogen(self):
        self.n2_required = self.total_o2_required * 3.71
        self.n2_tank_mass = self.n2_required * self.nitrogen_tank_weight_per_kg
        self.results['n2_required_kg'] = round(self.n2_required, 2)
        self.results['n2_tank_mass'] = round(self.n2_tank_mass, 2)
        self.declare(Fact(stage='water_calc'))

    @Rule(Fact(stage='water_calc'))
    def water(self):
        self.hygiene_total = self.crew_count * self.duration * self.hygiene_water_per_day
        self.excretion_total = self.crew_count * self.duration * 3 * 250
        self.total_water = self.hygiene_total + self.excretion_total
        self.recovered_water = self.total_water * (self.water_recycler_efficiency / 100.0) if self.use_water_recycler else 0
        self.water_net = self.total_water - self.recovered_water
        self.results.update({
            'water_hygiene_raw': round(self.hygiene_total, 2),
            'water_excretion': round(self.excretion_total, 2),
            'water_recovered': round(self.recovered_water, 2),
            'water_net': round(self.water_net, 2),
            'water_recycler_mass': round(self.water_recycler_weight, 2)
        })
        self.declare(Fact(stage='total_mass_calc'))

    @Rule(Fact(stage='total_mass_calc'))
    def finalize(self):
        self.total_mass = (
            self.tank_mass +
            self.scrubber_mass +
            self.recycler_mass +
            self.n2_tank_mass +
            self.water_net / 1000 +
            self.water_recycler_weight
        )
        self.results['total_life_support_mass'] = round(self.total_mass, 2)
        self.results['within_limit'] = self.total_mass <= self.weight_limit

        # Final insert
        try:
            insert_gas_budget("gas_budget.db", {
                'timestamp': datetime.utcnow().isoformat(),
                'duration': self.duration,
                'crew_count': self.crew_count,
                'body_masses': ','.join(map(str, self.body_masses)),
                'activity': self.activity,
                'oxygen_tank_weight_per_kg': self.oxygen_tank_weight_per_kg,
                'co2_generated': round(self.total_co2_generated, 2),
                'o2_required_kg': round(self.total_o2_required, 2),
                'o2_reclaimed': round(self.o2_reclaimed, 2),
                'o2_tank_mass': round(self.tank_mass, 2),
                'scrubber_mass': round(self.scrubber_mass, 2),
                'recycler_mass': round(self.recycler_mass, 2),
                'total_gas_mass': round(self.total_mass, 2),
                'use_scrubber': self.use_scrubber,
                'use_recycler': self.use_recycler,
                'co2_scrubber_efficiency': self.co2_scrubber_efficiency,
                'scrubber_weight_per_kg': self.scrubber_weight_per_kg,
                'co2_recycler_efficiency': self.co2_recycler_efficiency,
                'recycler_weight': self.recycler_weight,
                'within_limit': self.total_mass <= self.weight_limit,
                'weight_limit': self.weight_limit,
                'n2_required_kg': round(self.n2_required, 2),
                'n2_tank_mass': round(self.n2_tank_mass, 2),
                'water_hygiene_raw': round(self.hygiene_total, 2),
                'water_excretion': round(self.excretion_total, 2),
                'water_recovered': round(self.recovered_water, 2),
                'water_net': round(self.water_net, 2),
                'use_water_recycler': self.use_water_recycler,
                'water_recycler_efficiency': self.water_recycler_efficiency,
                'nitrogen_tank_weight_per_kg': self.nitrogen_tank_weight_per_kg,
                'hygiene_water_per_day': self.hygiene_water_per_day,
                'water_recycler_mass': round(self.water_recycler_weight, 2),
                'total_life_support_mass': round(self.total_mass, 2),
                'base_weight_limit': self.base_weight_limit
            })
        except Exception as e:
            print("⚠️ insert_gas_budget failed:", e)

        print("✅ Final Results:")
        print(self.results)




class LifeSupportFacts(Fact):
    """Holds all mission and crew parameters."""
    pass

class LifeSupportEngine(KnowledgeEngine):
    def __init__(self):
        super().__init__()
        print("🚧 Engine initialized")
        self.results = {}

    @Rule(
        LifeSupportFacts(
            duration=MATCH.duration,
            crew_count=MATCH.crew_count,
            body_masses=MATCH.body_masses,
            activity=MATCH.activity,
            oxygen_tank_weight_per_kg=MATCH.oxygen_tank_weight_per_kg,
            weight_limit=MATCH.weight_limit,
            use_scrubber=MATCH.use_scrubber,
            use_recycler=MATCH.use_recycler,
            co2_scrubber_efficiency=MATCH.co2_scrubber_efficiency,
            scrubber_weight_per_kg=MATCH.scrubber_weight_per_kg,
            co2_recycler_efficiency=MATCH.co2_recycler_efficiency,
            recycler_weight=MATCH.recycler_weight,
            nitrogen_tank_weight_per_kg=MATCH.nitrogen_tank_weight_per_kg,
            hygiene_water_per_day=MATCH.hygiene_water_per_day,
            use_water_recycler=MATCH.use_water_recycler,
            water_recycler_efficiency=MATCH.water_recycler_efficiency,
            water_recycler_weight=MATCH.water_recycler_weight
        )
    )
    def compute_life_support(self, duration, crew_count, body_masses, activity,
                         oxygen_tank_weight_per_kg, weight_limit,
                         use_scrubber, use_recycler, co2_scrubber_efficiency,
                         scrubber_weight_per_kg, co2_recycler_efficiency,
                         recycler_weight, nitrogen_tank_weight_per_kg,
                         hygiene_water_per_day, use_water_recycler,
                         water_recycler_efficiency, water_recycler_weight):

        print("🚀 Rule matched. Searching for LifeSupportFacts...")
        print("🚀 LifeSupportFacts bound:")
        print(f"📅 Duration: {duration} days")
        print(f"👥 Crew count: {crew_count} members")
        print(f"⚖️ Body masses: {body_masses}")
        print(f"🏃 Activity level: {activity}")
        print(f"🫧 Hygiene water/day: {hygiene_water_per_day} g")
        print(f"🟦 O₂ tank mass/kg: {oxygen_tank_weight_per_kg}")
        print(f"🟨 N₂ tank mass/kg: {nitrogen_tank_weight_per_kg}")
        print(f"💧 Use water recycler: {use_water_recycler} (efficiency: {water_recycler_efficiency}%, mass: {water_recycler_weight} kg)")
        print(f"🧪 Use scrubber: {use_scrubber} (efficiency: {co2_scrubber_efficiency}%, kg CO₂/kg scrubber: {scrubber_weight_per_kg})")
        print(f"🔁 Use CO₂ recycler: {use_recycler} (efficiency: {co2_recycler_efficiency}%, mass: {recycler_weight} kg)")
        print(f"🚫 Weight limit: {weight_limit} kg")


        # Grab the first matching LifeSupportFacts

        for f in self.facts.values():
            if isinstance(f, Fact) and all(k in f for k in ['duration', 'crew_count', 'body_masses']):
                fact = f
                break

        else:
            print("⚠️ No usable LifeSupportFacts found.")
            return

        # === Unpack facts ===
        duration = fact['duration']
        crew_count = fact['crew_count']
        body_masses = fact['body_masses']
        activity = fact['activity']
        oxygen_tank_weight_per_kg = fact['oxygen_tank_weight_per_kg']
        weight_limit = fact['weight_limit']
        use_scrubber = fact['use_scrubber']
        use_recycler = fact['use_recycler']
        co2_scrubber_efficiency = fact['co2_scrubber_efficiency']
        scrubber_weight_per_kg = fact['scrubber_weight_per_kg']
        co2_recycler_efficiency = fact['co2_recycler_efficiency']
        recycler_weight = fact['recycler_weight']
        nitrogen_tank_weight_per_kg = fact['nitrogen_tank_weight_per_kg']
        hygiene_water_per_day = fact['hygiene_water_per_day']
        use_water_recycler = fact['use_water_recycler']
        water_recycler_efficiency = fact['water_recycler_efficiency']
        water_recycler_weight = fact['water_recycler_weight']

        # === OXYGEN NEED ===
        base_o2_per_day = 0.75
        activity_factor = {'low': 1.0, 'moderate': 1.5, 'daily': 2.0}
        adjusted_factors = [mass / 70.0 for mass in body_masses]
        total_o2_required = duration * base_o2_per_day * activity_factor[activity] * sum(adjusted_factors)

        # === CO2 GENERATION ===
        base_co2_per_day = {'low': 0.8, 'moderate': 1.4, 'daily': 2.2}
        total_co2_generated = duration * base_co2_per_day[activity] * crew_count

        scrubber_mass = 0
        recycler_mass = 0
        o2_reclaimed = 0
        co2_removed_by_scrubber = 0

        if use_scrubber:
            eff = co2_scrubber_efficiency
            if eff < 1.0: eff *= 100.0
            co2_removed_by_scrubber = total_co2_generated * (eff / 100.0)
            scrubber_mass = co2_removed_by_scrubber * scrubber_weight_per_kg
            o2_reclaimed += co2_removed_by_scrubber * 0.8  # assume 80% yield

        if use_recycler:
            eff = co2_recycler_efficiency
            if eff < 1.0: eff *= 100.0
            remaining_co2 = max(total_co2_generated - co2_removed_by_scrubber, 0)
            reclaimed_by_recycler = remaining_co2 * (eff / 100.0)
            o2_reclaimed += reclaimed_by_recycler
            recycler_mass = recycler_weight

        # ✅ Cap reclaimed O₂ to the amount needed
        o2_reclaimed = min(o2_reclaimed, total_o2_required)

        o2_from_tanks = max(total_o2_required - o2_reclaimed, 0)
        tank_mass = o2_from_tanks * (1 + oxygen_tank_weight_per_kg)

        total_mass = tank_mass + scrubber_mass + recycler_mass

        # === NITROGEN REQUIREMENT ===
        n2_required = total_o2_required * 3.71
        n2_tank_mass = n2_required * nitrogen_tank_weight_per_kg
        total_mass += n2_tank_mass

        # === WATER: Hygiene + Excretion ===
        hygiene_total = crew_count * duration * hygiene_water_per_day
        excretion_total = crew_count * duration * 3 * 250
        water_total_raw = hygiene_total + excretion_total

        recovered_water = water_total_raw * (water_recycler_efficiency / 100.0) if use_water_recycler else 0
        water_net = water_total_raw - recovered_water
        total_mass += water_net / 1000
        total_mass += water_recycler_weight

        # === Store Results ===
        self.results['o2_required_kg'] = round(total_o2_required, 2)
        self.results['o2_reclaimed'] = round(o2_reclaimed, 2)
        self.results['o2_tank_mass'] = round(tank_mass, 2)
        self.results['scrubber_mass'] = round(scrubber_mass, 2)
        self.results['recycler_mass'] = round(recycler_mass, 2)
        self.results['co2_generated'] = round(total_co2_generated, 2)
        self.results['within_limit'] = total_mass <= weight_limit
        self.results['n2_required_kg'] = round(n2_required, 2)
        self.results['n2_tank_mass'] = round(n2_tank_mass, 2)
        self.results['water_hygiene_raw'] = round(hygiene_total, 2)
        self.results['water_excretion'] = round(excretion_total, 2)
        self.results['water_recovered'] = round(recovered_water, 2)
        self.results['water_net'] = round(water_net, 2)
        self.results['water_recycler_mass'] = round(water_recycler_weight, 2)
        self.results['total_life_support_mass'] = round(total_mass, 2)

        # === Insert into DB ===
        try:
            insert_gas_budget(
                db_path='gas_budget.db',
                data={
                    'timestamp': datetime.utcnow().isoformat(),
                    'duration': duration,
                    'crew_count': crew_count,
                    'body_masses': ','.join([str(x) for x in body_masses]),
                    'activity': activity,
                    'oxygen_tank_weight_per_kg': oxygen_tank_weight_per_kg,
                    'co2_generated': round(total_co2_generated, 2),
                    'o2_required_kg': round(total_o2_required, 2),
                    'o2_reclaimed': round(o2_reclaimed, 2),
                    'o2_tank_mass': round(tank_mass, 2),
                    'scrubber_mass': round(scrubber_mass, 2),
                    'recycler_mass': round(recycler_mass, 2),
                    'total_gas_mass': round(total_mass, 2),
                    'use_scrubber': use_scrubber,
                    'use_recycler': use_recycler,
                    'co2_scrubber_efficiency': co2_scrubber_efficiency,
                    'scrubber_weight_per_kg': scrubber_weight_per_kg,
                    'co2_recycler_efficiency': co2_recycler_efficiency,
                    'recycler_weight': recycler_weight,
                    'within_limit': total_mass <= weight_limit,
                    'weight_limit': weight_limit,
                    'n2_required_kg': round(n2_required, 2),
                    'n2_tank_mass': round(n2_tank_mass, 2),
                    'water_hygiene_raw': round(hygiene_total, 2),
                    'water_excretion': round(excretion_total, 2),
                    'water_recovered': round(recovered_water, 2),
                    'water_net': round(water_net, 2),
                    'use_water_recycler': use_water_recycler,
                    'water_recycler_efficiency': water_recycler_efficiency,
                    'nitrogen_tank_weight_per_kg': nitrogen_tank_weight_per_kg,
                    'hygiene_water_per_day': hygiene_water_per_day,
                    'water_recycler_mass': round(water_recycler_weight, 2),
                    'total_life_support_mass': round(total_mass, 2)
                }
            )
        except Exception as e:
            print("⚠️ insert_gas_budget failed:", e)

        print("✅ Engine Results:")
        print(self.results)