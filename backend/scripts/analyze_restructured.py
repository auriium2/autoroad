# %%
"""
MIT AutoRoad Course Scheduler Analysis Module

This module analyzes course requirements and generates optimal schedules
using constraint programming.

Organized sections:
1. Imports and setup
2. Data fetching and preparation
3. Helper functions for requirement parsing
4. Core constraint satisfaction functions
5. Major-specific constraint handlers
6. Optimization and solution handling
7. Results export
"""

import requests
import pulp
import pprint
import pandas as pd
from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import CpModel
from datetime import datetime
import re
from pprint import pprint
from ..utils.utils import parse_prerequisites, find_current_school_year, is_valid_class_semester
import concurrent.futures
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# %%
#############################################
# SECTION 1: DATA FETCHING AND PREPARATION  #
#############################################

def fetch_requirement(key):
    """Fetch a requirement JSON by key from the FireRoad API"""
    resp = requests.get(f"https://fireroad.mit.edu/requirements/get_json/{key}")
    resp.raise_for_status()
    return key, resp.json()

# Fetch all course data
response = requests.get('https://fireroad.mit.edu/courses/all?full=true')
data = response.json()

# Create a DataFrame with course information
courses_df = pd.DataFrame(data)

# Extract and process requirements
requirements = ["girs", "major2", "major2a", "major6-3new", "major6-2new"]
with concurrent.futures.ThreadPoolExecutor() as executor:
    requirements_data = list(executor.map(fetch_requirement, requirements))

requirements_df = pd.DataFrame(requirements_data, columns=["key", "reqs"])

# Extract requirements for different majors
course2_requirements = requirements_df.set_index("key").loc['major2'].reqs
course2a_requirements = requirements_df.set_index("key").loc['major2a'].reqs
course6_3_requirements = requirements_df.set_index("key").loc['major6-3new'].reqs
course6_2_requirements = requirements_df.set_index("key").loc['major6-2new'].reqs
gir_requirements = requirements_df.set_index("key").loc['girs'].reqs

# %%
#############################################
# SECTION 2: HELPER FUNCTIONS              #
#############################################

def get_courses_for_hass(hass_type):
    """Get courses that satisfy a specific HASS requirement type"""
    return [course for course in data if course["hass_attribute"] == hass_type]

def get_courses_for_gir(gir_type):
    """Get courses that satisfy a specific GIR requirement"""
    return [course for course in data if gir_type in course["gir_attribute"]]

def count_leaf_courses(requirement, available_courses):
    """
    Count the number of leaf courses that satisfy a requirement
    
    Args:
        requirement: Requirement object with 'threshold' and 'content'
        available_courses: List of available courses
        
    Returns:
        int: Count of leaf courses that satisfy the requirement
    """
    if isinstance(requirement, str):
        # Base case: this is a leaf course
        return 1 if requirement in available_courses else 0
    
    if isinstance(requirement, dict):
        if "threshold" in requirement and "content" in requirement:
            # This is a nested requirement with threshold
            count = 0
            for item in requirement["content"]:
                count += count_leaf_courses(item, available_courses)
            return count
        else:
            # This might be a course ID or other type
            # Check if it's a valid course ID
            course_id = requirement.get("id", "")
            return 1 if course_id in available_courses else 0
    
    # Default case
    return 0

# %%
#############################################
# SECTION 3: REQUIREMENT SATISFACTION      #
#############################################

def generic_satisfied(requirement, taken, threshold=None):
    """
    Check if a generic requirement is satisfied by the taken courses
    
    Args:
        requirement: Requirement object
        taken: List of taken courses
        threshold: Override threshold value (optional)
        
    Returns:
        bool: True if requirement is satisfied, False otherwise
    """
    def get_courses_for_hass(hass_type):
        return [course for course in data if course["hass_attribute"] == hass_type]
    
    if isinstance(requirement, str):
        if requirement.startswith('hass_'):
            hass_type = requirement.split('_')[1].upper()
            hass_courses = get_courses_for_hass(hass_type)
            hass_subjects = [course["subject_id"] for course in hass_courses]
            return any(subject in taken for subject in hass_subjects)
        return requirement in taken
    
    if not isinstance(requirement, dict):
        return False
    
    req_threshold = threshold if threshold is not None else requirement.get("threshold", 1)
    content = requirement.get("content", [])
    
    satisfied_count = sum(1 for item in content if generic_satisfied(item, taken))
    return satisfied_count >= req_threshold

