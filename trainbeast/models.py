from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Category(Base):
    """Kategoria (startowa) lub sekcja własna; `position` ustala kolejność."""

    __tablename__ = "category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    position: Mapped[int] = mapped_column(Integer)


class Exercise(Base):
    """Definicja ćwiczenia (osobno od jego wystąpienia w treningu)."""

    __tablename__ = "exercise"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    category: Mapped[str] = mapped_column(String(100))  # nazwa z tabeli Category
    # pierwsza oś: "weight" | "distance" | "reps" | "floors"
    load_type: Mapped[str] = mapped_column(String(10), default="weight")
    # druga oś: "reps" | "time"
    effort_type: Mapped[str] = mapped_column(String(10), default="reps")  # "reps" | "time"


class Workout(Base):
    __tablename__ = "workout"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_date: Mapped[date] = mapped_column(Date, unique=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    exercises: Mapped[list["WorkoutExercise"]] = relationship(
        back_populates="workout",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WorkoutExercise.position, WorkoutExercise.id",
    )


class WorkoutExercise(Base):
    """Wystąpienie ćwiczenia w konkretnym treningu."""

    __tablename__ = "workout_exercise"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workout.id", ondelete="CASCADE"))
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercise.id"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text, default=None)  # notatka do ćwiczenia w tym treningu

    workout: Mapped[Workout] = relationship(back_populates="exercises")
    exercise: Mapped[Exercise] = relationship()
    sets: Mapped[list["WorkoutSet"]] = relationship(
        back_populates="workout_exercise",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WorkoutSet.position",
    )


class WorkoutSet(Base):
    __tablename__ = "workout_set"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_exercise_id: Mapped[int] = mapped_column(
        ForeignKey("workout_exercise.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    # Jednostki bazowe; wypełnione tylko pola pasujące do typu ćwiczenia.
    weight_kg: Mapped[float | None] = mapped_column(Float, default=None)
    distance_m: Mapped[int | None] = mapped_column(Integer, default=None)
    reps: Mapped[int | None] = mapped_column(Integer, default=None)
    duration_s: Mapped[int | None] = mapped_column(Integer, default=None)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    # Jednostka wybrana przy serii (tylko etykieta - wartości zostają w jednostkach bazowych, bez przeliczania).
    # NULL = jednostka bazowa: kg / km / m.
    unit: Mapped[str | None] = mapped_column(String(5), default=None)  # kg | lbs | km | mile
    unit_minor: Mapped[str | None] = mapped_column(String(5), default=None)  # m | ys (dystans)

    workout_exercise: Mapped[WorkoutExercise] = relationship(back_populates="sets")
