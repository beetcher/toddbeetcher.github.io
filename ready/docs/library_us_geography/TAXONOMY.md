# READY U.S. geography library: taxonomy (draft for owner review)

This is the vocabulary the U.S. geography library (plan R3) uses. It uses only what the READY schema allows today. Nothing in the schema was changed. `ready/tests/test_seed_library_us_geography.py` checks every topic, audience, objective and tag in the files against the lists on this page, because the open text fields would otherwise accept a typo silently.

## What the schema fixes and what it leaves open

| Field | Schema rule | Used here |
|---|---|---|
| `difficulty` | Closed: introductory, basic, intermediate, advanced, expert. One value per record. | All five |
| `status` | Closed: draft, published, retired | `draft` only |
| connection `role` | Closed: strong, ambiguous, incorrect | All three |
| `question_type` | Closed: single_choice, multiple_choice | Both |
| `topics`, `audiences`, `learning_objectives`, `tags` | Open lists of text | Defined below |
| `attributes` | Closed and empty | Not used |

## Audiences: the age bands

The plan's five audiences are used unchanged. The audience carries the age level; `difficulty` carries depth of thinking within it.

| Value | About | Language and context |
|---|---|---|
| `grades_3_5` | ages 8 to 10 | Short sentences, concrete nouns, friendly one or two line feedback. Everyday settings: family trips, the playground, school. |
| `grades_6_8` | ages 11 to 13 | Plain classroom vocabulary (region, hemisphere, scale). One reasoning step. Feedback names the rule and the reason. |
| `grades_9_12` | ages 14 to 18 | Course vocabulary (windward, confluence, coordinates). Two-step reasoning and cause and effect. |
| `adult_general` | adults with no special geography background | Plain adult language. Everyday uses: travel, scheduling, news, general knowledge. |
| `adult_enthusiast` | adults who enjoy maps, travel or the outdoors | Precise vocabulary. Trade-offs, nuance, and places where sources differ. |

A set names exactly one audience. A question may be placed in several sets for different audiences or levels. An answer atom's audiences are the union of the sets that offer it.

Younger bands never reuse an older band's wording: the same fact is asked again in a new way. For example the nation's capital is asked in `grades_3_5` as "What is the capital city of the United States?", and why the capital is not inside any state is asked in `adult_general`.

## What each difficulty level means

Difficulty describes the thinking asked, not the length of the text. Same length does not mean same difficulty. Each age band uses the levels it can reasonably reach, so a "basic" set for grades 3 to 5 and a "basic" set for adults are not the same test of knowledge. Filter on audience first, then difficulty.

| Level | A person at this level can... | Typical bands |
|---|---|---|
| introductory | Recognise a familiar place, feature or term. One step, one fact. | grades 3 to 5; grades 6 to 8; some adult |
| basic | Recall a standard fact and apply it once (a capital, a neighbor, a direction, a time difference). | all bands |
| intermediate | Combine two facts or explain a reason (why a place is dry, why a capital is small). | grades 6 to 8 up; adults |
| advanced | Reason across several facts, handle exact terms, and see why a plausible option fails. | grades 9 to 12; adults |
| expert | Weigh how and why sources, maps or conventions differ, and explain the reasoning. | adult enthusiast; some adult general |

## Subtopics, as topics

Every record carries the topic `us_geography`, plus one subtopic topic for each of its learning objectives. The plan's eleven subtopics became ten families: states and capitals stay together; regions and borders share one family because regions are defined by who borders whom.

| Topic value | Covers |
|---|---|
| `states_capitals` | states, capitals, why capitals are where they are, size comparisons that never change |
| `regions_borders` | the Census Bureau's four regions, other regional names, neighboring states and countries |
| `physical_features` | mountains, rivers, lakes, coasts, deserts, plains, islands, oceans |
| `map_skills` | compass directions, latitude and longitude, hemispheres, scale, contour lines, projections, reading a map described in words |
| `time_zones` | the zones of the country, clock arithmetic, split states, daylight-saving exceptions |
| `climate_biomes` | weather versus climate, elevation, rain shadow, lake-effect snow, grassland, desert and forest biomes |
| `territories_dc` | the 50 states, the District of Columbia, inhabited territories |
| `parks_landmarks` | well-known national parks, canyons, bridges and falls: stable facts only |
| `human_geography` | why cities grew where they did, ports, canals, trade routes, land use, place names, regional economies in general terms |
| `everyday_geography` | travel direction, clock changes, scheduling across zones, road numbering, planning |

## Learning objectives (10)

| # | Objective value | In plain words | Topic | Tag |
|---|---|---|---|---|
| 1 | `locate_states_and_capitals` | Know the states and their capitals, and why capitals are where they are | `states_capitals` | `skill_states_capitals` |
| 2 | `name_regions_and_neighbors` | Group states into regions and name neighbors and borders | `regions_borders` | `skill_regions_borders` |
| 3 | `identify_physical_features` | Identify mountains, rivers, lakes, coasts, deserts and plains | `physical_features` | `skill_physical_features` |
| 4 | `read_maps_and_coordinates` | Use directions, coordinates, scale and described maps | `map_skills` | `skill_map_skills` |
| 5 | `work_with_time_zones` | Reason about time zones and clock differences | `time_zones` | `skill_time_zones` |
| 6 | `link_climate_and_biomes_to_place` | Link climate and biomes to place, elevation and water | `climate_biomes` | `skill_climate_biomes` |
| 7 | `tell_states_territories_and_dc_apart` | Tell states, territories and the District of Columbia apart | `territories_dc` | `skill_territories_dc` |
| 8 | `recognize_parks_and_landmarks` | Place well-known parks and landmarks | `parks_landmarks` | `skill_parks_landmarks` |
| 9 | `explain_why_places_developed` | Explain why places, cities and economies developed where they did | `human_geography` | `skill_human_geography` |
| 10 | `use_geography_in_everyday_decisions` | Use geography in everyday travel, scheduling and planning | `everyday_geography` | `skill_everyday_geography` |

Each set has exactly one objective. A question that is placed in several sets keeps the same objective in all of them.

## Tag scheme

Every record has `builder_created`, `needs_owner_review`, `us_geography`, its batch label `ready_lib_us_geography_NN` (01 is the sample; 02 to 06 are the main batches, one per age band), and the skill tag for each of its objectives. Questions and sets also have one format tag: `format_fact` (recall or identify), `format_reasoning` (explain why), `format_scenario` (a concrete situation) or `format_select_all` (multiple choice, select all that apply). Answer atoms carry no format tag.

## Conventions used in the content

- **Regions.** When a question asks for a region, it names the convention in the question or the feedback. The default is the U.S. Census Bureau's four regions (Northeast, Midwest, South, West). Other widely used names (Southwest, Pacific Northwest, Great Plains, Mid-Atlantic) are accepted as real, not wrong; where they would be offered against a Census question they are marked `ambiguous` or `incorrect` according to what the stem asks, with an editor note.
- **Roles.** `ambiguous` is used where a name, boundary or convention is contested or where two usages are both common. Every ambiguous choice has an editor note.
- **Evergreen.** No populations, city rankings, economic statistics, officeholders or recent events. Stable superlatives are limited to the largest state by land area. Physical heights and lengths are not given as numbers.
- **Contested names left out on purpose.** Official names of the highest peak in North America and of the large gulf south of the Gulf Coast states have changed by government order more than once. The library does not ask about those names. See REVIEW-NOTES.
- **Text only.** Locations are described in words. No question needs a picture or map.
- **Indigenous place names.** Used only where the origin is well established, with respectful wording.
