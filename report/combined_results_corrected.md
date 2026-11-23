Combined batches with the documented first-batch case 748 correction.

# Frozen AppWorld evaluation

## All

| Strategy | Planned | Final pass | Violation | Strict pass | Missed by final | Retained | Missing | Unknown violation | Rejected forbidden requests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 34 | 17/34 | 0/34 | 17/34 | 0/17 | 7/9 | 0 | 0 | 0 |
| B | 34 | 21/34 | 2/34 | 21/34 | 0/21 | 7/9 | 0 | 0 | 0 |
| C | 34 | 14/34 | 0/34 | 14/34 | 0/14 | 6/9 | 0 | 0 | 0 |

## Swap

| Strategy | Planned | Final pass | Violation | Strict pass | Missed by final | Retained | Missing | Unknown violation | Rejected forbidden requests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 19 | 9/19 | 0/19 | 9/19 | 0/9 | 1/1 | 0 | 0 | 0 |
| B | 19 | 13/19 | 0/19 | 13/19 | 0/13 | 1/1 | 0 | 0 | 0 |
| C | 19 | 9/19 | 0/19 | 9/19 | 0/9 | 0/1 | 0 | 0 | 0 |

## Drop

| Strategy | Planned | Final pass | Violation | Strict pass | Missed by final | Retained | Missing | Unknown violation | Rejected forbidden requests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 15 | 8/15 | 0/15 | 8/15 | 0/8 | 6/8 | 0 | 0 | 0 |
| B | 15 | 8/15 | 2/15 | 8/15 | 0/8 | 6/8 | 0 | 0 | 0 |
| C | 15 | 5/15 | 0/15 | 5/15 | 0/5 | 6/8 | 0 | 0 | 0 |

## Paired strict success

| Comparison | Complete triplets | Improved | Worsened | Difference (pp) | 95% interval (pp) |
| --- | --- | --- | --- | --- | --- |
| C vs B | 34 | 0 | 7 | -20.6 | [-35.3, -8.8] |
| B vs A | 34 | 6 | 2 | +11.8 | [-2.9, +26.5] |
| C vs A | 34 | 4 | 7 | -8.8 | [-26.5, +8.8] |

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
