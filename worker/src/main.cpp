#include <iostream>
#include <iomanip>
#include <chrono>
#include <httplib.h>
#include <nlohmann/json.hpp>
#include "solver.hpp"
#include "types.hpp"

using json = nlohmann::json;

namespace autoroad {

WorkerRequest parse_request(const std::string& body) {
    auto j = json::parse(body);
    
    WorkerRequest request;
    request.cpmodel_proto_base64 = j["cpmodel_proto"].get<std::string>();
    
    for (const auto& v : j["variable_mapping"]) {
        VariableInfo info;
        info.var_index = v["var_index"].get<int>();
        info.course_idx = v["course_idx"].get<int>();
        info.semester = v["semester"].get<int>();
        request.variable_mapping.push_back(info);
    }
    
    for (const auto& c : j["courses_metadata"]) {
        CourseMetadata meta;
        meta.subject_id = c["subject_id"].get<std::string>();
        meta.title = c["title"].get<std::string>();
        meta.units = c["units"].get<int>();
        request.courses_metadata.push_back(meta);
    }
    
    if (j.contains("objective_components")) {
        for (const auto& [key, value] : j["objective_components"].items()) {
            request.objective_components[key] = value.get<std::vector<int>>();
        }
    }
    
    if (j.contains("solver_params")) {
        const auto& sp = j["solver_params"];
        if (sp.contains("max_time_seconds")) {
            request.solver_params.max_time_seconds = sp["max_time_seconds"].get<double>();
        }
        if (sp.contains("num_workers")) {
            request.solver_params.num_workers = sp["num_workers"].get<int>();
        }
    }
    
    return request;
}

}  // namespace autoroad

int main(int argc, char* argv[]) {
    int port = 8080;
    if (argc > 1) {
        port = std::stoi(argv[1]);
    }
    
    httplib::Server svr;
    
    // Health check endpoint
    svr.Get("/health", [](const httplib::Request&, httplib::Response& res) {
        res.set_header("Connection", "close");
        res.set_content(R"({"status":"healthy","solver":"cpp-worker"})", "application/json");
    });
    
    // Solve endpoint with SSE streaming
    svr.Post("/solve", [](const httplib::Request& req, httplib::Response& res) {
        res.set_header("Connection", "close");
        res.set_header("Cache-Control", "no-cache");
        res.set_header("Access-Control-Allow-Origin", "*");
        
        auto start_time = std::chrono::steady_clock::now();
        
        try {
            auto request = autoroad::parse_request(req.body);
            std::cout << "[solve] Received model with " << request.variable_mapping.size() 
                      << " variables, " << request.courses_metadata.size() << " courses"
                      << ", num_workers=" << request.solver_params.num_workers << std::endl;
            std::cout.flush();
            
            res.set_chunked_content_provider(
                "text/event-stream",
                [request = std::move(request), start_time](size_t /*offset*/, httplib::DataSink& sink) {
                    int solution_count = 0;
                    autoroad::Solver solver(request, [&sink, &solution_count](const std::string& event_type, const std::string& data) {
                        std::string sse_event = "data: " + data + "\n\n";
                        sink.write(sse_event.c_str(), sse_event.size());
                        if (event_type == "solution") {
                            solution_count++;
                        }
                    });
                    
                    solver.solve();
                    sink.done();
                    
                    auto end_time = std::chrono::steady_clock::now();
                    double elapsed = std::chrono::duration<double>(end_time - start_time).count();
                    std::cout << "[solve] Complete: " << solution_count << " solutions in " 
                              << std::fixed << std::setprecision(2) << elapsed << "s" << std::endl;
                    std::cout.flush();
                    return true;
                }
            );
        } catch (const std::exception& e) {
            std::cout << "[solve] Error: " << e.what() << std::endl;
            std::cout.flush();
            json error = {{"type", "error"}, {"error", e.what()}};
            std::string sse_event = "data: " + error.dump() + "\n\n";
            res.set_content(sse_event, "text/event-stream");
        }
    });
    
    // CORS preflight
    svr.Options("/solve", [](const httplib::Request&, httplib::Response& res) {
        res.set_header("Connection", "close");
        res.set_header("Access-Control-Allow-Origin", "*");
        res.set_header("Access-Control-Allow-Methods", "POST, OPTIONS");
        res.set_header("Access-Control-Allow-Headers", "Content-Type");
        res.status = 204;
    });
    
    std::cout << "Starting autoroad worker on port " << port << std::endl;
    std::cout.flush();
    
    svr.set_logger([](const httplib::Request& req, const httplib::Response& res) {
        std::cout << req.method << " " << req.path << " -> " << res.status << std::endl;
        std::cout.flush();
    });
    
    svr.listen("0.0.0.0", port);
    
    return 0;
}
