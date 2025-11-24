# Plan: AI-Generated Beta Requirements System

## Overview
Enable LLM-based expansion of plain string requirements into concrete course lists, creating "beta" versions that can be validated by the optimizer while maintaining the original canonical requirements.

**Critical Requirement**: This system MUST use an agentic framework (like Claude Agent SDK, LangChain Agents, or AutoGPT) with robust tool-calling capabilities. Simple prompt-based approaches will fail due to the complexity of requirement interpretation and course catalog navigation.

---

## 1. Architecture

### 1.1 Data Flow
```
Plain String Requirement (Fireroad)
        ↓
AI Agent (with Fireroad API + Course Catalog access)
        ↓
Agent uses tools to search, filter, validate courses
        ↓
Expanded Requirement Tree (beta version)
        ↓
Saved as Custom Requirement File
        ↓
Frontend: User can toggle between canonical & beta
        ↓
Optimizer uses beta version for validation
```

### 1.2 Why Agentic Framework is Required

**Simple LLM approach fails because:**
1. Course catalog has ~2,000 courses - can't fit in context
2. Requirements reference complex filters ("first decimal ≥ 1", "restricted electives")
3. Need iterative refinement: search → filter → validate → adjust
4. Must handle ambiguity through multi-step reasoning
5. Edge cases require fallback strategies and error recovery

**Agentic approach succeeds because:**
- Agent can make multiple tool calls to narrow down courses
- Can validate intermediate results before finalizing
- Can handle unexpected cases through reasoning
- Can ask clarifying questions or make conservative assumptions
- Built-in error handling and retry logic

### 1.3 Recommended Frameworks

**Option 1: Claude Agent SDK (Recommended)**
- Pros: Built on Claude Sonnet 4, excellent reasoning, native tool use
- Cons: Requires Python, relatively new SDK
- Best for: Complex multi-step reasoning, ambiguous requirements

**Option 2: LangChain Agents**
- Pros: Mature ecosystem, many integrations, well-documented
- Cons: Can be verbose, sometimes over-engineered
- Best for: If already using LangChain, need extensive tooling

**Option 3: Custom Agentic Loop**
- Pros: Full control, minimal dependencies
- Cons: Need to implement retry logic, error handling, memory
- Best for: Simple cases, want maximum control

**Recommendation**: Start with **Claude Agent SDK** for best reasoning + tool use.

---

## 2. Agent Design

### 2.1 Agent Architecture
```python
from anthropic import Anthropic

class RequirementExpansionAgent:
    """
    Agentic system for expanding plain-string requirements
    into concrete course lists.
    """
    
    def __init__(self):
        self.client = Anthropic()
        self.tools = [
            search_courses_tool,
            filter_by_pattern_tool,
            get_courses_by_attribute_tool,
            validate_course_exists_tool,
            get_prerequisite_chain_tool,
        ]
        self.conversation_history = []
        
    async def expand_requirement(
        self, 
        plain_string: str,
        context: dict,
        max_iterations: int = 10
    ) -> RequirementTree:
        """
        Main agentic loop:
        1. Agent analyzes plain string
        2. Agent uses tools to find matching courses
        3. Agent validates and refines results
        4. Agent generates final requirement tree
        """
        
        system_prompt = self._build_system_prompt(context)
        user_message = self._build_initial_message(plain_string, context)
        
        for iteration in range(max_iterations):
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                tools=self.tools,
                system=system_prompt,
                messages=self.conversation_history + [user_message]
            )
            
            # Agent might use tools (search, filter, etc.)
            if response.stop_reason == "tool_use":
                tool_results = await self._execute_tools(response.content)
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content
                })
                self.conversation_history.append({
                    "role": "user", 
                    "content": tool_results
                })
                continue
            
            # Agent finished reasoning, return result
            if response.stop_reason == "end_turn":
                return self._parse_final_output(response.content)
        
        raise Exception("Agent exceeded max iterations")
```

### 2.2 System Prompt Design

