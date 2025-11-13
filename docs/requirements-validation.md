# Requirements Validation

## Connection Type Semantics

FireRoad requirements use **hierarchical evaluation**, not flattened leaf evaluation.

### Rules

- **`"all"`** = ALL direct children must be satisfied
- **`"any"`** = At least ONE direct child must be satisfied  
- **`threshold` with `criterion="subjects"`** = At least N valid courses available in entire subtree
- **`threshold` with other criteria** = At least N direct children must be satisfied

### Key Insight

Connection types apply to **direct children only**, not all leaf courses recursively.

```
Group (connection_type="all")
├── Child Group A (connection_type="any")
│   ├── Course 1 ✓ valid
│   └── Course 2 ✗ invalid
└── Child Group B (connection_type="any")
    ├── Course 3 ✓ valid
    └── Course 4 ✗ invalid

Result: ✅ FEASIBLE
Reason: Both direct children (Group A and Group B) are feasible,
        even though 50% of leaf courses are invalid.
```

### Validation Modes

**Mark Mode** (default)
- Sets `was_pruned=True` on invalid/infeasible nodes
- Preserves full tree structure for debugging
- Use: `validate_and_prune(req, courses_df, remove_invalid=False)`

**Remove Mode**
- Actually removes invalid courses from tree
- Returns `None` if requirement becomes infeasible
- Use: `validate_and_prune(req, courses_df, remove_invalid=True)`

### Feasibility Determination

A group is marked `was_pruned=True` (infeasible) only when:

| Connection Type | Infeasible When |
|-----------------|-----------------|
| `"all"` | Any direct child is infeasible |
| `"any"` | All direct children are infeasible |
| `threshold` with `criterion="subjects"` | Fewer than N valid courses available in subtree |
| `threshold` with other criteria | Fewer than N direct children are feasible |

### Verified Examples

From real FireRoad data:

**6-3 major:**
- **Elective Subjects**: `connection_type="all"`, 3/3 direct children valid, 111/123 leaf courses valid → ✅ **FEASIBLE**

**6-2 major:**
- **Basic Requirements**: `connection_type="all"`, 7/7 direct children valid, 139/161 leaf courses valid → ✅ **FEASIBLE**

**15-3 major (Finance):**
- **Finance Electives**: `threshold=5 subjects`, 21 valid courses available, 2 direct child groups → ✅ **FEASIBLE**
- **Restricted Electives**: `threshold=7 subjects`, 28 valid courses available across children → ✅ **FEASIBLE**

This confirms:
1. Groups with `connection_type` remain feasible when their direct children satisfy the connection type, regardless of invalid leaf courses deeper in the tree
2. Groups with `threshold` and `criterion="subjects"` count total valid courses in the subtree, not just direct children
