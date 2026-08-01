# 角色

## 目的

角色实体表示世界中的 agents。`Character` 节点可以带着公开状态、私有状态、当前活动、库存、情绪状态、记忆、信念和服务配置进行模拟。`BackgroundCharacter` 节点表示较轻量的离场或环境人物，但仍可以占据地点、锚定到地标并持有物品。

## 重要属性

| 实体 | 重要属性 |
| --- | --- |
| `Character` | `id`, `user_controlled`, `name`, `age`, `gender`, `appearance`, `description`, `public_state`, `private_state`, `current_activity` |
| `BackgroundCharacter` | `id`, `name`, `description` |
| `CurrentActivity` value | `name`, `started_at`, `expected_end`, `interruptible`, `constraints` |
| `CharacterTtsConfig` | `id`, `character_voice`, `rvc_character_voice`, `rvc_character_pitch`, `backend` |

## 关系

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

## 归属与生命周期

World-scoped characters 是作者态模板角色。Simulation-scoped characters 是运行时参与者。创建运行或把作者态角色引入运行时，simulation 可以复制 world characters。

`private_state`、记忆、主观断言、private visibility 关系和情绪状态都属于角色上下文数据。模拟组件会使用它们，但默认不应把它们当作公开叙事。

## 创建与删除行为

Characters 可以创建在 worlds 或 simulations 下。设置 location 会替换已有 `PRESENT_IN` 关系。设置 landmark 会替换已有 `ANCHORED_TO` 关系。

删除 character 会删除角色以及由该角色直接持有的依赖节点，包括 intents、item stacks、emotion state、相关 emotion audit nodes 和 character TTS config。删除 background character 会删除节点和直接持有的 item stacks。

## 不变量

- 正常状态下，一个 character 只能有一个活动 location 关系。
- 正常状态下，一个 character 只能有一个活动 landmark anchor。
- 用户控制角色是 `user_controlled = true` 的 `Character` 节点；background characters 是独立节点。
- Private state 是角色上下文的一部分，只有允许从该角色视角推理的组件才应读取。
- Character TTS config 是可选的，可以指向后端配置，也可以依赖全局或 simulation 默认值。

## 示例 Cypher 表示

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

## 相关 API 端点

- `/characters`, `/characters/{character_id}`, `/worlds/{world_id}/characters`, `/simulations/{simulation_id}/characters`
- `/characters/{character_id}/location`, `/characters/{character_id}/landmark`, `/characters/{character_id}/inventory`
- `/characters/{character_id}/tts-config`
- `/background-characters`, `/background-characters/{character_id}`, `/worlds/{world_id}/background-characters`, `/simulations/{simulation_id}/background-characters`
- `/background-characters/{character_id}/location`, `/background-characters/{character_id}/landmark`

