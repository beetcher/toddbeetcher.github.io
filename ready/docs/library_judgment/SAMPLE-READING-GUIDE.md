# Reading the judgment sample (one page)

Open `ready/seed/library_judgment/judgment_sample_01.json`. It has 8 questions, 34 answers and 10 sets. Everything is `draft`; nothing is imported anywhere.

**This is practice and discussion material. It is not a validated test, does not measure intelligence, honesty or job performance, and should not be used to rank or judge people.**

## The three kinds of record
- **Question atom**: a short scenario and the question, for example the goldfish poster or the odd figure an hour before a report.
- **Answer atom**: one course of action, with no right or wrong attached.
- **Set**: one question plus 4 offered answers, for one audience and one level. The role and the teaching feedback live on each offered answer inside the set.

## What each role means here
- `strong`: the most defensible response under the facts given, with the reason.
- `ambiguous`: a reasonable response with a real cost or trade-off. The feedback names the cost; the connection carries an editor note. It is not marked as a mistake.
- `incorrect`: clearly worse: acts on weak evidence, skips an obvious check, or contains a reasoning error, which the feedback names in plain words.

## Things to look for
1. **One answer, two roles.** "Ask where the claim came from, then look for a second source" is `strong` for the goldfish poster and `ambiguous` for the report an hour from deadline, where the teammate cannot be reached.
2. **One question, several sets.** The goldfish question is offered to a teen (introductory) and to adults and college students (basic) with different distractors. The supplier-rumor question is offered to a manager and to an early-career person.
3. **Both question types.** The flagged-delivery item is "choose the TWO most defensible"; the rest are single choice.
4. **Levels.** introductory, basic and intermediate, to show that difficulty is the number of competing considerations, not vocabulary.
5. **Ask or wait.** The report and supplier items have "ask or delay" as the strong move. They are tagged `move_ask_or_delay`.
6. **Ambiguous in practice.** Holding the report, a small trial for the library question, and reporting a duplicate expense directly are all defensible; each shows a cost.
7. **Feedback on every choice**, written in a curious, not "gotcha", tone.

## If the voice or level is wrong
- Too hard or easy: change `difficulty` on the set, or ask for a rewrite of the stem.
- A strong answer you would argue with: change its role to `ambiguous` in that set (or tell me and I will change it everywhere).
- Audience wrong: change the `audiences` values on the set.
- Voice: tell me (plainer, more formal, shorter feedback) and the rest follows.
