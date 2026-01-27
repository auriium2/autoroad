# Why tho?

To plan one (1) feasible degree at mit, you have to consider:
- the degree requirements of the girs
  - all of the girs and their placement
  - which of the girs to take (some are worse than others)
  - the hass requirement, which states that you must
    - take at least 8 humanities classes
    - from these 8, one of each must be a hass h, hass a, hass s
  - you must also take 4 ci-h writing-type classes (which *may or may not also be hasses*)
    - two must be ci-h classes (writing type under the hass requirement)
    - two must be ci-m classes (writing type under the major)
    - not all hasses are ci-type
  - you must take a REST (Restricted Elective in SomeThing) class
- the degree requirements of your current degree
  - depending on your major, these can be arbitrarily nested [in increasingly convoluted ways](https://fireroad.mit.edu/requirements/edit/major6-3new).
- the class requirements of your mandatory [humanities concentration](https://registrar.mit.edu/registration-academics/academic-requirements/hass-requirement/hass-concentrations)
  - this is *not the same thing* as the hasses OR ci-types
  - yes, you have to have a humanities concentration at mit
  - no, i do not want a concentration in linguistics
- the fact that all of these courses have *prerequisites* that may break down if you fail or decide to take a different class


AI slop below that i'll fill out with the actual technical details later, it gives you an ok picture but like... it doesnt get it lol

# How? (Basic)

Define binary decision variables for every (course, semester) pair. Add constraints:
- Prerequisites must come before dependent courses
- Degree requirements (reverse-engineered from Fireroad's source)
- Unit caps, no double-counting, user pins

Then optimize across 11 objectives with diminishing returns:
- Minimize total units
- Balance workload per semester
- Avoid finals conflicts
- Minimize friday classes
- Prioritize requirement satisfaction
- etc.

Send the problem design to a remote worker pool, since solving each problem takes a lot of cpu cores and we need to serve many users.


# How (Advanced)

## The Solver

Autoroad uses Google's [CP-SAT solver](https://developers.google.com/optimization/cp/cp_solver) (Constraint Programming with SAT) from OR-Tools. CP-SAT is designed for discrete optimization problems with complex constraints - exactly what degree planning needs.

### Decision Variables

For each course in MIT's catalog and each semester in your plan, we create a binary variable:
```
take_6.100A_s3 ∈ {0, 1}   # 1 if taking 6.100A in semester 3
```

Special semesters:
- **ASE (-1)**: Advanced Standing Exam credit (only if you have an ASE marker)
- **Must Take (-2)**: Course must be taken somewhere, optimizer chooses when

Variables are only created when the course is actually offered in that semester.

### Basic Constraints (Always Enforced)

1. **At-most-once**: Each course can be taken in at most one semester
2. **Freshman Fall**: Hard cap of 48 units in semester 1 (MIT policy)
3. **IAP limits**: Hard cap of 12 units per IAP semester
4. **HASS minimum**: At least 8 HASS courses total
5. **Past semester lock**: Can't schedule courses in semesters that have passed

## Hard Constraints

User-configurable constraints that must be satisfied:

| Constraint | Description |
|------------|-------------|
| `ban_iap` | No courses during IAP (January term), except pinned courses |
| `no_schedule_conflicts` | Prevent overlapping class times using Hydrant schedule data |
| `schedule_free_time` | Block off time slots where you don't want classes |
| `ban_prefix` | Ban all courses matching a prefix (e.g., "21M" for music) |

## Objective System

Objectives are soft constraints with tier-based penalties. The formula:
```
penalty = base_cost × 5^tier
```

Tiers 1-4 let you express relative priorities:
- Tier 1: 5x multiplier (lowest priority)
- Tier 2: 25x multiplier (default)
- Tier 3: 125x multiplier
- Tier 4: 625x multiplier (highest priority)

### Available Objectives

**Workload Management:**
| Objective | Default Tier | Description |
|-----------|--------------|-------------|
| `limit_classes_per_semester` | 4 | Penalize semesters with >4 classes |
| `limit_units_per_semester` | 3 | Penalize semesters with >60 units |
| `limit_hours_per_semester` | 2 | Penalize semesters exceeding weekly hours threshold |
| `limit_finals_per_semester` | 1 | Penalize semesters with >2 finals |
| `minimum_classes_per_semester` | 2 | Penalize semesters with <2 classes |

**Course Quality:**
| Objective | Default Tier | Description |
|-----------|--------------|-------------|
| `avoid_small_classes` | 4 | Penalize courses <3 units |
| `avoid_low_ratings` | 2 | Penalize courses below rating threshold (default 5.5) |
| `avoid_special_classes` | 2 | Penalize Concourse/STS/ES courses |
| `avoid_iap` | 2 | Penalize placing courses in IAP |

**Requirement Satisfaction:**
| Objective | Default Tier | Description |
|-----------|--------------|-------------|
| `category_rewards` | 2 | Reward courses in priority requirement categories (geometric decay) |
| `discourage_equivalent_courses` | 4 | Penalize taking multiple equivalent courses (e.g., 6.100A and 6.100L) |

The `category_rewards` objective uses a geometric series with diminishing returns:
```
reward(k) = base × (1 - decay^k) / (1 - decay)
```
This means the first course satisfying a requirement category is worth more than the second, and so on.

## Requirement Parsing

Fireroad requirements use a custom syntax that gets parsed into a tree structure:

```
,   = AND (all children must be satisfied)
/   = OR (any child can satisfy)
{>=N}   = At least N subjects
{<=N}   = At most N subjects  
{>=Nu}  = At least N units
{>=N|>=M}  = N subjects with M distinct courses
```

### Node Types

The parser builds a tree of typed nodes:

| Node Type | CP-SAT Translation |
|-----------|-------------------|
| `Course` | Variable for taking this specific course |
| `AllGroup` | All children must be satisfied (conjunction) |
| `AnyGroup` | At least one child must be satisfied (disjunction) |
| `SubjectThresholdGroup` | Sum of satisfied children >= threshold |
| `UnitThresholdGroup` | Sum of units from satisfied children >= threshold |

Each node creates a satisfaction variable and constraints that tie it to its children.

### Prerequisite Handling

Prerequisites form their own constraint trees:
- **Course prerequisites**: Must take 18.01 before 18.02
- **GIR prerequisites**: Must complete CAL1 (any calculus) before some courses
- **Threshold prerequisites**: Must complete N-of-M courses

Override markers let users skip prerequisite checks (for petitioned courses).

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Frontend  │────▶│  Python API  │────▶│  C++ Worker │
│  (React)    │     │  (FastAPI)   │     │  (CP-SAT)   │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                    Model Building:
                    - Parse requirements
                    - Create variables
                    - Add constraints
                    - Build objective
                           │
                           ▼
                    Serialize to protobuf
                           │
                           ▼
                    Stream solutions via SSE
```

The Python API builds the complete CP-SAT model, then serializes it to protobuf and sends it to a C++ worker for solving. This gives us:
- Fast model building (Python is fine for this)
- Fast solving (C++ worker with 8 parallel threads)
- Horizontal scaling (multiple workers in the pool)

Solutions stream back in real-time via Server-Sent Events, so users see improving solutions as the solver finds them.

### Serialized Model Format

```python
SerializedModel {
    cpmodel_proto: bytes           # The actual CP-SAT model
    variable_mapping: [...]        # Maps var indices to (course, semester)
    courses_metadata: [...]        # Course info for solution decoding
    solver_params: {               # Solver configuration
        max_time_seconds: 20,
        num_workers: 8
    },
    objective_components: [...]    # For cost breakdown calculation
}
```

## Performance

- **Solver timeout**: 20 seconds max
- **Parallel threads**: 8 workers per solve
- **Connection pooling**: Shared HTTP client for external APIs
- **Retry logic**: Exponential backoff for Fireroad/Hydrant API calls
- **Caching**: 1-hour TTL on course data, requirements, and prerequisites
