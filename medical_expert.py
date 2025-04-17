#medical_expert.py

from flask import Flask, request, jsonify
from experta import Fact, KnowledgeEngine, Rule, DefFacts, OR, NOT

# Define the Expert System (same as you already have)
class SpaceMedicalExpertSystem(KnowledgeEngine):
    def __init__(self):
        super().__init__()
        self.results = set()
        self._vestibular_notice_given = False  # Add flag


    @DefFacts()
    def _initial_action(self):
        yield Fact(action='start')

    # ---------------------- SYMPTOM RULES ----------------------
    def add_recommendation(self, text):
        self.results.add(text)


    @Rule(Fact(action='start'), Fact(symptom='muscle_pain', severity='mild'))
    def muscle_pain_mild(self):
        self.add_recommendation("🧮 Mild muscle pain: Light resistance exercises and hydration recommended.")

    @Rule(Fact(action='start'), Fact(symptom='muscle_pain', severity='moderate'))
    def muscle_pain_moderate(self):
        self.add_recommendation("🧮 Moderate muscle pain: Increase intensity of physical exercise and stretch frequently.")

    @Rule(Fact(action='start'), Fact(symptom='muscle_pain', severity='severe'))
    def muscle_pain_severe(self):
        self.add_recommendation("🧮 Severe muscle pain: Consult mission medical officer and consider analgesics.")

    @Rule(Fact(action='start'), Fact(symptom='vision_issue', severity='mild'))
    def vision_mild(self):
        self.add_recommendation("👁️ Mild vision issues: Limit screen exposure and stay hydrated.")

    @Rule(Fact(action='start'), Fact(symptom='vision_issue', severity='moderate'))
    def vision_moderate(self):
        self.add_recommendation("👁️ Moderate vision issues: Possible early SANS. Monitor closely and rest.")

    @Rule(Fact(action='start'), Fact(symptom='vision_issue', severity='severe'))
    def vision_severe(self):
        self.add_recommendation("👁️ Severe vision change: Risk of SANS. Alert medical team immediately.")

    @Rule(Fact(action='start'), Fact(symptom='stress', severity='mild'))
    def stress_mild(self):
        self.add_recommendation("🧘 Mild stress: Breathing exercises and music therapy suggested.")

    @Rule(Fact(action='start'), Fact(symptom='stress', severity='moderate'))
    def stress_moderate(self):
        self.add_recommendation("🧘 Moderate stress: Use mental health logs and talk with peers.")

    @Rule(Fact(action='start'), Fact(symptom='stress', severity='severe'))
    def stress_severe(self):
        self.add_recommendation("🧘 Severe stress: Contact onboard psychological support immediately.")

    @Rule(Fact(action='start'), Fact(symptom='back_pain', severity='mild'))
    def back_pain_mild(self):
        self.add_recommendation("🧐 Mild back pain: Try light stretching and adjust your sleeping posture.")

    @Rule(Fact(action='start'), Fact(symptom='back_pain', severity='moderate'))
    def back_pain_moderate(self):
        self.add_recommendation("🧐 Moderate back pain: Do core strengthening and posture correction exercises.")

    @Rule(Fact(action='start'), Fact(symptom='back_pain', severity='severe'))
    def back_pain_severe(self):
        self.add_recommendation("🧐 Severe back pain: Possible spinal deconditioning. Consult a flight surgeon.")

    @Rule(Fact(action='start'), Fact(symptom='insomnia', severity='mild'))
    def insomnia_mild(self):
        self.add_recommendation("🌙 Mild insomnia: Follow a strict sleep schedule and avoid caffeine.")

    @Rule(Fact(action='start'), Fact(symptom='insomnia', severity='moderate'))
    def insomnia_moderate(self):
        self.add_recommendation("🌙 Moderate insomnia: Use white noise and relaxation techniques before sleep.")

    @Rule(Fact(action='start'), Fact(symptom='insomnia', severity='severe'))
    def insomnia_severe(self):
        self.add_recommendation("🌙 Severe insomnia: Report to mission medical. Sleep meds might be necessary.")

    @Rule(Fact(action='start'), Fact(symptom='headache', severity='mild'))
    def headache_mild(self):
        self.add_recommendation("🧕 Mild headache: Drink water and avoid screen time.")

    @Rule(Fact(action='start'), Fact(symptom='headache', severity='moderate'))
    def headache_moderate(self):
        self.add_recommendation("🧕 Moderate headache: Check for CO₂ buildup. Rest and hydrate.")

    @Rule(Fact(action='start'), Fact(symptom='headache', severity='severe'))
    def headache_severe(self):
        self.add_recommendation("🧕 Severe headache: Possible ICP elevation. Seek urgent care.")

    @Rule(Fact(action='start'), Fact(symptom='dizziness', severity='mild'))
    def dizziness_mild(self):
        self.add_recommendation("🌀 Mild dizziness: Take slow movements and stay hydrated.")

    @Rule(Fact(action='start'), Fact(symptom='dizziness', severity='moderate'))
    def dizziness_moderate(self):
        self.add_recommendation("🌀 Moderate dizziness: Lie down briefly and monitor balance issues.")

    @Rule(Fact(action='start'), Fact(symptom='dizziness', severity='severe'))
    def dizziness_severe(self):
        self.add_recommendation("🌀 Severe dizziness: Risk of vestibular dysfunction. Alert medical staff.")

    @Rule(Fact(action='start'), Fact(symptom='appetite_loss', severity='mild'))
    def appetite_loss_mild(self):
        self.add_recommendation("🍽️ Mild appetite loss: Increase meal frequency with smaller portions.")

    @Rule(Fact(action='start'), Fact(symptom='appetite_loss', severity='moderate'))
    def appetite_loss_moderate(self):
        self.add_recommendation("🍽️ Moderate appetite loss: Nutritional monitoring required. Try favorite foods.")

    @Rule(Fact(action='start'), Fact(symptom='appetite_loss', severity='severe'))
    def appetite_loss_severe(self):
        self.add_recommendation("🍽️ Severe appetite loss: Malnutrition risk. Consult onboard dietician.")

    @Rule(Fact(action='start'), Fact(symptom='motion_sickness', severity='mild'))
    def motion_sickness_mild(self):
        self.add_recommendation("🚀 Mild motion sickness: Avoid quick head movements and sip water.")

    @Rule(Fact(action='start'), Fact(symptom='motion_sickness', severity='moderate'))
    def motion_sickness_moderate(self):
        self.add_recommendation("🚀 Moderate motion sickness: Take anti-nausea medication if available.")

    @Rule(Fact(action='start'), Fact(symptom='motion_sickness', severity='severe'))
    def motion_sickness_severe(self):
        self.add_recommendation("🚀 Severe motion sickness: Rest in stable position and seek medical aid.")

    # ---------------------- MISSION PHASE RULES ----------------------

    @Rule(Fact(action='start'), Fact(mission_phase='early'))
    def early_phase(self):
        self.add_recommendation("🕒 You are in the early phase of the mission. Some symptoms may relate to initial adaptation.")

    @Rule(Fact(action='start'), Fact(mission_phase='mid'))
    def mid_phase(self):
        self.add_recommendation("🕒 Mid-mission phase: Watch for circulatory, vision, and sleep-related symptoms.")

    # ---------------------- CORIOLIS RULES ----------------------

    @Rule(
        Fact(action='start'),
        OR(Fact(symptom='motion_sickness'), Fact(symptom='dizziness')),
        Fact(centrifugal_habitat=True)
    )
    def centrifugal_vestibular_effect(self):
        self.add_recommendation("🌀 Coriolis-induced vestibular disruption detected from centrifugal habitat. Take anti-nausea medication and relocate to a microgravity area temporarily.")

    @Rule(Fact(action='start'), Fact(mission_phase='late'), Fact(centrifugal_habitat=True))
    def late_phase_with_centrifuge(self):
        self.add_recommendation("🕒 Long-duration mission: Increased risk of immune suppression; possible slight risk of spaceflight associated neuro-ocular syndrome (SANS) and bone density loss, depending on centrifuge.")

    @Rule(Fact(action='start'), Fact(mission_phase='late'), NOT(Fact(centrifugal_habitat=True)))
    def late_phase_standard(self):
        self.add_recommendation("🕒 Long-duration mission: Increased risk of bone density loss, SANS, and immune suppression.")

    def get_results(self):
        return "\n".join(dict.fromkeys(self.results))  # preserves order but removes duplicates

