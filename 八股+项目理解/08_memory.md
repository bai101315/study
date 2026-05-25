# Memory机制


回答：
```
Agent需要记忆才能在多步任务中保持状态、跨任务积累知识。记忆机制分四层:感知记忆(当前输入的原始内容)、短期记忆(context window里的对话历史)、长期记忆(存在外部数据库、语义检索召回)、实体记忆(结构化提取的关键事实)。

实际设计时要解决三个核心问题:存什么、怎么存、什么时候取出来用，根据信息类型选合适的存储方式，再搭配主动检索和按需检索两种笨略使用
```

# 项目
```text
第一层：Session / Checkpoint
保存当前会话的完整运行状态，负责“接着聊”。

第二层：Memory
保存跨会话、跨重启的长期用户/Agent 画像，负责“记住偏好和事实”。

第三层：Thread 文件空间
保存每个 session 的 workspace/uploads/outputs，负责“文件隔离”。
```

## 1, Session 是什么

每个 Agent 默认对应一个固定 thread_id。你切换 Agent 时，会切换到这个 Agent 对应的 thread。

thread_id同时会用于：

```text
LangGraph checkpoint 分区
thread 文件目录隔离
memory 更新来源标记
sandbox 路径映射
```

## 2. Checkpoint 负责什么

Checkpoint 是 LangGraph 的状态持久化机制。项目在 main.py (line 601) 里创建
Checkpoint 保存的是 LangGraph 的 state，比如：

```python
class ThreadState(AgentState):
    sandbox: SandboxState | None
    thread_data: ThreadDataState | None
    title: str | None
    artifacts: list[str]
    todos: list | None
    uploaded_files: list[dict] | None
```
其中最重要的是 messages，它来自 AgentState，langchain内置的State；checkpoint会保存：

```
HumanMessage
AIMessage
ToolMessage
tool_calls
artifacts
todos
thread_data
其他图状态
```

## 3. Memory 负责什么

Memory 是长期记忆，存成 JSON 文件，不保存完整聊天记录，而是保存摘要和事实。
保存格式：
```json
{
  "version": "1.0",
  "lastUpdated": "...",
  "user": {
    "workContext": {"summary": "", "updatedAt": ""},
    "personalContext": {"summary": "", "updatedAt": ""},
    "topOfMind": {"summary": "", "updatedAt": ""}
  },
  "history": {
    "recentMonths": {"summary": "", "updatedAt": ""},
    "earlierContext": {"summary": "", "updatedAt": ""},
    "longTermBackground": {"summary": "", "updatedAt": ""}
  },
  "facts": []
}
```
每个 Agent 独立 memory, 每个agent_name 都会有自己独特的memory存储路径

## 4. Memory 如何注入给 Agent
通过system prompt
所以长期 memory 的作用方式是：变成 system prompt 的一部分，让模型在新会话里也能看到长期偏好和事实。

## 5. Memory 如何更新
更新不是每条消息同步写入，而是通过中间件异步队列。
每个agent执行结束后，after_agent被调用，
它会拿到

```text
拿到 thread_id
拿到 state["messages"]
过滤消息
检测用户纠正/正反馈
加入 memory queue
```

过滤规则：过滤掉： **工具中间结果，也不会记录上传文件路径这种 session 级临时信息**
```
保留 HumanMessage
保留没有 tool_calls 的最终 AIMessage
跳过 ToolMessage
跳过带 tool_calls 的中间 AIMessage
移除 <uploaded_files> 临时块
```
然后放入队列，队列有debounce，```threading.Timer(config.debounce_seconds, self._process_queue)```,  这样连续聊天时不会每一轮都立刻调用 LLM 更新 memory，而是等一段时间批处理。

## 6. MemoryUpdater 如何写入

```text
读取当前 memory.json
  -> 把本轮对话格式化
  -> 构造 MEMORY_UPDATE_PROMPT
  -> 调用 LLM
  -> 解析 LLM 返回 JSON
  -> 应用 updates
  -> 去掉上传文件相关记忆
  -> 保存 memory.json
```

要求LLM返回JSON文件：
```json
{
  "user": {
    "workContext": {"summary": "...", "shouldUpdate": true},
    "personalContext": {"summary": "...", "shouldUpdate": false},
    "topOfMind": {"summary": "...", "shouldUpdate": true}
  },
  "history": {
    "recentMonths": {"summary": "...", "shouldUpdate": true}
  },
  "newFacts": [
    {
      "content": "...",
      "category": "preference",
      "confidence": 0.9
    }
  ],
  "factsToRemove": ["fact_id"]
}
```
保存时使用原子写入

## 7. Thread 文件空间是什么

memory.json是 \.deer_flow\agents\bwq\memory.json
输出的文件目录：.deer_flow\threads\daily-report-3f60b650\user-data\outputs

ThreadDataMiddleware 会根据 thread_id 注入

```python
thread_data = {
    "workspace_path": ".../threads/<thread_id>/user-data/workspace",
    "uploads_path": ".../threads/<thread_id>/user-data/uploads",
    "outputs_path": ".../threads/<thread_id>/user-data/outputs",
}
```
文件系统会把
```text
/mnt/user-data/workspace
/mnt/user-data/uploads
/mnt/user-data/outputs
```
映射到真实的路径


## 总结
三层架构：
```text
checkpoint:
  粒度：thread_id
  内容：完整 LangGraph state，尤其 messages
  目的：恢复当前对话上下文
  存储：SQLite / memory / postgres

memory:
  粒度：agent_name 或 global
  内容：长期摘要、用户偏好、事实
  目的：跨 session 个性化
  存储：memory.json

thread files:
  粒度：thread_id
  内容：workspace/uploads/outputs 文件
  目的：工具文件隔离
  存储：.deer_flow/threads/<thread_id>/
```

一次完整会话：
```text
用户输入
  -> state = {"messages": [HumanMessage(...)]}
  -> agent.ainvoke(... thread_id ...)
  -> LangGraph 从 checkpoint 载入该 thread 之前状态
  -> system prompt 里已注入 memory.json 的长期记忆
  -> model/tool 循环执行
  -> LangGraph 把新 state 写入 checkpoint
  -> after_agent 触发 MemoryMiddleware
  -> 过滤最终用户/AI消息
  -> 加入 MemoryUpdateQueue
  -> debounce 时间到
  -> MemoryUpdater 调用 LLM 总结
  -> 写入 memory.json
```

thread_id: checkpoint 
agent: memory.json

Memory 更新是异步 debounce 的。用户刚说完一句后立即重启程序，可能还没来得及写入 memory。但 checkpoint 通常已经写了，因为它在 LangGraph 执行过程中由 checkpointer 管。