```
You are an expert at interpreting MIT degree requirements and expanding 
them into concrete course lists.

Your task: Given a plain-string requirement, use the available tools to 
find ALL courses that satisfy the requirement, then output a structured 
requirement tree.

Available Tools:
1. search_courses(query, filters) - Search course catalog
2. filter_by_pattern(pattern) - Filter by subject ID pattern
3. get_courses_by_attribute(attr, value) - Get courses with specific attributes
4. validate_course(course_id) - Check if course exists
5. get_prerequisites(course_id) - Get prerequisite chain

Reasoning Process:
1. Parse the plain string to identify:
   - Subject area (e.g., "math subjects")
   - Filters (e.g., "first decimal ≥ 1")
   - Constraints (e.g., "under faculty supervision")
   - Threshold (e.g., "2 subjects", "72 units")

2. Use tools to find matching courses:
   - Start broad: search_courses("math")
   - Narrow down: filter_by_pattern("18.[1-9]*")
   - Validate: Check each course still exists

3. Handle ambiguity conservatively:
   - If unclear, include course (false positive better than false negative)
   - Add notes about assumptions made
   - Mark low-confidence expansions

4. Generate output in Fireroad format:
   - req_id: unique identifier
   - title: human-readable description
   - connection_type: "any" (student chooses) or "all" (must take all)
   - threshold: how many courses/units required
   - items: list of course IDs or nested groups

Example:

Input: "2 math subjects (first decimal ≥ 1)"
Context: Part of Course 6-3 Bachelor's requirements

Reasoning:
1. "math subjects" → Department 18 (Mathematics)
2. "first decimal ≥ 1" → Subject ID pattern 18.[1-9]* 
   (excludes 18.01, 18.02, etc. which are 18.0x)
3. "2 subjects" → threshold of 2, criterion "subjects", type "GTE"

Tool Calls:
search_courses("", {"department": "18"}) 
→ Returns ~200 math courses

filter_by_pattern("18.[1-9]*")
→ Narrows to ~150 courses (excludes 18.0x intro courses)

Output:
{
  "req_id": "course_6_3_math_electives",
  "title": "Math Electives (First Decimal ≥ 1)",
  "connection_type": "any",
  "threshold": {
    "cutoff": 2,
    "criterion": "subjects",
    "type": "GTE"
  },
  "items": [
    {"req": "18.100A"},
    {"req": "18.100B"},
    {"req": "18.100Q"},
    ... (all 18.1xx, 18.2xx, etc. courses)
  ]
}
```

### 2.3 Tool Implementations

**Tool 1: `search_courses`**
```python
{
  "name": "search_courses",
  "description": "Search MIT course catalog by query and filters",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Search query (course title, keywords, or empty for all)"
      },
      "filters": {
        "type": "object",
        "properties": {
          "department": {"type": "string"},
          "level": {"type": "string", "enum": ["undergrad", "grad"]},
          "gir_attribute": {"type": "string"},
          "hass_attribute": {"type": "string"},
          "offered_fall": {"type": "boolean"},
          "offered_spring": {"type": "boolean"}
        }
      }
    },
    "required": ["query"]
  }
}

async def execute_search_courses(query: str, filters: dict) -> list:
    # Proxy to Fireroad API
    response = await fetch(
        f"https://fireroad.mit.edu/courses/search/{query}",
        params=filters
    )
    return response.json()["courses"]
```

**Tool 2: `filter_by_pattern`**
```python
{
  "name": "filter_by_pattern",
  "description": "Filter courses by subject ID pattern (regex)",
  "input_schema": {
    "type": "object",
    "properties": {
      "pattern": {
        "type": "string",
        "description": "Regex pattern for subject IDs (e.g., '18.[1-9].*' for 18.1xx and higher)"
      }
    },
    "required": ["pattern"]
  }
}

async def execute_filter_by_pattern(pattern: str) -> list:
    # Get all courses, filter by regex
    all_courses = await get_all_courses()
    regex = re.compile(pattern)
    return [c for c in all_courses if regex.match(c["subject_id"])]
```

**Tool 3: `get_courses_by_attribute`**
```python
{
  "name": "get_courses_by_attribute",
  "description": "Get all courses with a specific attribute value",
  "input_schema": {
    "type": "object",
    "properties": {
      "attribute": {
        "type": "string",
        "enum": ["gir_attribute", "hass_attribute", "communication_requirement"]
      },
      "value": {
        "type": "string",
        "description": "Attribute value (e.g., 'REST', 'HASS-A', 'CI-H')"
      }
    },
    "required": ["attribute", "value"]
  }
}
```

**Tool 4: `validate_course_exists`**
```python
{
  "name": "validate_course_exists",
  "description": "Check if a course ID exists in the current catalog",
  "input_schema": {
    "type": "object",
    "properties": {
      "course_id": {"type": "string"}
    },
    "required": ["course_id"]
  }
}
```

