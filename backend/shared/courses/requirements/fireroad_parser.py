"""
Parser for .fireroad requirement files.

This parser converts the Fireroad file format into the JSON structure
that our requirements parser expects (same as Fireroad API returns).

Fireroad file format:
- Line 1: Header - short#,#medium#,#title#,#title_no_degree
- Line 2: Description
- Line 3: Empty
- Lines 4+: Top-level section names (until empty line)
- Empty line
- Variable declarations: name, "title" := expression

Expression syntax:
- Comma (,) = AND
- Slash (/) = OR  
- Parentheses for grouping
- {>=N} = threshold (at least N)
- {<=N} = threshold (at most N)
- {>=N|>=M} = threshold with distinct threshold
- Variable references resolve to their definitions
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

COMMENT_PREFIX = "%%"
DECLARATION_SEP = ":="
HEADER_SEP = "#,#"
VAR_TITLE_SEP = ","

MODIFIER_REGEX = re.compile(r"\{(.*?)\}(?![^\(]*\))")


@dataclass
class ParsedStatement:
    title: str | None = None
    description: str | None = None
    requirement: str | None = None  # Leaf node (course ID)
    children: list[ParsedStatement] = field(default_factory=list)
    connection_type: str = "all"  # "all", "any", "none"
    threshold_type: str | None = None  # "GTE", "LTE", "GT", "LT"
    threshold_cutoff: int = 0
    threshold_criterion: str = "subjects"  # "subjects" or "units"
    distinct_threshold_type: str | None = None
    distinct_threshold_cutoff: int = 0
    is_plain_string: bool = False

    def to_json(self) -> dict[str, Any]:
        result: dict[str, Any] = {}

        if self.title:
            result["title"] = self.title
        if self.description:
            result["desc"] = self.description
        if self.is_plain_string:
            result["plain-string"] = True

        if self.threshold_type is not None:
            result["threshold"] = {
                "type": self.threshold_type,
                "cutoff": self.threshold_cutoff,
                "criterion": self.threshold_criterion,
            }
        if self.distinct_threshold_type is not None:
            result["distinct-threshold"] = {
                "type": self.distinct_threshold_type,
                "cutoff": self.distinct_threshold_cutoff,
                "criterion": self.threshold_criterion,
            }

        if self.requirement is not None:
            result["req"] = self.requirement
        elif self.children:
            result["reqs"] = [child.to_json() for child in self.children]
            result["connection-type"] = self.connection_type

        return result


def _strip_comments(line: str) -> str:
    if COMMENT_PREFIX in line:
        return line[:line.find(COMMENT_PREFIX)]
    return line


def _undecorated(s: str) -> str:
    return s.strip(" \t\r\n\"'")


def _unwrap_parens(s: str) -> str:
    """Remove outer parentheses if they wrap the entire expression."""
    s = s.strip()
    while len(s) >= 2 and s[0] == "(" and s[-1] == ")":
        # Check that these parens actually wrap the whole thing
        depth = 0
        closes_at_end = True
        for i, c in enumerate(s):
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0 and i < len(s) - 1:
                    closes_at_end = False
                    break
        if closes_at_end:
            s = s[1:-1].strip()
        else:
            break
    return s


def _parse_modifier(modifier: str) -> tuple[str | None, int, str, str | None, int]:
    """
    Parse a modifier like {>=3}, {<=2u}, {>=2|>=1}.
    
    Returns: (threshold_type, cutoff, criterion, distinct_type, distinct_cutoff)
    """
    threshold_type: str | None = None
    cutoff = 0
    criterion = "subjects"
    distinct_type: str | None = None
    distinct_cutoff = 0

    if "|" in modifier:
        parts = modifier.split("|")
        if len(parts) == 2:
            if parts[0]:
                threshold_type, cutoff, criterion = _parse_single_modifier(parts[0])
            if parts[1]:
                distinct_type, distinct_cutoff, _ = _parse_single_modifier(parts[1])
    else:
        threshold_type, cutoff, criterion = _parse_single_modifier(modifier)

    return threshold_type, cutoff, criterion, distinct_type, distinct_cutoff


def _parse_single_modifier(mod: str) -> tuple[str, int, str]:
    """Parse a single modifier component like >=3 or <=2u."""
    threshold_type = "GTE"
    criterion = "subjects"

    if ">=" in mod:
        threshold_type = "GTE"
    elif "<=" in mod:
        threshold_type = "LTE"
    elif ">" in mod:
        threshold_type = "GT"
    elif "<" in mod:
        threshold_type = "LT"

    num_str = mod.replace(">", "").replace("<", "").replace("=", "")
    if "u" in num_str.lower():
        criterion = "units"
        num_str = num_str.replace("u", "").replace("U", "")

    try:
        cutoff = int(num_str)
    except ValueError:
        cutoff = 1

    return threshold_type, cutoff, criterion


def _separate_top_level(text: str) -> tuple[list[str], str]:
    """
    Split expression by top-level separators (not inside parens).
    
    Returns: (components, connection_type)
    """
    text = text.strip()

    # Check for plain string (double-quoted)
    if len(text) >= 4 and text[:2] == '""' and text[-2:] == '""':
        return [_undecorated(text)], "none"

    components: list[str] = []
    connection_type = "all"
    depth = 0
    current = ""

    for char in text:
        if char == "," and depth == 0:
            connection_type = "all"
            components.append(current)
            current = ""
        elif char == "/" and depth == 0:
            connection_type = "any"
            components.append(current)
            current = ""
        else:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            current += char

    if current:
        components.append(current)

    return [_undecorated(c) for c in components if _undecorated(c)], connection_type


def _parse_expression(expr: str, title: str | None = None) -> ParsedStatement:
    """Parse a requirement expression into a ParsedStatement."""
    stmt = ParsedStatement(title=title)

    # Extract and apply modifier
    expr_clean = expr
    match = MODIFIER_REGEX.search(expr)
    if match:
        modifier = match.group(1)
        t_type, t_cut, t_crit, d_type, d_cut = _parse_modifier(modifier)
        stmt.threshold_type = t_type
        stmt.threshold_cutoff = t_cut
        stmt.threshold_criterion = t_crit
        stmt.distinct_threshold_type = d_type
        stmt.distinct_threshold_cutoff = d_cut
        expr_clean = MODIFIER_REGEX.sub("", expr)

    components, conn_type = _separate_top_level(expr_clean)

    # Handle threshold with connection type
    if stmt.threshold_type is not None and stmt.threshold_cutoff == 0 and stmt.threshold_type == "GTE":
        stmt.connection_type = "any"
    else:
        stmt.connection_type = conn_type

    stmt.is_plain_string = (conn_type == "none")

    if len(components) == 1 or stmt.is_plain_string:
        # Might be a single course or a variable reference - store as requirement
        stmt.requirement = _unwrap_parens(components[0]) if components else ""
    else:
        # Multiple components - recurse
        for comp in components:
            child = _parse_expression(_unwrap_parens(comp))
            stmt.children.append(child)

    return stmt


def _substitute_variables(stmt: ParsedStatement, variables: dict[str, ParsedStatement]) -> None:
    """Recursively substitute variable references."""
    if stmt.requirement is not None:
        if stmt.requirement in variables:
            # Replace this statement with the variable's content
            var_stmt = variables[stmt.requirement]
            # Copy over the variable's children/requirement
            stmt.children = var_stmt.children.copy()
            if var_stmt.requirement is not None and var_stmt.requirement not in variables:
                stmt.requirement = var_stmt.requirement
            else:
                stmt.requirement = None
            stmt.connection_type = var_stmt.connection_type
            stmt.is_plain_string = var_stmt.is_plain_string
            # Keep our own threshold if we have one, otherwise use variable's
            if stmt.threshold_type is None:
                stmt.threshold_type = var_stmt.threshold_type
                stmt.threshold_cutoff = var_stmt.threshold_cutoff
                stmt.threshold_criterion = var_stmt.threshold_criterion
            if stmt.distinct_threshold_type is None:
                stmt.distinct_threshold_type = var_stmt.distinct_threshold_type
                stmt.distinct_threshold_cutoff = var_stmt.distinct_threshold_cutoff
            # Recurse on new children
            for child in stmt.children:
                _substitute_variables(child, variables)
    else:
        for child in stmt.children:
            _substitute_variables(child, variables)


def parse_fireroad_file(content: str) -> dict[str, Any]:
    """
    Parse a .fireroad file into the JSON format expected by our requirements parser.
    
    Returns dict with: short, medium, title, description, reqs
    """
    lines = content.split("\n")
    # Strip comments and whitespace
    lines = [_strip_comments(line).strip() for line in lines]

    if len(lines) < 2:
        raise ValueError("Invalid .fireroad file: too few lines")

    # Line 1: Header
    header_parts = lines[0].split(HEADER_SEP)
    short = header_parts[0] if header_parts else ""
    medium = header_parts[1] if len(header_parts) > 1 else short
    title = header_parts[2] if len(header_parts) > 2 else medium
    title_no_degree = header_parts[3] if len(header_parts) > 3 else title

    # Skip empty lines after header to find description
    idx = 1
    while idx < len(lines) and not lines[idx]:
        idx += 1

    # Next non-empty line is description
    description = ""
    if idx < len(lines):
        description = lines[idx].replace("\\n", "\n")
        idx += 1

    # Skip empty lines after description
    while idx < len(lines) and not lines[idx]:
        idx += 1

    # Check if we have top-level section names (lines without :=)
    # These can be separated by empty lines
    section_names: list[str] = []
    temp_idx = idx
    while temp_idx < len(lines):
        line = lines[temp_idx]
        if DECLARATION_SEP in line:
            # Hit a declaration, stop looking for section names
            break
        if line:
            section_names.append(_undecorated(line))
        temp_idx += 1

    # If we found section names, advance past them
    if section_names:
        idx = temp_idx

    # Parse variable declarations
    variables: dict[str, ParsedStatement] = {}

    while idx < len(lines):
        line = lines[idx]
        idx += 1

        if not line:
            continue
        if DECLARATION_SEP not in line:
            continue

        parts = line.split(DECLARATION_SEP, 1)
        if len(parts) != 2:
            continue

        declaration = parts[0]
        expression = parts[1].strip()

        # Parse declaration: "name" or "name, title"
        var_name = ""
        var_title = ""

        if VAR_TITLE_SEP in declaration and '"' in declaration:
            # Has title: name, "title"
            sep_idx = declaration.find(VAR_TITLE_SEP)
            var_name = _undecorated(declaration[:sep_idx])
            var_title = _undecorated(declaration[sep_idx + 1:])
        else:
            var_name = _undecorated(declaration)
            var_title = var_name

        stmt = _parse_expression(expression, title=var_title)
        variables[var_name] = stmt

    # Substitute variables
    for stmt in variables.values():
        _substitute_variables(stmt, variables)

    # Build top-level requirements from section names
    top_level_reqs: list[ParsedStatement] = []

    if section_names:
        for name in section_names:
            if name in variables:
                top_level_reqs.append(variables[name])
    else:
        # If no explicit top-level sections, use only the last variable
        # (it typically references/combines the others, e.g., "total := (all_courses){>=3}")
        if variables:
            top_level_reqs = [list(variables.values())[-1]]

    # Convert to JSON format
    return {
        "short": short,
        "medium": medium,
        "title": title,
        "title_no_degree": title_no_degree,
        "description": description,
        "reqs": [stmt.to_json() for stmt in top_level_reqs],
    }
