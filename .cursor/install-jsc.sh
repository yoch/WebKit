#!/usr/bin/env bash
#
# Cloud Agent install script for the WebKit JSCOnly (JavaScriptCore) port.
#
# Installs the system packages required to configure and build the JSCOnly
# port with `Tools/Scripts/build-webkit --jsc-only`, then runs a release
# build so the environment is immediately usable.
#
# This script is idempotent: apt-get install is a no-op when packages are
# already present, and the WebKit build system performs an incremental
# (ninja) rebuild on repeated runs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ---------------------------------------------------------------------------
# 1. System dependencies
# ---------------------------------------------------------------------------
# JSCOnly uses the "Generic" event loop, so it needs no GLib/GTK stack. The
# dependency set is limited to build tooling, the Clang toolchain (with the
# matching libstdc++ development files that Clang's default GCC toolchain
# links against) and ICU.
PACKAGES=(
    bison
    ccache
    clang-20
    cmake
    flex
    g++
    gperf
    libc++-20-dev
    libc++abi-20-dev
    libicu-dev
    lld-20
    ninja-build
    perl
    python3
    ruby
    unifdef
)

export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends "${PACKAGES[@]}"

# ---------------------------------------------------------------------------
# 2. Build the JSCOnly port (release)
# ---------------------------------------------------------------------------
# ccache keeps incremental/fresh builds fast; the build itself is incremental
# on repeat runs thanks to ninja.
export CCACHE_DIR="${CCACHE_DIR:-${HOME}/.ccache}"

# Notes on the build flags:
#   * CMAKE_C/CXX_COMPILER=clang-20: build with Clang 20 (WebKit's Linux/Clang
#     toolchain baseline). Ubuntu 24.04's default Clang 18 is too old.
#   * -stdlib=libc++: WebKit's Clang/Linux build targets LLVM libc++. Building
#     against GNU libstdc++ triggers a std::function/concepts miscompile
#     ("exception specification uses itself") in WTF's Invocable concept.
#   * DEVELOPER_MODE_FATAL_WARNINGS=OFF: don't promote warnings from a
#     non-SDK compiler to hard errors via -Werror.
#   * --makeargs="jsc": build only the `jsc` application (and its dependencies).
#     The API-test targets (TestWTF/TestWebKitAPI) are not required to run the
#     engine and currently fail to compile on this tree (a WTF private header is
#     not forwarded into the API-test header map), so they are excluded here.
cd "${REPO_ROOT}"
Tools/Scripts/build-webkit --jsc-only --release \
    --cmakeargs="-DCMAKE_C_COMPILER=clang-20 -DCMAKE_CXX_COMPILER=clang++-20 -DDEVELOPER_MODE_FATAL_WARNINGS=OFF -DCMAKE_CXX_FLAGS=-stdlib=libc++ -DCMAKE_EXE_LINKER_FLAGS=-stdlib=libc++ -DCMAKE_SHARED_LINKER_FLAGS=-stdlib=libc++ -DCMAKE_MODULE_LINKER_FLAGS=-stdlib=libc++" \
    --makeargs="jsc"

echo "JSCOnly build complete. The 'jsc' shell is at:"
echo "  ${REPO_ROOT}/WebKitBuild/JSCOnly/Release/bin/jsc"