**Tool 5: `get_prerequisite_chain`**
```python
{
  "name": "get_prerequisite_chain",
  "description": "Get the full prerequisite tree for a course",
  "input_schema": {
    "type": "object",
    "properties": {
      "course_id": {"type": "string"}
    },
    "required": ["course_id"]
  }
}

# Useful for requirements like "advanced courses" - agent can filter
# courses that have prerequisites vs intro courses
```

---

## 3. Example Agent Execution Traces

### Example 1: Math Electives

**Input**: `"2 math subjects (first decimal ≥ 1)"`

**Agent Trace**:
```
[Agent] Analyzing requirement: "2 math subjects (first decimal ≥ 1)"

[Agent → Tool] search_courses(query="", filters={"department": "18"})
[Tool → Agent] Found 203 courses in department 18

[Agent] Now need to filter by "first decimal ≥ 1"
[Agent] This means subject ID like 18.Xxx where X ≥ 1
[Agent] Pattern: 18\.[1-9]

[Agent → Tool] filter_by_pattern(pattern="18\\.[1-9]")
[Tool → Agent] Found 157 courses matching pattern

[Agent] Validating sample courses...
[Agent → Tool] validate_course_exists("18.100A")
[Tool → Agent] ✓ Exists

[Agent → Tool] validate_course_exists("18.102")
[Tool → Agent] ✓ Exists

[Agent] Generating final requirement tree with 157 courses
[Agent] Threshold: 2 subjects, type GTE (at least 2)

[Agent → Output]
{
  "req_id": "math_electives_first_decimal_gte_1",
  "title": "Math Electives (18.1XX and higher)",
  "connection_type": "any",
  "threshold": {"cutoff": 2, "criterion": "subjects", "type": "GTE"},
  "items": [
    {"req": "18.100A"}, {"req": "18.100B"}, ...
  ]
}
```

### Example 2: Engineering Content Electives

**Input**: `"48-60 units Elective Subjects with Engineering Content"`

**Agent Trace**:
```
[Agent] Analyzing: "48-60 units Elective Subjects with Engineering Content"

[Agent] Key components:
- Threshold: 48-60 units (range)
- Type: Electives (student choice)
- Constraint: "Engineering Content" - ambiguous

[Agent] Need to interpret "Engineering Content"
[Agent] This likely means Course 1-16 (engineering departments)

[Agent → Tool] search_courses(query="", filters={"department": "1"})
[Tool → Agent] 87 courses in Civil & Environmental Engineering

[Agent → Tool] search_courses(query="", filters={"department": "2"})
[Tool → Agent] 124 courses in Mechanical Engineering

[Agent] This will be a long list. Instead, use pattern matching.

[Agent → Tool] filter_by_pattern(pattern="^(1|2|3|4|5|6|7|8|9|10|11|12|13|14|15|16)\\.")
[Tool → Agent] Found 1,243 courses in engineering departments

[Agent] Problem: Some of these are required courses, not electives.
[Agent] Conservative approach: Include all, let degree requirements handle exclusions

[Agent] Note: "Engineering Content" is somewhat ambiguous.
[Agent] Assumption: All courses in departments 1-16 count.

[Agent → Output]
{
  "req_id": "engineering_electives_48_60_units",
  "title": "Elective Subjects with Engineering Content",
  "connection_type": "any",
  "threshold": {"cutoff": 48, "criterion": "units", "type": "GTE"},
  "notes": "Assumed 'Engineering Content' = Departments 1-16. May need manual review.",
  "confidence": 0.7,
  "items": [
    {"req": "1.001"}, {"req": "1.002"}, ... (all 1,243 courses)
  ]
}
```

### Example 3: HASS Requirement

**Input**: `"8 HASS subjects"`

