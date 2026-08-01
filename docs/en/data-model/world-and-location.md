# World and Location

## Purpose

World and location entities define the authored setting and the runtime spatial graph. A `World` is the reusable source material, while a `Simulation` is a mutable copy or run anchored to a world. `Location` and `Landmark` nodes give characters, objects, and generated media concrete places to attach to.

## Important properties

| Entity | Important properties |
| --- | --- |
| `Author` | `id`, `name`, `url` |
| `World` | `id`, `name`, `description`, `starting_time`, `version`, `url`, `language` |
| `Simulation` | `id`, `name`, `description`, `current_time`, `emotion_enabled`, `suggested_actions` |
| `Location` | `id`, `name`, `description` |
| `Landmark` | `id`, `name`, `description` |

## Relationships

- `(:Author)-[:CREATED]->(:World)`
- `(:World)-[:NEW_VERSION_OF]->(:World)`
- `(:Simulation)-[:BASED_ON]->(:World)`
- `(:World|Simulation)-[:CONTAINS]->(:Location)`
- `(:Location)-[:CONTAINS]->(:Location)` for nested regions or rooms.
- `(:Location)-[:CONTAINS]->(:Landmark)`
- Characters, background characters, items, equipment, and containers use `PRESENT_IN` or `ANCHORED_TO` to attach to the spatial graph.

## Ownership and lifecycle

Authors own worlds through `CREATED`. Worlds own their authored graph through `CONTAINS`. Simulations own runtime state through `CONTAINS` and keep a pointer back to the source world through `BASED_ON`.

Locations are scoped to either a world or a simulation. A simulation may read world locations as inherited context, but runtime changes should be made against the simulation-scoped copy when the run needs to diverge.

## Creation and deletion behaviour

Creating a world creates the `World` node and attaches it to an author. Creating a simulation creates a `Simulation` node and connects it to the source world.

Deleting a world removes its contained authored graph and refuses or protects cases where simulations still depend on it. Deleting a simulation removes the contained runtime graph, generation jobs, and graph snapshots owned by that simulation. Deleting a location deletes the nested location and landmark subtree below it.

## Invariants

- Every world should have exactly one author relationship.
- Every simulation should have exactly one `BASED_ON` world.
- A landmark belongs to a location, not directly to a world or simulation.
- Nested locations should remain within the same source scope.
- `current_time` is simulation state; `starting_time` is world template state.

## Example Cypher representation

```cypher
CREATE (author:Author {id: "author-1", name: "Ada", url: null})
CREATE (world:World {
  id: "world-1",
  name: "Harbor of Glass",
  description: "A coastal city of guilds and machines.",
  starting_time: datetime("1894-04-16T08:00:00Z"),
  version: "1.0.0",
  language: "en"
})
CREATE (simulation:Simulation {
  id: "sim-1",
  name: "Morning run",
  current_time: datetime("1894-04-16T08:00:00Z"),
  emotion_enabled: true
})
CREATE (district:Location {id: "loc-1", name: "East Docks", description: "Busy piers."})
CREATE (pier:Location {id: "loc-2", name: "Pier 7", description: "A foggy pier."})
CREATE (bell:Landmark {id: "landmark-1", name: "Signal Bell", description: "A brass harbor bell."})
CREATE (author)-[:CREATED]->(world)
CREATE (simulation)-[:BASED_ON]->(world)
CREATE (world)-[:CONTAINS]->(district)
CREATE (district)-[:CONTAINS]->(pier)
CREATE (pier)-[:CONTAINS]->(bell);
```

## Related API endpoints

- `/authors`, `/authors/{author_id}`, `/worlds/{world_id}/author`
- `/worlds`, `/worlds/{world_id}`, `/worlds/import`, `/worlds/{world_id}/export`
- `/simulations`, `/simulations/{simulation_id}`, `/worlds/{world_id}/simulations`
- `/locations`, `/locations/{location_id}`, `/worlds/{world_id}/locations`, `/simulations/{simulation_id}/locations`, `/locations/{location_id}/locations`
- `/landmarks`, `/landmarks/{landmark_id}`, `/locations/{location_id}/landmarks`, `/landmarks/{landmark_id}/location`

