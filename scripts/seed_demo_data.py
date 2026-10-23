"""Jednorazowo, ręcznie: czyści historię treningów i zapisuje sztuczne treningi (3 miesiące, pn/śr/pt).

Uruchom: python scripts/seed_demo_data.py [ścieżka_do_bazy]
Przed zmianami robi kopię pliku bazy obok oryginału (<baza>.RRRRMMDD.bak). Katalog ćwiczeń, sekcje,
ćwiczenia własne i ustawienia zostają; usuwane są tylko treningi, ćwiczenia w treningach i serie.
"""
import shutil
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trainbeast.database import default_db_path, make_engine, make_session_factory  # noqa: E402
from trainbeast.models import Exercise, Workout, WorkoutExercise, WorkoutSet  # noqa: E402
from trainbeast.services import DEMO_EXERCISES, TrainingService, generate_demo_workouts  # noqa: E402


def main() -> None:
    db_file = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else default_db_path()
    today = date.today()
    if db_file.is_file():
        backup = db_file.with_name(f"{db_file.name}.{today:%Y%m%d}.bak")
        shutil.copy2(db_file, backup)
        print(f"Kopia zapasowa: {backup}")
    sf = make_session_factory(make_engine(f"sqlite:///{db_file}"))
    TrainingService(sf)  # dopisuje brakujące ćwiczenia startowe (idempotentnie)
    with sf.begin() as s:
        ids = {}
        for name in DEMO_EXERCISES:  # pełna nazwa w katalogu: „<EN> (<PL>)”
            exercise = s.scalars(select(Exercise).where(Exercise.name.like(f"{name} (%"))).first()
            if exercise is None:
                print(f"Brak w katalogu: {name} (pomijam)")
            else:
                ids[name] = exercise.id
        s.execute(delete(WorkoutSet))
        s.execute(delete(WorkoutExercise))
        s.execute(delete(Workout))
        workouts = sets = 0
        for demo in generate_demo_workouts(today):
            workout = Workout(workout_date=demo.day, name="", exercises=[])
            for position, ex in enumerate(e for e in demo.exercises if e.name in ids):
                we = WorkoutExercise(exercise_id=ids[ex.name], position=position, sets=[])
                for set_position, st in enumerate(ex.sets):
                    we.sets.append(
                        WorkoutSet(
                            position=set_position,
                            weight_kg=st.weight_kg,
                            distance_m=st.distance_m,
                            reps=st.reps,
                            duration_s=st.duration_s,
                            done=st.done,
                        )
                    )
                    sets += 1
                workout.exercises.append(we)
            s.add(workout)
            workouts += 1
    print(f"Utworzono treningów: {workouts}, serii: {sets}")


if __name__ == "__main__":
    main()
