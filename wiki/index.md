# Wiki Index

> Content catalog. Every wiki page listed under its type with a one-line summary.
> Read this first to find relevant pages for any query.
> Last updated: 2026-06-24 | Total pages: 10

## Entities

- [[aiagent]] — 核心类，代表一个完整的 AI agent 实例（~60 参数构造函数，init_agent 转发模式，6 阶段初始化）
- [[iteration-budget]] — TODO
- [[memory-store]] — TODO
- [[context-compressor]] — TODO

## Concepts

- [[conversation-loop]] — 核心 ReAct while 循环（4000 行，骨架 20 行 + 边界 3980 行）
- [[tool-system]] — 工具注册、发现、过滤、调度的完整链路（registry → check_fn → dispatch）
- [[tool-disclosure]] — 三层过滤：toolset 选择 → check_fn 过滤 → dynamic schema
- [[memory-system]] — 跨 session 持久记忆（frozen snapshots + nudge 机制 + 外部 provider）
- [[prompt-caching]] — 三层 prompt（STABLE/CONTEXT/VOLATILE）+ SQLite 持久化 + Anthropic cache_control
- [[guardrail-system]] — 行为约束（ToolCallGuardrailController + IterationBudget + 命令审批）
- [[llm-wiki-usage]] — LLM Wiki 使用指南：ingest/query/lint 三种操作、常见陷阱、vs Memory 对比
- [[trajectory]] — 对话轨迹保存（ShareGPT JSONL 格式，用于模型训练/微调）
- [[sandbox-system]] — TODO
- [[subagent-system]] — TODO
- [[skill-system]] — TODO
- [[cli-architecture]] — TODO
- [[context-compression]] — TODO

## Comparisons

## Queries
