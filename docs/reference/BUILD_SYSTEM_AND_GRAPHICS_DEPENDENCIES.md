# Build System and Graphics Dependencies — Requirements Audit

Date: 2026-11-17. Scope: decide, from evidence, whether CMake, Ninja, ANGLE, the Android NDK and Emscripten are needed by Project RETR0 now. **Outcome: nothing was installed, downloaded or reconfigured.** Every tool that a native build would need later is already on this machine.

## 1. Evidence from the project

| Check | Result |
|---|---|
| C/C++ sources, headers, `CMakeLists.txt`, `*.cmake`, `.vcxproj`, `.sln`, Makefiles, Meson files in the project (excluding `TOOLS/`, `.venv`, decompiler output, backups) | **None** |
| `06_RECONSTRUCTION/` contents | Python only: `BACKEND/cloudcell_codec/` (protocol codec) and `BACKEND/local_service/` (replacement service). `APPLICATION/` and `ASSETS/` are empty |
| Native analysis | Ghidra projects and pseudocode only (`02_NATIVE_ENGINE/`); `02_NATIVE_ENGINE/IDA/` is empty |
| Planned native work | `DECOMPILATION_PROGRESS_AUDIT.md` task 12 ("C++ physics reference reconstruction") is the first planned C++ component. It has not started and depends on tasks 9–10 |

## 2. Toolchains already installed (verified 2026-11-17)

