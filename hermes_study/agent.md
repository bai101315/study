# Hermes Agent本质

## 创建方式
就是 AIAgent() ，一个普通 Python 类实例

```python
run_agent.py 第 326 行
class AIAgent:
    def init(self, base_url, api_key, provider, model, ...):
        from agent.agent_init import init_agent
        init_agent(self, ...)   # 注入 100+ 个属性到 self 上
```

没有 Builder 模式，没有工厂函数，没有 create_xxx_agent()。就是一个 Python 类，init 接收约 60 个参数（model、provider、callback、credentials...），然后委托给 init_agent() 函数把属性直接打到 self 上：

```python
self.model = "deepseek-v4-pro"
self.provider = "deepseek"
self.max_iterations = 90
self.tools = [...]       # 过滤好的 tool schemas
self._memory_store = ... # 持久记忆
self.valid_tool_names = set(...)  # 可用工具名集合
self.base_url = "https://api.deepseek.com"
... 约 100+ 个属性
```

调用方式极其简单：```agent = AIAgent()```

## 核心循环
Hermes 使用的确实是 ReAct（Reasoning + Acting） 模式，但不是调任何库。核心循环在 conversation_loop.py，自己用 while 写的：

```python
agent/conversation_loop.py 第 598 行起

api_call_count = 0

while (api_call_count < agent.max_iterations      # ← 最多 90 轮
        and agent.iteration_budget.remaining > 0) \
        or agent._budget_grace_call:

    api_call_count += 1

    # ─── Step 1: 构建 API kwargs，含 messages + tools ───
    api_kwargs = agent._build_api_kwargs(api_messages)
    # api_kwargs = {
    #     "model": "deepseek-v4-pro",
    #     "messages": [...],     # 完整对话历史
    #     "tools": agent.tools,  # 过滤后的 tool schemas
    # }

    # ─── Step 2: 调用 LLM ─── 
    response = client.chat.completions.create(**api_kwargs)

    # ─── Step 3: 解析响应 ─── 
    msg = response.choices[0].message

    if msg.tool_calls:
        # ─── Step 4a: 有工具调用 → 执行 → 结果追加到 messages → 继续循环
        for tc in msg.tool_calls:
            tool_result = handle_function_call(tc.function.name, tc.function.args)
            messages.append({"role": "tool", "content": tool_result, ...})
        # → 回到 while 顶部，下一轮 LLM 会看到工具结果
    else:
        # ─── Step 4b: 纯文本响应 → 结束
        final_response = msg.content
        break
```

## 和create_agent()区别

和 LangChain create_agent 的本质区别

| | Hermes AIAgent | LangChain create_agent |
|---|---|---|
| 本质 | 一个普通 Python 对象 + while 循环 | 框架内的 Runnable 图节点 |
| 创建 | agent = AIAgent(...) 直接 new | create_agent(llm, tools) 返回 CompiledGraph |
| 循环 | 裸 while 循环，自实现 | LangGraph 状态机 add_node/add_edge |
| 状态 | 实例属性 self.xxx | TypedDict 状态对象，通过节点传递 |
| 工具格式 | 原生 OpenAI function-calling dict | @tool 装饰器 + BaseTool 抽象 |
| 提示词 | 自己拼字符串 | ChatPromptTemplate + MessagesPlaceholder |
| 中间件 | 无（函数直调） | RunnableLambda / RunnablePassthrough |
| 依赖 | 只依赖 openai SDK | langchain-core + langgraph + langchain |
| 可观测性 | 自己打 log | LangSmith / callbacks |
| 灵活性 | 直接改源码的 while 循环 | 插拔式中间件，但受框架约束 |


**langchain**底层是一个编译好的状态图:
```agent (LLM) → tools (conditional) → agent → END```
hermes:
```while 循环 { call_llm() → if tool_calls: execute() → append → continue else: return }```

## Hermes 拒绝框架的深层原因

1. 直接操作 messages 数组
    Hermes 的对话状态就是纯 Python List[Dict]，每条消息是 {"role": "user/assistant/tool", "content": ...}。没有任何封装。LangChain 需要 BaseMessage / HumanMessage / AIMessage 等类型的包装。

2. prompt cache 是首要设计约束
   系统提示词在会话内必须保持 byte-stable，否则 Anthropic/DeepSeek 的 prefix cache 失效。框架的中间件和模板渲染会让这一点变得不可控。

3. Provider 差异在 transport 层解决，不变更核心循环
   DeepSeek 和 Anthropic 和 Gemini 的 API 差异只在 agent/transports/ 下的 build_kwargs() 里处理。核心 while 循环对所有 provider 完全一样。

4. 工具就是 dict，不是类
    不需要 @tool 装饰器，不需要 BaseTool 继承。就用 OpenAI 原生的 JSON Schema dict + 一个 handler 函数。

这不是 LangChain 那种"组装 DAG 图然后编译执行"的范式，而是最直接的"接收输入 → while 调用 LLM → 执行工具 → 返回结果"的命令式代码。
    
