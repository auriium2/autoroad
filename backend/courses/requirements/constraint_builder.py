"""
Build CP-SAT constraints from RequirementNode structures.

This module provides a clean interface for converting Fireroad requirement trees
into OR-Tools CP-SAT constraints. It addresses several design flaws from the original:

1. Separation of concerns: Constraint building is separate from solving and printing
2. Clear error handling: Missing courses and infeasible requirements are tracked separately
3. Type safety: Proper type hints and validation throughout
4. Immutability: Uses dataclasses and avoids global state
5. Testability: Pure functions that don't depend on external state
6. Maintainability: Clear structure with well-defined responsibilities
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd
from ortools.sat.python import cp_model

from .types import (
    RequirementCourse,
    RequirementGroup,
    RequirementNode,
    RequirementPlainString,
    RequirementThreshold,
)


@dataclass
class CourseSchedule:
    """
    Represents the available courses and their scheduling information.
    
    This encapsulates all the course data needed to build constraints,
    making the constraint builder independent of specific dataframe structures.
    """
    courses_df: pd.DataFrame
    planning_year_start: int
    
    def get_course_index(self, course_id: str) -> int | None:
        """Get the internal index for a course ID, or None if not found."""
        matches = self.courses_df.index[self.courses_df['subject_id'] == course_id].tolist()
        return matches[0] if matches else None
    
    def get_courses_by_attribute(self, attribute: str, value: str) -> list[int]:
        """Get all course indices that have a specific attribute value."""
        if attribute not in self.courses_df.columns:
            return []
        return self.courses_df.index[self.courses_df[attribute] == value].tolist()
    
    def get_courses_by_hass_any(self) -> list[int]:
        """Get all courses with any HASS attribute."""
        if "hass_attribute" not in self.courses_df.columns:
            return []
        hass_values = ["HASS-A", "HASS-E", "HASS-H", "HASS-S"]
        return self.courses_df.index[self.courses_df["hass_attribute"].isin(hass_values)].tolist()


@dataclass
class ConstraintContext:
    """
    Context for building constraints, containing the model and decision variables.
    
    This separates the constraint building context from the requirements structure,
    making it easier to test and reason about.
    """
    model: cp_model.CpModel
    take_vars: dict[tuple[int, int], cp_model.IntVar]
    schedule: CourseSchedule
    
    # Track auxiliary variables created during constraint building
    aux_vars: dict[str, cp_model.IntVar] = field(default_factory=dict)
    
    # Counter for generating unique variable names
    _counter: int = 0
    
    def fresh_name(self, prefix: str = "var") -> str:
        """Generate a unique variable name with the given prefix."""
        self._counter += 1
        return f"{prefix}_{self._counter}"


@dataclass
class ConstraintResult:
    """
    Result of building constraints for a requirement.
    
    Returns both the satisfaction variable and any warnings/errors encountered.
    """
    satisfied_var: cp_model.IntVar | None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        """Whether this requirement could be represented as constraints."""
        return self.satisfied_var is not None
    
    @property
    def has_issues(self) -> bool:
        """Whether there were any warnings or errors."""
        return len(self.warnings) > 0 or len(self.errors) > 0


class RequirementConstraintBuilder:
    """
    Builds CP-SAT constraints from a RequirementNode tree.
    
    This is the main entry point for converting requirements into constraints.
    It handles the recursive traversal of the requirement tree and delegates
    to specialized handlers for different requirement types.
    """
    
    def __init__(self, ctx: ConstraintContext):
        self.ctx = ctx
        self.results: list[ConstraintResult] = []
    
    def build(self, node: RequirementNode, parent_path: str = "root") -> ConstraintResult:
        """
        Build constraints for a requirement node and its descendants.
        
        Args:
            node: The requirement node to process
            parent_path: Path to this node for error reporting
            
        Returns:
            ConstraintResult containing the satisfaction variable and any issues
        """
        if isinstance(node, RequirementCourse):
            result = self._build_course(node, parent_path)
        elif isinstance(node, RequirementPlainString):
            result = self._build_plain_string(node, parent_path)
        elif isinstance(node, RequirementGroup):
            result = self._build_group(node, parent_path)
        else:
            # Should never happen due to type system, but handle gracefully
            result = ConstraintResult(
                satisfied_var=None,
                errors=[f"Unknown requirement type: {type(node).__name__}"]
            )
        
        self.results.append(result)
        return result
    
    def _build_course(self, node: RequirementCourse, parent_path: str) -> ConstraintResult:
        """Build constraints for a single course requirement."""
        course_id = node.course_id
        path = f"{parent_path} -> {course_id}"
        
        # Handle special requirements
        if course_id == "HASS":
            return self._build_hass_any(node, path)
        elif course_id.startswith("GIR:"):
            gir_code = course_id.split(":", 1)[1]
            return self._build_attribute_requirement(
                node, path, "gir_attribute", gir_code
            )
        elif course_id.startswith("HASS-"):
            return self._build_attribute_requirement(
                node, path, "hass_attribute", course_id
            )
        elif course_id.startswith("CI-"):
            return self._build_attribute_requirement(
                node, path, "communication_requirement", course_id
            )
        
        # Regular course
        course_idx = self.ctx.schedule.get_course_index(course_id)
        if course_idx is None:
            return ConstraintResult(
                satisfied_var=None,
                errors=[f"Course '{course_id}' not found in course database"]
            )
        
        # Create a variable for whether this course requirement is satisfied
        var_name = f"req_{course_id.replace('.', '_')}"
        satisfied_var = self.ctx.model.NewBoolVar(var_name)
        
        # Course is satisfied if it's taken in any valid semester
        valid_takes = [
            self.ctx.take_vars[course_idx, s]
            for s in range(1, 13)
            if (course_idx, s) in self.ctx.take_vars
        ]
        
        if not valid_takes:
            # Course exists but is never offered in valid semesters
            self.ctx.model.Add(satisfied_var == 0)
            return ConstraintResult(
                satisfied_var=satisfied_var,
                warnings=[f"Course '{course_id}' is never offered in any semester"]
            )
        
        # Satisfied if taken at least once
        sum_takes = sum(valid_takes)
        self.ctx.model.Add(sum_takes >= 1).OnlyEnforceIf(satisfied_var)
        self.ctx.model.Add(sum_takes == 0).OnlyEnforceIf(satisfied_var.Not())
        
        return ConstraintResult(satisfied_var=satisfied_var)
    
    def _build_hass_any(self, node: RequirementCourse, path: str) -> ConstraintResult:
        """Build constraints for the generic 'HASS' requirement (any HASS course)."""
        course_indices = self.ctx.schedule.get_courses_by_hass_any()
        
        if not course_indices:
            return ConstraintResult(
                satisfied_var=None,
                errors=["No HASS courses found in course database"]
            )
        
        satisfied_var = self.ctx.model.NewBoolVar("req_hass_any")
        
        # Typically requires 8 HASS courses total
        # This should ideally come from the requirement's threshold
        required_count = 8
        
        valid_takes = [
            self.ctx.take_vars[c, s]
            for c in course_indices
            for s in range(1, 13)
            if (c, s) in self.ctx.take_vars
        ]
        
        if valid_takes:
            sum_takes = sum(valid_takes)
            self.ctx.model.Add(sum_takes >= required_count).OnlyEnforceIf(satisfied_var)
            self.ctx.model.Add(sum_takes < required_count).OnlyEnforceIf(satisfied_var.Not())
        else:
            self.ctx.model.Add(satisfied_var == 0)
        
        return ConstraintResult(satisfied_var=satisfied_var)
    
    def _build_attribute_requirement(
        self,
        node: RequirementCourse,
        path: str,
        attribute: str,
        value: str
    ) -> ConstraintResult:
        """Build constraints for requirements based on course attributes (GIR, HASS, CI)."""
        course_indices = self.ctx.schedule.get_courses_by_attribute(attribute, value)
        
        if not course_indices:
            return ConstraintResult(
                satisfied_var=None,
                warnings=[f"No courses found with {attribute}='{value}'"]
            )
        
        var_name = f"req_{attribute}_{value.replace(':', '_').replace('-', '_')}"
        satisfied_var = self.ctx.model.NewBoolVar(var_name)
        
        # Satisfied if any course with this attribute is taken
        valid_takes = [
            self.ctx.take_vars[c, s]
            for c in course_indices
            for s in range(1, 13)
            if (c, s) in self.ctx.take_vars
        ]
        
        if valid_takes:
            sum_takes = sum(valid_takes)
            self.ctx.model.Add(sum_takes >= 1).OnlyEnforceIf(satisfied_var)
            self.ctx.model.Add(sum_takes == 0).OnlyEnforceIf(satisfied_var.Not())
        else:
            self.ctx.model.Add(satisfied_var == 0)
        
        return ConstraintResult(satisfied_var=satisfied_var)
    
    def _build_plain_string(self, node: RequirementPlainString, path: str) -> ConstraintResult:
        """
        Build constraints for plain-string requirements.
        
        Plain-string requirements are descriptive text that can't be automatically
        validated. We create a placeholder variable that's always true so the
        requirement structure is preserved, but actual validation must be manual.
        """
        var_name = self.ctx.fresh_name("req_plainstring")
        placeholder = self.ctx.model.NewBoolVar(var_name)
        
        # Always consider plain-string requirements as satisfied
        # since we can't automatically validate them
        self.ctx.model.Add(placeholder == 1)
        
        return ConstraintResult(
            satisfied_var=placeholder,
            warnings=[f"Plain-string requirement can't be validated: '{node.description}'"]
        )
    
    def _build_group(self, node: RequirementGroup, parent_path: str) -> ConstraintResult:
        """Build constraints for a group of requirements."""
        group_name = node.title or self.ctx.fresh_name("group")
        path = f"{parent_path} -> {group_name}"
        
        # Process all child requirements
        child_results = []
        child_vars = []
        warnings = []
        errors = []
        
        for child in node.items:
            result = self.build(child, path)
            child_results.append(result)
            
            if result.is_valid:
                child_vars.append(result.satisfied_var)
            
            warnings.extend(result.warnings)
            errors.extend(result.errors)
        
        # Create variable for this group
        var_name = f"req_group_{group_name.replace(' ', '_')}"
        group_var = self.ctx.model.NewBoolVar(var_name)
        
        # Store in aux_vars for debugging/reporting
        self.ctx.aux_vars[group_name] = group_var
        
        # Handle threshold if present
        if node.threshold is not None:
            return self._build_threshold_group(
                node, group_var, child_vars, path, warnings, errors
            )
        
        # Handle connection type
        if not child_vars:
            # No valid children - group cannot be satisfied
            self.ctx.model.Add(group_var == 0)
            errors.append(f"Group '{group_name}' has no valid child requirements")
            return ConstraintResult(
                satisfied_var=group_var,
                warnings=warnings,
                errors=errors
            )
        
        if node.connection_type == "all" or node.connection_type is None:
            # ALL: All children must be satisfied
            self.ctx.model.AddMinEquality(group_var, child_vars)
            
            # Check if any children are invalid
            if len(child_vars) < len(node.items):
                errors.append(
                    f"Group '{group_name}' requires all {len(node.items)} children "
                    f"but only {len(child_vars)} are valid"
                )
        
        elif node.connection_type == "any":
            # ANY: At least one child must be satisfied
            self.ctx.model.AddMaxEquality(group_var, child_vars)
        
        else:
            errors.append(f"Unknown connection type: {node.connection_type}")
        
        return ConstraintResult(
            satisfied_var=group_var,
            warnings=warnings,
            errors=errors
        )
    
    def _build_threshold_group(
        self,
        node: RequirementGroup,
        group_var: cp_model.IntVar,
        child_vars: list[cp_model.IntVar],
        path: str,
        warnings: list[str],
        errors: list[str]
    ) -> ConstraintResult:
        """Build constraints for a group with a threshold."""
        threshold = node.threshold
        group_name = node.title or "unnamed"
        
        if threshold.type == "LTE":
            # Less-than-or-equal thresholds are rare and need special handling
            warnings.append(
                f"Group '{group_name}' uses LTE threshold which may need manual review"
            )
        
        # For GTE thresholds, need at least 'cutoff' items satisfied
        cutoff = threshold.cutoff
        
        # Determine if we're counting subjects or units
        if threshold.criterion == "units":
            # TODO: Implement unit counting - needs access to course units
            warnings.append(
                f"Group '{group_name}' uses unit-based threshold - "
                "not yet implemented, falling back to subject counting"
            )
        
        # Check feasibility
        total_children = len(node.items)
        available_children = len(child_vars)
        
        if available_children < cutoff:
            errors.append(
                f"Group '{group_name}' requires {cutoff} satisfied children "
                f"but only {available_children}/{total_children} are valid"
            )
            # Make the group unsatisfiable
            self.ctx.model.Add(group_var == 0)
        elif not child_vars:
            self.ctx.model.Add(group_var == 0)
        else:
            # Count how many children are satisfied
            sum_satisfied = sum(child_vars)
            self.ctx.model.Add(sum_satisfied >= cutoff).OnlyEnforceIf(group_var)
            self.ctx.model.Add(sum_satisfied < cutoff).OnlyEnforceIf(group_var.Not())
        
        return ConstraintResult(
            satisfied_var=group_var,
            warnings=warnings,
            errors=errors
        )
    
    def enforce_requirement(self, node: RequirementNode) -> None:
        """
        Build constraints for a requirement and enforce it (require it to be satisfied).
        
        This is a convenience method for the common case of building a requirement
        tree and requiring that the root requirement be satisfied.
        """
        result = self.build(node)
        
        if result.is_valid:
            # Require that the root requirement be satisfied
            self.ctx.model.Add(result.satisfied_var == 1)
        else:
            # Requirement couldn't be built - this is a critical error
            error_msg = "; ".join(result.errors)
            raise ValueError(f"Cannot enforce requirement: {error_msg}")
    
    def get_summary(self) -> dict:
        """
        Get a summary of all issues encountered during constraint building.
        
        Returns a dictionary with warnings and errors grouped by severity.
        """
        all_warnings = []
        all_errors = []
        
        for result in self.results:
            all_warnings.extend(result.warnings)
            all_errors.extend(result.errors)
        
        return {
            "warning_count": len(all_warnings),
            "error_count": len(all_errors),
            "warnings": all_warnings,
            "errors": all_errors,
            "has_issues": len(all_warnings) > 0 or len(all_errors) > 0
        }


def add_requirement_constraints(
    model: cp_model.CpModel,
    take_vars: dict[tuple[int, int], cp_model.IntVar],
    requirement: RequirementNode,
    courses_df: pd.DataFrame,
    planning_year_start: int,
    enforce: bool = True
) -> dict[str, cp_model.IntVar]:
    """
    Add constraints for a requirement tree to a CP-SAT model.
    
    This is the main entry point function that sets up the context and
    builds all constraints.
    
    Args:
        model: The CP-SAT model to add constraints to
        take_vars: Dictionary mapping (course_idx, semester) to decision variables
        requirement: Root of the requirement tree
        courses_df: DataFrame containing course information
        planning_year_start: Start year for planning (used for semester validation)
        enforce: Whether to require the root requirement be satisfied (default: True)
    
    Returns:
        Dictionary of auxiliary variables created during constraint building,
        useful for debugging and reporting
    
    Raises:
        ValueError: If enforce=True and the requirement cannot be built
    """
    schedule = CourseSchedule(courses_df, planning_year_start)
    ctx = ConstraintContext(model, take_vars, schedule)
    builder = RequirementConstraintBuilder(ctx)
    
    if enforce:
        builder.enforce_requirement(requirement)
    else:
        builder.build(requirement)
    
    # Print summary of issues
    summary = builder.get_summary()
    if summary["has_issues"]:
        print(f"\n=== Constraint Building Summary ===")
        print(f"Warnings: {summary['warning_count']}")
        print(f"Errors: {summary['error_count']}")
        
        if summary["warnings"]:
            print("\nWarnings:")
            for warning in summary["warnings"]:
                print(f"  - {warning}")
        
        if summary["errors"]:
            print("\nErrors:")
            for error in summary["errors"]:
                print(f"  - {error}")
        print("=" * 35)
    
    return ctx.aux_vars
