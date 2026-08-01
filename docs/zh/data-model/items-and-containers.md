# 物品与容器

## 目的

物品实体建模物理状态。`Item` 是可复用类型定义。`ItemStack` 是世界中某种物品的具体数量。`Equipment` 是可以被持有或装备的具体对象。`Container` 是可以嵌套其他物理实体、也可以锁定或打开的物理持有者。

## 重要属性

| 实体 | 重要属性 |
| --- | --- |
| `Item` | `id`, `name`, `description`, `unique` |
| `ItemStack` | `id`, `quantity`, `quality`, `position`, 关联的 `Item` 类型 |
| `Equipment` | `id`, `name`, `description`, `quality`, `position`, inventory view 中的 equipped state 和 equipped position |
| `Container` | `id`, `name`, `description`, `state`, `position` |

Container `state` 是 `hidden`, `locked`, `unlocked`, `open` 之一。

## 关系

- `(:World|Simulation)-[:CONTAINS]->(:Item|ItemStack|Equipment|Container)`
- `(:ItemStack)-[:OF_TYPE]->(:Item)`
- `(:ItemStack|Equipment|Container)-[:PRESENT_IN {position}]->(:Location)`
- `(:Character|BackgroundCharacter|Container)-[:HOLDS]->(:ItemStack|Equipment|Container)`
- `(:Character)-[:EQUIPS {position}]->(:Equipment)`
- `(:Character|BackgroundCharacter|Container)-[:OWNS]->(:ItemStack|Equipment|Container)`
- `(:Item)-[:UNLOCKS]->(:Container)`

## 归属与生命周期

`Item` 节点描述对象是什么。`ItemStack` 节点描述该物品实例在哪里、有多少、质量如何。Equipment 和 containers 本身就是具体实例，因此不指向单独的类型节点。

物理位置由 holder、container 或 location 关系表示。所有权和占有是分开的：物品可以由一个实体拥有，同时当前被另一个实体持有。

## 创建与删除行为

Items、stacks、equipment 和 containers 可以创建在 worlds 或 simulations 下。把 stack、equipment 或 container 移动到 location 会删除 holder 关系。移动到 holder 会删除 location placement。Container 内容分配会替换所选内容集合之前的内容链接。

删除 `Item` 会删除它的 stacks。删除 container 会删除该 container 下的嵌套 `HOLDS` 子树。删除 equipment 或 stacks 会移除具体节点及其 placement、ownership、media 和 holding links。

## 不变量

- 每个 `ItemStack` 必须恰好有一个 `OF_TYPE` 关系。
- 一个物理实体应该只有一个有效 placement：`PRESENT_IN`、`HOLDS` 或 `EQUIPS`。
- `OWNS` 不表示当前占有。
- Containers 可以包含 stacks、equipment 和其他 containers，但不应引入 container cycles。
- `UNLOCKS` 从 item type 指向 container instance。

## 示例 Cypher 表示

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

## 相关 API 端点

- `/items`, `/items/{item_id}`, `/worlds/{world_id}/items`, `/simulations/{simulation_id}/items`
- `/stacks`, `/stacks/{stack_id}`, `/worlds/{world_id}/items/{item_id}/stacks`, `/simulations/{simulation_id}/items/{item_id}/stacks`
- `/stacks/{stack_id}/location`, `/stacks/{stack_id}/holder`, `/stacks/{stack_id}/owner`
- `/equipment`, `/equipment/{equipment_id}`, `/worlds/{world_id}/equipment`, `/simulations/{simulation_id}/equipment`
- `/equipment/{equipment_id}/location`, `/equipment/{equipment_id}/holder`, `/equipment/{equipment_id}/owner`
- `/containers`, `/containers/{container_id}`, `/worlds/{world_id}/containers`, `/simulations/{simulation_id}/containers`
- `/containers/{container_id}/location`, `/containers/{container_id}/holder`, `/containers/{container_id}/owner`
- `/containers/{container_id}/stacks`, `/containers/{container_id}/equipment`, `/containers/{container_id}/containers`, `/containers/{container_id}/unlocking-items`

