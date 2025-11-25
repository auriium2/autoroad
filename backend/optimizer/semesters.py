"""
Semester constants for the optimizer.

Semester semantics:
- -2: Must Take (special bucket forcing course to be scheduled in some regular semester)
- -1: ASE (Advanced Standing Exam - prior credit, counts as before semester 1)
-  0: Does NOT exist (no semester 0!)
- 1-12: Regular semesters (Fall/IAP/Spring over 4 years)
"""

REGULAR_SEMESTERS: list[int] = list(range(1, 13))
VALID_SEMESTERS: list[int] = [-1] + REGULAR_SEMESTERS  # ASE + regular semesters
ALL_SEMESTERS: list[int] = [-2, -1] + REGULAR_SEMESTERS  # Must Take + ASE + regular
