# Area games

Every playable Grade 5 area game lives here, one folder per curriculum area:

```text
areas/
  registry.ts                      ← the ONLY place that maps area id → screen → component
  maths/mat-NN-<slug>/             ← G5-AREA-MAT-NN
  english/eng-NN-<slug>/           ← G5-AREA-ENG-NN
  sinhala/sin-NN-<slug>/           ← G5-AREA-SIN-NN
  sinhala/shared/                  ← SinhalaJourney shell + teardown receipt used by sin-01…03
```

`<slug>` is the backend name of the same game: `areas/maths/mat-08-division-adventure/` is played
by `backend/app/gamification/application/division_adventure_flow.py`.

## Adding or finding a game

1. Find the row below (or search `registry.ts` for the area id).
2. The folder holds the React component (`*Journey.tsx`, `*Quest.tsx`, …), its pure logic
   (`*Logic.ts`), optional `manifest.ts` (skills, chapters, asset root), optional Phaser scene, CSS,
   and `__tests__/`.
3. Images are in `frontend/public/curriculum/game/<area id>/`.
4. To add a game: create the folder, add one `areaGame(...)` row to `registry.ts`. The app shell
   (`mobile-learning-flow/MobileLearningApp.tsx`) needs no change. Every game receives
   `AreaGameProps` (`api`, `learnerId`, `condition`, `reducedMotion`, `onBack`, `onFailure`).

The screen names in `registry.ts` are stable `data-screen` values used by CSS and tests; do not
rename them.

## Index