**Agent Trace**:
```
[Agent] Analyzing: "8 HASS subjects"

[Agent] This is straightforward - need all courses with HASS attributes

[Agent → Tool] get_courses_by_attribute(attribute="hass_attribute", value="HASS-A")
[Tool → Agent] 143 courses with HASS-A

[Agent → Tool] get_courses_by_attribute(attribute="hass_attribute", value="HASS-H")
[Tool → Agent] 89 courses with HASS-H

[Agent → Tool] get_courses_by_attribute(attribute="hass_attribute", value="HASS-S")
[Tool → Agent] 127 courses with HASS-S

[Agent → Tool] get_courses_by_attribute(attribute="hass_attribute", value="HASS-E")
[Tool → Agent] 31 courses with HASS-E

[Agent] Total: 390 courses across 4 HASS categories

[Agent → Output]
{
  "req_id": "hass_requirement",
  "title": "HASS Requirement",
  "connection_type": "any",
  "threshold": {"cutoff": 8, "criterion": "subjects", "type": "GTE"},
  "items": [
    {
      "title": "HASS-A (Arts)",
      "connection_type": "any",
      "items": [{"req": "21M.011"}, {"req": "21M.051"}, ...]
    },
    {
      "title": "HASS-H (Humanities)",
      "connection_type": "any",
      "items": [{"req": "21H.001"}, {"req": "21H.105"}, ...]
    },
    ...
  ]
}
```

---

## 4. Implementation Phases

### Phase 1: Agent POC (1 week)
- [ ] Set up Claude Agent SDK environment
- [ ] Implement 5 core tools (search, filter, attribute, validate, prereqs)
- [ ] Write system prompt with reasoning instructions
- [ ] Test agent on 5 representative plain strings:
  - "2 math subjects (first decimal ≥ 1)"
  - "72 units of electives"
  - "Engineering Content under faculty supervision"
  - "One subject from list X or Y"
  - "Advanced HASS subjects"
- [ ] Manually review outputs for accuracy
- [ ] Measure: How many tool calls? How long? Cost per expansion?

**Success Criteria**:
- Agent successfully expands 4/5 requirements
- Outputs are valid Fireroad format
- No hallucinated courses
- Reasoning is transparent and auditable

### Phase 2: Backend Service (1 week)
- [ ] Create FastAPI endpoint: `POST /api/requirements/expand`
  - Input: `{ requirement_key, plain_string, context, max_iterations }`
  - Output: `{ expanded_tree, confidence, agent_trace, cost }`
- [ ] Add agent execution wrapper with error handling
- [ ] Add rate limiting (1 request/minute to prevent API abuse)
- [ ] Add caching (same plain string → cached expansion)
- [ ] Add monitoring: track agent iterations, tool calls, costs
- [ ] Save agent traces for debugging

**API Example**:
```bash
curl -X POST /api/requirements/expand \
  -H "Content-Type: application/json" \
  -d '{
    "requirement_key": "course_6_3",
    "plain_string": "2 math subjects (first decimal ≥ 1)",
    "context": {
      "major": "Course 6-3",
      "level": "Bachelor"
    }
  }'

# Response:
{
  "expanded_tree": { ... },
  "confidence": 0.95,
  "agent_trace": [
    {"step": 1, "action": "search_courses", "result": "203 courses"},
    {"step": 2, "action": "filter_by_pattern", "result": "157 courses"},
    ...
  ],
  "cost_usd": 0.12,
  "execution_time_seconds": 8.3
}
```

### Phase 3: Frontend Integration (1 week)
- [ ] Add "Generate Beta" button to requirement cards (admin mode?)
- [ ] Show modal with agent progress (real-time tool calls)
- [ ] Display agent reasoning trace for transparency
- [ ] Preview expanded requirement before saving
- [ ] Allow manual editing of AI-generated output
- [ ] Save to `/frontend/requirements/beta/` with metadata
- [ ] Automatically mark as `source=beta` in UI

**UI Mockup**:
```
┌────────────────────────────────────────────┐
│ Course 6-3: Math Electives                 │
│ ⚠️  Contains plain string requirement      │
│                                            │
│ "2 math subjects (first decimal ≥ 1)"     │
│                                            │
│ [Generate Beta Version with AI] 🤖         │
└────────────────────────────────────────────┘

(Click button)

┌────────────────────────────────────────────┐
│ 🤖 AI Agent is expanding requirement...    │
│                                            │
│ ✓ Step 1: Searched math courses (203)     │
│ ✓ Step 2: Filtered by pattern (157)       │
│ ⏳ Step 3: Validating courses...          │
│                                            │
│ [View Detailed Trace]                      │
└────────────────────────────────────────────┘

(Finished)

┌────────────────────────────────────────────┐
│ ✅ Beta requirement generated!             │
│                                            │
│ Found 157 courses matching:                │
│ 18.100A, 18.100B, 18.100Q, 18.101, ...     │
│                                            │
│ Confidence: 95%                            │
│ Cost: $0.12                                │
│                                            │
│ [Preview] [Edit] [Save] [Discard]          │
└────────────────────────────────────────────┘
```

