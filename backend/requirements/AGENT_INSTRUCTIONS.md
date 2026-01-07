# Agent Instructions: Resolving Vague Requirements

## Overview

MIT degree requirements sometimes contain vague requirements like "48-60 units of engineering electives" or "2 math subjects (first decimal >= 1)". These are represented in Fireroad as `plain-string: true` nodes, meaning the system cannot automatically validate them.

Your task is to convert these vague requirements into concrete course lists that the optimizer can work with.

## APIs Available

### 1. Fireroad Course Search API
Search for courses by department, keyword, or attributes:

```bash
# Search by keyword
curl "https://fireroad.mit.edu/courses/search/physics"

# Get all courses in a department (e.g., Course 18 = Math)
curl "https://fireroad.mit.edu/courses/dept/18"

# Get specific course details
curl "https://fireroad.mit.edu/courses/lookup/18.06"
```

Response includes: `subject_id`, `title`, `total_units`, `offered_fall`, `offered_spring`, `level`, `gir_attribute`, `hass_attribute`, etc.

### 2. MIT Course Catalog
The official source of truth for degree requirements:
- Degree charts: `https://catalog.mit.edu/degree-charts/`
- Department pages: `https://catalog.mit.edu/schools/[school]/[department]/`
- Example: `https://catalog.mit.edu/degree-charts/mathematics-course-18/`

### 3. Local Backend API
Our backend proxies Fireroad and adds local beta files:

```bash
# List all requirements
curl "http://localhost:8000/api/requirements/list"

# Get parsed requirement tree (shows plain-string nodes)
curl "http://localhost:8000/api/requirements/get/major18pm"

# Get course data (our cached course catalog)
curl "http://localhost:8000/api/courses"
```


## Fireroad File Format

### Header Line
First line contains metadata separated by `#,#`:
```
SHORT#,#MEDIUM#,#TITLE-NO-DEGREE#,#FULL-TITLE
```
Example:
```
18#,#18 Major (Pure)#,#Pure Mathematics#,#Bachelor of Science in Mathematics (Pure Mathematics Option)
```

### Description
Optional paragraph(s) describing the major.

### Structure Section
List requirement group names (references defined below):
```
required_subjects
restricted_electives
communication
```

### Definition Section
Define each requirement group:
```
name, "Display Title" := COURSE_LIST{THRESHOLD}
```

#### Course List Syntax
- Single course: `18.06`
- Alternatives (OR): `18.06/18.C06` - student picks one
- Required together (AND): `6.100A, 6.100B` - student must take both
- Nested groups: `(6.100A/6.100B), 18.06`
- Reference another group: `group_name`

#### Threshold Syntax
- `{>=3}` - at least 3 courses from the list
- `{>=48u}` - at least 48 units from the list
- `{>=2|>=1}` - complex threshold (2 from first part, 1 from second)
- No threshold = must complete all items

#### Plain-String (Vague) Requirement
```
elect_eng, "Engineering Electives" := ""48-60 units""{>=48u}
```
The `""double-quoted""` text indicates a plain-string that cannot be validated.

### Comments
Lines starting with `%%` are comments:
```
%% This section defines the core requirements
```

## Research Process

1. **Fetch the current requirement** to understand the structure:
   ```bash
   curl "http://localhost:8000/api/requirements/get/major8" | jq '.'
   ```

2. **Find plain-string nodes** that need resolution:
   ```bash
   curl -s "http://localhost:8000/api/requirements/get/major8" | \
     jq '.. | objects | select(.["plain-string"] == true)'
   ```

3. **Research the official requirements**:
   - Check MIT catalog degree charts
   - Look for departmental approved course lists
   - Search for specific guidance on what satisfies the requirement

4. **Get course lists from Fireroad**:
   ```bash
   # Get all Course 18 subjects
   curl -s "https://fireroad.mit.edu/courses/dept/18" | jq '.[].subject_id'
   
   # Filter by level or other attributes
   curl -s "https://fireroad.mit.edu/courses/dept/18" | \
     jq '[.[] | select(.total_units >= 12)] | .[].subject_id'
   ```

5. **Verify courses exist and are offered**:
   ```bash
   curl -s "https://fireroad.mit.edu/courses/lookup/18.100A" | \
     jq '{id: .subject_id, units: .total_units, fall: .offered_fall, spring: .offered_spring}'
   ```

## Common Patterns to Resolve

### "N subjects from Course X"
```bash
# Get all courses from department
curl -s "https://fireroad.mit.edu/courses/dept/18" | jq -r '.[].subject_id' | sort
```
Then filter to appropriate level (intro, intermediate, advanced).

### "N units of electives"
List all valid elective courses, then apply unit threshold:
```
electives := 15.301/15.310/15.311/15.401/15.402/...{>=48u}
```

### "Math subjects (first decimal >= 1)"
This means 18.1xx and above (not 18.0xx intro courses):
```bash
curl -s "https://fireroad.mit.edu/courses/dept/18" | \
  jq -r '[.[] | select(.subject_id | test("^18\\.[1-9]"))] | .[].subject_id'
```

### "Subjects beyond X"
Find courses that are more advanced than the named course. Usually means:
- Higher course numbers in the same department
- Courses that list X as a prerequisite

### "Lab subjects"
Check course descriptions or look for courses with lab_units > 0:
```bash
curl -s "https://fireroad.mit.edu/courses/dept/8" | \
  jq '[.[] | select(.lab_units > 0)] | .[].subject_id'
```

## Output Format

Create or modify a `.fireroad` file in `backend/requirements/`. 

Example transformation:

**Before (from Fireroad):**
```json
{
  "plain-string": true,
  "req": "2 math subjects (first decimal ≥ 1)",
  "threshold": {"cutoff": 2, "criterion": "subjects", "type": "GTE"}
}
```

**After (in .fireroad file):**
```
math_electives, "Math Electives" := 18.100A/18.100B/18.100P/18.100Q/18.101/18.102/18.103/18.104/18.112/18.152/18.200/18.211/18.212/18.300/18.303/18.330/18.353/18.384/18.400/18.404/18.410/18.424/18.434/18.504/18.600/18.642/18.650/18.676/18.700/18.701/18.702/18.703/18.704/18.705/18.715/18.721/18.725/18.745/18.755/18.781/18.782/18.783/18.784/18.785/18.786/18.821/18.900/18.901/18.904/18.905/18.906/18.950/18.965/18.994{>=2}
```

## Workflow

1. **Download the requirement**: If not already local, fetch from Fireroad and save
2. **Identify plain-string nodes**: Find all vague requirements
3. **Research each one**: Use APIs and MIT catalog
4. **Build course lists**: Comprehensive but accurate
5. **Update the .fireroad file**: Replace vague requirements with concrete lists
6. **Validate**: Ensure the file parses correctly

## Validation

After generating the course list:

1. Verify each course exists: `curl "https://fireroad.mit.edu/courses/lookup/COURSE_ID"`
2. Check courses are currently offered (not historical)
3. Ensure the list is comprehensive enough for real student choices
4. Preserve the original threshold from the requirement
5. Test the file parses: restart backend and check for errors

## Notes

- Preserve the original requirement name and title
- Keep any existing threshold modifiers
- Use `/` for alternatives within a logical group
- When in doubt, include more courses - the optimizer will pick optimal ones
- Add a comment (`%%`) if the course list source is non-obvious
- Historical courses (is_historical: true) should generally be excluded
