# FRT Memory Vault — Verified Benchmark Data

> This repository publishes **measured benchmark data only** — no source code.
> All numbers below come from independently verified test runs (SHA-pinned artifacts, third-party re-judged).

## FRT Projects (with releases)

| Project | Repository | Releases |
|---|---|---|
| FRT-Everitas-AI | https://github.com/januspater630/FRT-Everitas-AI | 5 |
| FRT-CFNS | https://github.com/januspater630/FRT-CFNS | 2 |
| FRT-Cosmic-Encryption | https://github.com/januspater630/FRT-Cosmic-Encryption | 1 |
| Janus-Vault | https://github.com/januspater630/Janus-Vault | 1 |
| FRT-Memory-Vault | https://github.com/januspater630/FRT-Memory-Vault | 1 |

## Core Verified Metrics

| Metric | Value | Note |
|---|---|---|
| Compression ratio range | **3×–11×** | measured, not estimated |
| Character-level restoration | **≥99%** | lossless restoration verified |
| High-ratio boundary test point | **11.93×** | with lossless expansion preserved |
| Single real test corpus | **345 MB** | `_core_0804_0818.txt` |
| Memory/semantic segments processed | **93,544** | |
| Unique sentence-level entries | **979,069** | |

## Why This Is Not Deletion-Based Compression

Deletion-based routes lose ≥99% character fidelity at ~**2.9×** (measured: 95.59% at 2.92×).
The structured "existence/access path decoupling" route keeps **100% restoration up to 11.93×**.

| Retention R | Storage | Ratio | Trace ≥99% | Mechanism |
|---|---|---|---|---|
| 1.0 | 35.0% | 2.86× | 100% ✅ | dedup only (zero deletion) |
| 0.95 | 34.3% | 2.92× | 95.59% ❌ | delete 5% unique sentences |
| 0.75 | 31.8% | 3.14× | 89.15% ❌ | delete 25% |
| 0.50 | 25.8% | 3.88× | 86.44% ❌ | delete 50% |
| 0.20 | 6.6% | 15.1× | 29.49% ❌ | delete 80% |

## Boundary Test Results (295-trace criterion, measured)

| Dict size | Storage | Ratio | Position-level recovery | Traces 100% | ≥99% | 20-question compass |
|---|---|---|---|---|---|---|
| R=1.0 dedup | 35.02% | 2.86× | 1.0000 | 100% | 100% ✅ | 17/20 |
| dict 2000 | 25.73% | 3.89× | lossless | 100% | 100% ✅ | 17/20 |
| dict 4000 | 25.19% | 3.97× | lossless | 100% | 100% ✅ | 17/20 |
| dict 6000 | 24.84% | 4.03× | lossless | 100% | 100% ✅ | 17/20 |
| dict 10000 | 24.34% | 4.11× | lossless | 100% | 100% ✅ | 17/20 |
| dict 15000 | 23.94% | 4.18× | lossless | 100% | 100% ✅ | 17/20 |
| dict 25000 | 23.51% | 4.25× | lossless | 100% | 100% ✅ | 17/20 |
| dict 40000 | 23.13% | **4.32×** | **1.0000** | **100%** | **100% ✅** | 17/20 |
| dict 40000 + zlib | 8.39% | **11.93×** | **1.0000** | **100%** | **100% ✅** | 17/20 |

## Cross-Corpus Generalization (Hostile Blind Test, 2 unseen domains)

- 8 configurations across 2 never-seen domains (tool-output/search dump 30 MB + theory monograph 112 KB)
- Byte-level lossless 100% PASS + trace recovery 100% PASS on all reachable configs
- 3× tier holds (2.84×); 10× tier surpassed (25×–45×)
- 4×/5× not reachable in those domains (SCR jump) — honestly reported: ratio is a function of domain redundancy, not a dial

## How to Verify

- All artifacts are SHA-256 pinned; judges are independent of the compressor.
- Compressor input: corpus + dict-size only — zero test-target leakage.
- We welcome third-party verification. Contact us via GitHub issues.

## Contact / Partnership

Looking for partners to run joint benchmarks on real AI memory / log / text workloads.
If you care about the unit lifecycle cost of AI long-term memory — storage, copies, transfer, I/O, retrieval, context — we would love to talk.

Potential partners list: see `PARTNERS.md`.
