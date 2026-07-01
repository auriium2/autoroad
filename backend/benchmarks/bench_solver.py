"""
A reproducible benchmark script for MIT degree-plan optimization solver.
Measures wall-clock time for key stages, comparing unoptimized baseline vs optimized versions.
"""

import time
import asyncio
from typing import Any
import polars as pl
from ortools.sat.python import cp_model

from shared.models.requests import Marker
from shared.courses.requirements.parser import parse_fireroad_response
from shared.courses.requirements.validator import validate_and_prune
from shared.optimizer.constraints.basic import add_basic_constraints, create_take_vars
from shared.optimizer.marker_constraint_builder import add_marker_constraints
from shared.optimizer.prerequisite_constraint_builder import add_prerequisite_constraints
from shared.optimizer.requirements.builder import add_requirement_constraints
from shared.optimizer.objectives.builder import ObjectiveBuilder
from shared.optimizer.objectives.registry import get_default_objectives, instantiate_objective
from shared.services.cache import (
    get_courses_data,
    get_parsed_prerequisites_by_index,
    get_requirements,
)

async def run_one_benchmark(
    requirement_keys: tuple[str, ...],
    markers: list[Marker] | None = None,
    start_year: int = 2025,
    max_semesters: int = 12,
    with_objectives: bool = True,
    freeze_past_semesters: bool = False,
    enable_pruning: bool = True,
    num_search_workers: int = 1,
) -> dict[str, Any]:
    timings = {}

    # --- 1. Data Fetching ---
    t0 = time.perf_counter()
    courses_data = await get_courses_data()
    courses_df = pl.DataFrame(courses_data, infer_schema_length=None)
    requirements_data = await get_requirements(requirement_keys)
    prereq_trees = await get_parsed_prerequisites_by_index(courses_df)
    timings["Data Fetching"] = time.perf_counter() - t0

    # --- 2. Model & Variable Creation ---
    t0 = time.perf_counter()
    model = cp_model.CpModel()
    
    # Prune only if enabled
    req_data_arg = requirements_data if enable_pruning else None
    prereq_arg = prereq_trees if enable_pruning else None
    
    take_vars = create_take_vars(
        model, courses_df, start_year, max_semesters, markers,
        requirements_data=req_data_arg, prereq_trees=prereq_arg
    )
    add_basic_constraints(model, take_vars, courses_df, max_semesters)
    
    if freeze_past_semesters and markers:
        from shared.optimizer.constraints.basic import add_past_semester_constraints
        add_past_semester_constraints(model, take_vars, courses_df, start_year, markers)
    timings["Model & Var Creation"] = time.perf_counter() - t0

    # --- 3. Adding Markers ---
    t0 = time.perf_counter()
    if markers:
        add_marker_constraints(model, take_vars, markers, courses_df, start_year)
    timings["Adding Markers"] = time.perf_counter() - t0

    # --- 4. Adding Prerequisites ---
    t0 = time.perf_counter()
    override_course_ids = set()
    if markers:
        override_course_ids = {m.courseId for m in markers if m.status == 'override'}
    add_prerequisite_constraints(model, take_vars, courses_df, start_year, prereq_trees, override_course_ids)
    timings["Adding Prerequisites"] = time.perf_counter() - t0

    # --- 5. Adding Requirements ---
    t0 = time.perf_counter()
    course_to_requirements: dict[int, set[str]] = {}
    for req_key in requirement_keys:
        if req_key in requirements_data:
            req_data = requirements_data[req_key]
            if isinstance(req_data, dict):
                req_tree = parse_fireroad_response(req_data)
                validation = validate_and_prune(req_tree, courses_df, remove_invalid=False)
                if validation.pruned_tree is not None:
                    _aux_vars, _debug_names, mapping = add_requirement_constraints(
                        model, take_vars, validation.pruned_tree,
                        courses_df, req_key, enforce=True
                    )
                    for course_idx, req_paths in mapping.items():
                        if course_idx not in course_to_requirements:
                            course_to_requirements[course_idx] = set()
                        course_to_requirements[course_idx].update(req_paths)
    timings["Adding Requirements"] = time.perf_counter() - t0

    # --- 6. Building Objectives ---
    t0 = time.perf_counter()
    if with_objectives:
        builder = ObjectiveBuilder()
        from shared.optimizer.objectives.units import MinimizeUnits
        builder.add(MinimizeUnits(), key="minimize_units")
        for key, params in get_default_objectives():
            obj = instantiate_objective(key, params)
            builder.add(obj, key=key)

        marked_course_ids = {m.courseId for m in markers} if markers else set()
        objective = builder.build(
            model, take_vars, courses_df, start_year,
            objective_tiers={},
            requirement_tiers={},
            marked_course_ids=marked_course_ids,
            course_to_requirements=course_to_requirements,
            lock_past_semesters=freeze_past_semesters,
            current_semester=0
        )
        model.Minimize(objective)
    timings["Building Objectives"] = time.perf_counter() - t0

    # --- 7. Solving Model ---
    t0 = time.perf_counter()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 20.0
    solver.parameters.random_seed = 42
    solver.parameters.num_search_workers = num_search_workers
    status = solver.Solve(model)
    timings["Solving CP-SAT"] = time.perf_counter() - t0
    
    status_str = "UNKNOWN"
    if status == cp_model.OPTIMAL:
        status_str = "OPTIMAL"
    elif status == cp_model.FEASIBLE:
        status_str = "FEASIBLE"
    elif status == cp_model.INFEASIBLE:
        status_str = "INFEASIBLE"
    elif status == cp_model.MODEL_INVALID:
        status_str = "MODEL_INVALID"
    
    timings["Status"] = status_str
    timings["Num Vars"] = len(take_vars)
    timings["Num Constraints"] = len(model.Proto().constraints)

    return timings

