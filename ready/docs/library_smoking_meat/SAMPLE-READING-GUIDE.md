# Reading the smoking-meat sample (one page)

Open `ready/seed/library_smoking_meat/smoking_meat_sample_01.json`. It has 9 questions, 36 answers and 10 sets. Everything is `draft` and nothing is imported anywhere.

## The three kinds of record
- **Question atom**: the stem only, for example "It is Wednesday evening. You want to smoke a frozen pork shoulder on Saturday morning..."
- **Answer atom**: one piece of answer text with no right or wrong attached.
- **Set**: one question plus 4 offered answers. The role (strong, ambiguous, incorrect) and the teaching feedback live on each offered answer inside the set, never on the atom.

## What each role means
- `strong`: the best answer in this context. Single-choice sets have exactly one. Select-all sets have at least two.
- `ambiguous`: a defensible answer where respected cooks differ (for example foil versus butcher paper, or hot-and-fast). The feedback names the trade-off, and the connection has an editor note saying why it is ambiguous.
- `incorrect`: a plausible mistake. The feedback says why it fails and what to do instead.

## Things to look for
1. **One answer, two roles.** `pull_at_safe_min` ("Take it off as soon as the thermometer shows the safe minimum for that meat") is **strong** for chicken breasts and **incorrect** for pulled pork. Same words, different context. Likewise `probe_thickest` is strong in the basic set and ambiguous in the intermediate set.
2. **One question, two sets.** "Where should the tip of the probe end up?" appears for a beginner at basic level and for a home enthusiast at intermediate level, with different offered answers.
3. **Both question types.** `leftovers` is select-all; the rest are single choice.
4. **Levels and audiences.** introductory, basic and intermediate; beginner, enthusiast and host.
5. **Feedback on every choice**, including the wrong ones.
6. **Food safety versus technique.** The thawing, leftovers, carbon monoxide and holding questions have firm answers. The stall and wrapping questions deliberately carry `ambiguous` choices.

## If the voice or level is wrong
- Too hard or too easy: change `difficulty` on the set (and on the atoms that serve it), or ask for a rewrite of the stem.
- Voice: the feedback is plain and second-person. Tell me what to change (shorter, more casual, more technical) and the rest of the library follows it.
- A disputed technique answer: change its role in the set, or tell me and I will change it everywhere.
- Audience wrong: change the one `audiences` value on the set.
