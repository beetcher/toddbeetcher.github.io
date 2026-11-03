# Sample batch: how to review it in ten minutes

File to open: `ready/seed/library/ai_sample_01.json` (8 questions, 31 answers, 9 sets). Everything in it is **draft** material written by the READY builder. It is not an official assessment and has not been tested on real learners.

## The three layers

- **Question**: only the question text and whether it is single-choice or select-all. It has no right answer of its own.
- **Answer**: only text. It has no right or wrong of its own either.
- **Set**: one question plus 4 offered answers. The set decides what each answer *means in that context*, and carries the teaching feedback.

## What the roles mean

| Role | Meaning | Credit under the grading rule |
|---|---|---|
| `strong` | The best answer here. Single-choice sets have exactly one. Select-all sets here have two. | Full credit |
| `ambiguous` | Reasonable people could argue it either way. The feedback says why. | Half credit if chosen alone with no strong answer |
| `incorrect` | A real misconception or a poor choice. Never a joke. | No credit |

Ambiguous connections carry a short editor's note (`notes`) saying why. Learners never see the notes.

## Three ideas to look for

1. **One answer, different meanings.** *"Check the important facts against a source you trust first."* appears in three sets. It is **strong** for the statistic question, **incorrect** for the customer-spreadsheet question (a good habit, but it does not fix a privacy problem), and **ambiguous** for the bake-sale names question (names are not facts, but a quick search is still sensible). Search the file for `l01_a_check_source`.
2. **One question, two sets.** *"AI writes a clear summary... What should you do before you quote it?"* is used for an adult beginner at basic level and for a workplace reader at intermediate level. Same question, different choices and feedback. Look at `l01_s_quote_statistic_basic` and `l01_s_quote_statistic_work`.
3. **Feedback on every choice.** Each of the 36 choices explains why it works or fails and what to do instead.

## What to look at

- Is the **wording plain enough** for the audience named in the set (`audiences`)?
- Is the **level** right? The sample has one introductory, four basic and four intermediate sets. Do the intermediate ones ask for more thinking, not just longer text?
- Is the **strong answer** really the best one, and are the **ambiguous** ones really debatable?
- Any **accidental clue**: is the correct answer always the longest, or always listed in the same place?
- Would any scenario feel **sensitive, unfair, or too specialist**?
- Anything that could go **out of date**? (None of the sample names a product, price, law or date.)

## What to change if something is off

| If... | Do this |
|---|---|
| The voice is too formal or too chatty | Tell me the voice you want; I will redo the wording across all batches before more are written. |
| The level feels wrong | Say which sets. I will move the set (difficulty is stored on the set and on the atoms). |
| An ambiguous choice should be strong or incorrect | Tell me the set name (the `label` or `client_ref`). Role lives only on the set connection. |
| You dislike a scenario | Name the question. Dropping it removes its sets too. |
| You want different audiences | See `TAXONOMY.md`; audience values are free text, so adding one is a content change, not a schema change. |

## Reminder: it is still draft

Every record has `status: draft` and `dry_run: true`. The selection service only picks published records, so none of this can appear in a test until it is published on purpose. The tag `needs_owner_review` stays on every record until you approve it.
