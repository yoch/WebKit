# Environment (research start)

Recorded before experiments on 2026-08-26. Performance binaries are
**not** the same SHA as the source notes; both are listed.

| Item | Value |
| --- | --- |
| Research branch | `cursor/jsc-profile-maturity-91da` |
| Fork PR | https://github.com/yoch/WebKit/pull/6 |
| Source notes / branch base (upstream `main`) | `cab391584f801d18cde18093204d9b980964ca80` (2026-08-26) |
| Fork `origin/main` | `5549b3663c5d3904eab780389cd14c58523d1dfa` (stale vs upstream; **not** used as base) |
| Parked per-site IC candidate | `e01f57903d9e389b5651a167db7c519244f45842` (not present on this branch) |
| Unpatched `jsc` used for FMS matrices | `/tmp/ic-research-v2/unpatched-f05/bin/jsc` |
| Unpatched `libJavaScriptCore` SHA-256 | `c54efc1645a0fbdabe8d0eb7966e4b57f2efcf4a88f686ca5a3291eabd6642b1` |
| Unpatched binary provenance | built 2026-08-25 from `cursor/jsc-inadequate-coverage-v2-91da` @ `3a999a1a45ed` (Release, clang-18, libc++) |
| FrozenMiniSearch | `e07e4d98adfd7d4004c6df975ba3dab42e0292b6` (`/tmp/fms-issue4`) |
| Node (issue version) | v26.7.0 official linux-x64, V8 `14.6.202.34-node.28` at `/tmp/node-26/node-v26.7.0-linux-x64/bin/node` |
| d8 | V8 15.4.61 via `~/.jsvu/bin/v8` |
| Bun | `1.4.1-canary.1+11fb73032` (`1.4.1` CLI) |
| Toolchain | Ubuntu clang 18.1.3, x86_64, 4 CPUs |
| CPU | Intel Xeon, 4 cores, 1 thread/core |
| OS | Linux 6.12.94+, Ubuntu 24.04 |
| Bundle SHA-256 `M.js` (`issue4-multi-only` history) | `5cc070fb385b26294909c48c61f296a531deba16fb80d403aacab29742344b5d` |
| Bundle SHA-256 `FULL.js` (`resident-pressure`) | `020adca4a18abc4cf9c26a0000282c75352976165b43d41d34253cda417d4bef` |
| Multi fingerprint (all successful runs) | `0ebf5d2b` |

This branch is **unpatched upstream**. The parked InadequateCoverage
threshold patch is not present.

Previous research (parked, do not reuse as truth): yoch/WebKit PRs #4/#5
and FrozenMiniSearch PRs #11–#14. Causal V8 pretenuring write-up:
`cursor/jsc-inadequate-coverage-v2-91da`
`Tools/InadequateCoverageResearch/ISSUE4-CAUSAL-RESULTS.md`.
This report **re-measures** the history matrix at n=30 and the
no-pretenuring ablation at n=30; it does not copy those older numbers
as source of truth.
