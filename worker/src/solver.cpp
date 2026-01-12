#include "solver.hpp"
#include <chrono>
#include <nlohmann/json.hpp>
#include "ortools/sat/cp_model_solver.h"

namespace autoroad {

using json = nlohmann::json;
using namespace operations_research::sat;

namespace {

std::vector<uint8_t> base64_decode(const std::string& encoded) {
    static const std::string chars =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

    std::vector<uint8_t> decoded;
    decoded.reserve(encoded.size() * 3 / 4);

    int val = 0;
    int bits = -8;

    for (char c : encoded) {
        if (c == '=') break;
        size_t pos = chars.find(c);
        if (pos == std::string::npos) continue;

        val = (val << 6) + static_cast<int>(pos);
        bits += 6;

        if (bits >= 0) {
            decoded.push_back(static_cast<uint8_t>((val >> bits) & 0xFF));
            bits -= 8;
        }
    }

    return decoded;
}

std::string status_to_string(CpSolverStatus status) {
    switch (status) {
        case CpSolverStatus::OPTIMAL: return "OPTIMAL";
        case CpSolverStatus::FEASIBLE: return "FEASIBLE";
        case CpSolverStatus::INFEASIBLE: return "INFEASIBLE";
        case CpSolverStatus::MODEL_INVALID: return "MODEL_INVALID";
        default: return "UNKNOWN";
    }
}

}  // namespace

Solver::Solver(const WorkerRequest& request, EventCallback on_event)
    : request_(request), on_event_(std::move(on_event)) {}

bool Solver::deserialize_model() {
    auto proto_bytes = base64_decode(request_.cpmodel_proto_base64);
    return model_proto_.ParseFromArray(proto_bytes.data(), static_cast<int>(proto_bytes.size()));
}

void Solver::emit_progress(const std::string& message, int step, int total_steps) {
    json data = {
        {"type", "progress"},
        {"message", message},
        {"step", step},
        {"totalSteps", total_steps}
    };
    on_event_("progress", data.dump());
}

void Solver::emit_solution(const SolutionEvent& solution) {
    json nodes = json::array();
    for (const auto& node : solution.nodes) {
        json node_json = {
            {"courseId", node.course_id},
            {"section", node.section},
            {"title", node.title},
            {"units", node.units}
        };
        if (!node.attributes.empty()) {
            node_json["attributes"] = node.attributes;
        }
        nodes.push_back(std::move(node_json));
    }

    json data = {
        {"type", "solution"},
        {"solutionNumber", solution.solution_number},
        {"nodes", nodes},
        {"objectiveValue", solution.objective_value},
        {"costBreakdown", solution.cost_breakdown}
    };
    on_event_("solution", data.dump());
}

void Solver::emit_completion(const CompletionEvent& completion) {
    json data = {
        {"type", "complete"},
        {"status", completion.status},
        {"solutionCount", completion.solution_count},
        {"solveTimeSeconds", completion.solve_time_seconds}
    };
    on_event_("complete", data.dump());
}

void Solver::solve() {
    emit_progress("Deserializing model...", 1, 3);

    if (!deserialize_model()) {
        json error = {{"type", "error"}, {"error", "Failed to deserialize CpModel protobuf"}};
        on_event_("error", error.dump());
        return;
    }

    emit_progress("Configuring solver...", 2, 3);

    // Configure solver parameters - match Python behavior
    SatParameters params;
    params.set_max_time_in_seconds(request_.solver_params.max_time_seconds);
    params.set_num_workers(0);  // Auto-detect CPU count
    params.set_enumerate_all_solutions(false);
    params.set_log_search_progress(false);

    int solution_count = 0;

    Model model;
    model.Add(NewSatParameters(params));

    model.Add(NewFeasibleSolutionObserver([&](const CpSolverResponse& response) {
        solution_count++;

        SolutionEvent event;
        event.solution_number = solution_count;
        event.objective_value = response.objective_value();

        // Extract assigned courses from solution
        // response.solution(i) gives the value of variable at index i
        for (const auto& var_info : request_.variable_mapping) {
            // Boolean variable: value is 0 or 1
            if (response.solution(var_info.var_index) == 1) {
                const auto& course = request_.courses_metadata[var_info.course_idx];
                SolutionNode node;
                node.course_id = course.subject_id;
                node.section = var_info.semester >= 0 ? var_info.semester - 1 : var_info.semester;
                node.title = course.title;
                node.units = course.units;
                node.attributes = course.attributes;
                event.nodes.push_back(std::move(node));
            }
        }

        emit_solution(event);
    }));

    emit_progress("Solving...", 3, 3);

    auto start_time = std::chrono::steady_clock::now();

    const CpSolverResponse response = SolveCpModel(model_proto_, &model);

    auto end_time = std::chrono::steady_clock::now();
    double solve_time = std::chrono::duration<double>(end_time - start_time).count();

    // Emit completion
    CompletionEvent completion;
    completion.status = status_to_string(response.status());
    completion.solution_count = solution_count;
    completion.solve_time_seconds = solve_time;

    emit_completion(completion);
}

}  // namespace autoroad
