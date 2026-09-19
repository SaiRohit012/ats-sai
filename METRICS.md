# Measurements and the three-bullet structure

Every displayed job has exactly three bullets. Every displayed project has exactly three bullets in this order:

1. The problem/purpose and what was built.
2. The implementation, technologies and method.
3. The achieved result, with a source-backed numerical outcome when one exists; otherwise flag the measurement gap.

The resumes retain estimates and targets as such. A targeted 60% triage reduction is not described as a measured 60% achievement. Release identifiers are not performance metrics.

## Other project evidence available in the library

| Project | Numerical claims available in the supplied sources | Source/library variants |
|---|---|---|
| Financial Fraud Signal Dashboard | Estimated 45% detection-latency reduction; >95% validation coverage | V1 and V2 |
| CampusBuddy | <200ms latency; 30% less operational overhead in V1 | V1 |
| Distributed Task Scheduler | Estimated 35% throughput improvement; zero observed race conditions at full load | V1 and V2 |

These are supplied claims, not measurements reproduced during this resume-editing task. Retain them only if you can explain the benchmark and evidence.

## Gaps kept out of achieved-results claims

- **Redwood:** the user confirmed no outcome metrics are available yet. Five architecture layers quantifies scope. Future evidence could include the actual automated-test count, regressions caught, defects resolved or measured execution-time savings.
- **PayFlow:** no throughput, latency, concurrency or test-count benchmark was supplied. Record concurrent transfer load, total requests, failures, p95 latency and double-spend observations under stated hardware/test conditions.
- **Key-value store:** no numerical resilience or throughput benchmark was supplied. Record node count, dataset size, read/write rates, node failures injected and recovery time under a specified quorum configuration.
- **RideWise:** no numerical outcome test was supplied. Record actual tested fare strategies, scenarios, coverage or extension work, with reproducible evidence.

These suggestions are a measurement plan, not completed tests or resume claims. No invented benchmark values or fabricated percentage improvements were inserted. Both default resumes select PayFlow and the Distributed Key-Value Store. The application flags their absent numerical outcomes while retaining their supported correctness results. Job relevance takes precedence over substituting a project merely because it has a percentage.
