Second batch only.

# Frozen AppWorld evaluation

## All

| Strategy | Planned | Final pass | Violation | Strict pass | Missed by final | Retained | Missing | Unknown violation | Rejected forbidden requests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 21 | 10/21 | 0/21 | 10/21 | 0/10 | 2/2 | 0 | 0 | 0 |
| B | 21 | 13/21 | 1/21 | 13/21 | 0/13 | 2/2 | 0 | 0 | 0 |
| C | 21 | 8/21 | 0/21 | 8/21 | 0/8 | 2/2 | 0 | 0 | 0 |

## Swap

| Strategy | Planned | Final pass | Violation | Strict pass | Missed by final | Retained | Missing | Unknown violation | Rejected forbidden requests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 15 | 7/15 | 0/15 | 7/15 | 0/7 | N/A | 0 | 0 | 0 |
| B | 15 | 10/15 | 0/15 | 10/15 | 0/10 | N/A | 0 | 0 | 0 |
| C | 15 | 7/15 | 0/15 | 7/15 | 0/7 | N/A | 0 | 0 | 0 |

## Drop

| Strategy | Planned | Final pass | Violation | Strict pass | Missed by final | Retained | Missing | Unknown violation | Rejected forbidden requests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 6 | 3/6 | 0/6 | 3/6 | 0/3 | 2/2 | 0 | 0 | 0 |
| B | 6 | 3/6 | 1/6 | 3/6 | 0/3 | 2/2 | 0 | 0 | 0 |
| C | 6 | 1/6 | 0/6 | 1/6 | 0/1 | 2/2 | 0 | 0 | 0 |

## Paired strict success

| Comparison | Complete triplets | Improved | Worsened | Difference (pp) | 95% interval (pp) |
| --- | --- | --- | --- | --- | --- |
| C vs B | 21 | 0 | 5 | -23.8 | [-42.9, -4.8] |
| B vs A | 21 | 5 | 2 | +14.3 | [-9.5, +38.1] |
| C vs A | 21 | 3 | 5 | -9.5 | [-38.1, +14.3] |

## API usage

| Stage | Settled calls | Input tokens | Output tokens | Conservative USD |
| --- | --- | --- | --- | --- |
| screen-v1 | 335 | 2259287 | 38498 | 0.723984 |
| formal-v1 C | 31 | 140927 | 2438 | 0.045204 |
| formal-v1 A | 21 | 103283 | 2369 | 0.033828 |
| formal-v1 B | 36 | 151950 | 2195 | 0.048219 |
| expansion-screen-v1 | 341 | 1861824 | 36330 | 0.602143 |
| formal-expansion-v1 C | 57 | 328847 | 5119 | 0.112080 |
| formal-expansion-v1 B | 64 | 372232 | 5985 | 0.118852 |
| formal-expansion-v1 A | 43 | 276188 | 5552 | 0.089519 |

Intervals resample task families. With a small or constant sample they can be uninformative. Counts exclude missing and indeterminate values from their applicable denominators.