def hass_any_satisfied(requirement, taken, threshold=None):
    """
    Check if a HASS requirement is satisfied by the taken courses
    
    Args:
        requirement: HASS requirement object
        taken: List of taken courses
        threshold: Override threshold value (optional)
        
    Returns:
        bool: True if requirement is satisfied, False otherwise
    """
    def get_courses_for_hass(hass_type):
        return [course for course in data if course["hass_attribute"] == hass_type]
    
    req_threshold = threshold if threshold is not None else requirement.get("threshold", 1)
    content = requirement.get("content", [])
    
    satisfied_count = 0
    for item in content:
        if isinstance(item, str) and item.startswith('hass_'):
            hass_type = item.split('_')[1].upper()
            hass_courses = get_courses_for_hass(hass_type)
            hass_subjects = [course["subject_id"] for course in hass_courses]
            if any(subject in taken for subject in hass_subjects):
                satisfied_count += 1
    
    return satisfied_count >= req_threshold

# %%
#############################################
# SECTION 4: CONSTRAINT PROGRAMMING CORE    #
#############################################

def add_requirement_constraints(model, course_vars, requirements, req_vars=None, parent_group=""):
    """
    Add constraints to the model for satisfying curriculum requirements
    
    Args:
        model: CP-SAT model
        course_vars: Dictionary mapping course IDs to BoolVar instances
        requirements: Requirements to add constraints for
        req_vars: Dictionary to store requirement variables
        parent_group: Name of the parent requirement group
        
    Returns:
        Dictionary mapping requirement names to satisfaction variables
    """
    if req_vars is None:
        req_vars = {}
    
    def process_requirement(req, req_name, parent=None):
        """Process a single requirement and add constraints to the model"""
        nonlocal req_vars
        
        # Skip processing if this is the CI-H/CI-HW requirement handled separately
        if req_name in ["Communication Intensive Subjects in the Humanities, Arts, and Social Sciences (CI-H)"]:
            return None
        
        # Common group name formatting
        group_name = f"{parent}/{req_name}" if parent else req_name
        
        # Handle string requirements (usually course IDs)
        if isinstance(req, str):
            # Handle HASS requirements
            if req.startswith("hass_"):
                hass_type = req.split("_")[1].upper()
                hass_courses = [c["subject_id"] for c in data if c["hass_attribute"] == hass_type]
                
                # Create a placeholder variable for this HASS requirement
                var_name = f"{group_name}"
                placeholder = model.NewBoolVar(var_name)
                req_vars[var_name] = placeholder
                
                # The requirement is satisfied if at least one HASS course is taken
                satisfied_expr = []
                for course_id in hass_courses:
                    if course_id in course_vars:
                        satisfied_expr.append(course_vars[course_id])
                
                if satisfied_expr:
                    # Placeholder is true if at least one HASS course is taken
                    model.AddBoolOr(satisfied_expr).OnlyEnforceIf(placeholder)
                    model.AddBoolAnd([v.Not() for v in satisfied_expr]).OnlyEnforceIf(placeholder.Not())
                else:
                    # No HASS courses available, requirement cannot be satisfied
                    model.Add(placeholder == 0)
                
                return placeholder
            
            # Regular course requirement
            elif req in course_vars:
                var_name = f"{group_name}"
                req_vars[var_name] = course_vars[req]
                return course_vars[req]
            else:
                # Course not available
                var_name = f"{group_name}"
                dummy = model.NewBoolVar(var_name)
                model.Add(dummy == 0)
                req_vars[var_name] = dummy
                return dummy
        
        # Handle complex requirements with threshold and content
        elif isinstance(req, dict) and "threshold" in req and "content" in req:
            threshold = req["threshold"]
            content = req["content"]
            
            # Special handling for specific requirements
            if group_name == "Two Subjects from each of 2 EE Tracks":
                return handle_ee_tracks_requirement(model, course_vars, req, group_name)
            
            # Create a variable for this requirement group
            var_name = f"{group_name}"
            placeholder = model.NewBoolVar(var_name)
            req_vars[var_name] = placeholder
            
            # Process all sub-requirements
            sub_req_vars = []
            for i, item in enumerate(content):
                sub_name = f"item_{i}" if isinstance(item, (dict, list)) else item
                sub_var = process_requirement(item, sub_name, group_name)
                if sub_var:
                    sub_req_vars.append(sub_var)
            
            # Use leaf course counting for complex requirements
            use_leaf_counting = len(sub_req_vars) > 0 and threshold > 1
            
            if use_leaf_counting:
                available_courses = set(course_vars.keys())
                leaf_count = count_leaf_courses(req, available_courses)
                
                # Check if we have enough courses to potentially satisfy this requirement
                if leaf_count < threshold:
                    # Not enough courses available to satisfy requirement
                    handle_insufficient_courses(
                        model, placeholder, group_name, threshold, leaf_count, 
                        sub_req_vars, use_leaf_counting
                    )
                else:
                    # We have enough courses, add normal threshold constraint
                    model.Add(sum(sub_req_vars) >= threshold).OnlyEnforceIf(placeholder)
                    model.Add(sum(sub_req_vars) < threshold).OnlyEnforceIf(placeholder.Not())
            else:
                # Simple threshold constraint for non-leaf requirements
                if sub_req_vars:
                    model.Add(sum(sub_req_vars) >= threshold).OnlyEnforceIf(placeholder)
                    model.Add(sum(sub_req_vars) < threshold).OnlyEnforceIf(placeholder.Not())
                else:
                    # No sub-requirements, this requirement cannot be satisfied
                    model.Add(placeholder == 0)
            
            return placeholder
        
        # Unsupported requirement type
        else:
            var_name = f"{group_name}_unsupported"
            dummy = model.NewBoolVar(var_name)
            model.Add(dummy == 0)
            req_vars[var_name] = dummy
            return dummy
    
    def handle_insufficient_courses(model, placeholder, group_name, threshold, check_total, 
                                   sub_req_vars, use_leaf_counting):
        """Handle cases where there aren't enough courses to satisfy a requirement"""
        # Log the issue
        logger.warning(f"Marking {group_name} as infeasible: not enough total options ({check_total} < {threshold})")

        # Don't force it to be unsatisfied if it's a flexible requirement that can be bypassed
        if group_name in ["Electives", "Two Additional EECS"]:
            # For flexible requirements, we'll try to satisfy as much as possible
            logger.info(f"FLEXIBLE REQUIREMENT: {group_name} marked as feasible despite threshold issues")
        else:
            model.Add(placeholder == 0)  # Force to be unsatisfied for non-flexible requirements

        # For flexible requirements, let the solver try to optimize
        if group_name in ["Electives", "Two Additional EECS"] and sub_req_vars:
            if use_leaf_counting:
                # Using the same approach as the feasible case but with reduced threshold
                logger.info(f"Creating flexible leaf course constraint for {group_name} with reduced threshold {min(threshold, check_total)}")

                # Track which sub-requirements are satisfied
                satisfied_subs = []
                for i, sub_var in enumerate(sub_req_vars):
                    satisfied_sub = model.NewBoolVar(f"__internal_satisfied_sub_flex_{group_name}_{i}")
                    model.Add(sub_var == 1).OnlyEnforceIf(satisfied_sub)
                    model.Add(sub_var == 0).OnlyEnforceIf(satisfied_sub.Not())
                    satisfied_subs.append(satisfied_sub)

                # Try to satisfy as many as possible up to the available count
                adjusted_threshold = min(threshold, check_total)
                model.Add(sum(satisfied_subs) >= adjusted_threshold).OnlyEnforceIf(placeholder)
                model.Add(sum(satisfied_subs) < adjusted_threshold).OnlyEnforceIf(placeholder.Not())

    def handle_ee_tracks_requirement(model, course_vars, req, group_name):
        """Special handler for the EE tracks requirement in Course 6"""
        # This implementation handles the special "2 subjects from each of 2 EE tracks" requirement
        # by creating variables for each track and ensuring at least 2 tracks have 2+ subjects
        
        logger.info(f"Processing special EE Tracks requirement: {group_name}")
        
        # Create a variable for this requirement group
        placeholder = model.NewBoolVar(group_name)
        req_vars[group_name] = placeholder
        
        # Define EE tracks (based on Course 6 structure)
        # Note: This should be adapted to match the actual course groupings
        ee_tracks = {
            "Track 1: Circuits": ["6.2000", "6.2040", "6.2060", "6.2100", "6.2020"],
            "Track 2: Devices": ["6.2300", "6.2360", "6.2370", "6.2500"],
            "Track 3: Control": ["6.3000", "6.3010", "6.3400"],
            "Track 4: Communication": ["6.3700", "6.3900"],
            # Add other tracks as needed
        }
        
        # Create variables for each track meeting the "2 subjects" requirement
        track_vars = []
        for track_name, track_courses in ee_tracks.items():
            track_var = model.NewBoolVar(f"{group_name}/{track_name}")
            
            # Filter for courses in this track that are in our course_vars
            available_track_courses = [c for c in track_courses if c in course_vars]
            track_course_vars = [course_vars[c] for c in available_track_courses]
            
            if len(track_course_vars) >= 2:
                # Track is satisfied if at least 2 courses from it are taken
                model.Add(sum(track_course_vars) >= 2).OnlyEnforceIf(track_var)
                model.Add(sum(track_course_vars) < 2).OnlyEnforceIf(track_var.Not())
                track_vars.append(track_var)
            else:
                # Not enough courses in this track
                model.Add(track_var == 0)
        
        # Overall requirement is satisfied if at least 2 tracks are satisfied
        if len(track_vars) >= 2:
            model.Add(sum(track_vars) >= 2).OnlyEnforceIf(placeholder)
            model.Add(sum(track_vars) < 2).OnlyEnforceIf(placeholder.Not())
        else:
            # Not enough tracks available
            model.Add(placeholder == 0)
            logger.warning(f"Not enough EE tracks available to satisfy {group_name}")
        
        return placeholder
                
    # Process the main requirement
    if isinstance(requirements, dict):
        # Single requirement object
        result = process_requirement(requirements, parent_group or "requirement")
        return req_vars
    
    # Process each requirement in a list
    for req_name, req in requirements.items():
        process_requirement(req, req_name)
    
    return req_vars

