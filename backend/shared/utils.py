from datetime import datetime

import polars as pl


class CourseOfferingCache:
    """Pre-computed course offering data for fast validity checks."""

    _instance: "CourseOfferingCache | None" = None
    _df_id: int | None = None

    def __init__(self, df: pl.DataFrame):
        self.offered_fall: list[bool] = df["offered_fall"].to_list()
        self.offered_IAP: list[bool] = df["offered_IAP"].to_list()
        self.offered_spring: list[bool] = df["offered_spring"].to_list()
        self.not_offered_year: list[str | None] = df["not_offered_year"].to_list()
        self.subject_ids: list[str] = df["subject_id"].to_list()

    @classmethod
    def get(cls, df: pl.DataFrame) -> "CourseOfferingCache":
        df_id = id(df)
        if cls._instance is None or cls._df_id != df_id:
            cls._instance = cls(df)
            cls._df_id = df_id
        return cls._instance


def is_valid_class_semester(
    class_idx: int,
    semester: int,
    df: pl.DataFrame,
    planning_year_start: int,
    musician: bool = False,
) -> bool:
    cache = CourseOfferingCache.get(df)

    # Determine the semester year and academic year string
    if semester % 3 == 1:  # Fall semester
        semester_year = planning_year_start + (semester // 3)
        academic_year = f"{semester_year}-{semester_year + 1}"
        semester_ok = cache.offered_fall[class_idx]
    elif semester % 3 == 2:  # IAP semester
        semester_year = planning_year_start + (semester // 3)
        academic_year = f"{semester_year}-{semester_year + 1}"
        semester_ok = cache.offered_IAP[class_idx]
    else:  # Spring semester
        semester_year = planning_year_start + (semester // 3) - 1
        academic_year = f"{semester_year}-{semester_year + 1}"
        semester_ok = cache.offered_spring[class_idx]

    not_offered_year = cache.not_offered_year[class_idx]
    if not_offered_year is None:
        year_ok = True
    else:
        year_ok = str(academic_year) != str(not_offered_year)

    if not musician and cache.subject_ids[class_idx].lower().startswith("21m"):
        return False
    return semester_ok and year_ok


def find_current_school_year() -> tuple[str, str]:
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month

    if current_month >= 9:  # September or later
        school_year = f"{current_year}-{current_year + 1}"
        planning_for_year = f"{current_year + 1}-{current_year + 2}"
    else:  # Before September
        school_year = f"{current_year - 1}-{current_year}"
        planning_for_year = f"{current_year}-{current_year + 1}"

    return school_year, planning_for_year


def semester_idx_to_hydrant_code(semester_idx: int, planning_year_start: int) -> str:
    """
    Convert 1-based semester index to Hydrant semester code.
    
    Semester 1 = Freshman Fall (f{planning_year_start})
    Semester 2 = Freshman IAP (i{planning_year_start + 1})
    Semester 3 = Freshman Spring (s{planning_year_start + 1})
    """
    year_in_plan = (semester_idx - 1) // 3
    term_in_year = (semester_idx - 1) % 3  # 0=Fall, 1=IAP, 2=Spring
    
    academic_year = planning_year_start + year_in_plan
    
    if term_in_year == 0:  # Fall
        return f"f{academic_year % 100}"
    elif term_in_year == 1:  # IAP
        return f"i{(academic_year + 1) % 100}"
    else:  # Spring
        return f"s{(academic_year + 1) % 100}"


def hydrant_code_to_semester_idx(code: str, planning_year_start: int) -> int:
    """
    Convert Hydrant semester code to 1-based semester index.
    
    f25 with planning_year_start=2025 -> 1 (Freshman Fall)
    i26 with planning_year_start=2025 -> 2 (Freshman IAP)
    s26 with planning_year_start=2025 -> 3 (Freshman Spring)
    """
    term = code[0]
    year = int(code[1:]) + 2000
    
    if term == "f":
        year_in_plan = year - planning_year_start
        return year_in_plan * 3 + 1
    elif term == "i":
        year_in_plan = year - 1 - planning_year_start
        return year_in_plan * 3 + 2
    else:  # spring
        year_in_plan = year - 1 - planning_year_start
        return year_in_plan * 3 + 3


def get_current_semester_index(planning_year_start: int) -> int:
    """
    Calculate which semester index (1-12) is the current semester.
    Returns 0 if we're before the planning year starts.

    Semester mapping:
    1 = Freshman Fall, 2 = Freshman IAP, 3 = Freshman Spring
    4 = Sophomore Fall, 5 = Sophomore IAP, 6 = Sophomore Spring
    ...
    10 = Senior Fall, 11 = Senior IAP, 12 = Senior Spring
    """
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month

    # Determine which academic year we're in
    if current_month >= 9:  # Fall semester (September onwards)
        academic_year_start = current_year
        semester_in_year = 0  # Fall
    elif current_month == 1:  # IAP (January only)
        academic_year_start = current_year - 1
        semester_in_year = 1  # IAP
    elif current_month >= 2:  # Spring semester (February onwards)
        academic_year_start = current_year - 1
        semester_in_year = 2  # Spring
    else:  # August or earlier (before fall semester starts)
        # Still in previous academic year's spring/summer
        academic_year_start = current_year - 1
        semester_in_year = 2  # Spring

    # Calculate year offset from planning start
    years_since_start = academic_year_start - planning_year_start

    # Calculate semester index (1-12)
    # Each year has 3 semesters (Fall=0, IAP=1, Spring=2)
    semester_index = years_since_start * 3 + semester_in_year + 1

    # Clamp to valid range
    if semester_index < 1:
        return 0  # Not started yet
    if semester_index > 12:
        return 12  # Already graduated

    return semester_index
