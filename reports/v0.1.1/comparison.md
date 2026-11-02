# v0.1.0 / v0.1.1 controlled comparison

Same explicit corpus, environment and harness. Original v0.1.0 reports remain untouched.

| Cohort | v0.1.0 success | v0.1.1 success | old p50/p95 ms | new p50/p95 ms |
|---|---:|---:|---:|---:|
| cold | 79/80 | 80/80 | 12.054/121.935 | 14.565/25.890 |
| boundary | 45/48 | 48/48 | 16.743/109.294 | 17.870/26.969 |
| singular | 24/24 | 24/24 | 16.693/22.175 | 19.830/25.531 |
| unreachable | 24/24 | 24/24 | 401.655/884.487 | 0.015/0.017 |

Unreachable success means rejection, not an IK solution.
The extra geometric enumeration adds median overhead; singular-case latency is not
improved in this run. The improvement is branch reliability and tail/unreachable latency,
not a claim that every case became faster. Simulator position quantization can yield
zero reported differences; this does not imply infinite physical accuracy.

## Failures retained and explained

- Case 12 (cold): `IK rejected after 8 attempts; best position=0.0119647 m, orientation=0.00808771 rad`. New success=True, attempts=2. The original starts hit local minima/boundary branches; geometry-derived branches provide a validated alternative.
- Case 81 (boundary): `IK rejected after 8 attempts; best position=0.00277184 m, orientation=0.00668687 rad`. New success=True, attempts=2. The original starts hit local minima/boundary branches; geometry-derived branches provide a validated alternative.
- Case 83 (boundary): `IK rejected after 8 attempts; best position=0.0853471 m, orientation=0.178582 rad`. New success=True, attempts=2. The original starts hit local minima/boundary branches; geometry-derived branches provide a validated alternative.
- Case 98 (boundary): `IK rejected after 8 attempts; best position=0.0112217 m, orientation=0.0570782 rad`. New success=True, attempts=2. The original starts hit local minima/boundary branches; geometry-derived branches provide a validated alternative.

The user-supplied historical 79/80 and 45/48 rates had no attached case identities.
This new frozen corpus independently reproduces those rates; identical original cases
are not asserted. Explicit target data and hashes make this comparison replayable.

## Safety and resources

| Metric | v0.1.0 | v0.1.1 |
|---|---:|---:|
| Misses versus dense discrete reference | 0 | 0 |
| Atomic rejection pose changes | 0 | 0 |
| Fail-closed stress rejections | 0 | 1000 |
| Peak traced bytes | 103105 | 33820 |
| Stress RSS growth bytes | 442368 | 151552 |
| Rejection p95 ms | 0.018505024490877982 | 0.022799940779805183 |

Legacy oversized allocation calls were intercepted by the audit harness before
allocation; its memory/timing figures do not represent a real OOM run. v0.1.1 uses
normal production rejection. Both reports retain the intervention count.
Dense reference resolution is 0.0005 rad, not continuous collision ground truth.
RSS includes allocator/cache effects; traced allocations and RSS are reported separately.
