# 后台模拟

World Simulation Engine 尝试让离场角色保持活动，同时不阻塞每一次用户交互。前台生成处理用户当前场景。离场生成按 simulation 单独排队，可以在后台完成，除非它可能与前台回合冲突。

## 前台与离场执行

```mermaid
sequenceDiagram
    autonumber
    participant User as 用户
    participant Foreground as 前台生成
    participant Conflict as 冲突检查
    participant Queue as 离场队列
    participant Worker as 离场 worker
    participant Actor as 离场角色模拟器
    participant Store as Neo4j

    User->>Foreground: 提交输入
    Foreground->>Conflict: 检查活动中的离场生成
    alt 用户动作可能触及离场结果
        Conflict->>Worker: wait_for_off_scene_activity()
        Worker->>Store: 完成待处理离场提交
        Worker-->>Foreground: 可以安全继续
    else 无冲突
        Conflict-->>Foreground: 立即继续
    end

    Foreground->>Store: 提交前台回合
    Foreground->>Queue: 根据已提交回合安排离场活动
    Queue-->>Worker: work item
    Worker->>Actor: 选择可用离场 actor
    Note over Actor: 读取该 actor 的私有角色上下文
    Actor-->>Worker: 拟议动作
    Worker->>Worker: 校验并协调单 actor 活动
    Worker->>Store: 应用 state commit 和 memory summary
    Note over Store: 离场结果在应用时成为已提交事实
```

## 调度模型

前台回合提交后，`WorldSimulator._schedule_off_scene_activity()` 创建离场生成状态，并为 simulation 入队工作。按 simulation 的 worker 消费这些 work items。worker 会选择可用 actors、提出活动、校验活动、把它协调成简单的已接受时间线、应用状态变更，并总结记忆。

角色没有当前活动、活动到了重新评估时间，或者活动可被打断，都算作可用。调度器会限制前台角色轮中考虑的计划角色数量，避免单个回合膨胀成全员无界生成。

## 冲突检查

前台生成会在解释之前和角色校验之前调用 `_wait_for_conflicting_off_scene_activity()`。当用户动作可能依赖离场工作时，它会等待，例如：

- 用户按名字提到离场 actor；
- 用户移动到或互动于离场活动正在发生的地点；
- 前台角色提案可能与待处理的离场 actor 或地点碰撞。

如果没有明显冲突，前台生成会继续。下一次读取图状态时会看到已经提交的离场工作。

## 为什么需要它

全局的“每个人每回合都行动”循环太慢，而且会过度暴露隐藏上下文。纯前台循环会冻结用户当前视野之外的所有人。队列模型是折中：

- 可见且相关的活动与用户回合同步；
- 无关的离场活动可以独立推进；
- 私有角色上下文仍然保持 actor 作用域；
- 离场结果在成为事实之前仍会经过校验、协调、提交和记忆总结。

