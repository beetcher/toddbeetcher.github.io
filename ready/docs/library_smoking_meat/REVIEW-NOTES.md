# Review notes: smoking-meat library (draft)

Everything here is draft, written by the READY builder (an AI), not by a pitmaster or food-safety professional. These are the items I am least sure of, so you can spend your review time there first.

## 1. Food-safety numbers to check once (the only firm right answers)
All come from widely published US government food-safety guidance as I know it. I did not look anything up in this run. Please check each against the current official source before publishing.
- Danger zone about 40°F to 140°F (4°C to 60°C); the two-hour limit, and about one hour on a very hot day (sets `buffet_heat_basic`, `leftovers_basic`, `danger_zone_*`).
- Safe minimums: poultry 165°F; ground beef 160°F; whole cuts of pork 145°F followed by a short rest (`poultry_temp_intro`, `ground_temp_basic*`, `pork_loin_temp_intro`, `ribs_done_i`).
- Reheat chilled leftovers to 165°F; hold hot at 140°F or above (`reheat_target_*`, `hot_hold_i`).
- Ice-water test reads about 32°F; boiling water about 212°F at sea level (`thermo_check_basic`).
- Unknown time in the danger zone means discard (`cooler_drop_a`). This is deliberately conservative.
- Thawing only in the refrigerator or in cold water (`thaw_plan_intro`, `thaw_ways_intro`); not rinsing raw meat (`pat_dry_basic`).

## 2. Technique calls where I committed to one answer
I marked genuine schools of thought `ambiguous` (35 choices, each with an editor note). These I made `strong` or `incorrect` and an expert might push back:
- `wood_amount_basic` and `_enth`: "a few small pieces early" is strong. The claim that meat takes up smoke most readily early is common but not settled, so it is worded "tends to" and "keep adding wood" is ambiguous in both sets.
- `white_smoke_intermediate`, `bitter_ribs_intro`, `soot_a`: thick white smoke means a smoldering, air-starved fire. Widely taught; I believe it is right.
- `uneven_offset_i`: rotating the meat is strong and baffles are ambiguous. Some would call baffles the better answer.
- `rest_first_intro`, `rest_debate_enth`: the reason a rest helps is worded loosely ("settle", "even out"). The mechanism is debated, so I avoided stating one.
- `pork_pull_intermediate` and `ribs_done_i`: "feel decides" is strong. The low-200s figure in a feedback note is a rough guide and varies by cut.
- `spritz_i`: spritzing as a trade-off is strong; the three alternatives are marked incorrect and are overstated if someone really believes in spritzing for moisture.
- `kamado_vents_i`, `lump_briq_basic`, `first_cooker_intro`: statements about how equipment types behave. General, but cookers differ.
- `fat_trim_i`: how much fat to leave is a school; no number is given on purpose.

## 3. Wording and tone to read
- `injecting_i`: I stated the conservative principle (a needle can carry surface bacteria inward; use clean tools; cook to a safe center temperature) without a specific temperature. A food-safety reviewer may want it more specific.
- `cure_guess_*`: kept to "cured products need exact, tested recipes". No quantities anywhere.
- `flare_up_basic`: close the lid and vents. It assumes a charcoal cooker, as the stem says. For a large or spreading fire the feedback tells the learner to step back and call for help.
- `ash_disposal_*`: letting coals cool fully is strong; soaking in a metal bucket is ambiguous because practice varies.
- `kids_zone_basic`, `overnight_i`, `canopy_a`: safety-judgment items. Check that the "never unattended" wording matches how you would actually teach it.

## 4. Known weaknesses in the draft
- **Option length.** I fixed every set where the strong answer was clearly the longest (a test now enforces "not more than 1.25 times the next longest"). In 44 of the 76 single-choice sets the strong answer is still the longest option, though by a small margin. That is still a mild tell. If you adopt this library, a rewrite pass for length would help.
- **Distractors in the long-answer sets** (`hot_fast_*`, `cooker_business_pro`, `rest_debate_enth`) were padded to match the length of the best answer, so a few read a little stiff.
- **Select-all sets** are 11 of 78. Good, but many single-choice sets have only one plausible-sounding wrong answer next to two obvious ones.
- **Audience balance.** Host (14 sets) and competitor/caterer (15) have fewer sets than beginner (22) and enthusiast (27).
- **Thin objectives.** `slice_and_serve_well` has 3 sets and `choose_equipment_and_fuel` has 4. `manage_fire_and_airflow` has no advanced or expert set; `produce_clean_smoke` has none at intermediate or advanced.
- **Reuse is within a file only.** A cross-file reuse would need a second import path. 58 of 253 answer atoms in the main library appear in two sets; 6 carry different roles in different sets.
- **Stems at expert level** lean toward teaching, process and trade-off reasoning; there is little on pure technique at that level.

## 5. Things left out on purpose
- No brand names, prices, rankings or statistics (a test scans for common ones).
- No curing quantities, no canning, no raw-milk or similar topics, no fish or sausage making.
- No questions that need an image, a chart or a link.
- No cooking-time tables, and no wood-by-meat pairing tables, because they are matters of taste and custom.
