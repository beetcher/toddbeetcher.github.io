# PLAN-R5: READY question library, judgment and critical thinking — draft content

Category slug: `judgment`. Folders: `ready/seed/library_judgment/`, `ready/docs/library_judgment/`, test file `ready/tests/test_seed_library_judgment.py`, report `ready/docs/reports/PLAN-R5-report.md`. Batch labels `ready_lib_judgment_01`...

**Read `ready/docs/plans/READY-LIBRARY-COMMON.md` first. It applies in full.** The rest of this file is only what is specific to this category.

## The design problem (think about this first)
Judgment and critical thinking do not have a single answer key. A good pool needs a different shape than trivia. Use this approach, and record your reasoning in `ready/docs/library_judgment/JUDGMENT-DESIGN.md` before writing items (one to two pages: the approach, why it fits READY's roles, and its limits):

1. **Situational items.** Each question is a short, realistic scenario with competing considerations (a workplace decision, a claim someone brings you, a messy set of facts). Responses are courses of action or interpretations.
2. **READY's three roles are the point.** `strong` = the most defensible response and why; `ambiguous` = a reasonable response with a real trade-off or a hidden cost (explain it, do not punish it harshly); `incorrect` = clearly worse (acts on bad evidence, skips an obvious check, reasoning error). Many items should include an ambiguous option that reveals how the person weighs trade-offs.
3. **Use `multiple_choice` for "choose the two best responses" and ranking-like items**, and `single_choice` for "most defensible".
4. **Difficulty is about ambiguity and number of competing considerations, not vocabulary or domain knowledge.** Introductory = one clear consideration; expert = several competing, incomplete or conflicting pieces of information. No item should require specialist knowledge.
5. **Tag by skill** so tests can be assembled per skill later.

## Skill families (use as topics/tags; 8 to 12 learning objectives)
evaluating sources and evidence; separating claim, evidence and assumption; correlation vs. causation; reasoning about probability and base rates in plain terms (no formulas); recognizing common reasoning errors (named by function in feedback, not jargon only: for example circular reasoning, cherry-picking, false dilemma, appeal to authority); cognitive biases in decisions (anchoring, sunk cost, confirmation bias, overconfidence); decisions under uncertainty and incomplete information; weighing trade-offs and second-order effects; ethical judgment in ordinary workplace situations; asking good questions and noticing missing information; updating a view when evidence changes; knowing when to escalate, slow down or ask for help; evaluating AI-generated or persuasive content.

## Audiences (suggested)
`teen_9_12`, `college_student`, `early_career_professional`, `team_lead_or_manager`, `general_adult`.

## Category-specific content rules
- **No political, religious, partisan or culture-war scenarios.** No scenarios that depend on one country's or culture's norms. Prefer everyday and workplace settings with invented, neutral details.
- No item may reward a particular ideology, personality type or social background. The reasoning in the feedback must hold for a reasonable person from any background.
- Do not claim to measure intelligence, honesty or future job performance. This is practice and discussion material, not a validated psychometric instrument. State this in JUDGMENT-DESIGN.md and each record's `origin.notes` (one short sentence).
- Do not copy or imitate the items of published instruments (for example commercial critical-thinking appraisals). Write original scenarios.
- Feedback explains the reasoning in plain language: what the person would be weighing, why the strong response holds up, what each other option costs, and what you could do to resolve the uncertainty. Keep a tone of curiosity, never "gotcha".
- At every level include items where the right move is to ask for more information or to delay the decision.
- Include a good share of items using the same scenario with different decision points, so one scenario can serve different skills and audiences.
- Self-review extra check: for every item, would two thoughtful people disagree about the `strong` answer? If yes, fix the item or move the contested option to `ambiguous`.
