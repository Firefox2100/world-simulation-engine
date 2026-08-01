# Items and Containers

## Purpose

Item entities model physical state. `Item` is the reusable type definition. `ItemStack` is a concrete quantity of an item in the world. `Equipment` is a concrete object that can be held or equipped. `Container` is a physical holder that can nest other physical entities and can be locked or opened.

## Important properties

| Entity | Important properties |
| --- | --- |
| `Item` | `id`, `name`, `description`, `unique` |
| `ItemStack` | `id`, `quantity`, `quality`, `position`, linked `Item` type |
| `Equipment` | `id`, `name`, `description`, `quality`, `position`, equipped state and equipped position when in inventory views |
| `Container` | `id`, `name`, `description`, `state`, `position` |

Container `state` is one of `hidden`, `locked`, `unlocked`, or `open`.

## Relationships

- `(:World|Simulation)-[:CONTAINS]->(:Item|ItemStack|Equipment|Container)`
- `(:ItemStack)-[:OF_TYPE]->(:Item)`
- `(:ItemStack|Equipment|Container)-[:PRESENT_IN {position}]->(:Location)`
- `(:Character|BackgroundCharacter|Container)-[:HOLDS]->(:ItemStack|Equipment|Container)`
- `(:Character)-[:EQUIPS {position}]->(:Equipment)`
- `(:Character|BackgroundCharacter|Container)-[:OWNS]->(:ItemStack|Equipment|Container)`
- `(:Item)-[:UNLOCKS]->(:Container)`

## Ownership and lifecycle

`Item` nodes describe what an object is. `ItemStack` nodes describe where instances of that item are, how many are present, and what quality they have. Equipment and containers are already concrete instances, so they do not point to a separate type node.

Physical placement is represented by the holder, container, or location relationship. Ownership is separate from possession: an item can be owned by one entity while currently held by another.

## Creation and deletion behaviour

Items, stacks, equipment, and containers can be created under worlds or simulations. Moving a stack, equipment item, or container to a location removes holder relationships. Moving it to a holder removes location placement. Container content assignment replaces previous content links for the selected content set.

Deleting an `Item` deletes its stacks. Deleting a container deletes the nested `HOLDS` subtree below that container. Deleting equipment or stacks removes the concrete node and its placement, ownership, media, and holding links.

## Invariants

- Every `ItemStack` must have exactly one `OF_TYPE` relationship.
- A physical entity should have one effective placement: `PRESENT_IN`, `HOLDS`, or `EQUIPS`.
- `OWNS` does not imply current possession.
- Containers may contain stacks, equipment, and other containers, but container cycles should not be introduced.
- `UNLOCKS` points from an item type to a container instance.

## Example Cypher representation

```cypher
MATCH (simulation:Simulation {id: "sim-1"})
MATCH (mira:Character {id: "char-1"})
MATCH (pier:Location {id: "loc-2"})
CREATE (key:Item {
  id: "item-1",
  name: "Brass key",
  description: "A small key stamped with a pier number.",
  unique: true
})
CREATE (key_stack:ItemStack {id: "stack-1", quantity: 1, quality: "worn"})
CREATE (crate:Container {
  id: "container-1",
  name: "Locked crate",
  description: "A salt-stained supply crate.",
  state: "locked"
})
CREATE (simulation)-[:CONTAINS]->(key)
CREATE (simulation)-[:CONTAINS]->(key_stack)
CREATE (simulation)-[:CONTAINS]->(crate)
CREATE (key_stack)-[:OF_TYPE]->(key)
CREATE (mira)-[:HOLDS]->(key_stack)
CREATE (crate)-[:PRESENT_IN {position: "under the pier stairs"}]->(pier)
CREATE (key)-[:UNLOCKS]->(crate);
```

## Related API endpoints

- `/items`, `/items/{item_id}`, `/worlds/{world_id}/items`, `/simulations/{simulation_id}/items`
- `/stacks`, `/stacks/{stack_id}`, `/worlds/{world_id}/items/{item_id}/stacks`, `/simulations/{simulation_id}/items/{item_id}/stacks`
- `/stacks/{stack_id}/location`, `/stacks/{stack_id}/holder`, `/stacks/{stack_id}/owner`
- `/equipment`, `/equipment/{equipment_id}`, `/worlds/{world_id}/equipment`, `/simulations/{simulation_id}/equipment`
- `/equipment/{equipment_id}/location`, `/equipment/{equipment_id}/holder`, `/equipment/{equipment_id}/owner`
- `/containers`, `/containers/{container_id}`, `/worlds/{world_id}/containers`, `/simulations/{simulation_id}/containers`
- `/containers/{container_id}/location`, `/containers/{container_id}/holder`, `/containers/{container_id}/owner`
- `/containers/{container_id}/stacks`, `/containers/{container_id}/equipment`, `/containers/{container_id}/containers`, `/containers/{container_id}/unlocking-items`

