# Fireroad Complete Threshold, Connection Type, and Criterion Code

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Complete Code Listings](#complete-code-listings)
   - [Data Structures (reqlist.py)](#data-structures-reqlistpy)
   - [Progress Calculation (progress.py)](#progress-calculation-progresspy)
   - [Test Cases](#test-cases-testspy)
3. [Key Algorithms Explained](#key-algorithms-explained)
4. [Implementation Guide](#implementation-guide)
5. [File Reference Map](#file-reference-map)

---

## Executive Summary

This document contains **all source code** related to how Fireroad handles:
- **Thresholds** (`threshold`, `distinct_threshold`)
- **Connection Types** (`all`, `any`, `none`)
- **Criteria** (`subjects`, `units`)

### The Three Core Rules for Progress Calculation

When a parent requirement has a threshold with `criterion='subjects'`:

1. **Direct course child (taken)** → contributes **1** to parent progress
2. **Group child WITHOUT threshold (connection_type='all')** → contributes **1** when satisfied
3. **Group child WITH threshold** → contributes its **progress value** when satisfied

---

## Complete Code Listings

### Data Structures (reqlist.py)

#### Constants and Helper Functions

**File**: `/Users/matt/fireroad-server/requirements/reqlist.py`

```python
from django.db import models
import re

# Connection type constants
CONNECTION_TYPE_ALL = "all"
CONNECTION_TYPE_ANY = "any"
CONNECTION_TYPE_NONE = "none"

# Threshold type constants
THRESHOLD_TYPE_LT = "LT"
THRESHOLD_TYPE_LTE = "LTE"
THRESHOLD_TYPE_GT = "GT"
THRESHOLD_TYPE_GTE = "GTE"

# Criterion constants
CRITERION_SUBJECTS = "subjects"
CRITERION_UNITS = "units"

# Default unit count for courses
DEFAULT_UNIT_COUNT = 12

def top_level_separator_regex(separator):
    """Returns a regex that matches separators in only the top level of a string
    (i.e. no separators found within parenthetical statements)."""
    sep_pattern = re.escape(separator)
    return sep_pattern + r'(?![^\(]*\))'

modifier_regex = "\\{(.*?)\\}(?![^\\(]*\\))"

def undecorated_component(component):
    """Returns the given component string without leading/trailing whitespace
    and quotation marks."""
    return component.strip(" \t\r\n\"'")

def unwrapped_component(component):
    """Returns the given component string without leading/trailing whitespace
    and unwrapped out of any parenthesis pairs."""
    unwrapping = component.strip(" \t\n\r")
    while unwrapping[0] == "(" and unwrapping[-1] == ")":
        # Make sure these parentheses are not closed within the string
        indent_level = 0
        stop_unwrapping = False
        for i in range(len(unwrapping)):
            if unwrapping[i] == "(":
                indent_level += 1
            elif unwrapping[i] == ")":
                indent_level -= 1
                if indent_level == 0 and i < len(unwrapping) - 1:
                    stop_unwrapping = True
                    break
        if stop_unwrapping:
            break
        unwrapping = unwrapping[1:-1]

    return unwrapping

def components_separated_by_regex(string, regex):
    return [undecorated_component(comp) for comp in re.split(regex, string)]
```

#### Threshold Class

**File**: `/Users/matt/fireroad-server/requirements/reqlist.py`

```python
class Threshold(object):
    """An object describing a threshold of child requirements to fulfill to fulfill an overall requirement
    type: threshold type (GT, GTE, LT, LTE)
    cutoff: the number of subjects/units to fulfill the requirement
    get_actual_cutoff(): actual number of subjects/units needed to fulfill the requirement (adjusted up or down 1 for less than or greater than)
    criterion: metric to meet cutoff (subjects or units)
    cutoff_for_criterion: converts cutoff into subjects to units
    is_satisfied_by: tests if the threshold is satisfied by a given subject and unit Progress object
    """

    def __init__(self, threshold_type, number, criterion):
        self.type = threshold_type
        self.cutoff = number
        self.criterion = criterion

    def cutoff_for_criterion(self, criterion):
        """Returns the cutoff value converted to the given criterion.
        If threshold is in subjects but you want units, multiplies by DEFAULT_UNIT_COUNT.
        If threshold is in units but you want subjects, divides by DEFAULT_UNIT_COUNT."""
        if self.criterion == criterion:
            co = self.cutoff
        elif self.criterion == CRITERION_SUBJECTS:
            co = self.cutoff * DEFAULT_UNIT_COUNT
        else:
            co = self.cutoff / DEFAULT_UNIT_COUNT
        return co

    def get_actual_cutoff(self):
        """Adjusts the cutoff for > and < thresholds.
        > becomes +1, < becomes -1"""
        if self.type == THRESHOLD_TYPE_GT:
            return self.cutoff + 1
        elif self.type == THRESHOLD_TYPE_LT:
            return self.cutoff - 1
        return self.cutoff

    def is_satisfied_by(self, subject_progress, unit_progress):
        """Tests if this threshold is satisfied by the given progress values."""
        progress = (subject_progress, unit_progress)[self.criterion == CRITERION_UNITS]
        actualcutoff = self.get_actual_cutoff()

        if self.type == THRESHOLD_TYPE_LT or self.type == THRESHOLD_TYPE_LTE:
            return progress <= actualcutoff
        elif self.type == THRESHOLD_TYPE_GT or self.type == THRESHOLD_TYPE_GTE:
            return progress >= actualcutoff

    def __repr__(self):
        return self.type + " " + self.criterion + " " + str(self.cutoff)
```

#### Syntax and JSON Constants

**File**: `/Users/matt/fireroad-server/requirements/reqlist.py`

```python
class SyntaxConstants:
    """Static constants for use in parsing."""
    all_separator = ","
    any_separator = "/"
    comment_character = "%%"
    declaration_character = ":="
    variable_declaration_separator = ","
    header_separator = "#,#"

    threshold_parameter = "threshold="
    url_parameter = "url="

class JSONConstants:
    """Static constants for use in output to JSON."""
    # Common keys
    title = "title"
    description = "desc"

    # Top level keys in a RequirementsList JSON dictionary
    list_id = "list-id"
    short_title = "short-title"
    medium_title = "medium-title"
    title_no_degree = "title-no-degree"
    catalog_url = "url"
    # And requirements

    # Top level keys in a RequirementsStatement JSON dictionary
    requirement = "req" # string requirement (if not present, see reqs)
    is_plain_string = "plain-string" # optional boolean
    requirements = "reqs" # list of RequirementsStatement objects (if not present, see req)
    connection_type = "connection-type" # exists if requirements exists, and is "all", "any", or "none"
    threshold = "threshold" # optional dictionary (see below)
    distinct_threshold = "distinct-threshold" # optional dictionary (see below)
    thresh_description = "threshold-desc" # User-facing string describing the thresholds (if applicable)

    # Keys within the threshold or distinct-threshold dictionaries
    thresh_type = "type"
    thresh_cutoff = "cutoff"
    thresh_criterion = "criterion"
```

#### RequirementsStatement Class - Core Fields

**File**: `/Users/matt/fireroad-server/requirements/reqlist.py`

```python
class RequirementsStatement(models.Model):
    """Represents a single requirements statement, encompassing a series of
    subjects or other requirements statements connected by AND or OR."""

    #list = models.ForeignKey("RequirementsList", on_delete=models.CASCADE, related_name="requirements", null=True)

    title = models.CharField(max_length=250, null=True)
    description = models.TextField(null=True)
    requirement = models.CharField(max_length=100, null=True)
    parent = models.ForeignKey("self", null=True, related_name="requirements", on_delete=models.CASCADE)
    is_plain_string = models.BooleanField(default=False)

    connection_type = models.CharField(max_length=10, choices=(
        (CONNECTION_TYPE_ALL, "all"),
        (CONNECTION_TYPE_ANY, "any"),
        (CONNECTION_TYPE_NONE, "none")
    ), default=CONNECTION_TYPE_ALL)

    # Threshold
    threshold_type = models.CharField(max_length=4, choices=(
        (THRESHOLD_TYPE_LT, "less than"),
        (THRESHOLD_TYPE_LTE, "at most"),
        (THRESHOLD_TYPE_GT, "greater than"),
        (THRESHOLD_TYPE_GTE, "at least")
    ), null=True)
    threshold_cutoff = models.IntegerField(default=0, null=False)
    threshold_criterion = models.CharField(max_length=10, choices=(
        (CRITERION_SUBJECTS, "subjects"),
        (CRITERION_UNITS, "units")
    ), default=CRITERION_SUBJECTS)

    # Distinct threshold
    distinct_threshold_type = models.CharField(max_length=4, choices=(
        (THRESHOLD_TYPE_LT, "less than"),
        (THRESHOLD_TYPE_LTE, "at most"),
        (THRESHOLD_TYPE_GT, "greater than"),
        (THRESHOLD_TYPE_GTE, "at least")
    ), null=True)
    distinct_threshold_cutoff = models.IntegerField(default=0, null=False)
    distinct_threshold_criterion = models.CharField(max_length=10, choices=(
        (CRITERION_SUBJECTS, "subjects"),
        (CRITERION_UNITS, "units")
    ), default=CRITERION_SUBJECTS)

    def get_threshold(self):
        if self.threshold_type is not None:
            return Threshold(self.threshold_type, self.threshold_cutoff, self.threshold_criterion)
        else:
            return None
            
    def get_distinct_threshold(self):
        if self.distinct_threshold_type is not None:
            return Threshold(self.distinct_threshold_type, self.distinct_threshold_cutoff, self.distinct_threshold_criterion)
        else:
            return None
```

#### RequirementsStatement - Threshold Description

**File**: `/Users/matt/fireroad-server/requirements/reqlist.py`

```python
    def threshold_description(self):
        """Returns a string description of this statement's threshold."""
        ret = ""
        if self.requirement is not None and self.connection_type == CONNECTION_TYPE_ALL and self.threshold_type is None:
            return ret

        if self.threshold_type is not None and self.threshold_cutoff != 1:
            if self.threshold_cutoff > 1:
                if self.threshold_type == THRESHOLD_TYPE_LTE:
                    ret = "select at most {}".format(self.threshold_cutoff)
                elif self.threshold_type == THRESHOLD_TYPE_LT:
                    ret = "select at most {}".format(self.threshold_cutoff - 1)
                elif self.threshold_type == THRESHOLD_TYPE_GTE:
                    ret = "select any {}".format(self.threshold_cutoff)
                elif self.threshold_type == THRESHOLD_TYPE_GT:
                    ret = "select any {}".format(self.threshold_cutoff + 1)

                if self.threshold_criterion == CRITERION_UNITS:
                    ret += " units"
                elif self.threshold_criterion == CRITERION_SUBJECTS and self.connection_type == CONNECTION_TYPE_ALL:
                    ret += " subjects"
            elif self.threshold_cutoff == 0 and self.connection_type == CONNECTION_TYPE_ANY:
                ret = "optional - select any"

        elif self.connection_type == CONNECTION_TYPE_ALL:
            ret = "select all"
        elif self.connection_type == CONNECTION_TYPE_ANY:
            if self.requirements.all().exists() and len(self.requirements.all()) == 2:
                ret = "select either"
            else:
                ret = "select any"

        if self.distinct_threshold_type is not None and self.distinct_threshold_cutoff > 0:
            if self.distinct_threshold_type == THRESHOLD_TYPE_LTE:
                category_text = "categories" if self.distinct_threshold_cutoff != 1 else "category"
                ret += " from at most {} {}".format(self.distinct_threshold_cutoff, category_text)
            elif self.distinct_threshold_type == THRESHOLD_TYPE_LT:
                category_text = "categories" if self.distinct_threshold_cutoff - 1 != 1 else "category"
                ret += " from at most {} {}".format(self.distinct_threshold_cutoff - 1, category_text)
            elif self.distinct_threshold_type == THRESHOLD_TYPE_GTE:
                category_text = "categories" if self.distinct_threshold_cutoff != 1 else "category"
                ret += " from at least {} {}".format(self.distinct_threshold_cutoff, category_text)
            elif self.distinct_threshold_type == THRESHOLD_TYPE_GT:
                category_text = "categories" if self.distinct_threshold_cutoff + 1 != 1 else "category"
                ret += " from at least {} {}".format(self.distinct_threshold_cutoff + 1, category_text)

        return ret
```

#### RequirementsStatement - Parsing Methods

**File**: `/Users/matt/fireroad-server/requirements/reqlist.py`

```python
    def separate_top_level_items(self, text):
        """Returns a list of the top-level substituents of the given requirements
        statement, as well as a connection type string."""

        trimmed = text.strip(" \t\n\r")
        if len(trimmed) >= 4 and trimmed[:2] == '""' and trimmed[-2:] == '""':
            return ([undecorated_component(trimmed)], CONNECTION_TYPE_NONE)

        components = []
        connection_type = CONNECTION_TYPE_ALL
        current_indent_level = 0

        for character in trimmed:
            if character == SyntaxConstants.all_separator and current_indent_level == 0:
                connection_type = CONNECTION_TYPE_ALL
                components.append("")
            elif character == SyntaxConstants.any_separator and current_indent_level == 0:
                connection_type = CONNECTION_TYPE_ANY
                components.append("")
            else:
                if character == "(":
                    current_indent_level += 1
                elif character == ")":
                    current_indent_level -= 1
                if len(components) == 0:
                    components.append("")
                components[-1] += character

        return ([undecorated_component(s) for s in components], connection_type)

    def parse_modifier_component(self, modifier):
        """Returns a tuple indicating the threshold type, the cutoff, and criterion."""

        # Of the form >=x, <=x, >x, or <x
        threshold_type = THRESHOLD_TYPE_GTE
        cutoff = 1
        criterion = CRITERION_SUBJECTS

        if ">=" in modifier:
            threshold_type = THRESHOLD_TYPE_GTE
        elif "<=" in modifier:
            threshold_type = THRESHOLD_TYPE_LTE
        elif ">" in modifier:
            threshold_type = THRESHOLD_TYPE_GT
        elif "<" in modifier:
            threshold_type = THRESHOLD_TYPE_LT
        number_string = modifier.replace(">", "").replace("<", "").replace("=", "")
        if "u" in number_string:
            criterion = CRITERION_UNITS
            number_string = number_string.replace("u", "")

        try:
            cutoff = int(number_string)
        except ValueError:
            print("Couldn't get number out of modifier string {}".format(modifier))

        return (threshold_type, cutoff, criterion)

    def parse_modifier(self, modifier):
        """Applies the given modifier to this RequirementsStatement object."""

        if "|" in modifier:
            comps = modifier.split("|")
            if len(comps) != 2:
                print("Unsupported number of components in modifier string: {}".format(modifier))
                return

            if len(comps[0]) > 0:
                type, cutoff, criterion = self.parse_modifier_component(comps[0])
                self.threshold_type = type
                self.threshold_cutoff = cutoff
                self.threshold_criterion = criterion
            if len(comps[1]) > 0:
                type, cutoff, criterion = self.parse_modifier_component(comps[1])
                self.distinct_threshold_type = type
                self.distinct_threshold_cutoff = cutoff
                self.distinct_threshold_criterion = criterion

        elif len(modifier) > 0:
            type, cutoff, criterion = self.parse_modifier_component(modifier)
            self.threshold_type = type
            self.threshold_cutoff = cutoff
            self.threshold_criterion = criterion

    def parse_string(self, string):
        """Parses the given requirements statement and sets self's properties
        accordingly."""
        filtered_statement = string
        modifier_match = re.search(modifier_regex, filtered_statement)
        if modifier_match is not None:
            self.parse_modifier(modifier_match.group(1))
            filtered_statement = re.sub(modifier_regex, "", filtered_statement)

        components, connection_type = self.separate_top_level_items(filtered_statement)
        
        # CRITICAL: This sets connection_type='any' for thresholds with cutoff=0
        if self.threshold_type is not None and self.threshold_cutoff == 0 and self.threshold_type == THRESHOLD_TYPE_GTE:
            self.connection_type = CONNECTION_TYPE_ANY
        else:
            self.connection_type = connection_type
        
        self.is_plain_string = (connection_type == CONNECTION_TYPE_NONE)

        if len(components) == 1 or self.is_plain_string:
            self.requirement = components[0]
        else:
            for c in components:
                RequirementsStatement.from_string(unwrapped_component(c), parent=self)
```

#### RequirementsStatement - JSON Output

**File**: `/Users/matt/fireroad-server/requirements/reqlist.py`

```python
    def to_json_object(self, full=True, child_fn=None):
        """Encodes this requirements statement into a serializable object that can
        be dumped to JSON.

        If this statement has child requirements, it uses the child_fn to output
        the JSON for each child. If child_fn is None, uses the to_json_object()
        on the child requirements; if not, it should be a function that takes a
        RequirementsStatement and produces a JSON object describing it.

        The full keyword argument is currently not used by RequirementsStatement."""

        base = {}
        if self.title is not None and len(self.title) > 0:
            base[JSONConstants.title] = self.title
        if self.description is not None and len(self.description) > 0:
            base[JSONConstants.description] = self.description

        if self.threshold_type is not None:
            base[JSONConstants.threshold] = {
                JSONConstants.thresh_type: self.threshold_type,
                JSONConstants.thresh_cutoff: self.threshold_cutoff,
                JSONConstants.thresh_criterion: self.threshold_criterion,
            }
        if self.distinct_threshold_type is not None:
            base[JSONConstants.distinct_threshold] = {
                JSONConstants.thresh_type: self.distinct_threshold_type,
                JSONConstants.thresh_cutoff: self.distinct_threshold_cutoff,
                JSONConstants.thresh_criterion: self.distinct_threshold_criterion,
            }

        desc = self.threshold_description()
        if len(desc) > 0:
            base[JSONConstants.thresh_description] = desc
        if self.is_plain_string:
            base[JSONConstants.is_plain_string] = self.is_plain_string

        if self.requirement is not None:
            base[JSONConstants.requirement] = self.requirement
        elif full and self.requirements.exists():
            base[JSONConstants.requirements] = [(child_fn(r) if child_fn is not None else r.to_json_object()) for r in self.requirements.all()]
            base[JSONConstants.connection_type] = self.connection_type

        return base
```

---

### Progress Calculation (progress.py)

**File**: `/Users/matt/fireroad-server/requirements/progress.py`

#### Helper Functions

```python
from reqlist import *
import random
from catalog.models import Course

def ceiling_thresh(progress, maximum):
    """Creates a progress object
    Ensures that 0 < progress < maximum"""

    effective_progress = max(0, progress)

    if maximum > 0:
        return Progress(min(effective_progress, maximum), maximum)
    else:
        return Progress(effective_progress, maximum)


def total_units(courses):
    """Finds the total units in a list of Course objects"""
    total = 0
    for course in courses:
        total += course.total_units
    return total


def sum_progresses(progresses, criterion_type, maxFunc):
    """Adds together a list of Progress objects by combining them one by one
    criterion_type: either subjects or units
    maxFunc: describes how to combine the maximums of the Progress objects"""

    if criterion_type == CRITERION_SUBJECTS:
        mapfunc = lambda p: p.subject_fulfillment
    elif criterion_type == CRITERION_UNITS:
        mapfunc = lambda p: p.unit_fulfillment
    sum_progress = reduce(lambda p1, p2: p1.combine(p2, maxFunc), map(mapfunc, progresses))
    return sum_progress


def force_unfill_progresses(satisfied_by_category, current_distinct_threshold, current_threshold):
    """Adjusts the fulfillment and progress of RequirementsProgress object with both distinct thresholds and thresholds
    These requirements follow the form "X subjects/units from at least N categories"
    satisfied_by_category: list of lists of Courses for each category
    current_distinct_threshold: threshold object for distinct threshold
    current_threshold: threshold object for regular threshold"""

    subject_cutoff = current_threshold.cutoff_for_criterion(CRITERION_SUBJECTS)
    unit_cutoff = current_threshold.cutoff_for_criterion(CRITERION_UNITS)

    #list of subjects by category sorted by units
    max_unit_subjects = map(lambda sat_cat: sorted(sat_cat, key = lambda s: s.total_units), satisfied_by_category)

    #split subjects into two sections: fixed and free
    #fixed subjects: must have one subject from each category
    #free subjects: remaining subjects to fill requirement can come from any category
    #choose maximum-unit courses to fulfill requirement with least amount of courses possible
    fixed_subject_progress = 0
    fixed_subject_max = current_distinct_threshold.get_actual_cutoff()
    fixed_unit_progress = 0
    fixed_unit_max = 0

    #fill fixed subjects with maximum-unit course in each category
    for category_subjects in max_unit_subjects:
        if len(category_subjects) > 0:
            subject_to_count = category_subjects.pop()
            fixed_subject_progress += 1
            fixed_unit_progress += subject_to_count.total_units
            fixed_unit_max += subject_to_count.total_units
        else:
            fixed_unit_max += DEFAULT_UNIT_COUNT

    #remaining subjects/units to fill
    remaining_subject_progress = subject_cutoff - fixed_subject_max
    remaining_unit_progress = unit_cutoff - fixed_unit_max

    #choose free courses from all remaining courses
    free_courses = sorted([course for category in max_unit_subjects for course in category], key = lambda s: s.total_units, reverse = True)
    free_subject_max = subject_cutoff - fixed_subject_max
    free_unit_max = unit_cutoff - fixed_unit_max

    free_subject_progress = min(len(free_courses), free_subject_max)
    free_unit_progress = min(total_units(free_courses), free_unit_max)

    #add fixed and free courses to get total progress
    subject_progress = Progress(fixed_subject_progress + free_subject_progress, subject_cutoff)
    unit_progress = Progress(fixed_unit_progress + free_unit_progress, unit_cutoff)
    return (subject_progress, unit_progress)
```

#### Progress Class

```python
class Progress(object):
    """An object describing simple progress towards a requirement
    Different from RequirementsProgress object as it only includes progress information,
    not nested RequirementsProgress objects, fulfillment status, title, and other information
    progress: number of units/subjects completed
    max: number of units/subjects needed to fulfill requirement"""

    def __init__(self, progress, max):
        self.progress = progress
        self.max = max

    def get_percent(self):
        if self.max > 0:
            return min(100, int(round((self.progress / float(self.max)) * 100)))
        else:
            return "N/A"

    def get_fraction(self):
        if self.max > 0:
            return self.progress / float(self.max)
        else:
            return "N/A"

    def get_raw_fraction(self, unit):
        denom = max(self.max, DEFAULT_UNIT_COUNT if unit == CRITERION_UNITS else 1)
        return self.progress/denom

    def combine(self, p2, maxFunc):
        if maxFunc is not None:
            return Progress(self.progress + p2.progress, self.max + maxFunc(p2.max))
        return Progress(self.progress + p2.progress, self.max + p2.max)

    def __repr__(self):
        return str(self.progress) + " / " + str(self.max)
```

#### RequirementsProgress Class - Initialization

```python
class RequirementsProgress(object):
    """
    Stores a user's progress towards a given requirements statement. This object
    wraps a requirements statement and has a to_json_object() method which
    returns the statement's own JSON dictionary representation with progress
    information added.

    Note: This class is maintained separately from the Django model so that
    persistent information can be stored in a database-friendly format, while
    information specific to a user's request is transient.
    """
    def __init__(self, statement, list_path):
        """Initializes a progress object with the given requirements statement."""
        self.statement = statement
        self.threshold = self.statement.get_threshold()
        self.distinct_threshold = self.statement.get_distinct_threshold()
        self.list_path = list_path
        self.children = []
        if self.statement.requirement is None:
            for index, child in enumerate(self.statement.requirements.iterator()):
                self.children.append(RequirementsProgress(child, list_path + "." + str(index)))
```

#### RequirementsProgress - Courses Satisfying Requirement

```python
    def courses_satisfying_req(self, courses):
        """
        Returns the whole courses and the half courses satisfying this requirement
        separately.
        """
        if self.statement.requirement is not None:
            req = self.statement.requirement
            if "GIR:" in req or "HASS" in req or "CI-" in req:
                # Separate whole and half courses
                whole_courses = []
                half_courses = []
                for c in courses:
                    if not c.satisfies(req, courses):
                        continue
                    if c.is_half_class:
                        half_courses.append(c)
                    else:
                        whole_courses.append(c)
                return whole_courses, half_courses
            else:
                return [c for c in courses if c.satisfies(req, courses)], []

        return [], []
```

#### RequirementsProgress - Manual Override

```python
    def override_requirement(self, manual_progress):
        """
        Sets the progress fulfillment variables based on a manual progress value, which is
        expressed in either units or subjects depending on the requirement's threshold.
        """
        self.is_fulfilled = manual_progress >= self.threshold.get_actual_cutoff()
        subjects = 0
        units = 0
        satisfied_courses = set()

        if self.threshold.criterion == CRITERION_UNITS:
            units = manual_progress
            subjects = manual_progress / DEFAULT_UNIT_COUNT
        else:
            units = manual_progress * DEFAULT_UNIT_COUNT
            subjects = manual_progress

        subject_progress = ceiling_thresh(subjects, self.threshold.cutoff_for_criterion(CRITERION_SUBJECTS))
        unit_progress = ceiling_thresh(units, self.threshold.cutoff_for_criterion(CRITERION_UNITS))
        #fill with dummy courses
        random_ids = random.sample(range(1000, max(10000, subject_progress.progress + 1000)), subject_progress.progress)

        for rand_id in random_ids:
            dummy_course = Course(id = self.list_path + "_" + str(rand_id), subject_id = "gen_course_" + self.list_path + "_" + str(rand_id), title = "Generated Course " + self.list_path + " " + str(rand_id))
            satisfied_courses.add(dummy_course)

        progress_units = CRITERION_SUBJECTS if self.threshold is None else self.threshold.criterion
        self.subject_fulfillment = subject_progress
        self.subject_progress = subject_progress.progress
        self.subject_max = subject_progress.max
        self.unit_fulfillment = unit_progress
        self.unit_progress = unit_progress.progress
        self.unit_max = unit_progress.max
        progress = unit_progress if self.threshold is not None and self.threshold.criterion == CRITERION_UNITS else subject_progress
        self.progress = progress.progress
        self.progress_max = progress.max
        self.percent_fulfilled = progress.get_percent()
        self.fraction_fulfilled = progress.get_fraction()
        self.raw_fraction_fulfilled = progress.get_raw_fraction(progress_units)
        self.satisfied_courses = list(satisfied_courses)
```

#### RequirementsProgress - Compute Method (MOST CRITICAL)

This is the main algorithm that implements the three rules!

```python
    def compute(self, courses, progress_overrides, progress_assertions):
        """Computes and stores the status of the requirements statement using the
        given list of Course objects."""
        # Compute status of children and then self, adapted from mobile apps' computeRequirementsStatus method
        satisfied_courses = set()
        if self.compute_assertions(courses, progress_assertions):
            self.bypass_children()
            return

        if self.list_path in progress_overrides:
            manual_progress = progress_overrides[self.list_path]
        else:
            manual_progress = 0
        self.is_bypassed = False
        self.assertion = None

        # SECTION 1: Handle basic (leaf) requirements
        if self.statement.requirement is not None:
            #it is a basic requirement
            if self.statement.is_plain_string and manual_progress != 0 and self.threshold is not None:
                #use manual progress
                self.override_requirement(manual_progress)
                return
            else:
                #Example: requirement CI-H, we want to show how many have been fulfilled
                whole_courses, half_courses = self.courses_satisfying_req(courses)
                satisfied_courses = whole_courses + half_courses

                if not self.threshold is None:
                    #A specific number of courses is required
                    subject_progress = ceiling_thresh(len(whole_courses) + len(half_courses) // 2, self.threshold.cutoff_for_criterion(CRITERION_SUBJECTS))
                    unit_progress = ceiling_thresh(total_units(satisfied_courses), self.threshold.cutoff_for_criterion(CRITERION_UNITS))
                    is_fulfilled = self.threshold.is_satisfied_by(subject_progress.progress, unit_progress.progress)
                else:
                    #Only one is needed
                    progress_subjects = min(len(satisfied_courses), 1)
                    is_fulfilled = len(satisfied_courses) > 0
                    subject_progress = ceiling_thresh(progress_subjects, 1)

                    if len(satisfied_courses) > 0:
                        unit_progress = ceiling_thresh(list(satisfied_courses)[0].total_units, DEFAULT_UNIT_COUNT)
                    else:
                        unit_progress = ceiling_thresh(0, DEFAULT_UNIT_COUNT)

            progress = unit_progress if self.threshold is not None and self.threshold.criterion == CRITERION_UNITS else subject_progress


        # SECTION 2: Handle compound requirements (the CRITICAL section!)
        if len(self.children) > 0:
            #It's a compound requirement
            num_reqs_satisfied = 0
            satisfied_by_category = []
            satisfied_courses = set()
            num_courses_satisfied = 0

            open_children = []
            for req_progress in self.children:
                req_progress.compute(courses, progress_overrides, progress_assertions)
                req_satisfied_courses = req_progress.satisfied_courses

                # Don't count anything from a requirement that is ignored
                if req_progress.assertion and req_progress.assertion.get("ignore", False):
                    continue
                open_children.append(req_progress)

                if req_progress.is_fulfilled and len(req_progress.satisfied_courses) > 0:
                    num_reqs_satisfied += 1

                satisfied_courses.update(req_satisfied_courses)
                satisfied_by_category.append(list(req_satisfied_courses))

                # ==========================================
                # THE THREE RULES ARE IMPLEMENTED HERE:
                # ==========================================
                # For thresholded ANY statements, children that are ALL statements
                # count as a single satisfied course. ANY children count for
                # all of their satisfied courses.
                if req_progress.statement.connection_type == CONNECTION_TYPE_ALL and req_progress.children:
                    # RULE 2: ALL group without threshold contributes 1 when fulfilled
                    num_courses_satisfied += req_progress.is_fulfilled and len(req_progress.satisfied_courses) > 0
                else:
                    # RULE 1 & 3: Plain courses contribute 1, groups with thresholds contribute their progress
                    num_courses_satisfied += len(req_satisfied_courses)

            satisfied_by_category = [sat for prog, sat in sorted(zip(open_children, satisfied_by_category), key = lambda z: z[0].raw_fraction_fulfilled, reverse = True)]
            sorted_progresses = sorted(open_children, key = lambda req: req.raw_fraction_fulfilled, reverse = True)

            # SECTION 3: Calculate progress based on threshold presence
            if self.threshold is None and self.distinct_threshold is None:
                is_fulfilled = (num_reqs_satisfied > 0)

                if self.statement.connection_type == CONNECTION_TYPE_ANY:
                    #Simple "any" statement
                    if len(sorted_progresses) > 0:
                        subject_progress = sorted_progresses[0].subject_fulfillment
                        unit_progress = sorted_progresses[0].unit_fulfillment
                    else:
                        subject_progress = Progress(0, 0)
                        unit_progress = Progress(0, 0)

                else:
                    #"All" statement, will be finalized later
                    subject_progress = sum_progresses(sorted_progresses, CRITERION_SUBJECTS, None)
                    unit_progress = sum_progresses(sorted_progresses, CRITERION_UNITS, None)

            else:

                if self.distinct_threshold is not None:
                    #Clip the progresses to the ones which the user is closest to completing
                    num_progresses_to_count = min(self.distinct_threshold.get_actual_cutoff(), len(sorted_progresses))
                    sorted_progresses = sorted_progresses[:num_progresses_to_count]
                    satisfied_by_category = satisfied_by_category[:num_progresses_to_count]
                    satisfied_courses = set()
                    num_courses_satisfied = 0

                    for i, child in zip(range(num_progresses_to_count), open_children):
                        satisfied_courses.update(satisfied_by_category[i])
                        if child.statement.connection_type == CONNECTION_TYPE_ALL:
                            num_courses_satisfied += (child.is_fulfilled and len(child.satisfied_courses) > 0)
                        else:
                            num_courses_satisfied += len(satisfied_by_category[i])

                if self.threshold is None and self.distinct_threshold is not None:
                    #Required number of statements
                    if self.distinct_threshold == THRESHOLD_TYPE_GTE or self.distinct_threshold.type == THRESHOLD_TYPE_GT:
                        is_fulfilled = num_reqs_satisfied >= self.distinct_threshold.get_actual_cutoff()
                    else:
                        is_fulfilled = True

                    subject_progress = sum_progresses(sorted_progresses, CRITERION_SUBJECTS, lambda x: max(x, 1))
                    unit_progress = sum_progresses(sorted_progresses, CRITERION_UNITS, lambda x: (x, DEFAULT_UNIT_COUNT)[x == 0])

                elif self.threshold is not None:
                    # ==========================================
                    # THIS IS WHERE num_courses_satisfied IS USED!
                    # ==========================================
                    #Required number of subjects or units
                    subject_progress = Progress(num_courses_satisfied, self.threshold.cutoff_for_criterion(CRITERION_SUBJECTS))
                    unit_progress = Progress(total_units(satisfied_courses), self.threshold.cutoff_for_criterion(CRITERION_UNITS))

                    if self.distinct_threshold is not None and (self.distinct_threshold.type == THRESHOLD_TYPE_GT or self.distinct_threshold.type == THRESHOLD_TYPE_GTE):
                        is_fulfilled = self.threshold.is_satisfied_by(subject_progress.progress, unit_progress.progress) and num_reqs_satisfied >= self.distinct_threshold.get_actual_cutoff()
                        if num_reqs_satisfied < self.distinct_threshold.get_actual_cutoff():
                            (subject_progress, unit_progress) = force_unfill_progresses(satisfied_by_category, self.distinct_threshold, self.threshold)
                    else:
                        is_fulfilled = self.threshold.is_satisfied_by(subject_progress.progress, unit_progress.progress)

            # SECTION 4: Handle ALL connection type special case
            if self.statement.connection_type == CONNECTION_TYPE_ALL:
                #"All" statement - make above progresses more stringent
                is_fulfilled = is_fulfilled and (num_reqs_satisfied == len(open_children))
                if subject_progress.progress == subject_progress.max and len(open_children) > num_reqs_satisfied:
                    subject_progress.max += len(open_children) - num_reqs_satisfied
                    unit_progress.max += (len(open_children) - num_reqs_satisfied) * DEFAULT_UNIT_COUNT
            
            #Polish up values
            subject_progress = ceiling_thresh(subject_progress.progress, subject_progress.max)
            unit_progress = ceiling_thresh(unit_progress.progress, unit_progress.max)
            progress = unit_progress if self.threshold is not None and self.threshold.criterion == CRITERION_UNITS else subject_progress

        # SECTION 5: Set final progress values
        progress_units = CRITERION_SUBJECTS if self.threshold is None else self.threshold.criterion
        self.is_fulfilled = is_fulfilled
        self.subject_fulfillment = subject_progress
        self.subject_progress = subject_progress.progress
        self.subject_max = subject_progress.max
        self.unit_fulfillment = unit_progress
        self.unit_progress = unit_progress.progress
        self.unit_max = unit_progress.max
        self.progress = progress.progress
        self.progress_max = progress.max
        self.percent_fulfilled = progress.get_percent()
        self.fraction_fulfilled = progress.get_fraction()
        self.raw_fraction_fulfilled = progress.get_raw_fraction(progress_units)
        self.satisfied_courses = list(satisfied_courses)
```

#### RequirementsProgress - Compute Assertions (for manual overrides)

```python
    def compute_assertions(self, courses, progress_assertions):
        """
        Computes the fulfillment of this requirement based on progress assertions, and returns
        True if the requirement has an assertion available or False otherwise.

        Assertions are in the format of a dictionary keyed by requirements list paths, where the
        values are dictionaries containing three possible keys: "substitutions", which should be a
        list of course IDs that combine to substitute for the requirement, "ignore", which
        indicates that the requirement is not to be used when satisfying later requirements, and
        "override", which is equivalent to the old manual progress value and indicates a progress
        toward the requirement in the unit specified by the requirement's threshold type (only
        used if the requirement is a plain string requirement and has a threshold). The order of
        precedence is override, ignore, substitutions.
        """
        self.assertion = progress_assertions.get(self.list_path, None)
        self.is_bypassed = False
        if self.assertion is not None:
            substitutions = self.assertion.get("substitutions", None) #List of substitutions
            ignore = self.assertion.get("ignore", False)               #Boolean
            override = self.assertion.get("override", 0)
        else:
            substitutions = None
            ignore = False
            override = 0

        if self.statement.is_plain_string and self.threshold is not None and override:
            self.override_requirement(override)
            return True
        if ignore:
            progress_units = CRITERION_SUBJECTS if self.threshold is None else self.threshold.criterion
            self.is_fulfilled = False
            subject_progress = Progress(0, 0)
            self.subject_fulfillment = subject_progress
            self.subject_progress = subject_progress.progress
            self.subject_max = subject_progress.max
            unit_progress = Progress(0, 0)
            self.unit_fulfillment = unit_progress
            self.unit_progress = unit_progress.progress
            self.unit_max = unit_progress.max
            progress = Progress(0, 0)
            self.progress = progress.progress
            self.progress_max = progress.max
            self.percent_fulfilled = progress.get_percent()
            self.fraction_fulfilled = progress.get_fraction()
            self.raw_fraction_fulfilled = progress.get_raw_fraction(progress_units)
            self.satisfied_courses = []
            return True
        if substitutions is not None:
            satisfied_courses = set()
            subs_satisfied = 0
            units_satisfied = 0
            for sub in substitutions:
                for course in courses:
                    if course.satisfies(sub, courses):
                        subs_satisfied += 1
                        units_satisfied += course.total_units
                        satisfied_courses.add(course)
                        break
            if self.statement.is_plain_string and self.threshold is not None:
                subject_progress = Progress(subs_satisfied,
                                            self.threshold.cutoff_for_criterion(CRITERION_SUBJECTS))
                unit_progress = Progress(units_satisfied,
                                         self.threshold.cutoff_for_criterion(CRITERION_UNITS))
                progress = subject_progress if self.threshold.criterion == CRITERION_SUBJECTS else unit_progress
                self.is_fulfilled = progress.progress == progress.max
            else:
                subject_progress = Progress(subs_satisfied, len(substitutions))
                self.is_fulfilled = subs_satisfied == len(substitutions)
                unit_progress = Progress(subs_satisfied * DEFAULT_UNIT_COUNT, len(substitutions) * DEFAULT_UNIT_COUNT)
                progress = subject_progress
            progress_units = CRITERION_SUBJECTS if self.threshold is None else self.threshold.criterion
            self.subject_fulfillment = subject_progress
            self.subject_progress = subject_progress.progress
            self.subject_max = subject_progress.max
            self.unit_fulfillment = unit_progress
            self.unit_progress = unit_progress.progress
            self.unit_max = unit_progress.max
            self.progress = progress.progress
            self.progress_max = progress.max
            self.percent_fulfilled = progress.get_percent()
            self.fraction_fulfilled = progress.get_fraction()
            self.raw_fraction_fulfilled = progress.get_raw_fraction(progress_units)
            self.satisfied_courses = list(satisfied_courses)
            return True

        return False
```

---

### Test Cases (tests.py)

**File**: `/Users/matt/fireroad-server/requirements/tests.py`

#### Test Parsing

```python
from django.test import TestCase
from .models import *
from .progress import *
from catalog.models import Course

class RequirementsStatementTest(TestCase):

    def test_parse_string_simple(self):
        string = "6.00"
        req = RequirementsStatement.from_string(string)
        self.assertEqual("6.00", req.requirement)
        self.assertFalse(req.requirements.exists())

    def test_parse_string_and(self):
        string = "2.001, 2.002"
        req = RequirementsStatement.from_string(string)
        self.assertEqual(None, req.requirement)
        self.assertEqual(CONNECTION_TYPE_ALL, req.connection_type)
        self.assertEqual(2, req.requirements.count())
        self.assertEqual(set(["2.001", "2.002"]),
                         set([child.requirement for child in req.requirements.all()]))

    def test_parse_string_or(self):
        string = "7.013/21M.284/6.003"
        req = RequirementsStatement.from_string(string)
        self.assertEqual(None, req.requirement)
        self.assertEqual(CONNECTION_TYPE_ANY, req.connection_type)
        self.assertEqual(3, req.requirements.count())
        self.assertEqual(set(["7.013", "21M.284", "6.003"]),
                         set([child.requirement for child in req.requirements.all()]))

    def test_parse_string_threshold(self):
        string = "CMS.01/CMS.02/CMS.03{>=2}"
        req = RequirementsStatement.from_string(string)
        self.assertEqual(None, req.requirement)
        self.assertEqual(CONNECTION_TYPE_ANY, req.connection_type)
        self.assertEqual(THRESHOLD_TYPE_GTE, req.threshold_type)
        self.assertEqual(2, req.threshold_cutoff)
        self.assertEqual(CRITERION_SUBJECTS, req.threshold_criterion)
        self.assertEqual(3, req.requirements.count())
        self.assertEqual(set(["CMS.01", "CMS.02", "CMS.03"]),
                         set([child.requirement for child in req.requirements.all()]))

    def test_parse_string_distinct_threshold(self):
        string = "x/y/z/w{<24u|>=1}"
        req = RequirementsStatement.from_string(string)
        self.assertEqual(None, req.requirement)
        self.assertEqual(CONNECTION_TYPE_ANY, req.connection_type)
        self.assertEqual(THRESHOLD_TYPE_LT, req.threshold_type)
        self.assertEqual(24, req.threshold_cutoff)
        self.assertEqual(CRITERION_UNITS, req.threshold_criterion)
        self.assertEqual(THRESHOLD_TYPE_GTE, req.distinct_threshold_type)
        self.assertEqual(1, req.distinct_threshold_cutoff)
        self.assertEqual(CRITERION_SUBJECTS, req.distinct_threshold_criterion)
        self.assertEqual(4, req.requirements.count())
        self.assertEqual(set("xyzw"),
                         set([child.requirement for child in req.requirements.all()]))

    def test_parse_string_plain_string(self):
        string = '""a requirement""{>36u}'
        req = RequirementsStatement.from_string(string)
        self.assertEqual("a requirement", req.requirement)
        self.assertEqual(True, req.is_plain_string)
        self.assertEqual(CONNECTION_TYPE_NONE, req.connection_type)
        self.assertEqual(THRESHOLD_TYPE_GT, req.threshold_type)
        self.assertEqual(36, req.threshold_cutoff)
        self.assertEqual(CRITERION_UNITS, req.threshold_criterion)
```

#### Test Progress Calculation

```python
class RequirementsProgressTest(TestCase):

    def setUp(self):
        Course.objects.create(subject_id="2.001", title="Foo").save()
        Course.objects.create(subject_id="2.002", title="Bar").save()
        Course.objects.create(subject_id="2.003", title="Foo Bar").save()
        Course.objects.create(subject_id="8.01",
                              title="Physics",
                              gir_attribute="GIR:PHY1").save()
        Course.objects.create(subject_id="21M.030",
                              title="World Music",
                              communication_requirement="CI-H").save()
        Course.objects.create(subject_id="21M.421",
                              title="MITSO",
                              hass_attribute="HASS-A").save()
        Course.objects.create(subject_id="17.55",
                              title="Latin American Studies",
                              communication_requirement="CI-H").save()
        Course.objects.create(subject_id="21L.001",
                              title="Some Literature Subject",
                              communication_requirement="CI-HW").save()
        for course in Course.objects.all():
            course.total_units = 12
            course.public = True
            course.save()

    def assert_basic_progress(self, courses, max_courses, progress):
        """Asserts that the given number of courses and the max number of
        courses are satisfied in the given RequirementsProgress object.
        Assumes each course is 12 units."""
        self.assertEqual(courses, progress.subject_progress)
        self.assertEqual(max_courses, progress.subject_max)
        self.assertEqual(courses * 12, progress.unit_progress)
        self.assertEqual(max_courses * 12, progress.unit_max)
        self.assertEqual(courses, progress.progress)
        self.assertEqual(max_courses, progress.progress_max)
        self.assertEqual(courses / float(max_courses) * 100.0, progress.percent_fulfilled)
        self.assertEqual(courses / float(max_courses), progress.fraction_fulfilled)

    def test_progress_basic_and(self):
        statement = RequirementsStatement.from_string("2.001, 2.003")
        progress = RequirementsProgress(statement, "0")
        courses = [Course.objects.get(subject_id="2.001")]
        progress.compute(courses, {}, {})
        self.assertFalse(progress.is_fulfilled)
        self.assert_basic_progress(1, 2, progress)
        self.assertEqual(courses, progress.satisfied_courses)

        progress = RequirementsProgress(statement, "0")
        courses = [Course.objects.get(subject_id="2.001"),
                   Course.objects.get(subject_id="2.003")]
        progress.compute(courses, {}, {})
        self.assertTrue(progress.is_fulfilled)
        self.assert_basic_progress(2, 2, progress)
        self.assertEqual(courses, progress.satisfied_courses)

    def test_progress_basic_or(self):
        statement = RequirementsStatement.from_string("2.001/2.003")
        progress = RequirementsProgress(statement, "0")
        courses = [Course.objects.get(subject_id="2.001")]
        progress.compute(courses, {}, {})
        self.assertTrue(progress.is_fulfilled)
        self.assert_basic_progress(1, 1, progress)
        self.assertEqual(courses, progress.satisfied_courses)

    def test_progress_or_threshold(self):
        statement = RequirementsStatement.from_string("2.001/2.002/2.003{>=2}")
        progress = RequirementsProgress(statement, "0")
        courses = [Course.objects.get(subject_id="2.001")]
        progress.compute(courses, {}, {})
        self.assertFalse(progress.is_fulfilled)
        self.assert_basic_progress(1, 2, progress)
        self.assertEqual(courses, progress.satisfied_courses)

        progress = RequirementsProgress(statement, "0")
        courses = [Course.objects.get(subject_id="2.001"),
                   Course.objects.get(subject_id="2.002"),
                   Course.objects.get(subject_id="2.003")]
        progress.compute(courses, {}, {})
        self.assertTrue(progress.is_fulfilled)
        self.assert_basic_progress(2, 2, progress)
        self.assertEqual(courses, progress.satisfied_courses)

    def test_progress_manual(self):
        statement = RequirementsStatement.from_string('""2 classes""{>=2}')
        manual = {"0": 1}
        courses = [Course.objects.get(subject_id="21M.421")]
        progress = RequirementsProgress(statement, "0")
        progress.compute(courses, manual, {})
        self.assertFalse(progress.is_fulfilled)
        self.assert_basic_progress(1, 2, progress)

    def test_progress_manual_units(self):
        statement = RequirementsStatement.from_string('""24 units""{>=24u}')
        manual = {"myid": 18}
        courses = [Course.objects.get(subject_id="21M.421")]
        progress = RequirementsProgress(statement, "myid")
        progress.compute(courses, manual, {})
        self.assertFalse(progress.is_fulfilled)
        self.assertEqual(1, progress.subject_progress)
        self.assertEqual(2, progress.subject_max)
        self.assertEqual(18, progress.unit_progress)
        self.assertEqual(24, progress.unit_max)
        self.assertEqual(18, progress.progress)
        self.assertEqual(24, progress.progress_max)
```

---

## Key Algorithms Explained

### Algorithm 1: Child Contribution to Parent Progress

**Location**: `progress.py:280-288`

```python
# For thresholded ANY statements, children that are ALL statements
# count as a single satisfied course. ANY children count for
# all of their satisfied courses.
if req_progress.statement.connection_type == CONNECTION_TYPE_ALL and req_progress.children:
    # ALL group without threshold → contributes 1 if fulfilled
    num_courses_satisfied += req_progress.is_fulfilled and len(req_progress.satisfied_courses) > 0
else:
    # Plain course or group with threshold → contributes count of satisfied courses
    num_courses_satisfied += len(req_satisfied_courses)
```

**Logic Flow**:

1. Check if child is an ALL group with children (not a plain course)
2. If YES: Add 1 if the group is fulfilled and has satisfied courses (boolean evaluates to 0 or 1)
3. If NO: Add the count of satisfied courses in that child

**Why this works**:
- Plain courses have no children, so they go to else branch and add `len([course])` = 1
- ALL groups without thresholds have `connection_type='all'`, so they add 1 when fulfilled
- Groups with thresholds typically have `connection_type='any'`, so they add their satisfied course count

### Algorithm 2: Connection Type Determination During Parsing

**Location**: `reqlist.py:651-655`

```python
components, connection_type = self.separate_top_level_items(filtered_statement)

# CRITICAL: This sets connection_type='any' for thresholds with cutoff=0
if self.threshold_type is not None and self.threshold_cutoff == 0 and self.threshold_type == THRESHOLD_TYPE_GTE:
    self.connection_type = CONNECTION_TYPE_ANY
else:
    self.connection_type = connection_type
```

**Why this matters**:
- Requirements like `"A/B/C{>=2}"` get parsed as `connection_type='any'` (from the `/` separator)
- Requirements like `"(A,B), (C,D){>=1}"` get parsed as `connection_type='all'` (from the `,` separator) UNLESS they have a threshold, which would make them ANY
- This determines which branch of the contribution logic they fall into

### Algorithm 3: Distinct Threshold Handling

**Location**: `progress.py:290-301`

```python
if self.distinct_threshold is not None:
    # Clip the progresses to the ones which the user is closest to completing
    num_progresses_to_count = min(self.distinct_threshold.get_actual_cutoff(), len(sorted_progresses))
    sorted_progresses = sorted_progresses[:num_progresses_to_count]
    satisfied_by_category = satisfied_by_category[:num_progresses_to_count]
    satisfied_courses = set()
    num_courses_satisfied = 0

    for i, child in zip(range(num_progresses_to_count), open_children):
        satisfied_courses.update(satisfied_by_category[i])
        if child.statement.connection_type == CONNECTION_TYPE_ALL:
            num_courses_satisfied += (child.is_fulfilled and len(child.satisfied_courses) > 0)
        else:
            num_courses_satisfied += len(satisfied_by_category[i])
```

**Process**:
1. Sort children by `raw_fraction_fulfilled` (descending)
2. Take only the top N categories (where N = distinct threshold cutoff)
3. Recalculate `num_courses_satisfied` using only those categories
4. Apply the same three-rule logic within those categories

### Algorithm 4: Final Progress Selection (Units vs Subjects)

**Location**: `progress.py:303-308, 330`

```python
# Always calculate both
subject_progress = Progress(num_courses_satisfied, self.threshold.cutoff_for_criterion(CRITERION_SUBJECTS))
unit_progress = Progress(total_units(satisfied_courses), self.threshold.cutoff_for_criterion(CRITERION_UNITS))

# Select which one to use based on criterion
progress = unit_progress if self.threshold is not None and self.threshold.criterion == CRITERION_UNITS else subject_progress
```

**Key Points**:
- **Both** subject_progress and unit_progress are always calculated
- `subject_progress` uses `num_courses_satisfied` (follows the three rules)
- `unit_progress` uses `total_units(satisfied_courses)` (simple sum)
- The `threshold.criterion` field determines which becomes the final `progress`

---

## Implementation Guide

### Pseudocode for Optimizer

```python
def calculate_child_contribution(child_req, satisfied_courses_in_child, is_child_fulfilled):
    """
    Returns how much this child contributes to parent's subject progress.
    This implements the THREE CORE RULES.
    """
    # Check if child has nested children (is a group)
    if child_req.has_children():
        # Check if it's an ALL group (and therefore without threshold)
        if child_req.connection_type == 'all':
            # RULE 2: ALL group → contributes 1 when fulfilled
            if is_child_fulfilled and len(satisfied_courses_in_child) > 0:
                return 1
            else:
                return 0
        else:
            # RULE 3: Group with threshold (connection_type='any') → contributes progress
            return len(satisfied_courses_in_child)
    else:
        # RULE 1: Plain course → contributes 1 if satisfied
        return len(satisfied_courses_in_child)  # 0 or 1


def calculate_parent_progress(parent_req, children_data, threshold):
    """
    Calculates progress for a parent requirement with threshold.
    
    Args:
        parent_req: Parent requirement object
        children_data: List of (child_req, satisfied_courses, is_fulfilled) tuples
        threshold: Threshold object
    """
    num_courses_satisfied = 0
    all_satisfied_courses = set()
    num_reqs_satisfied = 0
    
    # Process each child
    for child_req, satisfied_courses, is_fulfilled in children_data:
        # Skip ignored requirements
        if child_req.is_ignored():
            continue
        
        # Count fulfilled children (for distinct thresholds)
        if is_fulfilled and len(satisfied_courses) > 0:
            num_reqs_satisfied += 1
        
        # Accumulate all satisfied courses
        all_satisfied_courses.update(satisfied_courses)
        
        # Calculate contribution using the three rules
        contribution = calculate_child_contribution(
            child_req, 
            satisfied_courses, 
            is_fulfilled
        )
        num_courses_satisfied += contribution
    
    # Calculate progress based on criterion
    if threshold.criterion == 'subjects':
        progress = num_courses_satisfied
        max_needed = threshold.cutoff
    else:  # 'units'
        progress = sum(course.total_units for course in all_satisfied_courses)
        max_needed = threshold.cutoff
    
    # Check if threshold is satisfied
    is_fulfilled = threshold.is_satisfied_by(
        subject_progress=num_courses_satisfied,
        unit_progress=sum(course.total_units for course in all_satisfied_courses)
    )
    
    return (progress, max_needed, is_fulfilled)
```

### Helper Functions You'll Need

```python
def has_children(req):
    """Check if requirement has nested children (is a group)."""
    return len(req.requirements) > 0 or req.requirements.exists()

def has_threshold(req):
    """Check if requirement has a threshold defined."""
    return req.threshold_type is not None

def is_ignored(req):
    """Check if requirement is marked as ignored."""
    return (req.assertion is not None and 
            req.assertion.get("ignore", False))

def get_connection_type(req):
    """Get the connection type ('all', 'any', or 'none')."""
    return req.connection_type
```

### Constants You'll Need

```python
CONNECTION_TYPE_ALL = "all"
CONNECTION_TYPE_ANY = "any"
CONNECTION_TYPE_NONE = "none"

THRESHOLD_TYPE_LT = "LT"
THRESHOLD_TYPE_LTE = "LTE"
THRESHOLD_TYPE_GT = "GT"
THRESHOLD_TYPE_GTE = "GTE"

CRITERION_SUBJECTS = "subjects"
CRITERION_UNITS = "units"

DEFAULT_UNIT_COUNT = 12
```

---

## File Reference Map

### Complete File Paths

1. **Data Structures & Parsing**
   - `/Users/matt/fireroad-server/requirements/reqlist.py` (682 lines)
     - Lines 1-17: Constants
     - Lines 51-89: Threshold class
     - Lines 91-143: SyntaxConstants and JSONConstants
     - Lines 145-196: RequirementsStatement model fields
     - Lines 198-261: threshold_description() method
     - Lines 544-606: Parsing methods
     - Lines 608-655: parse_string() method

2. **Progress Calculation**
   - `/Users/matt/fireroad-server/requirements/progress.py` (425 lines)
     - Lines 1-10: ceiling_thresh() helper
     - Lines 12-18: total_units() helper
     - Lines 20-30: sum_progresses() helper
     - Lines 32-69: force_unfill_progresses() for distinct thresholds
     - Lines 104-138: Progress class
     - Lines 185-330: RequirementsProgress.compute() **[MOST CRITICAL]**
     - Lines 280-288: **The three-rule logic** for child contributions
     - Lines 303-308: Final progress calculation with threshold

3. **Tests**
   - `/Users/matt/fireroad-server/requirements/tests.py` (144 lines)
     - Lines 7-60: Parsing tests
     - Lines 62-144: Progress calculation tests

4. **Models**
   - `/Users/matt/fireroad-server/requirements/models.py` (186 lines)
     - Lines 1-125: RequirementsList class (extends RequirementsStatement)

5. **Editor/UI**
   - `/Users/matt/fireroad-server/requirements/editor.py` (374 lines)
     - Lines 180-185: Uses connection_type in rendering logic

### Key Line Numbers Reference

| Function/Logic | File | Lines |
|----------------|------|-------|
| **Three-rule child contribution logic** | progress.py | 280-288 |
| Progress calculation with threshold | progress.py | 303-308 |
| Final progress selection (units vs subjects) | progress.py | 330 |
| Distinct threshold handling | progress.py | 290-301 |
| ALL connection type adjustment | progress.py | 323-326 |
| Threshold class definition | reqlist.py | 51-89 |
| Connection type constants | reqlist.py | 5-7 |
| Criterion constants | reqlist.py | 13-14 |
| parse_modifier() - parses {>=2} syntax | reqlist.py | 573-595 |
| parse_string() - determines connection_type | reqlist.py | 597-655 |
| threshold_description() - generates user-facing text | reqlist.py | 198-261 |
| RequirementsStatement model fields | reqlist.py | 145-196 |

---

## Summary

This document contains **all source code** related to how Fireroad handles thresholds, connection types, and criteria. The most critical section is `/Users/matt/fireroad-server/requirements/progress.py:280-288`, which implements the three core rules:

```python
if req_progress.statement.connection_type == CONNECTION_TYPE_ALL and req_progress.children:
    num_courses_satisfied += req_progress.is_fulfilled and len(req_progress.satisfied_courses) > 0
else:
    num_courses_satisfied += len(req_satisfied_courses)
```

This single conditional captures the entire logic:
1. **Plain courses** (no children) → else branch → contribute 1
2. **ALL groups without threshold** → if branch → contribute 1 when fulfilled
3. **Groups with threshold** (typically ANY) → else branch → contribute their progress

**Document Version**: 2.0 (Complete Code Edition)  
**Analysis Date**: 2025-11-24  
**Codebase**: fireroad-server (commit: be03dbf)
