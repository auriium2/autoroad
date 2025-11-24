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
from typing import TypedDict
import re

import polars as pl
from ortools.sat.python import cp_model

from courses.requirements.types import (
    RequirementCourse,
    RequirementGroup,
    RequirementNode,
    RequirementPlainString,
)


class ConstraintSummary(TypedDict):
    """Summary of constraint building results."""
    warning_count: int
    error_count: int
    warnings: list[str]
    errors: list[str]
    has_issues: bool


@dataclass
class CourseSchedule:
    """
    Represents the available courses and their scheduling information.

    This encapsulates all the course data needed to build constraints,
    making the constraint builder independent of specific dataframe structures.
    """
    courses_df: pl.DataFrame
    planning_year_start: int

    def get_course_index(self, course_id: str) -> int | None:
        """Get the internal index for a course ID, or None if not found."""
        subject_ids = self.courses_df['subject_id'].to_list()
        try:
            return subject_ids.index(course_id)
        except ValueError:
            return None

    def get_courses_by_attribute(self, attribute: str, value: str) -> list[int]:
        """Get all course indices that have a specific attribute value."""
        if attribute not in self.courses_df.columns:
            return []
        attribute_values = self.courses_df[attribute].to_list()
        return [i for i, v in enumerate(attribute_values) if v == value]

    def get_courses_by_hass_any(self) -> list[int]:
        """Get all courses with any HASS attribute."""
        if "hass_attribute" not in self.courses_df.columns:
            return []
        hass_values = ["HASS-A", "HASS-E", "HASS-H", "HASS-S"]
        hass_attrs = self.courses_df["hass_attribute"].to_list()
        return [i for i, v in enumerate(hass_attrs) if v in hass_values]


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

    # Map from variable name to human-readable requirement path for debugging
    var_name_map: dict[str, str] = field(default_factory=dict)

    # Map from course index to set of requirement paths it can satisfy, for category rewards
    course_to_requirements: dict[int, set[str]] = field(default_factory=dict)

    # Counter for generating unique variable names
    _counter: int = 0

    def fresh_name(self, prefix: str = "var") -> str:
        """Generate a unique variable name with the given prefix."""
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def record_course_requirement(self, course_idx: int, requirement_path: str) -> None:
        """Record that a course can satisfy a given requirement path."""
        if course_idx not in self.course_to_requirements:
            self.course_to_requirements[course_idx] = set()
        self.course_to_requirements[course_idx].add(requirement_path)

    def register_var(self, var: cp_model.IntVar, debug_name: str) -> None:
        """Register a variable with its human-readable debug name."""
        self.var_name_map[var.Name()] = debug_name


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
        self.ctx: ConstraintContext = ctx
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
        # Skip pruned nodes - they represent invalid/unavailable courses
        if hasattr(node, 'was_pruned') and node.was_pruned:
            result = ConstraintResult(
                satisfied_var=None,
                warnings=[f"Skipping pruned requirement: {parent_path}"]
            )
            self.results.append(result)
            return result

        if isinstance(node, RequirementCourse):
            result = self._build_course(node, parent_path)
        elif isinstance(node, RequirementPlainString):
            result = self._build_plain_string(node, parent_path)
        elif isinstance(node, RequirementGroup):
            result = self._build_group(node, parent_path)
        else:
            # Unknown node type - create error result
            result = ConstraintResult(
                satisfied_var=None,
                errors=[f"Unknown requirement node type: {type(node).__name__} at {parent_path}"]
            )

        self.results.append(result)
        return result

    def _build_course(self, node: RequirementCourse, parent_path: str) -> ConstraintResult:
        """Build constraints for a single course requirement."""
        course_id = node.course_id
        path = f"{parent_path} -> {course_id}"

        # Extract numeric path for frontend matching (e.g., "root.6.0.0.0" from "root -> Bachelor... [root.6.0.0.0]")
        if " [" in parent_path:
            numeric_path = parent_path.split(" [")[1].rstrip("]")
        else:
            numeric_path = parent_path

        # Handle special requirements
        # For these, pass the numeric path directly since they don't need the readable path
        if course_id == "HASS":
            return self._build_hass_any(node, numeric_path)
        elif course_id.startswith("GIR:"):
            gir_code = course_id.split(":", 1)[1]
            return self._build_attribute_requirement(
                node, numeric_path, "gir_attribute", gir_code
            )
        elif course_id.startswith("HASS-"):
            return self._build_attribute_requirement(
                node, numeric_path, "hass_attribute", course_id
            )
        elif course_id.startswith("CI-"):
            return self._build_attribute_requirement(
                node, numeric_path, "communication_requirement", course_id
            )

        # Regular course
        course_idx = self.ctx.schedule.get_course_index(course_id)
        if course_idx is None:
            return ConstraintResult(
                satisfied_var=None,
                errors=[f"Course '{course_id}' not found in course database"]
            )

        # Record that this course can satisfy this requirement path (for category rewards)
        # Use numeric path to match frontend tier system
        self.ctx.record_course_requirement(course_idx, numeric_path)

        # Create a variable for whether this course requirement is satisfied
        var_name = self.ctx.fresh_name("req")
        satisfied_var = self.ctx.model.NewBoolVar(var_name)

        # Register the debug name (use req_id if available, otherwise course_id)
        debug_name = node.req_id if node.req_id else course_id
        self.ctx.register_var(satisfied_var, debug_name)

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

        # Record that all these courses can satisfy this requirement path
        for course_idx in course_indices:
            self.ctx.record_course_requirement(course_idx, path)

        var_name = self.ctx.fresh_name("req")
        satisfied_var = self.ctx.model.NewBoolVar(var_name)

        # Register the debug name
        debug_name = node.req_id if node.req_id else "HASS (any)"
        self.ctx.register_var(satisfied_var, debug_name)

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

        # Record that all these courses can satisfy this requirement path
        for course_idx in course_indices:
            self.ctx.record_course_requirement(course_idx, path)

        var_name = self.ctx.fresh_name("req")
        satisfied_var = self.ctx.model.NewBoolVar(var_name)

        # Register the debug name
        debug_name = node.req_id if node.req_id else f"{attribute}:{value}"
        self.ctx.register_var(satisfied_var, debug_name)

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

    def _collect_all_course_vars_from_results(
        self,
        child_nodes: list[RequirementNode],
        child_results: list[ConstraintResult]
    ) -> list[cp_model.IntVar]:
        """
        Recursively collect all course satisfaction variables from a list of children.
        This is used for thresholds with criterion='subjects' to match validator.py logic.

        Returns only leaf course variables, not group variables.
        """
        course_vars = []

        for node, result in zip(child_nodes, child_results):
            # Skip pruned or invalid results
            if hasattr(node, 'was_pruned') and node.was_pruned:
                continue
            if not result.is_valid:
                continue

            # If it's a course (leaf), add its satisfaction variable
            if isinstance(node, RequirementCourse):
                course_vars.append(result.satisfied_var)

            # If it's a group, recurse into its children
            elif isinstance(node, RequirementGroup):
                # Recursively build the group's children to get their course vars
                # We need to recurse into the original node structure
                nested_vars = self._collect_course_vars_recursive(node)
                course_vars.extend(nested_vars)

        return course_vars

    def _collect_course_vars_recursive(self, node: RequirementNode) -> list[cp_model.IntVar]:
        """
        Helper to recursively collect course variables from a node by rebuilding it.
        This is a bit inefficient but ensures we get the right variables.
        """
        # Skip pruned nodes
        if hasattr(node, 'was_pruned') and node.was_pruned:
            return []

        # If it's a course, build it and return its variable
        if isinstance(node, RequirementCourse):
            result = self._build_course(node, "temp")
            if result.is_valid and result.satisfied_var is not None:
                return [result.satisfied_var]
            return []

        # If it's a group, recurse into children
        if isinstance(node, RequirementGroup):
            course_vars: list[cp_model.IntVar] = []
            for child in node.items:
                course_vars.extend(self._collect_course_vars_recursive(child))
            return course_vars

        # Plain strings don't contribute
        return []

    def _build_plain_string(self, node: RequirementPlainString, path: str) -> ConstraintResult:
        """
        Build constraints for plain-string requirements.

        Plain-string requirements are descriptive text that cannot be automatically
        validated (e.g., "2 math subjects (first decimal ≥ 1)", "72 units of electives").
        
        We create a placeholder variable that's always satisfied, but provide detailed
        warnings about what constraints are being ignored.
        """
        var_name = self.ctx.fresh_name("req")
        placeholder = self.ctx.model.NewBoolVar(var_name)

        # Register the debug name
        debug_name = node.req_id if node.req_id else f"[Plain: {node.description[:50]}]"
        self.ctx.register_var(placeholder, debug_name)

        # Always mark as satisfied - we can't automatically validate these
        self.ctx.model.Add(placeholder == 1)

        warnings = []

        # Provide detailed warnings based on threshold type
        if node.threshold:
            criterion = node.threshold.criterion
            cutoff = node.threshold.cutoff
            thresh_type = node.threshold.type
            
            if criterion == "units":
                warnings.append(
                    f"⚠️  Plain-string unit requirement IGNORED: '{node.description}' "
                    f"requires {thresh_type} {cutoff} units. This cannot be automatically validated and "
                    f"must be manually verified in the final schedule."
                )
            elif criterion == "subjects":
                warnings.append(
                    f"⚠️  Plain-string subject requirement IGNORED: '{node.description}' "
                    f"requires {thresh_type} {cutoff} subjects. This cannot be automatically validated and "
                    f"must be manually verified in the final schedule."
                )
            else:
                warnings.append(
                    f"⚠️  Plain-string requirement IGNORED: '{node.description}' "
                    f"has threshold {thresh_type} {cutoff} ({criterion}). This cannot be automatically validated."
                )
        else:
            # Plain string without threshold (shouldn't happen based on our analysis, but handle it)
            warnings.append(
                f"⚠️  Plain-string requirement cannot be validated: '{node.description}'"
            )

        return ConstraintResult(
            satisfied_var=placeholder,
            warnings=warnings
        )

    def _build_group(self, node: RequirementGroup, parent_path: str) -> ConstraintResult:
        """Build constraints for a group of requirements."""
        group_name = node.title or self.ctx.fresh_name("group")

        # Extract numeric path from parent (e.g., "root.6" from "root [root.6]")
        if " [" in parent_path:
            # Parent has both readable and numeric: "root -> Degree [root.6]"
            readable_parent = parent_path.split(" [")[0]
            numeric_parent = parent_path.split(" [")[1].rstrip("]")
        else:
            # Parent is just the root
            readable_parent = parent_path
            numeric_parent = parent_path

        # Build human-readable path
        readable_path = f"{readable_parent} -> {group_name}"

        # Process all child requirements
        child_results = []
        child_vars = []
        warnings = []
        errors = []
        child_numeric_paths = []

        for idx, child in enumerate(node.items):
            # Create child path with both human-readable and numeric formats
            # Format: "root -> Bachelor... -> Architecture [root.6.0.0]"
            numeric_child = f"{numeric_parent}.{idx}"
            child_path = f"{readable_path} [{numeric_child}]"
            child_numeric_paths.append(numeric_child)

            result = self.build(child, child_path)
            child_results.append(result)

            if result.is_valid:
                child_vars.append(result.satisfied_var)

            warnings.extend(result.warnings)
            errors.extend(result.errors)

        # Collect ALL courses that satisfy any child and record them to this group
        # This allows category rewards to apply at any level of the requirement tree
        courses_from_children = set()
        for course_idx, req_paths in self.ctx.course_to_requirements.items():
            # Check if this course satisfies any child
            for child_path in child_numeric_paths:
                if child_path in req_paths:
                    courses_from_children.add(course_idx)
                    break

        # Record all courses from children to this group's path
        for course_idx in courses_from_children:
            self.ctx.record_course_requirement(course_idx, numeric_parent)

        # Create variable for this group
        var_name = self.ctx.fresh_name("req")
        group_var = self.ctx.model.NewBoolVar(var_name)

        # Register the debug name (use req_id if available)
        debug_name = node.req_id if node.req_id else group_name
        self.ctx.register_var(group_var, debug_name)

        # Store in aux_vars for debugging/reporting
        storage_key = node.req_id if node.req_id else group_name
        self.ctx.aux_vars[storage_key] = group_var

        # Handle threshold if present
        if node.threshold is not None:
            return self._build_threshold_group(
                node, group_var, child_vars, child_results, list(node.items), readable_path, warnings, errors
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
        child_results: list[ConstraintResult],
        child_nodes: list[RequirementNode],
        path: str,
        warnings: list[str],
        errors: list[str]
    ) -> ConstraintResult:
        """Build constraints for a group with a threshold."""
        threshold = node.threshold
        group_name = node.title or "unnamed"

        # This should never be None since we only call this when threshold is not None
        assert threshold is not None, "threshold must not be None"

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

        # Fireroad's actual behavior (from source code analysis in SUMMARY.md):
        # From progress.py:809-816:
        #   if req_progress.statement.connection_type == CONNECTION_TYPE_ALL and req_progress.children:
        #       num_courses_satisfied += req_progress.is_fulfilled and len(req_progress.satisfied_courses) > 0
        #   else:
        #       num_courses_satisfied += len(req_satisfied_courses)
        #
        # Translation for constraint builder:
        # - Direct course children: contribute 1 when taken (no children, goes to else)
        # - Group with connection_type='all' and children: contributes 1 when satisfied
        # - Group with other connection_type (including 'any' from thresholds): contributes count of satisfied courses
        if threshold.criterion == "subjects":
            # Build contribution variables for each child
            contribution_vars = []

            for idx, (child_node, child_result) in enumerate(zip(child_nodes, child_results)):
                # Skip children with no satisfied_var (e.g., courses not found in database)
                if child_result.satisfied_var is None:
                    continue

                if isinstance(child_node, RequirementCourse):
                    # Course: contributes 1 when taken
                    contribution_var = self.ctx.model.NewIntVar(0, 1, f"{group_name}_child{idx}_contribution")
                    self.ctx.model.Add(contribution_var == 1).OnlyEnforceIf(child_result.satisfied_var)
                    self.ctx.model.Add(contribution_var == 0).OnlyEnforceIf(child_result.satisfied_var.Not())
                    contribution_vars.append(contribution_var)
                elif isinstance(child_node, RequirementGroup):
                    # Check Fireroad's condition: connection_type='all' AND has children AND no threshold
                    # From progress.py lines 809-816: ALL groups without thresholds contribute 1 when satisfied,
                    # but ALL groups WITH thresholds contribute their course count (like any other group)
                    if child_node.connection_type == "all" and len(child_node.items) > 0 and child_node.threshold is None:
                        # ALL group with children but NO threshold: contributes 1 when satisfied
                        contribution_var = self.ctx.model.NewIntVar(0, 1, f"{group_name}_child{idx}_contribution")
                        self.ctx.model.Add(contribution_var == 1).OnlyEnforceIf(child_result.satisfied_var)
                        self.ctx.model.Add(contribution_var == 0).OnlyEnforceIf(child_result.satisfied_var.Not())
                        contribution_vars.append(contribution_var)
                    else:
                        # Other groups (including those with thresholds): contribute count of satisfied courses
                        # Per Fireroad semantics: groups with thresholds contribute the ACTUAL number of
                        # courses taken from that group, not the threshold cutoff
                        child_course_vars = self._collect_all_course_vars_from_results([child_node], [child_result])
                        if child_course_vars:
                            # Sum of courses taken from this child group
                            contribution_vars.extend(child_course_vars)
                        # If no courses available in child, it contributes 0 (handled by empty list)

            if not contribution_vars:
                self.ctx.model.Add(group_var == 0)
            else:
                # Sum all contributions
                total_contribution = sum(contribution_vars)
                self.ctx.model.Add(total_contribution >= cutoff).OnlyEnforceIf(group_var)
                self.ctx.model.Add(total_contribution < cutoff).OnlyEnforceIf(group_var.Not())
        else:
            # For other criteria (like 'units'), count direct children
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

        # Also enforce connection_type if present (both threshold AND connection_type must be satisfied)
        # This matches the validator.py logic where both are checked separately
        if node.connection_type == "all":
            # ALL: All children must be satisfied (in addition to threshold)
            if child_vars:
                for child_var in child_vars:
                    self.ctx.model.Add(child_var == 1).OnlyEnforceIf(group_var)
        elif node.connection_type == "any":
            # ANY: At least one child must be satisfied (in addition to threshold)
            # We add a one-way implication: if group is satisfied, at least one child must be satisfied
            # We do NOT use AddMaxEquality because that would override the threshold
            if child_vars:
                # If group_var is 1, then at least one child must be 1
                self.ctx.model.Add(sum(child_vars) >= 1).OnlyEnforceIf(group_var)

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

    def get_summary(self) -> ConstraintSummary:
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
    courses_df: pl.DataFrame,
    planning_year_start: int,
    enforce: bool = True
) -> tuple[dict[str, cp_model.IntVar], dict[str, str], dict[int, set[str]]]:
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
        Tuple of:
        - Dictionary of auxiliary variables created during constraint building
        - Dictionary mapping variable names to human-readable debug names
        - Dictionary mapping course indices to sets of requirement paths they satisfy

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
        print("\n=== Constraint Building Summary ===")
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

    return ctx.aux_vars, ctx.var_name_map, ctx.course_to_requirements
