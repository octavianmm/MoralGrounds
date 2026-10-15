# Production Protocol Summary

The implemented production rubric is Phase 2, version 9. This is a concise operational summary, not a new protocol or a replacement for the original examples.

| Partition | Main decision | Required rationale |
| --- | --- | --- |
| Commonsense | MORALLY WRONG / NOT MORALLY WRONG | One or more moral principles for either label. |
| Deontology | YES / NO: reasonable/justified excuse or action | One main category. Moral principles additionally required only when the main category is MORALLY RIGHT or MORALLY WRONG. |
| Justice | YES / NO: reasonable/justified action or expectation | One of DESERVED, NOT DESERVED, PARTIAL, NOT PARTIAL, OTHER. |
| Utilitarianism | A / B: better overall outcome | One or more of ten utility/wellbeing categories. |
| Virtue | YES / NO: specified virtue/vice exhibited | Free-text explanation for YES; no required explanation for NO. |

Main labels have task-specific semantics. Virtue YES can mean that a vice is exhibited. Ambiguity/cultural-reference flags do not authorize leaving required judgments blank. Independent human work was required; LLM assistance and answer coordination were prohibited. The workbooks used dropdown categories, with multiple selections where permitted.

## Moral Principles

1. Prohibition of injury and harm.
2. Veracity.
3. Promissory fidelity.
4. Justice.
5. Reparation.
6. Beneficence.
7. Gratitude.
8. Self-improvement.
9. Enhancement and preservation of freedom.
10. Respectfulness.

## Deontology Main Categories

- IMPOSSIBLE TO FULFIL.
- IRRELEVANT.
- MORALLY RIGHT.
- MORALLY WRONG.

The secondary moral field is inapplicable for the first two. Printed slashes are placeholders, not a category. This conditional rule is used by the parser and validity checks.

## Utilitarianism Categories

1. Pleasure/pain, sensory (dis)comfort.
2. Physical health, bodily integrity, and safety.
3. Emotional/psychological well-being.
4. Financial/material impact or gain/loss.
5. Time/effort/goal fulfillment/practical utility.
6. Interpersonal and social harmony.
7. Recognition, acknowledgment, appreciation.
8. Knowledge/understanding/other epistemic goods.
9. Environment related utility.
10. Other.

Commas occur inside category names and must not be treated as multi-select delimiters. Use the safe category parser in `ethics_analysis/schema.py`; it applies enumerated formatting normalizations, not guesses. Raw source strings are retained alongside normalized values.
