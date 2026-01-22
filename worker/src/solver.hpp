#pragma once

#include <functional>
#include <string>
#include <unordered_map>
#include "types.hpp"
#include "ortools/sat/cp_model.h"
#include "ortools/sat/cp_model.pb.h"

namespace autoroad {

using EventCallback = std::function<void(const std::string& event_type, const std::string& json_data)>;

class Solver {
public:
    Solver(const WorkerRequest& request, EventCallback on_event);

    void solve();

private:
    const WorkerRequest& request_;
    EventCallback on_event_;
    operations_research::sat::CpModelProto model_proto_;
    std::unordered_map<int, size_t> var_idx_to_mapping_idx_;

    bool deserialize_model();
    void emit_progress(const std::string& message, int step, int total_steps);
    void emit_solution(const SolutionEvent& solution);
    void emit_completion(const CompletionEvent& completion);
};

}  // namespace autoroad
