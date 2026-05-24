# 什么是 Multi-Agent？

回答：
```
多智能体系统(Multi-Agent)就是多个Agent协作完成任务，每个Agent各有分工，有的负责搜索、有的负责写代码、有的负责做评审。

我理解单个Agent主要受两个限制:一是context窗口大小，复杂任务信息量一多就撑爆了;二是单点能力，什么都让一个Agent做，每件事都是泛才。

Multi-Agent通过专业分工和并行执行，能处理更复杂、更长流程的任务，这是我在实际项目里选择多智能体方案的核心原因。
```

## Multi-Agent 核心思路

Multi-Agent 的核心思路，就是「团队作战代替单打独斗」。
与其让一个Agent包揽所有事，不如把任务按职能拆开，每个Agent只负责一件事，专心做好自己那块，做完把结果传给下一个。

Multi-Agent 之间的协作方式主要有三种模式。

- 第一种是顺序流水线 (Sequential Pipeline)，Agent A做完把结果交给Agent B,B做完交给Agent C，就像工厂流水线一样，每个环节依次处理。
- 第二种是井行扇出(Fan-out)，一个调度者把多个独立子任务同时分发给不同的Worker Agent，它们各自并行执行，最后由调度者收集汇总。
- 第三种是辩论/评审模式(Debate/Review)，多个Agent对同一个问题各自给出方案，然后由一个裁判Agent 或者它们互相评审来筛选最优解，这种模式在需要高质量决策的场景特别有用，比如代码评审、方案选型。

好处：
- 1，并行执行，效率更高； Orchestrator 识别出哪些子任务之间没有依赖关系，就把它们同时派出去，等所有结果回来再统一整合
- 2，每个 Worker 的 context 是完全隔离的，程序员 Agent 不会被测试用例的信息干扰，测试 Agent 也不会被代码实现的细节淹没，各自在干净的环境里专注工作，输出质量也更高。

Multi-Agent系统的组织方式主要有两种:
- 一种是中心化，由一个统一的调度者来分配任务、收集结果;
- 另一种是去中心化，Agent之间自行协商、直接通信。两种方案各有取舍，工程上用得更多的是中心化方案，因为调度逻辑清晰、责任归属明确、排查问题也容易。


# 项目

## 什么时候创建agent

在prompt里里面约束，在prompt里面注入<subagent_system>，

```md
您已启用子代理功能。您的角色是**任务协调器**：

1. **分解**：将复杂任务分解为并行子任务

2. **委托**：使用并行 `task` 调用同时启动多个子代理

3. **综合**：收集结果并将其整合为一个连贯的答案

**核心原则：复杂任务应分解并分布到多个子代理上以进行并行执行。**

**⛔ 硬性并发限制：每个响应最多调用 {n} 个 `task` 函数。此限制不可更改。**

```


## 怎么创建 —— task_tool.py (line 21)：
```python

@tool("task", parse_docstring=True)
async def task_tool(
    runtime: ToolRuntime[ContextT, ThreadState],
    description: str,
    prompt: str,
    subagent_type: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    max_turns: int | None = None,
) -> str:

description：短描述，用于日志/展示
prompt：交给子 Agent 的完整任务说明
subagent_type：子 Agent 类型
max_turns：可选，最大轮数

runtime 和 tool_call_id 是框架注入的。
```

模式如果调用的话，大概率会生成：
```json
{
  "name": "task",
  "args": {
    "description": "Analyze auth flow",
    "prompt": "Inspect the authentication modules and summarize risks.",
    "subagent_type": "general-purpose"
  }
}

```

## 子 Agent 类型定义:

```
目前内置两个：
general-purpose：通用复杂任务子 Agent
bash：命令执行专家子 Agent

general-purpose 在 general_purpose.py (line 1)，它默认继承主 Agent 的所有工具，但禁止：
disallowed_tools=["task", "ask_clarification", "present_files"]

bash 在 bash_agent.py (line 1)，只允许：
tools=["bash", "ls", "read_file", "write_file", "str_replace"]
```

```python

BUILTIN_SUBAGENTS = {
    "general-purpose": GENERAL_PURPOSE_CONFIG,
    "bash": BASH_AGENT_CONFIG,
}

GENERAL_PURPOSE_CONFIG = SubagentConfig(name="general-purpose", description=""""""", system_prompt="", *****)

@dataclass
class SubagentConfig:
    name: str
    description: str
    system_prompt: str
    tools: list[str] | None = None
    disallowed_tools: list[str] | None = ["task"]
    model: str = "inherit"
    max_turns: int = 50
    timeout_seconds: int = 900

```

## 创建流程

```text
task_tool()
  -> get_subagent_config(subagent_type)
  -> 复制/覆盖子 Agent 配置
  -> 把 skills prompt 加入子 Agent system_prompt
  -> 从 parent runtime 提取 sandbox/thread/model/trace 信息
  -> get_available_tools(subagent_enabled=False)
  -> 创建 SubagentExecutor
  -> executor.execute_async(prompt, task_id=tool_call_id)
  -> 后台轮询结果
  -> 返回字符串给主 Agent
```

重点：子 Agent 禁止再拿 task 工具：
tools = get_available_tools(model_name=parent_model, subagent_enabled=False)

真正创建子 Agent 的地方在 executor.py (line 187)：

```python
def _create_agent(self):
    model_name = _get_model_name(self.config, self.parent_model)
    model = create_chat_model(name=model_name, thinking_enabled=False)

    middlewares = build_subagent_runtime_middlewares(lazy_init=True)

    return create_agent(
        model=model,
        tools=self.tools,
        middleware=middlewares,
        system_prompt=self.config.system_prompt,
        state_schema=ThreadState,
    )
```





