# Environment (research start)

Recorded before experiments on 2026-08-26.

| Item | Value |
| --- | --- |
| Research branch | `cursor/jsc-profile-maturity-91da` |
| Upstream WebKit `main` | `cab391584f801d18cde18093204d9b980964ca80` (2026-08-26) |
| Fork `origin/main` | `5549b3663c5d3904eab780389cd14c58523d1dfa` (stale vs upstream; not used as base) |
| Parked per-site IC candidate | `e01f57903d9e389b5651a167db7c519244f45842` |
| FrozenMiniSearch issue-4 base | `e07e4d98adfd7d4004c6df975ba3dab42e0292b6` |
| Node | v26.7.0 official linux-x64, V8 `14.6.202.34-node.28` |
| Bun | `1.4.1-canary.1+11fb73032` |
| Toolchain | Ubuntu clang 18.1.3, x86_64, 4 CPUs |
| OS | Linux 6.12, Ubuntu 24.04 |
| Bundle SHA-256 `issue4-multi-only.js` | `aa36b88cf62c0a8be2bae0fd69a480d57ef4e053af1a89160e10c4607d1e6eb4` |
| Bundle SHA-256 `resident-pressure.js` | `020adca4a18abc4cf9c26a0000282c75352976165b43d41d34253cda417d4bef` |
| Fingerprint | `0ebf5d2b` |

This branch is **unpatched upstream**. The parked InadequateCoverage threshold patch is not present.

Previous research (parked, do not reuse as truth): yoch/WebKit PRs #4/#5 and FrozenMiniSearch PRs #11–#14.
