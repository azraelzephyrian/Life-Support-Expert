from experta import *
import numpy as np
from datetime import datetime
from db_utils import insert_gas_budget

class LifeSupportFacts(Fact):
    """Holds all mission and crew parameters."""
    pass

class LifeSupportEngine(KnowledgeEngine):

    def __init__(self):
        super().__init__()
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
            recycler_weight=MATCH.recycler_weight
        )
    )
    def compute_life_support(self, duration, crew_count, body_masses, activity,
                             oxygen_tank_weight_per_kg, weight_limit,
                             use_scrubber, use_recycler,
                             co2_scrubber_efficiency, scrubber_weight_per_kg,
                             co2_recycler_efficiency, recycler_weight):

        print("✔ Rule fired. Parameters:")
        print(locals())  # Print all bound parameters for debug

        # === OXYGEN NEED ===
        base_o2_per_day = 0.75  # kg/day per 70kg at rest
        activity_factor = {'low': 1.0, 'moderate': 1.5, 'daily': 2.0}
        adjusted_factors = [mass / 70.0 for mass in body_masses]
        total_o2_required = duration * base_o2_per_day * activity_factor[activity] * sum(adjusted_factors)

        # === CO2 GENERATION ===
        base_co2_per_day = {'low': 0.8, 'moderate': 1.4, 'daily': 2.2}
        total_co2_generated = duration * base_co2_per_day[activity] * crew_count

        if use_scrubber and use_recycler:
            self.results['error'] = "Cannot use both scrubber and recycler. Choose only one."
            return

        scrubber_mass = 0
        recycler_mass = 0
        o2_reclaimed = 0

        if use_scrubber:
            co2_removed = total_co2_generated * (co2_scrubber_efficiency / 100.0)
            scrubber_mass = co2_removed * scrubber_weight_per_kg
        elif use_recycler:
            o2_reclaimed = total_co2_generated * (co2_recycler_efficiency / 100.0)
            recycler_mass = recycler_weight

        o2_from_tanks = total_o2_required - o2_reclaimed
        o2_from_tanks = max(o2_from_tanks, 0)

        tank_mass = o2_from_tanks * oxygen_tank_weight_per_kg
        total_mass = tank_mass + scrubber_mass + recycler_mass

        self.results['o2_required_kg'] = round(total_o2_required, 2)
        self.results['o2_reclaimed'] = round(o2_reclaimed, 2)
        self.results['o2_tank_mass'] = round(tank_mass, 2)
        self.results['scrubber_mass'] = round(scrubber_mass, 2)
        self.results['recycler_mass'] = round(recycler_mass, 2)
        self.results['co2_generated'] = round(total_co2_generated, 2)
        self.results['total_life_support_mass'] = round(total_mass, 2)
        self.results['within_limit'] = total_mass <= weight_limit

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
                'within_limit': total_mass <= weight_limit
            }
        )



        print("=== Engine Results ===")
        print(self.results)
