# InadequateCoverage per-site reoptimization — research notes

This directory is a research harness. It is **not** an upstream WebKit patch.

The clean candidate (JSC + 3 JSTests only) lives on
`cursor/jsc-inadequate-coverage-candidate-91da`, rebased on current
WebKit/WebKit main. Do not open a PR against WebKit/WebKit from this
work.

## Snapshot vs HEAD

| Label | SHA | Notes |
| --- | --- | --- |
| Historical origin/main (pass 1) | `5549b3663c5d3904eab780389cd14c58523d1dfa` | Numbers in yoch/WebKit#2/#3 |
| Historical candidate (pass 1) | `f499cf9144fb769e6906061fa4314cfeb27f483f` | Reused FromLoop; Map-based test |
| Historical harness (pass 1) | `a4cd9ebcd3085203e3313804fbfd65f14906fa0d` | Global 1/5/100 sweep only |
| Pass 2 upstream | `3a999a1a45ed3cf451677c24ee47f18bd3ce7e65` | Design B; default briefly 3 |
| Audit-cited HEAD | `c9d5b3f137ca209ef6ec4cd79dc1856377e5f4dd` | Policy files unchanged |
| **Current upstream main** | resolve at run time (`git fetch` `--depth=1`) | Closure rebase target |

JSC policy files (`OptionsList` reopt knobs, `handleExitCounts`,
`handleExitCounts` stub) were unchanged from `3a999a1a` through the
closure rebase HEAD. Do not rewrite pass-1 or pass-2 numbers as if
they were measured on a later SHA.

## Toolchain (both baseline and candidate)

- Ubuntu clang 18.1.3 + libc++ (`-stdlib=libc++`)
- `Tools/Scripts/build-webkit --jsc-only --release`
- cmakeargs: `CMAKE_C_COMPILER=clang-18`, `CMAKE_CXX_COMPILER=clang++-18`, `DEVELOPER_MODE_FATAL_WARNINGS=OFF`, libc++ on CXX/EXE/SHARED/MODULE flags
- `--makeargs="-j4 jsc"`
- Isolated baseline: `/tmp/ic-research-v2/baseline` (RPATH patched)

## Design under test

**Design B** (this branch): dedicated
`osrExitCountForReoptimizationFromInadequateCoverage` (default **5**,
conservative closure choice — see `CLOSURE-RESULTS.md`) with the same
`adjustedExitCountThreshold` / retry doubling as the existing counters.
The helper multiplies by `codeTypeThresholdMultiplier()` like the
generic and FromLoop helpers (Eval ×10, Function/Program ×1).

**Design A** (pass 1): reuse `exitCountThresholdForReoptimizationFromLoop()`.
Simulated here by setting the dedicated option equal to FromLoop, and refuted
as a *coupling* by the FromLoop=100 / dedicated=5 vs dedicated=100 / FromLoop=5
matrix.

Pass 2 briefly proposed default 3 as "first value that survives 32×1/×2/×3".
That argument is an overfit and is withdrawn. 5 is retained because a
durable phase change is flat across t=3..6 while 5 resists 5-then-never
and rare spaced hits better. Not because FromLoop is 5.

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

Do **not** pass `--osrExitCountForReoptimizationFromInadequateCoverage`
in the tests: unpatched JSC with `--validateOptions=true` dies on the
unknown option (exit 134).
