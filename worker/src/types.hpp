#pragma once

#include <string>
#include <vector>
#include <unordered_map>

namespace autoroad {

struct VariableInfo {
    int var_index;      // Index in CpModel's variables list
    int course_idx;     // Row in courses_metadata
    int semester;       // 1-12, -1 (ASE), -2 (must take)
};

struct CourseMetadata {
    std::string subject_id;
    std::string title;
    int units;
    std::unordered_map<std::string, std::string> attributes;
};

struct SolverParams {
    double max_time_seconds = 20.0;
    int num_workers = 8;
};

struct WorkerRequest {
    std::string cpmodel_proto_base64;
    std::vector<VariableInfo> variable_mapping;
    std::vector<CourseMetadata> courses_metadata;
    std::unordered_map<std::string, std::vector<int>> objective_components;
    SolverParams solver_params;
};

struct SolutionNode {
    std::string course_id;
    int section;
    std::string title;
    int units;
    std::unordered_map<std::string, std::string> attributes;
};

struct SolutionEvent {
    int solution_number;
    std::vector<SolutionNode> nodes;
    double objective_value;
    std::unordered_map<std::string, double> cost_breakdown;
};

struct CompletionEvent {
    std::string status;  // OPTIMAL, FEASIBLE, INFEASIBLE, MODEL_INVALID
    int solution_count;
    double solve_time_seconds;
};

}  // namespace autoroad
