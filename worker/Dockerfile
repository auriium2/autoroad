# Build for x86_64
FROM --platform=linux/amd64 ubuntu:22.04 AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install OR-Tools
WORKDIR /opt
RUN wget -q https://github.com/google/or-tools/releases/download/v9.10/or-tools_amd64_ubuntu-22.04_cpp_v9.10.4067.tar.gz \
    && tar -xzf or-tools_amd64_ubuntu-22.04_cpp_v9.10.4067.tar.gz \
    && rm or-tools_amd64_ubuntu-22.04_cpp_v9.10.4067.tar.gz

# Install nlohmann_json (header only)
RUN git clone --depth 1 --branch v3.11.3 https://github.com/nlohmann/json.git /opt/json \
    && cd /opt/json && cmake -B build -DJSON_BuildTests=OFF && cmake --build build --target install

ENV CMAKE_PREFIX_PATH=/opt/or-tools_x86_64_Ubuntu-22.04_cpp_v9.10.4067

# Build worker
WORKDIR /app
COPY CMakeLists.txt .
COPY src/ src/

RUN cmake -B build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build --parallel \
    && strip build/worker

# Collect only the shared libraries we actually need
RUN mkdir -p /app/libs && \
    ldd build/worker | grep "=> /" | awk '{print $3}' | xargs -I {} cp {} /app/libs/ 2>/dev/null || true && \
    cp /opt/or-tools_x86_64_Ubuntu-22.04_cpp_v9.10.4067/lib/libortools.so* /app/libs/

# Runtime
FROM --platform=linux/amd64 gcr.io/distroless/cc-debian12

COPY --from=builder /app/build/worker /worker
COPY --from=builder /app/libs/ /usr/lib/

EXPOSE 8080

ENTRYPOINT ["/worker", "8080"]
