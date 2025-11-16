# Objective Scaling Reference

All objectives are normalized to have similar per-course costs around **~100**.

## TODO: Automatic Normalization

Consider implementing automatic normalization in the future:
- Add `estimate_per_course_cost()` method to ObjectiveComponent protocol
- Have ObjectiveBuilder compute scaling factors automatically during build()
- Sample random courses or use heuristics to estimate typical cost per course
- Apply normalization factor: `target_scale / estimated_scale`
- This would eliminate manual scaling and make objectives automatically balanced

For now, manual scaling is used (documented below).

This ensures that when weights sum to 1.0, each objective has comparable influence regardless of which objectives are combined.

## Linear Objectives (per course scale ~100)

| Objective | Per-Course Cost | Formula | Notes |
|-----------|----------------|---------|-------|
| **MinimizeUnits** | ~120 | `units × 10` | 12 units × 10 = 120 |
| **MaximizeRating** | ~100 | `max(0, 6.0 - rating) × 100` | 1.0 rating deficit = 100 |
| **MaximizeWeightedRating** | ~100 | `max(0, 6.0 - weighted_rating) × 100` | Same as MaximizeRating |
| **MinimizeTotalHours** | ~120 | `hours × 10` | 12 hours × 10 = 120 |
| **FrontloadCourses** | ~120 | `semester × 20` | Semester 6 × 20 = 120 |
| **BackloadCourses** | ~140 | `(13 - semester) × 20` | (13 - 6) × 20 = 140 |
| **MinimizeFridayClasses** | 100 | `100 × has_friday` | 100 penalty per Friday course |
| **ClusterCourses** | ~50-100 | `gap_hours × 50` | 1-2 hour gaps typical |
| **MaximizeCohortOverlap** | ~100 | `max(0, 50 - enrollment) × 4` | 25 deficit × 4 = 100 |

## Soft Constraints (high penalty when violated)

| Objective | Cost When Satisfied | Cost When Violated | Notes |
|-----------|--------------------|--------------------|-------|
| **MinimizeMaxSemesterHours** | 0 | `100 × excess_hours × 10` | 10 hours over → 10,000 |
| **MinimizeFinalsLoad** | 0 | `100 × excess_finals` | 2 excess finals → 200 |

## Typical Schedule Impact

For a typical 18-course schedule:

- **MinimizeUnits**: 18 × 120 = ~2,160
- **MaximizeRating**: 18 × 100 = ~1,800
- **MinimizeTotalHours**: 18 × 120 = ~2,160
- **Frontload/Backload**: 18 × 120 = ~2,160
- **MinimizeFridayClasses**: ~5 Friday courses × 100 = ~500
- **ClusterCourses**: ~20 gaps × 50 = ~1,000
- **MaximizeCohortOverlap**: 18 × 100 = ~1,800

All linear objectives produce values in the **1,000-2,500** range for typical schedules.

## Soft Constraints Behavior

Soft constraints are designed to:
- **Return 0** when the constraint is satisfied
- **Return large values** (10,000+) when violated
- This makes them **dominate** the objective when violated
- But **negligible** compared to linear objectives when satisfied

This allows you to mix soft constraints with linear objectives - the soft constraints act as "almost hard" requirements that can be violated if absolutely necessary.
