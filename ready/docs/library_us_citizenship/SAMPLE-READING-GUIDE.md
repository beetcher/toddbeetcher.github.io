# Reading the U.S. citizenship sample (one page)

Open `ready/seed/library_us_citizenship/us_citizenship_sample_01.json`. It has 8 questions, 27 answers and 10 sets. Everything is `draft` and nothing is imported anywhere.

**This is study-practice material. It is not the official naturalization test, it is not affiliated with or endorsed by USCIS, and it is not legal or immigration advice.** No question depends on who holds an office today.

## The three kinds of record
- **Question atom**: the stem only, for example "Which part of the national government writes and passes laws?"
- **Answer atom**: one piece of answer text with no right or wrong attached.
- **Set**: one question plus 4 offered answers, for one audience and one depth (`difficulty`). The role (strong, ambiguous, incorrect) and the teaching feedback live on each offered answer inside the set, never on the atom.

## What each role means
- `strong`: the best answer in this context. A single-choice set has exactly one. A select-all set has at least two.
- `ambiguous`: a defensible answer where terms or interpretation legitimately differ. The feedback says why, and the connection carries an editor note.
- `incorrect`: a plausible mistake. The feedback says why it fails and what to try instead.

## Things to look for
1. **One answer, two roles.** `The Thirteenth Amendment` is **strong** for "Which amendment ended slavery?" and **incorrect** for "Which amendment defines citizenship and equal protection?" `The President` is incorrect for "who passes laws" and strong for "commander in chief".
2. **One question, two sets.** The supreme-law question is offered to English learners (introductory, very short feedback) and to applicants (basic, with the reason). The slavery-amendment question is offered to applicants and to tutors, with a different distractor and a teaching tip.
3. **Both question types.** `three_branches` and `first_amend` are select-all; the rest are single choice.
4. **Levels and audiences.** introductory, basic and intermediate; English learner, applicant, general adult and tutor.
5. **Ambiguous in practice.** "A republic" for a government with elected representatives is marked ambiguous, not wrong, with an editor note.
6. **Feedback on every choice**, plain and short for the English learner, with the rule and reason for the others.

## If the voice or level is wrong
- Too hard or too easy: change `difficulty` on the set, or ask for a rewrite of the stem.
- Voice: tell me what to change (simpler for English learners, more formal for tutors) and the rest of the library follows.
- A disputed answer: change its role in the set, or tell me and I will change it everywhere.
- Audience wrong: change the one `audiences` value on the set.
- Before using this with real applicants, check the current official USCIS civics test materials.
