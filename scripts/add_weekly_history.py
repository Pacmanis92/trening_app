"""Jednorazowo, ręcznie: dopisuje 1 trening tygodniowo z losowymi wartościami za ostatnie 15 miesięcy.

Uruchom: python scripts/add_weekly_history.py [ścieżka_do_bazy]
Dodaje tylko treningi w tygodniach (pn-nd), w których nie ma jeszcze żadnego treningu, i tylko dla ćwiczeń, które
mają już zapisy. Niczego nie usuwa; przed zmianami robi kopię pliku bazy (<baza>.RRRRMMDD.HHMM.bak).
"""
import random
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trainbeast.database import default_db_path, make_engine, make_session_factory  # noqa: E402
from trainbeast.models import Exercise, Workout, WorkoutExercise, WorkoutSet  # noqa: E402

MONTHS = 15


def random_set(exercise: Exercise, position: int) -> WorkoutSet:
    rnd = random.Random()
    st = WorkoutSet(position=position, done=True)
    if exercise.load_type == "weight":
        st.weight_kg = rnd.choice([50, 52.5, 55, 57.5, 60, 62.5, 65])
        st.reps = rnd.randint(6, 12)
    elif exercise.load_type == "distance":
        st.duration_s = rnd.randint(1200, 2400)
        st.distance_m = int(st.duration_s * rnd.uniform(6.5, 8.5))
    else:  # floors
        st.reps = rnd.randint(40, 70)
        st.duration_s = rnd.randint(600, 1000)
    return st


def main() -> None:
    db_file = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else default_db_path()
    shutil.copy2(db_file, db_file.with_name(f"{db_file.name}.{datetime.now():%Y%m%d.%H%M}.bak"))
    sf = make_session_factory(make_engine(f"sqlite:///{db_file}"))
    today = date.today()
    year, month = divmod(today.year * 12 + today.month - 1 - MONTHS, 12)
    since = date(year, month + 1, min(today.day, 28))
    with sf.begin() as s:
        used = {w for w in s.scalars(select(Workout.workout_date))}
        weeks_taken = {d - timedelta(days=d.weekday()) for d in used}
        exercises = [
            e for e in s.scalars(select(Exercise)) if s.scalars(select(WorkoutExercise.id).where(WorkoutExercise.exercise_id == e.id)).first()
        ]
        monday = since - timedelta(days=since.weekday())
        added = 0
        while monday <= today:
            if monday not in weeks_taken:
                day = monday + timedelta(days=random.randint(0, 6))
                if since <= day <= today:
                    workout = Workout(workout_date=day, name="", exercises=[])
                    for pos, ex in enumerate(exercises):
                        we = WorkoutExercise(exercise_id=ex.id, position=pos, sets=[])
                        we.sets = [random_set(ex, n) for n in range(random.randint(2, 4))]
                        workout.exercises.append(we)
                    s.add(workout)
                    added += 1
            monday += timedelta(days=7)
    print(f"Dodano treningów: {added}")


if __name__ == "__main__":
    main()
