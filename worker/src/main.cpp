#include <iostream>
#include <iomanip>
#include <chrono>
#include <thread>
#include <atomic>
#include <cstdlib>
#include <cstring>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <httplib.h>
#include <nlohmann/json.hpp>
#include "solver.hpp"
#include "types.hpp"

using json = nlohmann::json;

std::atomic<std::chrono::steady_clock::time_point> last_activity{std::chrono::steady_clock::now()};
std::atomic<int> active_solves{0};

void update_activity() {
    last_activity.store(std::chrono::steady_clock::now());
}

bool unix_socket_post(const char* socket_path, const std::string& path) {
    int sock = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sock < 0) return false;

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, socket_path, sizeof(addr.sun_path) - 1);

    if (connect(sock, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(sock);
        return false;
    }

    std::string request = "POST " + path + " HTTP/1.0\r\nHost: localhost\r\nContent-Length: 0\r\n\r\n";
    write(sock, request.c_str(), request.size());

    //read respons before closing or something bad happens
    char buf[1024];
    while (read(sock, buf, sizeof(buf)) > 0) {}

    close(sock);
    return true;
}

void fly_suspend_thread(int idle_seconds) {
    const char* fly_app = std::getenv("FLY_APP_NAME");
    const char* fly_machine = std::getenv("FLY_MACHINE_ID");

    if (!fly_app || !fly_machine) {
        std::cout << "[suspend] Not running on Fly.io, skipping auto-suspend" << std::endl;
        return;
    }

    std::cout << "[suspend] Auto-suspend enabled, idle timeout: " << idle_seconds << "s" << std::endl;

    std::string suspend_path = "/v1/apps/" + std::string(fly_app) + "/machines/" + std::string(fly_machine) + "/suspend";

    while (true) {
        std::this_thread::sleep_for(std::chrono::seconds(1));

        auto now = std::chrono::steady_clock::now();
        auto last = last_activity.load();
        auto idle_time = std::chrono::duration_cast<std::chrono::seconds>(now - last).count();

        if (idle_time >= idle_seconds && active_solves.load() == 0) {
            std::cout << "[suspend] Idle for " << idle_time << "s, suspending..." << std::endl;
            std::cout.flush();

            unix_socket_post("/.fly/api", suspend_path);

            //Try it again
            update_activity();
        }
    }
}

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
        if (c.contains("attributes") && c["attributes"].is_object()) {
            for (const auto& [key, value] : c["attributes"].items()) {
                if (value.is_string()) {
                    meta.attributes[key] = value.get<std::string>();
                }
            }
        }
        request.courses_metadata.push_back(meta);
    }

    if (j.contains("objective_components") && j["objective_components"].is_array()) {
        for (const auto& comp : j["objective_components"]) {
            ObjectiveComponent oc;
            oc.name = comp["name"].get<std::string>();
            oc.var_indices = comp["var_indices"].get<std::vector<int>>();
            oc.coefficients = comp["coefficients"].get<std::vector<int64_t>>();
            if (comp.contains("offset")) {
                oc.offset = comp["offset"].get<int64_t>();
            }
            request.objective_components.push_back(std::move(oc));
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
        // Check auth
        const char* expected_secret = std::getenv("WORKER_SECRET");
        if (expected_secret && req.get_header_value("X-Worker-Secret") != expected_secret) {
            res.status = 401;
            res.set_content(R"({"error":"unauthorized"})", "application/json");
            return;
        }
        
        active_solves++;
        update_activity();
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
                    active_solves--;
                    sink.done();
                    update_activity();

                    auto end_time = std::chrono::steady_clock::now();
                    double elapsed = std::chrono::duration<double>(end_time - start_time).count();
                    std::cout << "[solve] Complete: " << solution_count << " solutions in "
                              << std::fixed << std::setprecision(2) << elapsed << "s" << std::endl;
                    std::cout.flush();
                    return true;
                }
            );
        } catch (const std::exception& e) {
            active_solves--;
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

    //Begin autosuspend
    std::thread suspend_thread(fly_suspend_thread, 3);
    suspend_thread.detach();

    // Short keep-alive timeout
    svr.set_keep_alive_max_count(1);
    svr.set_keep_alive_timeout(5);

    svr.set_logger([](const httplib::Request& req, const httplib::Response& res) {
        std::cout << req.method << " " << req.path << " -> " << res.status << std::endl;
        std::cout.flush();
    });

    if (!svr.listen("0.0.0.0", port)) {
        std::cerr << "Failed to bind to port " << port << std::endl;
        return 1;
    }

    return 0;
}
