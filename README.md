# Study Notes

这个仓库用于整理求职、笔试、面试和 Agent 工程项目理解相关资料。内容主要分为四类：算法模板、笔试复盘、AI Agent 项目八股、真实面经与回答稿。

## 快速导航

- [Study Notes](#study-notes)
  - [快速导航](#快速导航)
  - [目录结构](#目录结构)
  - [Agent 项目理解](#agent-项目理解)
  - [Hermes Agent 源码学习](#hermes-agent-源码学习)
  - [算法与笔试](#算法与笔试)
    - [算法模板](#算法模板)
    - [华为笔试复盘](#华为笔试复盘)
    - [选择题复盘](#选择题复盘)
  - [面试复盘](#面试复盘)
  - [资料与素材](#资料与素材)
  - [维护约定](#维护约定)

## 目录结构

```text
.
├── algorithm/              # 算法模板与刷题套路
├── notes/                  # 笔试选择题、华为 AI 岗笔试复盘
│   ├── choice/
│   └── huawei/
├── 八股+项目理解/           # Agent 项目介绍、八股问答、工程机制拆解
├── hermes_study/           # Hermes Agent 源码机制学习笔记
├── 面经/                   # 公司面试记录、问题清单、回答稿
│   └── 答案/
├── assets/images/          # Markdown 图片素材
├── 对比.md                 # AI 行业、竞品与 Agent 框架对比资料
└── main.py                 # 临时算法练习脚本
```

## Agent 项目理解

这部分围绕一个基于 LangGraph / LangChain 的本地多 Agent 运行时框架展开，重点关注多 Agent、工具治理、MCP、长期记忆、沙箱、中间件和上下文管理等工程问题。

推荐阅读顺序：

1. [项目介绍](八股+项目理解/项目介绍.md)
2. [Function Calling](八股+项目理解/01_function_calling.md)
3. [LLM 如何学会调用外部工具](八股+项目理解/02.md)
4. [MCP](八股+项目理解/03_MCP.md)
5. [Skill](八股+项目理解/04_skill.md)
6. [Multi-Agent](八股+项目理解/05_multi-agent.md)
7. [ReAct / Plan-and-Execute / Reflection](八股+项目理解/06_三种范式区别.md)
8. [A2A](八股+项目理解/07_A2A.md)
9. [Memory 机制](八股+项目理解/08_memory.md)
10. [信息载体](八股+项目理解/09_信息载体.md)
11. [中间件](八股+项目理解/10_中间件.md)
12. [Sandbox](八股+项目理解/11_sandbox.md)
13. [长期记忆面试版](八股+项目理解/12_memory.md)
14. [Sub-Agent](八股+项目理解/13_sub-agent.md)

补充主题：

- [RAG](八股+项目理解/RAG.md)
- [SSE / HTTP / WebSocket](八股+项目理解/SSE_http_Web.md)

## Hermes Agent 源码学习

`hermes_study/` 主要记录 Hermes Agent 的源码机制和工程设计，适合用来和自己的 Agent 项目做对照。

- [Agent 本质与核心循环](hermes_study/agent.md)
- [工具系统与渐进式披露](hermes_study/tool.md)
- [MCP 工具治理](hermes_study/MCP_tool.md)
- [Sub-Agent](hermes_study/sub-agent.md)
- [Memory](hermes_study/memory.md)
- [Sandbox](hermes_study/sandbox.md)
- [中间件与行为约束](hermes_study/middle.md)
- [日志与观察架构](hermes_study/log.md)
- [Prompt Cache](hermes_study/prompt_cache.md)
- [Hermes vs Deer Prompt Cache](hermes_study/prompt%20cache_vs_deer.md)
- [Self-Improving](hermes_study/self-improving.md)

## 算法与笔试

### 算法模板

- [二分](algorithm/二分.md)
- [动态规划](algorithm/动态规划.md)
- [图论](algorithm/图论.md)
- [数据结构](algorithm/数据结构.md)
- [滑动窗口](algorithm/滑动窗口.md)
- [链表、树、回溯](algorithm/链表_树_回溯.md)

### 华为笔试复盘

- [华为 04 月 08 号 AI 岗](notes/huawei/华为-04月08号AI岗.md)
- [华为 4.15](notes/huawei/华为4.15.md)
- [华为 4.22](notes/huawei/华为4.22.md)
- [华为 4.23 笔试](notes/huawei/华为4.23笔试.md)
- [华为 5.9 笔试复盘](notes/huawei/华为5.9.md)

### 选择题复盘

- [笔试选择题 02](notes/choice/笔试选择题02.md)
- [笔试选择题 03](notes/choice/笔试选择题03.md)

## 面试复盘

`面经/` 记录真实面试问题、追问方向和后续整理出的回答稿。

- [面经总览](面经/面经.md)
- [联想一面回答稿](面经/答案/联想一面.md)
- [顺丰一面回答稿](面经/答案/顺丰一面.md)
- [信息抽取 Prompt](面经/prompt.md)
- [Prompt 模板](面经/prompt模板.md)

覆盖过的方向包括：

- Agent 项目介绍、项目难点、工程亮点
- MCP、DeferredToolRegistry、Skill、tool_search
- 多 Agent 上下文隔离与子 Agent 通信
- Memory、Checkpoint、Sandbox、中间件
- RAG 权限控制、文档权限设计
- LangChain / LangGraph / Hermes / OpenClaw 对比
- Python 基础、408 基础、算法手撕

## 资料与素材

- `assets/images/`：统一存放 Markdown 中引用的图片。

## 维护约定

- 新增图片统一放在 `assets/images/`。
- 从 `notes/huawei/` 或 `notes/choice/` 引用图片时，使用 `../../assets/images/图片名`。
- 项目理解类笔记放在 `八股+项目理解/`，源码学习类笔记放在 `hermes_study/`。
- 面试问题原始记录放在 `面经/面经.md`，整理后的回答稿放在 `面经/答案/`。
- 算法模板按主题放在 `algorithm/`，尽量保持“题型 -> 模板 -> 易错点”的结构。
