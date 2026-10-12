"""Service for student_rosters. All logic is in roster_kit.py (the two rosters share one shape)."""
from .roster_kit import Roster

R = Roster("student_roster")
EXPANDABLE = True
create, create_with_person, get, list, update, update_with_person, soft_delete = (
    R.create, R.create_with_person, R.get, R.list, R.update, R.update_with_person, R.soft_delete)
