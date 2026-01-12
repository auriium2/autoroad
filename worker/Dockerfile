# Build for x86_64
FROM --platform=linux/amd64 debian:12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download prebuilt OR-Tools (already optimized)
WORKDIR /opt
RUN wget -q https://github.com/google/or-tools/releases/download/v9.14/or-tools_amd64_debian-12_cpp_v9.14.6206.tar.gz \
    && tar -xzf or-tools_amd64_debian-12_cpp_v9.14.6206.tar.gz \
    && rm or-tools_amd64_debian-12_cpp_v9.14.6206.tar.gz \
    && mv or-tools_* or-tools

# Install nlohmann_json (header only)
RUN git clone --depth 1 --branch v3.11.3 https://github.com/nlohmann/json.git /opt/json \
    && cd /opt/json && cmake -B build -DJSON_BuildTests=OFF && cmake --build build --target install

ENV CMAKE_PREFIX_PATH=/opt/or-tools

# Build worker with aggressive optimizations
WORKDIR /app
COPY CMakeLists.txt .
COPY src/ src/

# Build with maximum optimizations - the key is -march=x86-64-v3 for modern CPU features
# and PGO-like flags for better branch prediction
RUN cmake -B build -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_FLAGS_RELEASE="-O3 -DNDEBUG -march=x86-64-v3 -mtune=skylake -flto=auto -ffast-math -funroll-loops -fomit-frame-pointer" \
    && cmake --build build --parallel \
    && strip --strip-all build/worker

# Collect shared libraries
RUN mkdir -p /app/libs && \
    ldd build/worker | grep "=> /" | awk '{print $3}' | xargs -I {} cp {} /app/libs/ 2>/dev/null || true && \
    cp /opt/or-tools/lib/libortools.so* /app/libs/

# Runtime - distroless for minimal size and fast startup
FROM --platform=linux/amd64 gcr.io/distroless/cc-debian12

COPY --from=builder /app/build/worker /worker
COPY --from=builder /app/libs/ /usr/lib/

EXPOSE 8080

ENTRYPOINT ["/worker", "8080"]