| Area | Title | Folder | Component | Backend flow (`application/`) | Backend content | Data (`data/gamification/`) |
|---|---|---|---|---|---|---|
| `G5-AREA-MAT-01` | සංඛ්‍යා | [`maths/mat-01-number-world/`](maths/mat-01-number-world/) | `NumberWorldJourney.tsx` | `number_world_flow.py` | `content/number_world.py` | `grade5-number-world/` |
| `G5-AREA-MAT-02` | එකතු කිරීම | [`maths/mat-02-addition-adventure/`](maths/mat-02-addition-adventure/) | `AdditionAdventureJourney.tsx` | `addition_adventure_flow.py` | `content/addition_adventure.py` | `grade5-addition-adventure/` |
| `G5-AREA-MAT-03` | සංඛ්‍යා රටා | [`maths/mat-03-number-patterns/`](maths/mat-03-number-patterns/) | `NumberPatternJourney.tsx` | `number_patterns_flow.py` | `content/number_patterns.py` | `grade5-number-patterns/` |
| `G5-AREA-MAT-04` | අඩු කිරීම | [`maths/mat-04-subtraction-adventure/`](maths/mat-04-subtraction-adventure/) | `SubtractionAdventureJourney.tsx` | `subtraction_adventure_flow.py` | `content/subtraction_adventure.py` | `grade5-subtraction-adventure/` |
| `G5-AREA-MAT-05` | භාග | [`maths/mat-05-fraction-adventure/`](maths/mat-05-fraction-adventure/) | `FractionAdventureJourney.tsx` | `fraction_adventure_flow.py` | `content/fraction_adventure.py` | `grade5-fraction-adventure/` |
| `G5-AREA-MAT-06` | ගුණ කිරීම | [`maths/mat-06-multiplication-adventure/`](maths/mat-06-multiplication-adventure/) | `MultiplicationAdventureJourney.tsx` | `multiplication_adventure_flow.py` | `content/multiplication_adventure.py` | — (content in Python) |
| `G5-AREA-MAT-07` | කාලය | [`maths/mat-07-time-adventure/`](maths/mat-07-time-adventure/) | `TimeAdventureJourney.tsx` | `time_adventure_flow.py` | `content/time_adventure.py` | — (content in Python) |
| `G5-AREA-MAT-08` | බෙදීම | [`maths/mat-08-division-adventure/`](maths/mat-08-division-adventure/) | `DivisionAdventureJourney.tsx` | `division_adventure_flow.py` | `content/division_adventure.py` | — (content in Python) |
| `G5-AREA-MAT-09` | දිග හා දුර | [`maths/mat-09-distance-adventure/`](maths/mat-09-distance-adventure/) | `DistanceAdventureJourney.tsx` | `distance_adventure_flow.py` | `content/distance_adventure.py` | — (content in Python) |
| `G5-AREA-MAT-10` | මුදල් | [`maths/mat-10-money-adventure/`](maths/mat-10-money-adventure/) | `MoneyAdventureJourney.tsx` | `money_adventure_flow.py` | `content/money_adventure.py` | `grade5-money-adventure/` |
| `G5-AREA-MAT-11` | පරිමාව හා ධාරිතාව | [`maths/mat-11-capacity-adventure/`](maths/mat-11-capacity-adventure/) | `CapacityAdventureJourney.tsx` | `capacity_adventure_flow.py` | `content/capacity_adventure.py` | `grade5-capacity-adventure/` |
| `G5-AREA-MAT-12` | බර මැනීම | [`maths/mat-12-mass-adventure/`](maths/mat-12-mass-adventure/) | `MassAdventureJourney.tsx` | `mass_adventure_flow.py` | `content/mass_adventure.py` | — (content in Python) |
| `G5-AREA-MAT-13` | හැඩතල හා ඝන වස්තු | [`maths/mat-13-shape-adventure/`](maths/mat-13-shape-adventure/) | `ShapeAdventureJourney.tsx` | `shape_adventure_flow.py` | `content/shape_adventure.py` | — (content in Python) |
| `G5-AREA-MAT-14` | දිශා | [`maths/mat-14-direction-adventure/`](maths/mat-14-direction-adventure/) | `DirectionAdventureJourney.tsx` | `direction_adventure_flow.py` | `content/direction_adventure.py` | — (content in Python) |
| `G5-AREA-MAT-15` | දශම | [`maths/mat-15-decimal-adventure/`](maths/mat-15-decimal-adventure/) | `DecimalAdventureJourney.tsx` | `decimal_adventure_flow.py` | `content/decimal_adventure.py` | — (content in Python) |
| `G5-AREA-MAT-16` | රෝම සංඛ්‍යාංක | [`maths/mat-16-roman-adventure/`](maths/mat-16-roman-adventure/) | `RomanAdventureJourney.tsx` | `roman_adventure_flow.py` | `content/roman_adventure.py` | — (content in Python) |
| `G5-AREA-ENG-01` | Our Good Behaviour | [`english/eng-01-classroom-action-quest/`](english/eng-01-classroom-action-quest/) | `ClassroomActionQuest.tsx` | `classroom_action_quest_flow.py` | `content/classroom_action_quest.py` | `grade5-classroom-action-quest/` |
| `G5-AREA-ENG-02` | We are Sri Lankans | [`english/eng-02-sri-lanka-discovery/`](english/eng-02-sri-lanka-discovery/) | `SriLankaDiscovery.tsx` | `sri_lanka_discovery_flow.py` | `content/sri_lanka_discovery.py` | `grade5-sri-lanka-discovery/` |
| `G5-AREA-ENG-03` | Plants, Trees and Creepers | [`english/eng-03-plant-explorer/`](english/eng-03-plant-explorer/) | `PlantExplorerQuest.tsx` | `plant_explorer_flow.py` | `content/plant_explorer.py` | `grade5-plant-explorer/` |
| `G5-AREA-ENG-04` | Animals around us | [`english/eng-04-wildlife-ranger/`](english/eng-04-wildlife-ranger/) | `WildlifeRangerQuest.tsx` | `wildlife_ranger_flow.py` | `content/wildlife_ranger.py` | `grade5-wildlife-ranger/` |
| `G5-AREA-ENG-05` | What we use | [`english/eng-05-everyday-object-quest/`](english/eng-05-everyday-object-quest/) | `EverydayObjectQuest.tsx` | `everyday_object_quest_flow.py` | `content/everyday_object_quest.py` | `grade5-everyday-object-quest/` |
| `G5-AREA-ENG-06` | Our food | [`english/eng-06-island-food-festival/`](english/eng-06-island-food-festival/) | `IslandFoodFestival.tsx` | `island_food_festival_flow.py` | `content/island_food_festival.py` | `grade5-island-food-festival/` |
| `G5-AREA-ENG-07` | Safety & protection | [`english/eng-07-rainbow-wardrobe-quest/`](english/eng-07-rainbow-wardrobe-quest/) | `RainbowWardrobeQuest.tsx` | `rainbow_wardrobe_quest_flow.py` | `content/rainbow_wardrobe_quest.py` | `grade5-rainbow-wardrobe-quest/` |
| `G5-AREA-ENG-08` | Water | [`english/eng-08-water-works-adventure/`](english/eng-08-water-works-adventure/) | `WaterWorksAdventure.tsx` | `water_works_adventure_flow.py` | `content/water_works_adventure.py` | `grade5-water-works-adventure/` |
| `G5-AREA-ENG-09` | Transport | [`english/eng-09-transit-terminal-quest/`](english/eng-09-transit-terminal-quest/) | `TransitTerminalQuest.tsx` | `transit_terminal_quest_flow.py` | `content/transit_terminal_quest.py` | `grade5-transit-terminal-quest/` |
| `G5-AREA-ENG-10` | Home Garden | [`english/eng-10-bloom-builder-garden/`](english/eng-10-bloom-builder-garden/) | `BloomBuilderGarden.tsx` | `bloom_builder_garden_flow.py` | `content/bloom_builder_garden.py` | `grade5-bloom-builder-garden/` |
| `G5-AREA-ENG-11` | Ways of Making work Easy | [`english/eng-11-workplace-link-city/`](english/eng-11-workplace-link-city/) | `WorkplaceLinkCity.tsx` | `workplace_link_city_flow.py` | `content/workplace_link_city.py` | `grade5-workplace-link-city/` |
| `G5-AREA-ENG-12` | Human Behaviour | [`english/eng-12-family-word-constellation/`](english/eng-12-family-word-constellation/) | `FamilyWordConstellation.tsx` | `family_word_constellation_flow.py` | `content/family_word_constellation.py` | `grade5-family-word-constellation/` |
| `G5-AREA-ENG-13` | Earth & Sky | [`english/eng-13-earth-sky-explorer/`](english/eng-13-earth-sky-explorer/) | `EarthSkyExplorer.tsx` | `earth_sky_explorer_flow.py` | `content/earth_sky_explorer.py` | `grade5-earth-sky-explorer/` |
| `G5-AREA-ENG-14` | Changes we can do | [`english/eng-14-blueprint-quest/`](english/eng-14-blueprint-quest/) | `SchoolHomeBlueprintQuest.tsx` | `blueprint_quest_flow.py` | `content/blueprint_quest.py` | `grade5-blueprint-quest/` |
| `G5-AREA-ENG-15` | Man & Information | [`english/eng-15-information-station/`](english/eng-15-information-station/) | `InformationStation.tsx` | `information_station_flow.py` | `content/information_station.py` | `grade5-information-station/` |
| `G5-AREA-ENG-16` | Our Past | [`english/eng-16-heritage-museum-quest/`](english/eng-16-heritage-museum-quest/) | `HeritageMuseumQuest.tsx` | `heritage_museum_quest_flow.py` | `content/heritage_museum_quest.py` | `grade5-heritage-museum-quest/` |
| `G5-AREA-ENG-17` | Classroom Language | [`english/eng-17-classroom-language-live/`](english/eng-17-classroom-language-live/) | `ClassroomLanguageLive.tsx` | `classroom_language_live_flow.py` | `content/classroom_language_live.py` | `grade5-classroom-language-live/` |
| `G5-AREA-ENG-18` | Useful Expressions & Conversation Language | [`english/eng-18-conversation-street/`](english/eng-18-conversation-street/) | `ConversationStreet.tsx` | `conversation_street_flow.py` | `content/conversation_street.py` | `grade5-conversation-street/` |
| `G5-AREA-SIN-01` | පිල්ලම් හඳුනාගනිමු | [`sinhala/sin-01-pillam/`](sinhala/sin-01-pillam/) | `PillamJourney.tsx` | `sinhala_pillam_flow.py` | `content/sinhala_pillam.py` | `grade5-sinhala-pillam/` |
| `G5-AREA-SIN-02` | විරාම ලක්ෂණ හඳුනාගනිමු | [`sinhala/sin-02-punctuation/`](sinhala/sin-02-punctuation/) | `PunctuationJourney.tsx` | `sinhala_punctuation_flow.py` | `content/sinhala_punctuation.py` | `grade5-sinhala-punctuation/` |
| `G5-AREA-SIN-03` | තේරවිලි | [`sinhala/sin-03-riddles/`](sinhala/sin-03-riddles/) | `RiddleJourney.tsx` | `sinhala_riddle_flow.py` | `content/sinhala_riddles.py` | `grade5-sinhala-riddles/` |

"— (content in Python)" means the items for that area are generated inside the backend content
module and there is no versioned data package yet.