def add_prerequisite_constraints(model, course_vars, taken_courses=None):
    """
    Add constraints to enforce prerequisite relationships between courses
    
    Args:
        model: CP-SAT model
        course_vars: Dictionary mapping course IDs to BoolVar instances
        taken_courses: List of courses already taken
        
    Returns:
        None
    """
    if taken_courses is None:
        taken_courses = []
    
    for course_id, course_var in course_vars.items():
        course_info = next((c for c in data if c["subject_id"] == course_id), None)
        if not course_info or "prerequisites_str" not in course_info:
            continue
        
        prereq_str = course_info["prerequisites_str"]
        if not prereq_str:
            continue
        
        # Parse prerequisites and add constraints
        prereq_tree = parse_prerequisites(prereq_str)
        if prereq_tree:
            process_prereq_condition(model, prereq_tree, course_id, course_vars, course_var, taken_courses)

def process_prereq_condition(model, condition, course_id, course_vars, course_var, taken_courses):
    """
    Process prerequisite conditions and add appropriate constraints
    
    Args:
        model: CP-SAT model
        condition: Prerequisite condition (parsed tree)
        course_id: ID of the course whose prerequisites we're processing
        course_vars: Dictionary mapping course IDs to BoolVar instances
        course_var: BoolVar for the course being processed
        taken_courses: List of courses already taken
        
    Returns:
        None
    """
    def get_courses_for_gir(gir_type):
        return [course for course in data if gir_type in course["gir_attribute"]]
    
    # Base case: string condition (usually a course ID)
    if isinstance(condition, str):
        # Check if this is a GIR requirement
        if condition in ["GIR:PHY1", "GIR:PHY2", "GIR:CHEM", "GIR:BIOL", "GIR:CAL1", "GIR:CAL2"]:
            # Get courses that satisfy this GIR
            gir_courses = get_courses_for_gir(condition)
            gir_ids = [c["subject_id"] for c in gir_courses]
            
            # Check if any of the GIR courses are already taken
            if any(gir_id in taken_courses for gir_id in gir_ids):
                # Prerequisite already satisfied by taken courses
                return
            
            # Find GIR courses that are in our course_vars
            available_gir_vars = [course_vars[gir_id] for gir_id in gir_ids 
                                 if gir_id in course_vars and gir_id != course_id]
            
            if available_gir_vars:
                # Create constraint: at least one of the GIR courses must be taken
                # if this course is taken
                model.AddBoolOr(available_gir_vars).OnlyEnforceIf(course_var)
            else:
                # No GIR courses available, prerequisite cannot be satisfied
                model.Add(course_var == 0)
        
        # Regular course prerequisite
        elif condition in course_vars and condition != course_id:
            # Simple prerequisite: prerequisite course must be taken if this course is taken
            model.Add(course_vars[condition] == 1).OnlyEnforceIf(course_var)
        elif condition in taken_courses:
            # Prerequisite already satisfied
            pass
        else:
            # Prerequisite not available, course cannot be taken
            model.Add(course_var == 0)
    
    # Logical AND condition
    elif isinstance(condition, list) and condition and condition[0] == "and":
        for subcond in condition[1:]:
            process_prereq_condition(model, subcond, course_id, course_vars, course_var, taken_courses)
    
    # Logical OR condition
    elif isinstance(condition, list) and condition and condition[0] == "or":
        # Create variables for each subcondition
        sub_vars = []
        for subcond in condition[1:]:
            # Create a temp variable for this subcondition
            sub_var = model.NewBoolVar(f"__prereq_{course_id}_{len(sub_vars)}")
            sub_vars.append(sub_var)
            
            # Process subcondition with this variable
            process_sub_prereq(model, subcond, course_id, course_vars, sub_var, taken_courses)
        
        if sub_vars:
            # At least one subcondition must be true if the course is taken
            model.AddBoolOr(sub_vars).OnlyEnforceIf(course_var)