### Phase 4: Batch Processing (1 week)
- [ ] Script to analyze ALL Fireroad requirements
- [ ] Identify plain strings with thresholds (use PLAIN_STRING_REQUIREMENTS_ANALYSIS.md)
- [ ] Prioritize by major popularity (Course 6, 8, 18 first)
- [ ] Queue 211 expansion jobs with rate limiting
- [ ] Run overnight batch job (parallelize where possible)
- [ ] Generate report:
  - Success rate (# expanded / # attempted)
  - Failed expansions (with error messages)
  - Low-confidence expansions (< 0.8)
  - Manual review needed
- [ ] Save all agent traces for debugging

**Batch Script**:
```python
async def batch_expand_requirements():
    plain_strings = load_plain_string_requirements()  # 211 total
    
    results = {
        "success": [],
        "failed": [],
        "low_confidence": [],
    }
    
    for req in tqdm(plain_strings):
        try:
            result = await agent.expand_requirement(
                plain_string=req.description,
                context={"major": req.major, "level": req.level}
            )
            
            if result.confidence < 0.8:
                results["low_confidence"].append(result)
            else:
                results["success"].append(result)
                
            # Save to beta/ directory
            save_beta_requirement(result)
            
            # Rate limit
            await asyncio.sleep(1)
            
        except Exception as e:
            results["failed"].append({"requirement": req, "error": str(e)})
    
    generate_report(results)
```

### Phase 5: Review & Quality Assurance (Ongoing)
- [ ] Build review dashboard for AI-generated requirements
- [ ] Show side-by-side: original plain string vs expanded courses
- [ ] Allow marking as "approved", "needs_revision", "rejected"
- [ ] Track coverage: which majors have complete beta versions
- [ ] A/B test: Run optimizer with canonical vs beta, compare results
- [ ] Measure feasibility improvement: fewer INFEASIBLE statuses?
- [ ] Measure optimizer speed: does beta reduce search space?

---

## 5. Cost & Performance Analysis

### LLM API Costs (Claude Sonnet 4)
- **Input pricing**: $3 per million tokens
- **Output pricing**: $15 per million tokens
- **Typical expansion**:
  - Input: 2,000 tokens (system prompt + context)
  - Output: 1,500 tokens (course list)
  - Tool calls: 3-5 iterations × 500 tokens each
  - **Total per expansion**: ~5,000 tokens
- **Cost per expansion**: 
  - Input: 2,500 tokens × $3/M = $0.0075
  - Output: 2,500 tokens × $15/M = $0.0375
  - **Total: ~$0.045 per expansion**
- **Total for 211 plain strings**: 211 × $0.045 = **~$9.50**
- **With retries/failures**: Estimate **$15-20** for full catalog

### Performance
- **Per expansion time**: 5-15 seconds (depends on tool calls)
- **Batch processing time**: 211 expansions × 10s = ~35 minutes
- **Parallelization**: Can run 5-10 concurrent agents → **5-7 minutes total**

**Conclusion**: Extremely affordable and fast!

---

## 6. Edge Cases & Agent Strategies

### Case 1: Ambiguous Filters
**Input**: `"Restricted Electives under supervision by CEE faculty"`

**Agent Strategy**:
1. Identify ambiguity: "under supervision" is vague
2. Search for CEE (Course 1) courses as baseline
3. **Conservative assumption**: Include all CEE courses
4. Add `notes` field: "Assumed all Course 1 courses. Verify with advisor."
5. Mark `confidence: 0.6` (low confidence due to ambiguity)
6. Flag for human review

### Case 2: Numeric Patterns
**Input**: `"first decimal ≥ 1"`

**Agent Strategy**:
1. Parse pattern: "first decimal" = tens digit in subject ID
2. For `18.XYZ`, first decimal is X
3. `≥ 1` means X must be 1-9
4. Construct regex: `18\.[1-9]`
5. Use `filter_by_pattern` tool
6. Validate with sample courses

### Case 3: Dynamic Lists
**Input**: `"One subject from List A or List B"`

**Agent Strategy**:
1. Recognize reference to external lists
2. Search requirement file for "List A" definition
3. If not found, search Fireroad API for related requirements
4. If still not found, **fail gracefully** with error message
5. Suggest: "Manual review needed - List A/B not found"

### Case 4: Unit-Based Thresholds
**Input**: `"72 units of electives"`

**Agent Strategy**:
1. Recognize `criterion: "units"` instead of `"subjects"`
2. Fetch courses with unit information
3. Generate large list of eligible courses
4. Set threshold: `cutoff: 72, criterion: "units"`
5. **Note**: Optimizer must support unit counting (currently TODO)

### Case 5: Prerequisite-Based Filters
**Input**: `"Advanced subjects (with prerequisites)"`

**Agent Strategy**:
1. Use `get_prerequisite_chain` tool for candidate courses
2. Filter courses that have non-empty prerequisite strings
3. Exclude intro courses (typically 0XX level)
4. Generate list of "advanced" courses
5. Add note: "Defined as courses with prerequisites"

---

## 7. Monitoring & Observability

### Agent Execution Traces
Save detailed logs for every expansion:

```json
{
  "expansion_id": "exp_20250115_123456",
  "requirement_key": "course_6_3_math_electives",
  "plain_string": "2 math subjects (first decimal ≥ 1)",
  "timestamp": "2025-01-15T12:34:56Z",
  "agent_trace": [
    {
      "step": 1,
      "type": "reasoning",
      "content": "Analyzing requirement, identified: department=18, pattern=first decimal ≥ 1"
    },
    {
      "step": 2,
      "type": "tool_call",
      "tool": "search_courses",
      "input": {"query": "", "filters": {"department": "18"}},
      "output": {"count": 203, "courses": ["18.01", "18.02", ...]}
    },
    {
      "step": 3,
      "type": "reasoning",
      "content": "Need to filter by first decimal ≥ 1. Pattern: 18\\.[1-9]"
    },
    {
      "step": 4,
      "type": "tool_call",
      "tool": "filter_by_pattern",
      "input": {"pattern": "18\\.[1-9]"},
      "output": {"count": 157, "courses": ["18.100A", "18.102", ...]}
    }
  ],
  "result": {
    "success": true,
    "confidence": 0.95,
    "expanded_tree": { ... },
    "courses_found": 157
  },
  "cost_usd": 0.045,
  "execution_time_seconds": 8.2
}
```

### Metrics Dashboard
Track over time:
- **Success rate**: % of expansions that complete without errors
- **Confidence distribution**: How many are high (>0.9) vs low (<0.7) confidence
- **Cost tracking**: Total spend on expansions
- **Coverage**: % of plain strings that have beta versions
- **Human review rate**: % marked as "needs review"
- **Approval rate**: % of human-reviewed expansions approved

---

## 8. Success Criteria

### Quantitative Metrics
1. **Expansion Success Rate**: ≥ 95% of plain strings successfully expanded
2. **Accuracy**: ≥ 90% of human-reviewed expansions approved
3. **Coverage**: ≥ 80% of high-priority majors have beta versions
4. **Feasibility Improvement**: Reduce INFEASIBLE majors by ≥ 50%
5. **Cost Efficiency**: < $20 total for full catalog expansion

### Qualitative Metrics
1. **User Feedback**: Positive reception from students/advisors
2. **Agent Reasoning**: Traces are understandable and auditable
3. **Maintenance**: Beta requirements stay accurate for ≥ 1 semester
4. **Edge Case Handling**: Agent gracefully handles ambiguity
5. **Transparency**: Users understand what "beta" means

---

## 9. Risk Mitigation

### Risk 1: Hallucinated Courses
**Problem**: Agent invents course IDs that don't exist

**Mitigation**:
- Always use `validate_course_exists` tool before finalizing
- Cross-reference with official Fireroad catalog
- Add post-processing validation step
- Mark expansions with invalid courses as "failed"

### Risk 2: Incorrect Interpretations
**Problem**: Agent misunderstands plain string meaning

**Mitigation**:
- Require high confidence threshold (≥ 0.8) for auto-approval
- Human review for low-confidence expansions
- A/B test beta vs canonical, flag discrepancies
- Allow user feedback: "This expansion seems wrong"

### Risk 3: Stale Course Catalog
**Problem**: Courses change between semesters

**Mitigation**:
- Re-run batch expansion quarterly
- Version control: track which catalog was used
- Add "last_updated" timestamp to metadata
- Notify users if beta requirement is > 6 months old

### Risk 4: Tool Failures
**Problem**: Fireroad API down, rate limits hit

**Mitigation**:
- Implement exponential backoff + retry logic
- Cache tool results (e.g., department course lists)
- Graceful degradation: use cached catalog if API fails
- Monitor API health, pause batch jobs if errors spike

### Risk 5: Cost Overruns
**Problem**: Batch processing costs more than expected

**Mitigation**:
- Set hard budget limit ($50 max)
- Monitor cost per expansion, abort if > $0.50
- Use cheaper model (Haiku) for simple cases
- Cache common tool results to reduce API calls

---

## 10. Future Enhancements

### 10.1 Multi-Agent System
Instead of single agent, use specialized agents:
- **Requirement Parser Agent**: Interprets plain string
- **Course Search Agent**: Finds matching courses
- **Validation Agent**: Verifies results are correct
- **Coordinator Agent**: Orchestrates the others

### 10.2 Human-in-the-Loop
- Agent proposes expansion
- Human reviews and edits
- Agent learns from corrections
- Over time, improve accuracy through feedback

### 10.3 Confidence-Based Routing
- High confidence (>0.9): Auto-approve, no review needed
- Medium confidence (0.7-0.9): Flag for quick review
- Low confidence (<0.7): Require detailed human review

### 10.4 Version Control
- Track multiple beta versions (v1, v2, v3)
- Allow rollback if new expansion is worse
- Compare versions: what changed?

### 10.5 Continuous Learning
- Track which expansions get approved/rejected
- Use feedback to refine prompts
- Build dataset of (plain string, correct expansion) pairs
- Fine-tune smaller model for common patterns

---

## 11. Recommended Tech Stack

### Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Agent SDK**: Claude Agent SDK (Anthropic)
- **Database**: PostgreSQL (for traces, metadata)
- **Caching**: Redis (for tool results)
- **Queue**: Celery (for batch jobs)

### Frontend
- **Already built**: Next.js + React + TypeScript
- **New components**: Agent trace viewer, expansion preview

### Infrastructure
- **Hosting**: Vercel (frontend) + Railway/Render (backend)
- **Monitoring**: Sentry (errors) + PostHog (analytics)
- **Logging**: CloudWatch or Datadog

---

## 12. Next Steps

### Immediate (This Week)
1. Review this plan, get buy-in on agentic approach
2. Set up Claude Agent SDK development environment
3. Implement first tool: `search_courses`
4. Write initial system prompt
5. Test agent on 1 simple requirement: "8 HASS subjects"

### Week 2
1. Implement all 5 tools
2. Test agent on 5 diverse requirements
3. Measure success rate, cost, execution time
4. Refine system prompt based on results

### Week 3-4
1. Build FastAPI backend service
2. Add frontend "Generate Beta" button
3. Test end-to-end flow with real users
4. Gather feedback

### Month 2
1. Run batch expansion on all 211 plain strings
2. Human review of high-priority requirements
3. Deploy beta requirements for testing
4. A/B test canonical vs beta

---

## 13. Open Questions for Discussion

1. **Who can trigger expansions?** 
   - Admin only? 
   - Any authenticated user?
   - Fully automated batch?

2. **Human review workflow**:
   - Who reviews? (Academic advisors? Students? Developers?)
   - What's the approval process?
   - How to handle disagreements?

3. **Legal/Policy concerns**:
   - MIT might not want AI interpreting official requirements
   - How to clearly label beta versions as "unofficial"?
   - Liability if student relies on incorrect expansion?

4. **Fallback strategy**:
   - If expansion fails, what happens?
   - Fall back to plain string warning?
   - Require manual expansion?

5. **Update frequency**:
   - How often to regenerate beta requirements?
   - Per semester? Per year?
   - On-demand when catalog changes?

6. **Quality threshold**:
   - What confidence level is acceptable for auto-approval?
   - Should low-confidence expansions be hidden from users?

---

## Conclusion

**Key Takeaway**: This system MUST use an agentic framework. The complexity of interpreting MIT requirements, navigating the course catalog, and handling edge cases requires multi-step reasoning and tool use that only agents can provide.

**Recommended Path**:
1. Start with Claude Agent SDK (best reasoning + tool use)
2. Build POC with 5 core tools
3. Test on 5 diverse requirements
4. If successful (>80% accuracy), proceed to full implementation
5. If unsuccessful, reconsider approach or simplify requirements

**Expected Outcome**: A system that can automatically expand 90%+ of plain string requirements into concrete course lists, reducing optimizer infeasibility and improving user experience, all for <$20 and <1 hour of compute time.
