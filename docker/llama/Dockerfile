# llama-server from TheTom's TurboQuant llama.cpp fork, built once to run well on any x86-64 PC.
#
# Portable on purpose: GGML_NATIVE=OFF + GGML_CPU_ALL_VARIANTS=ON compiles one CPU backend per
# instruction-set level (AVX2/Haswell ... AVX-512/Sapphire Rapids) and GGML_BACKEND_DL=ON loads the
# best one for the processor it is running on at start-up. The same image therefore uses AVX2+FMA
# on this i3-4150 and AVX-512 / AVX-VNNI on a newer CPU, with no rebuild. Vulkan is included for
# Intel / AMD GPUs (passed in through /dev/dri); entrypoint.sh benchmarks whether it actually helps.
#
# Source: the local llama-cpp-turboquant checkout (default ~/llama-cpp-turboquant), snapshotted
# into this folder by build.sh. Build (2 parallel jobs keeps an 8 GB PC from running out of memory;
# raise JOBS in compose.yml on bigger PCs):
#   docker/llama/build.sh [path-to-llama-cpp-turboquant]
FROM ubuntu:24.04 AS build
ARG JOBS=2
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential cmake git ca-certificates libvulkan-dev glslc spirv-headers \
    && rm -rf /var/lib/apt/lists/*
# spirv-headers: ggml-vulkan needs find_package(SPIRV-Headers CONFIG) (newer llama.cpp).
# ADD unpacks the local tarball; build.sh writes it and BUILD_COMMIT, then deletes them.
ADD llama-src.tar.gz /src/
COPY BUILD_COMMIT /src/BUILD_COMMIT
RUN cmake -S /src -B /build \
        -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF \
        -DGGML_NATIVE=OFF -DGGML_CPU_ALL_VARIANTS=ON -DGGML_BACKEND_DL=ON -DBUILD_SHARED_LIBS=ON \
        -DGGML_VULKAN=ON \
        -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON -DCMAKE_INSTALL_RPATH='$ORIGIN' \
    && cmake --build /build --target llama-server llama-bench -j"$JOBS"
RUN mkdir -p /out \
    && cp /build/bin/llama-server /build/bin/llama-bench /src/BUILD_COMMIT /out/ \
    && find /build -name 'lib*.so*' -exec cp -a {} /out/ \;

FROM ubuntu:24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        libgomp1 libvulkan1 mesa-vulkan-drivers curl ca-certificates util-linux python3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /out/ /opt/llama/
COPY entrypoint.sh /opt/llama/entrypoint.sh
RUN chmod +x /opt/llama/entrypoint.sh
ENV PATH=/opt/llama:$PATH LD_LIBRARY_PATH=/opt/llama
VOLUME /models
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=30m --retries=3 \
    CMD curl -fs http://127.0.0.1:8080/health || exit 1
ENTRYPOINT ["/opt/llama/entrypoint.sh"]