def process_sub_prereq(model, condition, course_id, course_vars, result_var, taken_courses):
    """Helper function to process a prerequisite subcondition"""
    # Base case: string condition (usually a course ID)
    if isinstance(condition, str):
        if condition in course_vars and condition != course_id:
            # Subcondition is satisfied if the prerequisite course is taken
            model.Add(course_vars[condition] == 1).OnlyEnforceIf(result_var)
            model.Add(course_vars[condition] == 0).OnlyEnforceIf(result_var.Not())
        elif condition in taken_courses:
            # Prerequisite already satisfied
            model.Add(result_var == 1)
        else:
            # Prerequisite not available
            model.Add(result_var == 0)
    
    # Complex conditions
    elif isinstance(condition, list) and condition:
        if condition[0] == "and":
            # AND condition - all subconditions must be satisfied
            sub_vars = []
            for subcond in condition[1:]:
                sub_var = model.NewBoolVar(f"__prereq_sub_{course_id}_{len(sub_vars)}")
                process_sub_prereq(model, subcond, course_id, course_vars, sub_var, taken_courses)
                sub_vars.append(sub_var)
            
            if sub_vars:
                model.AddBoolAnd(sub_vars).OnlyEnforceIf(result_var)
                model.AddBoolOr([v.Not() for v in sub_vars]).OnlyEnforceIf(result_var.Not())
            else:
                model.Add(result_var == 0)
        
        elif condition[0] == "or":
            # OR condition - at least one subcondition must be satisfied
            sub_vars = []
            for subcond in condition[1:]:
                sub_var = model.NewBoolVar(f"__prereq_sub_{course_id}_{len(sub_vars)}")
                process_sub_prereq(model, subcond, course_id, course_vars, sub_var, taken_courses)
                sub_vars.append(sub_var)
            
            if sub_vars:
                model.AddBoolOr(sub_vars).OnlyEnforceIf(result_var)
                model.AddBoolAnd([v.Not() for v in sub_vars]).OnlyEnforceIf(result_var.Not())
            else:
                model.Add(result_var == 0)

