"""
Context for constraint building.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl
from ortools.sat.python import cp_model

from shared.optimizer.semesters import VALID_SEMESTERS


@dataclass
class Ctx:
    model: cp_model.CpModel
    take_vars: dict[tuple[int, int], cp_model.IntVar]
    courses_df: pl.DataFrame
    _subject_id2idx: dict[str, int] = field(default_factory=dict, init=False)
    _counter: int = field(default=0, init=False)

    # Track auxiliary variables for debugging/inspection after solving
    aux_vars: dict[str, cp_model.IntVar] = field(default_factory=dict)

    # Map from variable name to human-readable debug name
    var_name_map: dict[str, str] = field(default_factory=dict)

    # Map from course index to requirement paths it can satisfy (for category rewards)
    course_to_requirements: dict[int, set[str]] = field(default_factory=dict)

    # Cache for course "taken" variables (1 if course taken in any semester, 0 otherwise)
    # Used to avoid double-counting when same course appears in multiple requirement groups
    _course_taken_vars: dict[int, cp_model.IntVar] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        for idx, sid in enumerate(self.courses_df["subject_id"].to_list()):
            self._subject_id2idx[sid] = idx

    def fresh(self, prefix: str = "v") -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def get_idx(self, subject_id: str) -> int | None:
        return self._subject_id2idx.get(subject_id)

    def get_takes(self, course_idx: int) -> list[cp_model.IntVar]:
        return [self.take_vars[course_idx, s] for s in VALID_SEMESTERS if (course_idx, s) in self.take_vars]

    def get_by_attr(self, col: str, val: str) -> list[int]:
        if col not in self.courses_df.columns:
            return []
        vals = self.courses_df[col].to_list()
        return [i for i, v in enumerate(vals) if v == val]

    def get_any_hass(self) -> list[int]:
        if "hass_attribute" not in self.courses_df.columns:
            return []
        vals = self.courses_df["hass_attribute"].to_list()
        return [i for i, v in enumerate(vals) if v in ("HASS-A", "HASS-H", "HASS-S", "HASS-E")]

    def get_units(self, course_idx: int) -> int:
        if "total_units" not in self.courses_df.columns:
            return 12
        u = self.courses_df[course_idx, "total_units"]
        return int(u) if u is not None else 12

    def get_subject_id(self, course_idx: int) -> str:
        return self.courses_df[course_idx, "subject_id"]

    def is_half_class(self, course_idx: int) -> bool:
        if "is_half_class" not in self.courses_df.columns:
            return False
        val = self.courses_df[course_idx, "is_half_class"]
        return bool(val) if val is not None else False

    def register_aux_var(self, key: str, var: cp_model.IntVar) -> None:
        self.aux_vars[key] = var

    def register_var_name(self, var: cp_model.IntVar, debug_name: str) -> None:
        self.var_name_map[var.Name()] = debug_name

    def record_course_requirement(self, course_idx: int, path: str) -> None:
        if course_idx not in self.course_to_requirements:
            self.course_to_requirements[course_idx] = set()
        self.course_to_requirements[course_idx].add(path)

    def get_or_create_taken_var(self, course_idx: int) -> cp_model.IntVar | None:
        """
        Get or create a variable indicating whether the course is taken in any semester.
        This variable is cached to avoid double-counting when the same course appears
        in multiple requirement groups.
        """
        if course_idx in self._course_taken_vars:
            return self._course_taken_vars[course_idx]

        takes = self.get_takes(course_idx)
        if not takes:
            return None

        taken = self.model.NewBoolVar(self.fresh("taken"))
        self.model.AddMaxEquality(taken, takes)
        self._course_taken_vars[course_idx] = taken
        return taken
