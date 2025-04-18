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
