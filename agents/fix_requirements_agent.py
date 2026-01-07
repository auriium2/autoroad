#!/usr/bin/env python3
"""
Spawns Claude agents to fix vague requirements in fireroad files.

Usage:
    uv run python fix_requirements_agent.py [--requirement KEY]
    uv run python fix_requirements_agent.py --all-priority1
    uv run python fix_requirements_agent.py --parallel  # Run all in parallel

If --requirement is provided, fixes only that requirement.
Otherwise, works through Priority 1 requirements.
"""

import argparse
import anyio
from pathlib import Path

from claude_agent_sdk import query, ClaudeAgentOptions

INSTRUCTIONS_PATH = Path(__file__).parent.parent / "backend" / "requirements" / "AGENT_INSTRUCTIONS.md"
REQUIREMENTS_DIR = Path(__file__).parent.parent / "backend" / "requirements"

PRIORITY_1_REQUIREMENTS = [
    # Already done: major8, major18pm, major18c, major18am, major1, major15-1, major11
]

# Priority requirements - popular majors and common minors
# Skip obscure humanities majors (CMS, French, German, STS, Spanish, AADS, AMS, LALS, etc.)
ALL_RESOLVABLE = [
    # Popular majors (batch 1 done: major10, major10-ENG, major10b, major10c, major14-1, major14-2, major15-1old, major16-ENG)
    "major17",      # Political Science
    "major18gm",    # Math General
    "major2a",      # MechE
    "major3a",      # MatSci
    "major5-flex",  # Chemistry flex
    "major6-2",     # EECS
    "major6-3",     # CS
    "major6-4",     # AI+Decision
    "major8flex",   # Physics flex
    "major22-ENG",  # NukeE
    "major21M-1",   # Music
    "major21M-2",   # Music (theater)
    # Common minors
    "minor2",       # MechE
    "minor6",       # CS (if exists)
    "minor8",       # Physics
    "minor11",      # Urban Studies
    "minor12",      # Earth Science
    "minor14",      # Econ
    "minor15Mgmt",  # Management
    "minor17",      # PoliSci
    "minor18",      # Math
    "minor22",      # NukeE
    "minorEI",      # Entrepreneurship
    "minorEnergy",  # Energy
]


def build_prompt(requirement_key: str) -> str:
    instructions = INSTRUCTIONS_PATH.read_text()
    
    return f"""You are tasked with fixing vague requirements in an MIT degree requirement file.

## Instructions
{instructions}

## Your Task
Fix the vague "plain-string" requirements in: **{requirement_key}**

## Steps
1. Fetch the current requirement structure:
   ```bash
   curl -s "http://localhost:8000/api/requirements/get/{requirement_key}" | jq '.'
   ```

2. Identify plain-string nodes:
   ```bash
   curl -s "http://localhost:8000/api/requirements/get/{requirement_key}" | jq '.. | objects | select(.["plain-string"] == true)'
   ```

3. Research valid courses using:
   - Fireroad API: `curl "https://fireroad.mit.edu/courses/dept/DEPT_NUM"`
   - MIT Catalog website
   - Web search for "[major name] MIT approved electives"

4. Create the .fireroad file at: {REQUIREMENTS_DIR / f"{requirement_key}.fireroad"}
   - Use {REQUIREMENTS_DIR / "major6-3new.fireroad"} as a format example

5. Be comprehensive - include ALL valid courses that satisfy each requirement

When done, summarize what you fixed and any issues encountered.
"""


async def fix_requirement(requirement_key: str, quiet: bool = False, prefix: str = "") -> str:
    """Fix a single requirement. Returns summary of what was done."""
    tag = f"[{prefix or requirement_key}]"
    
    if not quiet:
        print(f"\n{'='*60}")
        print(f"Fixing: {requirement_key}")
        print('='*60)
    
    prompt = build_prompt(requirement_key)
    
    options = ClaudeAgentOptions(
        allowed_tools=["Bash", "Read", "Write", "Edit", "WebFetch", "WebSearch", "Glob", "Grep"],
        max_turns=50,
        model="haiku",  # Use cheaper/faster model
    )
    
    last_message = ""
    turn_count = 0
    async for message in query(prompt=prompt, options=options):
        turn_count += 1
        msg_str = ""
        if hasattr(message, 'content'):
            msg_str = str(message.content)
        elif isinstance(message, str):
            msg_str = message
        else:
            msg_str = str(message)
        
        last_message = msg_str
        
        if not quiet:
            print(msg_str)
        elif prefix:
            # In parallel mode, print minimal progress
            if turn_count % 5 == 1:  # Print every 5th turn
                short_msg = msg_str[:80].replace('\n', ' ') if msg_str else "working..."
                print(f"{tag} turn {turn_count}: {short_msg}...")
    
    if prefix:
        print(f"{tag} completed after {turn_count} turns")
    
    return last_message


async def fix_requirement_wrapper(requirement_key: str) -> tuple[str, str]:
    """Wrapper for parallel execution that catches errors."""
    try:
        result = await fix_requirement(requirement_key, quiet=True, prefix=requirement_key)
        return requirement_key, result
    except Exception as e:
        print(f"[{requirement_key}] ERROR: {e}")
        return requirement_key, f"ERROR: {e}"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Fix vague fireroad requirements using Claude agent")
    parser.add_argument("--requirement", "-r", type=str, help="Specific requirement key to fix")
    parser.add_argument("--batch", "-b", type=int, default=8, help="Number of agents to run in parallel (default: 8)")
    parser.add_argument("--start", "-s", type=int, default=0, help="Start index in ALL_RESOLVABLE list")
    parser.add_argument("--list", "-l", action="store_true", help="List all resolvable requirements")
    args = parser.parse_args()
    
    if args.list:
        print("All resolvable requirements:")
        for i, req in enumerate(ALL_RESOLVABLE):
            print(f"  {i:2}: {req}")
        print(f"\nTotal: {len(ALL_RESOLVABLE)}")
        return
    
    if args.requirement:
        await fix_requirement(args.requirement)
        return
    
    # Batch mode: run args.batch agents starting from args.start
    batch_reqs = ALL_RESOLVABLE[args.start:args.start + args.batch]
    if not batch_reqs:
        print(f"No requirements at index {args.start}. Total: {len(ALL_RESOLVABLE)}")
        return
    
    print(f"Spawning {len(batch_reqs)} agents (index {args.start}-{args.start + len(batch_reqs) - 1})...")
    print(f"Requirements: {', '.join(batch_reqs)}")
    print("="*60)
    
    async with anyio.create_task_group() as tg:
        results: list[tuple[str, str]] = []
        
        async def run_and_collect(req: str) -> None:
            result = await fix_requirement_wrapper(req)
            results.append(result)
        
        for req in batch_reqs:
            tg.start_soon(run_and_collect, req)
    
    print("\n" + "="*60)
    print("RESULTS SUMMARY")
    print("="*60)
    for req, result in results:
        status = "✓" if "ERROR" not in result else "✗"
        print(f"{status} {req}")
        if "ERROR" in result:
            print(f"    {result}")
    
    remaining = len(ALL_RESOLVABLE) - args.start - len(batch_reqs)
    if remaining > 0:
        print(f"\n{remaining} requirements remaining. Next batch:")
        print(f"  uv run python fix_requirements_agent.py -s {args.start + args.batch}")


if __name__ == "__main__":
    anyio.run(main)
