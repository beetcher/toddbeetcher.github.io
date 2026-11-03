# Reading the U.S. geography sample (one page)

Open `ready/seed/library_us_geography/us_geography_sample_01.json`. It has 8 questions, 33 answers and 10 sets. Everything is `draft` and nothing is imported anywhere.

## The three kinds of record
- **Question atom**: the stem only, for example "California has a long coast on the western edge of the country. Which ocean is it on?"
- **Answer atom**: one piece of answer text with no right or wrong attached.
- **Set**: one question plus 4 offered answers, for one age band (`audiences`) and one depth (`difficulty`). The role (strong, ambiguous, incorrect) and the teaching feedback live on each offered answer inside the set, never on the atom.

## What each role means
- `strong`: the best answer in this context. Single-choice sets have exactly one. Select-all sets have at least two.
- `ambiguous`: a defensible answer where usage or convention differs. The feedback names the difference, and the connection has an editor note saying why it is ambiguous.
- `incorrect`: a plausible mistake. The feedback says why it fails and what to try instead.

## Things to look for
1. **One answer, two roles.** `g1_a_atlantic_ocean` is **incorrect** for California's coast and **strong** for the Georgia and Florida coast. Pacific Ocean does the reverse.
2. **One question, two sets for different bands.** "Which city is the capital of the state of Washington...?" is offered to grades 3 to 5 and to grades 6 to 8, with different feedback and one different distractor. The rain-shadow question is offered to grades 9 to 12 and to general adults, with different wording of the answers.
3. **Both question types.** `borders_lower48` and `small_capitals` are select-all; the rest are single choice.
4. **Levels and bands.** introductory, basic and intermediate; grades 3 to 5, 6 to 8, 9 to 12 and general adult.
5. **Ambiguous in practice.** The Texas region question names the Census Bureau's four regions. "Southwest" is a real, common name, so it is marked ambiguous rather than flatly wrong, with an editor note.
6. **Feedback on every choice**, written to the band: short and friendly for grades 3 to 5, rule-and-reason for older bands.

## If the voice or level is wrong
- Too hard or too easy: change `difficulty` on the set (and on the atoms that serve it), or ask for a rewrite of the stem.
- Voice: feedback is plain and direct. Tell me what to change (warmer for the youngest, more formal for adults) and the rest of the library follows.
- A disputed answer: change its role in the set, or tell me and I will change it everywhere.
- Band wrong: change the one `audiences` value on the set.
