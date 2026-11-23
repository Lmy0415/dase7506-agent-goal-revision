# Sensitivity analysis for a Gmail model name

In case 748 the upstream evaluator refers to `gmail.EmailAttachment`, while the pinned AppWorld model is `gmail.Attachment`. This secondary analysis changes that name in both assertions and regrades all saved final states. The primary frozen table and model traces are preserved. No model calls are made.

# Frozen AppWorld evaluation

## All

| Strategy | Planned | Final pass | Violation | Strict pass | Missed by final | Retained | Missing | Unknown violation | Rejected forbidden requests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 13 | 7/13 | 0/13 | 7/13 | 0/7 | 5/7 | 0 | 0 | 0 |
| B | 13 | 8/13 | 1/13 | 8/13 | 0/8 | 5/7 | 0 | 0 | 0 |
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
| A | 9 | 5/9 | 0/9 | 5/9 | 0/5 | 4/6 | 0 | 0 | 0 |
| B | 9 | 5/9 | 1/9 | 5/9 | 0/5 | 4/6 | 0 | 0 | 0 |
| C | 9 | 4/9 | 0/9 | 4/9 | 0/4 | 4/6 | 0 | 0 | 0 |

## Paired strict success

| Comparison | Complete triplets | Improved | Worsened | Difference (pp) | 95% interval (pp) |
| --- | --- | --- | --- | --- | --- |
| C vs B | 13 | 0 | 2 | -15.4 | [-38.5, +0.0] |
| B vs A | 13 | 1 | 0 | +7.7 | [+0.0, +23.1] |
| C vs A | 13 | 1 | 2 | -7.7 | [-30.8, +15.4] |

## API usage

| Stage | Settled calls | Input tokens | Output tokens | Conservative USD |
| --- | --- | --- | --- | --- |
| screen-v1 | 335 | 2259287 | 38498 | 0.723984 |
| formal-v1 C | 31 | 140927 | 2438 | 0.045204 |
| formal-v1 A | 21 | 103283 | 2369 | 0.033828 |
| formal-v1 B | 36 | 151950 | 2195 | 0.048219 |

Intervals resample task families. With a small or constant sample they can be uninformative. Counts exclude missing and indeterminate values from their applicable denominators.
