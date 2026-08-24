# Characters

## Purpose

Character entities represent agents inside a world. `Character` nodes can be simulated with public and private state, current activity, inventory, emotion state, memory, beliefs, and service configuration. `BackgroundCharacter` nodes represent lighter off-scene or ambient people that can still occupy places, anchor to landmarks, and hold objects.

## Important properties

| Entity | Important properties |
| --- | --- |
| `Character` | `id`, `user_controlled`, `name`, `age`, `gender`, `appearance`, `description`, `public_state`, `private_state`, `current_activity` |
| `BackgroundCharacter` | `id`, `name`, `description` |
| `CurrentActivity` value | `name`, `started_at`, `expected_end`, `interruptible`, `constraints` |
| `CharacterTtsConfig` | `id`, `character_voice`, `rvc_character_voice`, `rvc_character_pitch`, `backend` |
| `EntityVariableSet` | `id`, `owner_id`, `variables` (list of `VariableDefinition`: `name`, `value_type`, `value`, `default_value`, `description`, bounds) |

## Relationships

- `(:World|Simulation)-[:CONTAINS]->(:Character|BackgroundCharacter)`
- `(:Character|BackgroundCharacter)-[:PRESENT_IN {position}]->(:Location)`
- `(:Character|BackgroundCharacter)-[:ANCHORED_TO]->(:Landmark)`
- `(:Character)-[:HOLDS]->(:Intent)`
- `(:Character|BackgroundCharacter|Container)-[:HOLDS]->(:ItemStack|Equipment|Container)`
- `(:Character)-[:EQUIPS {position}]->(:Equipment)`
- `(:Character|BackgroundCharacter)-[:OWNS]->(:ItemStack|Equipment|Container)`
- `(:Character)-[:REMEMBERS]->(:MemoryAtom)`
- `(:Character)-[:HOLDS_MODEL]->(:SubjectiveEntityClaim)`
- `(:Character)-[:HAS_EMOTION_STATE]->(:EmotionState)`
- `(:Character)-[:HAS_CONFIG]->(:CharacterTtsConfig)`
- `(:CharacterTtsConfig)-[:USE_CONFIG]->(:TtsModelConfig)`
- `(:Character)-[:HAS_VARIABLES]->(:EntityVariableSet)` — not exclusive to characters; any entity type can own one the same way.
- `(:World|Simulation)-[:CONTAINS]->(:EntityVariableSet)`

## Ownership and lifecycle

World-scoped characters are authored template characters. Simulation-scoped characters are runtime participants. A simulation can copy world characters when a run is created or when an authored character is introduced into a run.

`private_state`, memories, subjective claims, relationships with private visibility, and emotion state are character-context data. These fields are used by simulation components but should not be treated as public narration by default.

## Creation and deletion behaviour

Characters can be created under worlds or simulations. Setting a location replaces the existing `PRESENT_IN` relationship. Setting a landmark replaces the existing `ANCHORED_TO` relationship.

Deleting a character removes the character and dependent nodes that are held directly by that character, including intents, item stacks, emotion state, related emotion audit nodes, and character TTS config. Background character deletion removes the node and directly held item stacks.

## Invariants

- A character can have only one active location relationship in normal state.
- A character can have only one active landmark anchor in normal state.
- User-controlled characters are `Character` nodes with `user_controlled = true`; background characters are separate nodes.
- Private state is part of character context and should be read only by components that are allowed to reason from that character perspective.
- Character TTS config is optional and can either point to a backend config or rely on global/simulation defaults.

## Example Cypher representation

```cypher
MATCH (simulation:Simulation {id: "sim-1"})
MATCH (pier:Location {id: "loc-2"})
CREATE (character:Character {
  id: "char-1",
  user_controlled: true,
  name: "Mira Vale",
  age: 31,
  gender: "female",
  appearance: "Weatherproof coat and silver goggles",
  description: "A mechanic with a reputation for impossible repairs.",
  public_state: "Waiting beside the pier gate.",
  private_state: "Worried that the engine ledger is missing."
})
CREATE (simulation)-[:CONTAINS]->(character)
CREATE (character)-[:PRESENT_IN {position: "by the gate"}]->(pier);
```

## Related API endpoints

- `/characters`, `/characters/{character_id}`, `/worlds/{world_id}/characters`, `/simulations/{simulation_id}/characters`
- `/characters/{character_id}/location`, `/characters/{character_id}/landmark`, `/characters/{character_id}/inventory`
- `/characters/{character_id}/tts-config`
- `/entities/{owner_id}/variables` (GET/PUT; not character-specific, works for any entity type)
- `/background-characters`, `/background-characters/{character_id}`, `/worlds/{world_id}/background-characters`, `/simulations/{simulation_id}/background-characters`
- `/background-characters/{character_id}/location`, `/background-characters/{character_id}/landmark`

