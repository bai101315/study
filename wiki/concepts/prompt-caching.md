---
title: Prompt Caching
created: 2026-06-22
updated: 2026-06-22
type: concept
tags: [prompt-caching, design-decision]
sources: [agent/prompt_builder.py, agent/conversation_loop.py, agent/prompt_cache.py]
---

# Prompt Caching

Hermes 的三层 prompt 缓存架构，目的是在 multi-turn 对话中最大化 token 重用，
减少输入成本。

## 三层 Prompt

```
┌────────────────────────────────────────────┐
│ STABLE 层（不变）                          │
│ SOUL.md, tool guidance (MEMORY_GUIDANCE,  │
│ SKILLS_GUIDANCE, etc.), skills index,      │
│ environment hints, platform hints          │
├────────────────────────────────────────────┤
│ CONTEXT 层（按 project 变化）              │
│ AGENTS.md / .cursorrules, user-supplied    │
│ system_message                             │
├────────────────────────────────────────────┤
│ VOLATILE 层（每 session 变化）             │
│ MEMORY.md frozen snapshot, USER.md frozen  │
│ snapshot, external memory provider block,  │
│ date-stable timestamp                      │
└────────────────────────────────────────────┘
```

STABLE 和 CONTEXT 层在整个 session 中**不变化**，因此享受完整的 prompt cache 命中。
只有 VOLATILE 层的 ~2KB（memory snapshot）可能变化——但它在 prompt **末尾**，
不影响前面的 prefix cache。

## Anthropic Native Caching

对于 Anthropic 原生 API 和兼容网关（OpenRouter），`apply_anthropic_cache_control()`
在 API 消息上注入 `cache_control` breakpoints：system prompt 的最后一 block +
最后 3 条消息。输入 token 成本降低约 75%。

对于非 Anthropic provider，这层被自动跳过。

## SQLite 持久化

System prompt 在首次构建后写入 SQLite（session DB）。跨进程恢复时（gateway 每
消息创建新 AIAgent），直接从 DB 加载而不是重建。重建会读取磁盘上的最新 memory
快照，产生不同的 system prompt → break cache prefix → 缓存全部失效。

## Hermes 不变式

**System prompt 在每个 session 中只构建一次。** 缓存到 `agent._cached_system_prompt`，
后续所有 turn 原封不动地重放。这是 prompt caching 的基础契约——任何修改（包括
插件注入）都不进入 system prompt，而是注入到 user message 中。

## 关系

- [[memory-system]] — frozen snapshots 被设计为 session-stable 以保护 cache
- [[conversation-loop]] — 循环中组装 api_messages 时注入 cache_control
- [[agent-init]] — system prompt 在首次 `run_conversation()` 时延迟构建
