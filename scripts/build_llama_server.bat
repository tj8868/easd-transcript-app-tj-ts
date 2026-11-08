@echo off
REM Windows: build llama-server from TheTom's TurboQuant llama.cpp fork
REM (https://github.com/TheTom/llama-cpp-turboquant, branch feature/turboquant-kv-cache) into bin\.
REM The app starts it hidden in the background and runs the local LLM (Gemma 4 E2B, Q4_0)
REM with the TurboQuant KV cache (-ctk turbo3 -ctv turbo4).
REM Needs: Git, CMake, Visual Studio Build Tools (C++).
REM   Vulkan (Intel Iris Xe / Arc / Core Ultra, AMD, NVIDIA): LunarG Vulkan SDK (sets VULKAN_SDK).
REM   CUDA (NVIDIA): CUDA toolkit (sets CUDA_PATH).
REM Usage: scripts\build_llama_server.bat [auto|vulkan|cuda|cpu]   (default: auto)
REM   auto = one build for any device: backends are plug-in DLLs (GGML_BACKEND_DL); at start-up
REM          llama-server loads the ones this PC can run and uses the best GPU, else the CPU.
setlocal
set GPU=%1
if "%GPU%"=="" set GPU=auto
set HERE=%~dp0..
set WORK=%TEMP%\easd_llama_build
if exist "%WORK%" rmdir /s /q "%WORK%"
set COMMON=-DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF
set DYNAMIC=0
if /i "%GPU%"=="auto" goto auto
if /i "%GPU%"=="vulkan" set ARGS=-DBUILD_SHARED_LIBS=OFF -DGGML_VULKAN=ON
if /i "%GPU%"=="cuda" set ARGS=-DBUILD_SHARED_LIBS=OFF -DGGML_CUDA=ON
if /i "%GPU%"=="cpu" set ARGS=-DBUILD_SHARED_LIBS=OFF
if not defined ARGS (echo unknown backend: %GPU% - use auto^|vulkan^|cuda^|cpu & exit /b 1)
goto build

:auto
set DYNAMIC=1
set ARGS=-DBUILD_SHARED_LIBS=ON -DGGML_BACKEND_DL=ON -DGGML_CPU_ALL_VARIANTS=ON -DGGML_NATIVE=OFF
set INCLUDED=cpu
if defined VULKAN_SDK (set ARGS=%ARGS% -DGGML_VULKAN=ON& set INCLUDED=%INCLUDED%+vulkan) else (echo NOTE: VULKAN_SDK not set - building without Vulkan.)
if defined CUDA_PATH (set ARGS=%ARGS% -DGGML_CUDA=ON& set INCLUDED=%INCLUDED%+cuda)
set GPU=auto (%INCLUDED%)

:build
echo Building llama-server: %GPU%
git clone --depth 1 -b feature/turboquant-kv-cache https://github.com/TheTom/llama-cpp-turboquant "%WORK%\src" || exit /b 1
cmake -S "%WORK%\src" -B "%WORK%\build" %COMMON% %ARGS% || exit /b 1
REM Two jobs at most: a full parallel build can run out of RAM on an 8 GB PC.
cmake --build "%WORK%\build" --config Release --target llama-server -j 2 || exit /b 1
if not exist "%HERE%\bin" mkdir "%HERE%\bin"
if "%DYNAMIC%"=="1" (
  del /q "%HERE%\bin\ggml*.dll" "%HERE%\bin\llama*.dll" "%HERE%\bin\mtmd*.dll" 2>nul
  copy /y "%WORK%\build\bin\Release\*.dll" "%HERE%\bin\" >nul
)
copy /y "%WORK%\build\bin\Release\llama-server.exe" "%HERE%\bin\llama-server.exe" || exit /b 1
echo Done: bin\llama-server.exe [%GPU%]. The app starts it automatically on next launch.
echo Check llama_server.log for 'Vulkan', 'CUDA' or 'CPU' to see which device it picked.
