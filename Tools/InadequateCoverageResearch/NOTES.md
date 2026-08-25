# InadequateCoverage per-site reoptimization — v2 research

This directory is a research harness. It is **not** an upstream WebKit patch.

## Snapshot vs HEAD

| Label | SHA | Notes |
| --- | --- | --- |
| Historical origin/main (pass 1) | `5549b3663c5d3904eab780389cd14c58523d1dfa` | Numbers in yoch/WebKit#2/#3 |
| Historical candidate (pass 1) | `f499cf9144fb769e6906061fa4314cfeb27f483f` | Reused FromLoop; Map-based test |
| Historical harness (pass 1) | `a4cd9ebcd3085203e3313804fbfd65f14906fa0d` | Global 1/5/100 sweep only |
| **Current upstream main (pass 2)** | `3a999a1a45ed3cf451677c24ee47f18bd3ce7e65` | JSC policy files unchanged vs 5549b366 |

Do not rewrite pass-1 numbers as if they were measured on this HEAD.

## Toolchain (both baseline and candidate)

- Ubuntu clang 18.1.3 + libc++ (`-stdlib=libc++`)
- `Tools/Scripts/build-webkit --jsc-only --release`
- cmakeargs: `CMAKE_C_COMPILER=clang-18`, `CMAKE_CXX_COMPILER=clang++-18`, `DEVELOPER_MODE_FATAL_WARNINGS=OFF`, libc++ on CXX/EXE/SHARED/MODULE flags
- `--makeargs="-j4 jsc"`
- Isolated baseline: `/tmp/ic-research-v2/baseline` (RPATH patched)

## Design under test

**Design B** (this branch): dedicated
`osrExitCountForReoptimizationFromInadequateCoverage` (default **3**, after the
A–O sweep rejected 0/1/2 and failed to justify 5) with the same
`adjustedExitCountThreshold` / retry doubling as the existing counters.

**Design A** (pass 1): reuse `exitCountThresholdForReoptimizationFromLoop()`.
Simulated here by setting the dedicated option equal to FromLoop, and refuted
as a *coupling* by the FromLoop=100 / dedicated=5 vs dedicated=100 / FromLoop=5
matrix.

## load32 form

`jit.load32(&exit.m_count, GPRInfo::regT4)` is intentional.
`MacroAssemblerX86_64` / `ARM64` / `RISCV64` expose `load32(const void*, RegisterID)`
but not `load32(AbsoluteAddress, ...)`. The surrounding file uses
`AbsoluteAddress` for `add32`, which does have that overload.

## Official tests

Run via:

```
perl Tools/Scripts/run-jsc-stress-tests --jsc <jsc> JSTests/stress --filter inadequate-coverage
```
