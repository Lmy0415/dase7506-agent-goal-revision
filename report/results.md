# Frozen AppWorld evaluation

## All

| Strategy | Planned | Final pass | Violation | Strict pass | Missed by final | Retained | Missing | Unknown violation | Rejected forbidden requests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 13 | 6/13 | 0/13 | 6/13 | 0/6 | 5/7 | 0 | 0 | 0 |
| B | 13 | 7/13 | 1/13 | 7/13 | 0/7 | 5/7 | 0 | 0 | 0 |
| C | 13 | 6/13 | 0/13 | 6/13 | 0/6 | 4/7 | 0 | 0 | 0 |

## Swap

| Strategy | Planned | Final pass | Violation | Strict pass | Missed by final | Retained | Missing | Unknown violation | Rejected forbidden requests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 4 | 2/4 | 0/4 | 2/4 | 0/2 | 1/1 | 0 | 0 | 0 |
| B | 4 | 3/4 | 0/4 | 3/4 | 0/3 | 1/1 | 0 | 0 | 0 |
| C | 4 | 2/4 | 0/4 | 2/4 | 0/2 | 0/1 | 0 | 0 | 0 |

## Drop

| Strategy | Planned | Final pass | Violation | Strict pass | Missed by final | Retained | Missing | Unknown violation | Rejected forbidden requests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 9 | 4/9 | 0/9 | 4/9 | 0/4 | 4/6 | 0 | 0 | 0 |
| B | 9 | 4/9 | 1/9 | 4/9 | 0/4 | 4/6 | 0 | 0 | 0 |
| C | 9 | 4/9 | 0/9 | 4/9 | 0/4 | 4/6 | 0 | 0 | 0 |

## Paired strict success

| Comparison | Complete triplets | Improved | Worsened | Difference (pp) | 95% interval (pp) |
| --- | --- | --- | --- | --- | --- |
| C vs B | 13 | 0 | 1 | -7.7 | [-23.1, +0.0] |
| B vs A | 13 | 1 | 0 | +7.7 | [+0.0, +23.1] |
| C vs A | 13 | 1 | 1 | +0.0 | [-23.1, +23.1] |

## API usage

| Stage | Settled calls | Input tokens | Output tokens | Conservative USD |
| --- | --- | --- | --- | --- |
| screen-v1 | 335 | 2259287 | 38498 | 0.723984 |
| formal-v1 C | 31 | 140927 | 2438 | 0.045204 |
| formal-v1 A | 21 | 103283 | 2369 | 0.033828 |
| formal-v1 B | 36 | 151950 | 2195 | 0.048219 |

Intervals resample task families. With a small or constant sample they can be uninformative. Counts exclude missing and indeterminate values from their applicable denominators.
