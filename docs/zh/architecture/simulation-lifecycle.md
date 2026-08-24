# 模拟生命周期

Simulation API 会把一次模拟生成作为后台任务启动。普通用户回合会在 `WorldSimulator` 中运行 user-input LangGraph；继续生成和重新生成则会从保存的图状态快照恢复 character-round graph。

## 单回合序列

下图展示普通回合的数据边界。实际 graph 可能因为无效输入、出戏命令、trigger 评估、反应轮或没有计划中的角色活动而分支，但事实边界相同：候选数据和拟议数据在 state commit 应用已接受操作之前都只是临时状态。

```mermaid
sequenceDiagram
    autonumber
    participant User as 用户
    participant API as FastAPI simulation router
    participant Sim as WorldSimulator
    participant Input as 输入解释器
    participant Validator as 动作校验器
    participant Char as 角色模拟器
    participant Coord as 场景协调器
    participant Commit as 状态提交器
    participant Memory as 记忆/信念/情绪更新
    participant Narrator as 叙事器
    participant Store as Neo4j + media stores
    participant UI as 回合呈现

    User->>API: POST /simulations/{id}/input
    API->>Sim: start_generation(user_input)
    Sim->>Store: 保存 BEFORE_USER_INPUT 快照
    Sim->>Input: 根据公开模拟状态解释文本
    Input-->>Sim: 候选用户动作或 OOC 结果

    Sim->>Validator: 校验候选动作
    Validator-->>Sim: 校验结果（拟议有效性）

    alt 用户动作有效
        Sim->>Store: 从图作用域选择事件观察者
        Sim->>Commit: 为用户动作构建 StateCommitProposal
        Commit-->>Sim: 拟议物理图操作
        Sim->>Store: 创建 turn 并应用 state commit
        Note over Store: 用户动作在此成为已提交事实
        Sim->>Memory: 为观察者总结用户回合
        Memory-->>Sim: MemorySummaryProposal 和派生更新
        Sim->>Store: 应用事件、记忆、intent、关系、信念、情绪
    else 用户动作无效
        Sim->>Narrator: 叙述校验失败
        Narrator-->>Sim: 失败呈现
        Sim->>Store: 创建失败或 no-op turn presentation
    end

    Sim->>Char: 提出计划中的角色动作
    Note over Char: 读取私有角色上下文：视角、记忆、信念、关系、情绪
    Char-->>Sim: 每个角色的 ActionProposal
    Sim->>Validator: 校验角色提案
    Validator-->>Sim: 已校验的拟议动作计划
    Sim->>Coord: 解决同时动作和反应
    Coord-->>Sim: AcceptedSceneAction 时间线
    Note over Sim,Coord: 仍是拟议状态，不是图事实
    Sim->>Narrator: 叙述已接受时间线
    Narrator-->>Sim: 叙事块
    Sim->>Store: 选择事件观察者
    Sim->>Commit: 为已接受动作构建 StateCommitProposal
    Commit-->>Sim: 拟议物理图操作
    Sim->>Store: 创建 turn、应用 state commit、推进模拟时间
    Note over Store: 角色动作在此成为已提交事实
    Sim->>Memory: 总结已提交的角色回合
    Memory-->>Sim: 事件、记忆、intent、关系、信念、情绪
    Sim->>Store: 应用抽象和派生状态
    Store-->>UI: turn presentation blocks
    UI-->>User: 渲染叙事、对白、动作、媒体
```

## 状态阶段

| 阶段 | 示例 | 事实状态 |
| --- | --- | --- |
| 解释 | `InputInterpretation`、候选 `ProposedAction` | 不是事实，只是解析出的提案。 |
| 校验 | `ActionValidationResult` | 不是事实，只决定提案能否继续。 |
| 角色提案 | `ActionProposal`、`CharacterActionPlan` | 不是事实，是单个 actor 基于私有上下文的输出。 |
| 协调 | `SceneCoordinationResult`、`AcceptedSceneAction` | 不是事实，是准备提交的已接受时间线。 |
| 物理提交提案 | `StateCommitProposal` | 在数据库 store 应用之前不是事实。 |
| 物理提交 | `Turn`、图实体/关系变更、`Simulation.current_time` | 已提交事实。 |
| 抽象记忆提交 | `MemorySummaryProposal`、事件、记忆、intent | memory summary store 应用后的已提交派生事实。 |
| 呈现 | `TurnPresentationRendering` | 从已提交回合和叙事派生的显示层。 |

## 私有上下文

角色提案、反应提案、关系更新、主观模型更新和情绪更新会读取私有角色上下文。它不应被视为全局可见状态。角色 prompt 接收的是有作用域的 `CharacterPerspective`，不是完整图。这个视角可以包含私有记忆、主观断言、私有关系描述和情绪，但只对正在构建上下文的 actor 可见。

## 快照与重新生成

`WorldSimulator` 会在用户输入前、以及每个生成基准点之后保存图状态快照。继续生成和重新生成直接加载这些快照，不需要从叙事文本反推执行状态——重新运行依据的是结构化图状态和模拟器自身的中间状态。