# %%
#############################################
# SECTION 5: SOLUTION HANDLING             #
#############################################

class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Callback for handling solutions from the CP-SAT solver"""
    
    def __init__(self, course_vars, req_vars, n_courses=None, major_group_vars=None):
        """Initialize the solution printer callback"""
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.course_vars = course_vars
        self.req_vars = req_vars
        self.n_courses = n_courses
        self.major_group_vars = major_group_vars or {}
        self.solutions = []
        self.req_satisfaction = {}
        self.group_vars = {}
        self.flexible_reqs_status = {}
        self._solution_count = 0
    
    def on_solution_callback(self):
        """Called when a solution is found"""
        self._solution_count += 1
        solution = []
        
        # Record satisfied requirements
        req_status = {}
        for req_name, req_var in self.req_vars.items():
            req_status[req_name] = self.Value(req_var) == 1
        
        # Record solution courses
        for course_id, course_var in self.course_vars.items():
            if self.Value(course_var) == 1:
                solution.append(course_id)
        
        # Record solution
        self.solutions.append(solution)
        self.req_satisfaction[len(self.solutions) - 1] = req_status
        
        # Capture group variables (used for major requirements)
        for group_name, group_var in self.major_group_vars.items():
            self.group_vars[group_name] = group_var
            
            # Track flexible requirements
            if group_name in ["Electives", "Two Additional EECS", "Two Subjects from each of 2 EE Tracks"]:
                self.flexible_reqs_status[group_name] = self.Value(group_var) == 1
        
        # Display solution information
        print(f"\nSolution {self._solution_count}:")
        print(f"  Courses: {', '.join(solution)}")
        
        # Stop after finding a certain number of solutions
        if self.n_courses and len(solution) <= self.n_courses:
            self.StopSearch()
    
    def solution_count(self):
        """Return the number of solutions found"""
        return self._solution_count

# %%
#############################################
# SECTION 6: MAJOR-SPECIFIC CONSTRAINTS    #
#############################################

def add_course6_specific_constraints(model, course_vars, req_vars):
    """
    Add constraints specific to Course 6 requirements
    
    Args:
        model: CP-SAT model
        course_vars: Dictionary mapping course IDs to BoolVar instances
        req_vars: Dictionary of requirement variables
        
    Returns:
        None
    """
    logger.info("Adding Course 6-specific constraints")
    
    # Example: Special handling for AUS requirements in Course 6-3
    aus_courses = ["6.1200", "6.1201", "6.1210", "6.1220", "6.1400", "6.1800", "6.1900", "6.4100", "6.4590"]
    available_aus = [course_vars[c] for c in aus_courses if c in course_vars]
    
    # Find if we have the AUS requirement variable
    aus_req_var = None
    for name, var in req_vars.items():
        if "Advanced Undergraduate Subjects" in name:
            aus_req_var = var
            break
    
    # If we found the requirement variable, add custom constraint
    if aus_req_var and available_aus:
        model.Add(sum(available_aus) >= 2).OnlyEnforceIf(aus_req_var)
    
    # Add diagnostic constraints to identify issues with Course 6 optimization
    # This adds a dummy constraint that can be checked in solution analysis
    course6_diagnostic = model.NewBoolVar("__diagnostic_course6")
    if "Two Subjects from each of 2 EE Tracks" in req_vars:
        ee_tracks_var = req_vars["Two Subjects from each of 2 EE Tracks"]
        model.Add(course6_diagnostic == 1).OnlyEnforceIf(ee_tracks_var)
        model.Add(course6_diagnostic == 0).OnlyEnforceIf(ee_tracks_var.Not())

def add_course2_specific_constraints(model, course_vars, req_vars):
    """
    Add constraints specific to Course 2 requirements
    
    Args:
        model: CP-SAT model
        course_vars: Dictionary mapping course IDs to BoolVar instances
        req_vars: Dictionary of requirement variables
        
    Returns:
        None
    """
    logger.info("Adding Course 2-specific constraints")
    
    # Example: Special handling for ME restricted electives
    me_electives = ["2.001", "2.002", "2.003", "2.004", "2.005", "2.006", "2.007", "2.008", "2.009"]
    available_me = [course_vars[c] for c in me_electives if c in course_vars]
    
    # Find if we have the ME electives requirement variable
    me_elec_var = None
    for name, var in req_vars.items():
        if "Restricted Electives" in name:
            me_elec_var = var
            break
    
    # If we found the requirement variable, add custom constraint
    if me_elec_var and available_me:
        model.Add(sum(available_me) >= 2).OnlyEnforceIf(me_elec_var)
    
    # Add diagnostic constraints for Course 2 optimization
    course2_diagnostic = model.NewBoolVar("__diagnostic_course2")
    
    # Track some key Course 2 requirements for debugging
    key_course2_reqs = []
    for name, var in req_vars.items():
        if "Department Core" in name or "Mathematics Core" in name:
            key_course2_reqs.append(var)
    
    if key_course2_reqs:
        model.AddBoolAnd(key_course2_reqs).OnlyEnforceIf(course2_diagnostic)

# %%
#############################################
# SECTION 7: RESULTS EXPORT                #
#############################################

def export_take_blocks_to_road(take_list, output_file="output.road"):
    """
    Export a list of courses to a .road file
    
    Args:
        take_list: List of courses to include
        output_file: Name of output file
        
    Returns:
        None
    """
    # Get current school year
    school_year = find_current_school_year()
    
    # Initialize road data structure
    road_data = {
        "version": 6,
        "statics": {},
        "requirements": {},
        "overrides": {},
        "progress": {
            school_year: {}
        }
    }
    
    # Sort courses by subject ID
    sorted_courses = sorted(take_list)
    
    # Get course details from data
    course_details = {}
    for course_id in sorted_courses:
        course_info = next((c for c in data if c["subject_id"] == course_id), None)
        if course_info:
            course_details[course_id] = {
                "id": course_id,
                "title": course_info.get("title", ""),
                "units": course_info.get("total_units", 12),
                "semester": course_info.get("offered_fall", True) and "Fall" or "Spring"
            }
    
    # Create take blocks with at most 4 courses per semester
    courses_per_semester = 4
    fall_courses = [c for c in sorted_courses if is_valid_class_semester(c, "Fall")]
    spring_courses = [c for c in sorted_courses if is_valid_class_semester(c, "Spring")]
    
    # Build semesters
    semesters = []
    
    # Fall semester
    for i in range(0, len(fall_courses), courses_per_semester):
        chunk = fall_courses[i:i + courses_per_semester]
        semester = {
            "year": school_year,
            "season": "Fall",
            "courses": chunk
        }
        semesters.append(semester)
    
    # Spring semester
    for i in range(0, len(spring_courses), courses_per_semester):
        chunk = spring_courses[i:i + courses_per_semester]
        semester = {
            "year": school_year,
            "season": "Spring",
            "courses": chunk
        }
        semesters.append(semester)
    
    # Add semesters to road file
    road_data["progress"][school_year]["semesters"] = semesters
    
    # Write road file
    with open(output_file, 'w') as f:
        json.dump(road_data, f, indent=2)
    
    logger.info(f"Road file exported to {output_file}")

# %%
#############################################
# SECTION 8: MAIN EXECUTION               #
#############################################

def setup_and_solve(major="course6-3", taken_courses=None, max_courses=12, time_limit_seconds=30):
    """
    Set up and solve the course scheduling problem
    
    Args:
        major: Which major to optimize for (e.g., "course6-3", "course2")
        taken_courses: List of courses already taken
        max_courses: Maximum number of courses to include in solution
        time_limit_seconds: Time limit for solver
        
    Returns:
        dict: Solution information
    """
    if taken_courses is None:
        taken_courses = []
    
    # Create model
    model = cp_model.CpModel()
    
    # Create course variables
    course_vars = {}
    for course in data:
        course_id = course["subject_id"]
        if course_id not in taken_courses:
            course_vars[course_id] = model.NewBoolVar(f"take_{course_id}")
    
    # Add constraint on total courses
    model.Add(sum(course_vars.values()) <= max_courses)
    
    # Select appropriate requirements based on major
    if major == "course6-3":
        major_requirements = course6_3_requirements
    elif major == "course6-2":
        major_requirements = course6_2_requirements
    elif major == "course2":
        major_requirements = course2_requirements
    elif major == "course2a":
        major_requirements = course2a_requirements
    else:
        raise ValueError(f"Unsupported major: {major}")
    
    # Add GIR requirements
    gir_req_vars = add_requirement_constraints(model, course_vars, gir_requirements, parent_group="GIRs")
    
    # Add major requirements
    major_req_vars = add_requirement_constraints(model, course_vars, major_requirements, parent_group=major)
    
    # Add major-specific constraints
    if major.startswith("course6"):
        add_course6_specific_constraints(model, course_vars, major_req_vars)
    elif major.startswith("course2"):
        add_course2_specific_constraints(model, course_vars, major_req_vars)
    
    # Add prerequisite constraints
    add_prerequisite_constraints(model, course_vars, taken_courses)
    
    # Combine all requirement variables
    all_req_vars = {**gir_req_vars, **major_req_vars}
    
    # Set objective: maximize satisfied requirements
    # Give higher weight to major requirements
    objective_terms = []
    for name, var in all_req_vars.items():
        weight = 10 if name.startswith(major) else 5
        objective_terms.append(weight * var)
    
    # Add course-taking term to objective with smaller weight
    for course_id, var in course_vars.items():
        objective_terms.append(1 * var)
    
    model.Maximize(sum(objective_terms))
    
    # Solve model
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    
    # Create solution callback
    solution_printer = VarArraySolutionPrinter(
        course_vars, all_req_vars, max_courses, major_req_vars
    )
    
    # Solve
    status = solver.Solve(model, solution_printer)
    
    # Process results
    result = {
        "status": status,
        "status_name": solver.StatusName(status),
        "solutions": solution_printer.solutions,
        "req_satisfaction": solution_printer.req_satisfaction,
        "objective_value": solver.ObjectiveValue() if status in [cp_model.OPTIMAL, cp_model.FEASIBLE] else None
    }
    
    # Add diagnostics for debugging
    if major.startswith("course6"):
        result["diagnostics"] = {
            "major_type": "course6",
            "flexible_reqs": solution_printer.flexible_reqs_status
        }
    elif major.startswith("course2"):
        result["diagnostics"] = {
            "major_type": "course2",
            "flexible_reqs": solution_printer.flexible_reqs_status
        }
    
    return result

if __name__ == "__main__":
    # Example usage
    print("Solving for Course 6-3...")
    course6_result = setup_and_solve(major="course6-3")
    
    print("\nSolving for Course 2...")
    course2_result = setup_and_solve(major="course2")
    
    # Compare results to help debug Course 6 optimization issues
    print("\nComparing Course 6 vs Course 2 results for debugging:")
    print(f"Course 6-3 status: {course6_result['status_name']}")
    print(f"Course 2 status: {course2_result['status_name']}")
    
    # Export best solution if available
    if course6_result["solutions"]:
        export_take_blocks_to_road(course6_result["solutions"][0], "course6_solution.road")
    
    if course2_result["solutions"]:
        export_take_blocks_to_road(course2_result["solutions"][0], "course2_solution.road")