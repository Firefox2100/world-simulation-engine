# 世界与地点

## 目的

世界与地点实体定义作者设定和运行时空间图。`World` 是可复用源材料，`Simulation` 是锚定到 world 的可变副本或运行。`Location` 和 `Landmark` 节点为角色、对象和生成媒体提供具体附着点。

## 重要属性

| 实体 | 重要属性 |
| --- | --- |
| `Author` | `id`, `name`, `url` |
| `World` | `id`, `name`, `description`, `starting_time`, `version`, `url`, `language` |
| `Simulation` | `id`, `name`, `description`, `current_time`, `emotion_enabled`, `suggested_actions` |
| `Location` | `id`, `name`, `description` |
| `Landmark` | `id`, `name`, `description` |

## 关系

- `(:Author)-[:CREATED]->(:World)`
- `(:World)-[:NEW_VERSION_OF]->(:World)`
- `(:Simulation)-[:BASED_ON]->(:World)`
- `(:World|Simulation)-[:CONTAINS]->(:Location)`
- `(:Location)-[:CONTAINS]->(:Location)` 表示嵌套区域或房间。
- `(:Location)-[:CONTAINS]->(:Landmark)`
- 角色、背景角色、物品、装备和容器使用 `PRESENT_IN` 或 `ANCHORED_TO` 附着到空间图。

## 归属与生命周期

Author 通过 `CREATED` 拥有 worlds。World 通过 `CONTAINS` 拥有作者态图。Simulation 通过 `CONTAINS` 拥有运行时状态，并通过 `BASED_ON` 指回源 world。

Location 的作用域属于 world 或 simulation。Simulation 可以读取 world locations 作为继承上下文，但当运行需要分叉时，运行时变更应写入 simulation 作用域副本。

## 创建与删除行为

创建 world 会创建 `World` 节点并连接到 author。创建 simulation 会创建 `Simulation` 节点并连接到源 world。

删除 world 会移除它包含的作者态图，并在仍有 simulations 依赖时拒绝或保护该操作。删除 simulation 会移除该 simulation 拥有的运行时图、generation jobs 和 graph snapshots。删除 location 会删除它下面的嵌套地点和地标子树。

## 不变量

- 每个 world 应该恰好有一条 author 关系。
- 每个 simulation 应该恰好有一个 `BASED_ON` world。
- Landmark 属于 location，而不是直接属于 world 或 simulation。
- 嵌套 locations 应保持在同一个 source scope 中。
- `current_time` 是 simulation 状态；`starting_time` 是 world 模板状态。

## 示例 Cypher 表示

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

## 相关 API 端点

- `/authors`, `/authors/{author_id}`, `/worlds/{world_id}/author`
- `/worlds`, `/worlds/{world_id}`, `/worlds/import`, `/worlds/{world_id}/export`
- `/simulations`, `/simulations/{simulation_id}`, `/worlds/{world_id}/simulations`
- `/locations`, `/locations/{location_id}`, `/worlds/{world_id}/locations`, `/simulations/{simulation_id}/locations`, `/locations/{location_id}/locations`
- `/landmarks`, `/landmarks/{landmark_id}`, `/locations/{location_id}/landmarks`, `/landmarks/{landmark_id}/location`

