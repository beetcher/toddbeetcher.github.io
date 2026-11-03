# READY AI library: review notes (where I am least sure)

Read these first. Everything is draft. I reviewed it twice myself as a strict subject editor and a reading-level editor, and fixed what I found (list at the end), but I am a system, not a person who has taught this, and nobody else has read it. Set names below are the part after `_s_` in the set's `client_ref`, with the file number in front (for example `l04` is `ai_lib_04_intermediate.json`).

## 1. Roles you should re-judge (ambiguous choices)

There are 40 ambiguous choices in the main library, in 38 sets. Each carries an editor's note. The ones I trust least, because a reasonable teacher might call them strong or incorrect:

| Set | Choice | Why I am unsure |
|---|---|---|
| l04 `stats_edu` | "Confirm the claim in a second, independent source" | Many would call this strong. I marked it ambiguous because the strong choice is more specific. |
| l04 `transcript` | "Use only a tool your workplace has approved..." and "Find out your workplace rules..." | Both are defensible best answers in a workplace with strict rules. Two ambiguous choices in one set may be too many. |
| l03 `studyplan` | "Share it with a teacher..." | Probably a good answer; the ambiguity is weak. |
| l03 `pasted` | "Check what your workplace allows..." | Same as above. |
| l05 `deadline_set` | "Refuse to send anything until every line has been verified" | Could be correct if the document is high-stakes. |
| l05 `budget` | "Summarizing each department's written proposal" | Whether this must stay human depends on how much weight a summary carries. |
| l06 `triage` | "How long the task takes by hand" | A real factor; I say it should not weigh most. |
| l06 `smallteam` | "A risk-based plan also works" | I rank full review above it at this size; an expert might not. |
| l02 `too_long_set` | "Cut it down yourself" | Fine in real life; ambiguous only because the question tests asking the tool to revise. |

## 2. Statements about AI that could be argued or go stale

I avoided product names, versions, prices, dates, laws and statistics (the tests scan for them). These claims about how AI behaves are the ones I would check first:

- "Text-based AI is not a calculator, and long sums are where it can slip" (l03 `math`). Tools that call a real calculator behind the scenes could make this less true. Wording may need "on its own".
- "A tool does not necessarily look things up" (l02 `sure_set`). Some tools do search. I wrote "necessarily" to stay accurate.
- "Typing in capitals does not make the tool follow a request more closely" (l05 `skipstep`). Emphasis can sometimes matter a little. Consider softening.
- "AI tools can produce references that look real but do not exist" (l04 `halluc`, `halluc_edu`). Stable as a risk, but tools may get better at this; the advice (check every reference) stays sound.
- "Asking the same tool whether it is sure is not independent evidence" appears in several sets. I believe this is stable.
- "What it keeps depends on the tool's settings" (l02 `true_stmt`). Deliberately vague.
- l03 `bias` (the "typical nurse" picture): the lesson is stable, but it touches demographic stereotypes, which you may want to treat as a sensitive scenario.

## 3. Scenarios you may want to soften or drop

- l03 `bias` (pictures and stereotypes), l04 `grading` (a teacher using AI on student work), l04 `screen` (ranking volunteer applications), l04 `choosetask` (a warning sent to a coworker). None gives medical, legal or financial advice, and none depends on expertise to judge, but each touches people-decisions.
- l05 `rubric` (fairness of rubrics) asks the learner to test, not to judge any person.

## 4. Level calibration

- Levels were set by thinking demanded (see `TAXONOMY.md`), not tested on learners. Intermediate and advanced may overlap: several advanced sets are intermediate ideas with an added second step.
- Expert sets are conceptual (oversight design, error compounding, adoption). I have no way to know whether they are hard enough for your intended expert audience.
- Reading level was not measured with a tool. Introductory feedback sometimes uses two long sentences where one short one would do.

## 5. Gaps and balance

- Verification is over-weighted (17+ sets); `write_a_clear_request`, `choose_when_not_to_use_ai` and `improve_results_by_iterating` have only 4 to 5 sets each. See `COVERAGE.md` for the empty objective-by-level cells.
- Only four select-all questions in the main library.
- Workplace is the biggest audience (about half the sets); student and educator are thin.
- Many "incorrect" choices are clear overstatements ("Ban them from using AI", "Reject the idea"). They are plausible misconceptions to a degree, but a few are strawmen.

## 6. Reuse is weaker than hoped

- About 80% of answer atoms are used in only one set. Six atoms in the main library change role between sets (for example `check_source` is strong in one set and incorrect in another).
- Reuse only works inside a file, because import references cannot point to another file. The same sentence appears as separate atoms in files 05 and 06 (three pairs). Decide whether to merge them when importing.
- Twelve questions are placed in two or three sets for different audiences. Several of these re-placements change only one choice; I think that is honest but thin.

## 7. Mechanics to decide

- Every record is `draft`. The selection service only picks published, current records, so nothing here can reach a test yet. Publishing needs the questions, the answers and the sets to be published. I did not build a way to do that in bulk and did not change any record in any live service.
- `needs_owner_review` is on every record. Removing it after approval is a content edit, not a schema change.

## 8. What I fixed in my own review pass

- A search-and-replace slip that put homework wording into the grocery-list and recipe sets.
- Distractors that did not answer their question (for example "start from a blank request" as an answer to "who owns the correction").
- The strong answer was usually the longest choice (up to 7 of 7 sets in the first sample). I rebalanced; now it is the longest in about 24% of single-choice sets, close to chance.
- Sensitive example (a coworker's health leave) replaced by phone numbers and prices.
- British spellings ("marks", "prioritise") changed to US spelling.
- Thin feedback (some under 40 characters) expanded to say why and what to do instead.
- Two weak "ambiguous" roles changed to incorrect.