| Tool | Version | Location | On `PATH` |
|---|---|---|---|
| CMake (Android SDK) | 3.22.1 | `%LOCALAPPDATA%\Android\Sdk\cmake\3.22.1\bin\cmake.exe` | No |
| Ninja (Android SDK) | 1.10.2 | same folder | No |
| CMake (Visual Studio 2026) | 4.1.1-msvc1 | `C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe` | No |
| Ninja (Visual Studio 2026) | 1.12.1 | `…\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe` | No |
| MSVC | 14.50.35717 (VS 2026 Community), 14.29.30133 (VS 2019 Community) | `…\VC\Tools\MSVC\` | Via VS developer shell |
| GCC (MSYS2 UCRT64) | 16.2.0 | `C:\msys64\ucrt64\bin\gcc.exe` | Yes |
| Android NDK | 26.1.10909125, 27.0.12077973, 28.2.13676358 | `%LOCALAPPDATA%\Android\Sdk\ndk\` | No |
| Emscripten (emsdk) | Not installed | — | — |
| Clang (standalone) | Not on `PATH` (the NDK ships its own) | — | — |

## 3. Original rendering architecture (evidence)

From `libRealRacing3.so` 14.0.1, both ABIs (LIEF on `02_NATIVE_ENGINE/LIBRARIES/`):

| Evidence | Finding |
|---|---|
| `DT_NEEDED` | `libGLESv2.so`, `libEGL.so` (plus libz, libandroid, liblog, libm, libdl, libc, `libc++_shared`, Nimble, FMOD Ex, fuelmetrics, ARCore) |
| Imported `gl*` functions | 142 on each ABI, all OpenGL ES 2.0-level entry points; none of the ES 3.0-only entry points checked (`glBindVertexArray`, `glTexStorage2D`, `glDrawBuffers`, `glBlitFramebuffer`, `glMapBufferRange`, …) is imported directly. ES 3.x functions may be fetched at run time through `eglGetProcAddress` (imported) — UNVERIFIED |
| Imported `egl*` functions | 3 (`eglGetDisplay`, `eglGetProcAddress`, `eglQueryString`); the context itself is created on the Java side (GL thread, `ENGINE_ARCHITECTURE.md` §5.1) |
| Vulkan | No imports, no `vk*`/`libvulkan` strings |
| Direct3D / Metal | No references |
| Shaders | 103 GLSL ES source files in `res/raw/res.zip` (`Shaders/*.vsh`, `*.fsh`, `*.xsh`); the library contains `#version 100` and `#version 300 es` and uses `GL_EXT_shader_framebuffer_fetch` |
| Engine layers | Original source directories `mt3D` (37 files) and m3g scene graph (39 RTTI types); Skia and Dear ImGui are linked statically |

**Conclusion:** RR3 renders with OpenGL ES (2.0 API surface, GLSL ES 1.00/3.00 shaders) on EGL, with no other graphics API.

## 4. Decisions

### CMake — **not required now; already installed for later**

There is no C/C++ code to build: every reconstructed component is Python, and no target needs to share native sources across platforms yet. Installing another CMake would duplicate two existing installations, and creating a root `CMakeLists.txt` or engine folders now would be placeholders with nothing to build. **Not installed. No CMake files created.**

When it becomes justified: the first native reconstruction component (planned task 12, C++ physics reference implementation with tests). At that point use the existing tools:

- Windows: Visual Studio 2026's CMake 4.1.1 + Ninja 1.12.1 + MSVC 14.50, from a VS developer shell.
- Android: the SDK's CMake 3.22.1 + Ninja with `-DCMAKE_TOOLCHAIN_FILE=%LOCALAPPDATA%\Android\Sdk\ndk\<version>\build\cmake\android.toolchain.cmake` (pick one NDK, e.g. 28.2, and record it).
- Set `cmake_minimum_required(VERSION 3.22)` so both installed CMakes can build the same project.

### Ninja — **not required now; already installed (two versions)**

Only meaningful together with CMake. Not installed separately.

### Android NDK — **not required now; already installed (3 versions)**

No Android native code is being built. It becomes relevant for an Android build of reconstructed C++ components, or for packaging a Frida Gadget build for the runtime test (runtime test plan, option C variant). Nothing to install. The three side-by-side NDKs are left untouched; choose one per build and record it.

### ANGLE — **not required; not downloaded**

- There is no reconstructed renderer, and no native code at all, for ANGLE to serve.
- ANGLE cannot make the original Android `libRealRacing3.so` run on Windows or in a browser: the binary is ARM Android code tied to Android's libc, JNI and Java GL thread.
- Browsers already provide WebGL through their own implementation (Chrome and Edge themselves use ANGLE internally), so a web build would never bundle ANGLE.

It may become useful only if a reconstructed renderer is deliberately written against the OpenGL ES API, to reuse the original GLSL ES shaders closely, and must run on Windows or macOS. ANGLE would then supply ES on top of Direct3D 11, Vulkan or Metal. That decision belongs to the rendering-reconstruction milestone, together with the alternative of targeting desktop GL or Vulkan directly, or a small abstraction library. Official source when needed: the ANGLE project (`chromium.googlesource.com/angle/angle`); prebuilt `libEGL`/`libGLESv2` also ship with Chrome and Edge.

### Emscripten — **not required; not installed**

A browser build needs a reconstructed engine in C/C++ first. Revisit after a native renderer and game loop exist and run on desktop.

## 5. Graphics abstraction layer — recommendation (not implemented)

Yes, a reconstructed renderer should sit behind a small backend-neutral interface (buffers, textures, shaders and pipelines, draw calls), because:

- the original targets only GLES, while the preservation targets differ (Windows, possibly Linux and Web); and
- it lets backends be swapped: GLES via ANGLE, desktop GL, Vulkan, or WebGL2 via Emscripten.

Do not create the proposed `06_RECONSTRUCTION/{engine,graphics,platforms}` tree yet. Create each directory when its first real component lands, starting with `engine/physics` plus tests for task 12, and add `graphics/` only when the rendering analysis (audit task 20) has produced something to implement.

## 6. Configuration changes and verification

- **Configuration changes:** none. `PATH`, Java, compiler and SDK settings are unchanged.
- **Verification:** versions above were read by running the installed binaries (`cmake --version`, `ninja --version`), from `Pkg.Revision` in each NDK's `source.properties`, from `vswhere` (Visual Studio products) and from `gcc --version`. No build was attempted, because there is nothing to build.

## 7. Summary

| Component | Required now? | Installed? | Reason |
|---|---|---|---|
| CMake | No | Already installed (3.22.1 SDK; 4.1.1 VS 2026) | No C/C++ sources; first needed for the planned C++ physics component |
| Ninja | No | Already installed (1.10.2 SDK; 1.12.1 VS 2026) | Only with CMake |
| ANGLE | No | No (deliberately) | No renderer to host; cannot run the Android binary; browsers ship their own WebGL |
| Android NDK | No | Already installed (26.1, 27.0, 28.2) | No Android native builds yet |
| Emscripten | No | No (deliberately) | No C/C++ engine to compile to WebAssembly yet |
| MSVC | No (not yet) | Already installed (14.50, 14.29) | Ready for the first Windows C++ build |