async def run_benchmark():
    requirement_keys = ("major6-3new", "girs", "major18c")
    
    markers = [
        Marker(courseId="6.1200", section=3, status="pin"),
        Marker(courseId="18.01", section=-1, status="pin"),
        Marker(courseId="18.02", section=0, status="pin"),
        Marker(courseId="6.100A", section=1, status="pin"),
        Marker(courseId="6.1010", section=2, status="pin"),
        Marker(courseId="8.01", section=1, status="override"),
        Marker(courseId="18.06", section=5, status="banish"),
    ]

    print("==================================================")
    print("      AutoRoad Optimizer Performance Benchmark    ")
    print("==================================================")
    print(f"Requirements: {requirement_keys}")
    print(f"Num Markers: {len(markers)}")
    
    # Warmup
    print("\nPerforming Warmup...")
    await run_one_benchmark(requirement_keys, markers, enable_pruning=True, num_search_workers=8)
    
    print("\nRunning Baseline (Pruning=OFF, Workers=1)...")
    # Run 1 iteration of baseline to avoid exceeding the timeout limit of MCP
    baseline = await run_one_benchmark(requirement_keys, markers, enable_pruning=False, num_search_workers=1)
    
    print("\nRunning Optimized Phase 1 (Pruning=ON, Workers=1)...")
    opt_p1 = await run_one_benchmark(requirement_keys, markers, enable_pruning=True, num_search_workers=1)
    
    print("\nRunning Fully Optimized Phase 2 (Pruning=ON, Workers=8)...")
    # Run 3 runs to get a stable average since it is so fast
    runs = []
    for i in range(3):
        res = await run_one_benchmark(requirement_keys, markers, enable_pruning=True, num_search_workers=8)
        runs.append(res)
    
    # Average the 3 runs of Phase 2
    keys = ["Data Fetching", "Model & Var Creation", "Adding Markers", "Adding Prerequisites", "Adding Requirements", "Building Objectives", "Solving CP-SAT"]
    opt_p2 = {}
    for key in keys:
        opt_p2[key] = sum(r[key] for r in runs) / len(runs)
    opt_p2["Status"] = runs[0]["Status"]
    opt_p2["Num Vars"] = runs[0]["Num Vars"]
    opt_p2["Num Constraints"] = runs[0]["Num Constraints"]

    # Calculate Totals
    total_baseline = sum(baseline[k] for k in keys)
    total_p1 = sum(opt_p1[k] for k in keys)
    total_p2 = sum(opt_p2[k] for k in keys)

    print("\n" + "="*80)
    print("                           COMPARATIVE BENCHMARK RESULTS")
    print("="*80)
    print(f"{'Stage / Metric':<25} | {'Baseline':<15} | {'Opt Phase 1':<15} | {'Opt Phase 2 (Best)':<15}")
    print("-"*80)
    print(f"{'Solver Status':<25} | {baseline['Status']:<15} | {opt_p1['Status']:<15} | {opt_p2['Status']:<15}")
    print(f"{'Num Variables':<25} | {baseline['Num Vars']:<15d} | {opt_p1['Num Vars']:<15d} | {opt_p2['Num Vars']:<15d}")
    print(f"{'Num Constraints':<25} | {baseline['Num Constraints']:<15d} | {opt_p1['Num Constraints']:<15d} | {opt_p2['Num Constraints']:<15d}")
    print("-"*80)
    for key in keys:
        print(f"{key:<25} | {baseline[key]:>13.4f}s | {opt_p1[key]:>13.4f}s | {opt_p2[key]:>13.4f}s")
    print("-"*80)
    print(f"{'Total Pipeline Time':<25} | {total_baseline:>13.4f}s | {total_p1:>13.4f}s | {total_p2:>13.4f}s")
    print("="*80)
    
    headline_speedup = total_baseline / total_p2
    print(f"HEADLINE SPEEDUP (Solve + Setup): {headline_speedup:.2f}x faster!")
    print(f"CP-SAT Solve Speedup: {baseline['Solving CP-SAT'] / opt_p2['Solving CP-SAT']:.2f}x faster!")
    print(f"Model Setup Speedup: {sum(baseline[k] for k in keys[:-1]) / sum(opt_p2[k] for k in keys[:-1]):.2f}x faster!")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