为什么不用 LangChain？ 因为当你需要精细控制 prompt cache、跨 20 个 provider、子代理 fork、上下文压缩、记忆 nudge、后台回顾线程、文件系统检查点这些功能时，框架的抽象层会成为障碍，直接写 while 循环反而最简单。


## agent 初始化

## 阶段 0：CLI 启动，读取配置
    

    │
    ├─ cli.py: HermesCLI.init()
    │   ├─ 读取 ~/.hermes/config.yaml
    │   ├─ 读取 ~/.hermes/.env → 加载 API keys
    │   │
    │   ├─ self.model = "deepseek-v4-pro"     ← config.yaml → model.default
    │   ├─ self.provider = "deepseek"          ← config.yaml → model.provider
    │   ├─ self.base_url = "https://api.deepseek.com"
    │   │
    │   ├─ self.enabled_toolsets = _get_platform_tools(config, "cli")
    │   │   └─ 读取 config.yaml → platform_toolsets.cli = ["hermes-cli"]
    │   │
    │   └─ self.max_turns = agents.max_turns = 90

## 阶段 1：创建 AIAgent 实例

cli.py 第 4516 行:
      │
self.agent = AIAgent(
    model="deepseek-v4-pro",
    provider="deepseek",
    base_url="https://api.deepseek.com",
    api_key="sk-5157...",
    enabled_toolsets=["hermes-cli"],    ← 从这里来
    max_iterations=90,
    platform="cli",
    session_db=...,
    ...约 40 个参数
)
│
└─→ run_agent.py: AIAgent.init()
    └─→ agent/agent_init.py: init_agent(self, ...)

在 agent_init中会解析很多东西，然后绑定给agent

## 阶段 2：解析 Provider + Credentials

agent_init.py:
    │
    ├─ 解析 provider → "deepseek"
    ├─ 解析 api_mode → "chat_completions"（OpenAI 兼容协议）
    ├─ 建立 OpenAI client (api.deepseek.com)
    ├─ 获取 model metadata（context length 等）
    │
    └─ agent.reasoning_config = {...}
        agent.max_tokens = None
        agent.prefill_messages = []

## 阶段 3：加载工具 — Toolset 过滤 + Schema 生成

agent_init.py 第 818 行:
    │
    agent.tools = get_tool_definitions(
        enabled_toolsets=["hermes-cli"],
        disabled_toolsets=[],
    )
    │
    ├─ "hermes-cli" 是复合 toolset
    │   └─ 展开 includes: ["web","browser","terminal","file",...]
    │       └─ 进一步展开每个子 toolset
    │           └─ 得到 ~70 个工具名
    │
    ├─ 对每个工具名:
    │   ├─ registry.get_entry(name)
    │   ├─ check_fn()? → 通过才加入  (如 browser 工具检查 API key)
    │   ├─ dynamic_schema_overrides? → 更新描述（如 delegate_task 的并发数）
    │   └─ 组装为 {"type":"function","function":{name,description,parameters}}
    │
    ├─ 过滤完后约 45 个工具 schema
    │
    └─ agent.tools = [45 个 OpenAI function-calling 格式 dict]
        agent.valid_tool_names = {"read_file","write_file","terminal",...}
    
## 阶段 4：加载记忆 — MemoryStore 初始化


## 阶段 7：首次构建系统提示词（延迟执行）

系统提示词不在 init 时构建，而是延迟到 run_conversation() 首次调用时：
conversation_loop.py 第 417 行:
    │
    if agent._cached_system_prompt is None:
        _restore_or_build_system_prompt()
        │
        ├─ 检查 SQLite 是否有存储的 prompt?
        │   └─ 新会话 → 没有 → 首次构建
        │
        └─ agent._build_system_prompt(system_message)
            │
            └─→ system_prompt.py: build_system_prompt()
                    │
                    ├─ STABLE 层:
                    │   ├─ load_soul_md()  → /home/bai/.hermes/SOUL.md
                    │   ├─ DEFAULT_AGENT_IDENTITY（如果没有 SOUL.md）
                    │   ├─ MEMORY_GUIDANCE     ← 因为有 memory 工具
                    │   ├─ SESSION_SEARCH_GUIDANCE
                    │   ├─ SKILLS_GUIDANCE      ← 因为有 skill_manage 工具
                    │   ├─ build_skills_system_prompt()
                    │   │   └─ 扫描 ~/.hermes/skills/ → 生成技能索引
                    │   ├─ build_environment_hints() → "WSL" 提示
                    │   └─ PLATFORM_HINTS["cli"] → CLI 平台提示
                    │
                    ├─ CONTEXT 层:
                    │   ├─ system_message（如果有）
                    │   └─ build_context_files_prompt() → AGENTS.md
                    │
                    ├─ VOLATILE 层:
                    │   ├─ MEMORY.md 冻结快照  [0/2200 chars]
                    │   ├─ USER.md 冻结快照    [3%/1375 chars]
                    │   ├─ 外部 provider block  （无）
                    │   └─ "Conversation started: Monday, June 2, 2026"
                    │       "Model: deepseek-v4-pro"
                    │       "Provider: deepseek"
                    │
                    └─ 拼成大字符串 → agent._cached_system_prompt
                        └─ 存入 SQLite 供后续恢复

