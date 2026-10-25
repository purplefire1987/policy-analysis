# 政策跟踪知识库 · 工作区

管理一个政策知识库：定时收集、存储政策文件，每周输出一篇观点文章，按需生成分析报告。

**规则不在这个仓库。** 唯一规则来源是资料库里的 `AGENTS.md`
（`/Users/Mr_Zhou/Documents/知识库/资料库/AGENTS.md`），本仓库只放它的**工具**与**设计文档**。

## 目录

| 路径 | 是什么 |
|---|---|
| `tools/run.py` | 唯一入口（解析参数 → 路由 → 聚合退出码），8 个动作 |
| `tools/pkb/core/` | 机制：路径／读写／frontmatter／Markdown 解析／`Result` 契约 |
| `tools/pkb/domain/` | 口径：黑名单、五领域等枚举、链卡映射、归档周名单——**只住这里** |
| `tools/pkb/checks/` | 6 项判定，只返回 `Result` 不打印；`REGISTRY` 是唯一清单 |
| `tools/pkb/actions/` | 8 个动作的实现 |
| `tools/tests/` | 41 条单测（解析／口径与扫描器／契约与分层） |
| `automation-prompts/` | 三个自动化的提示词存档 |
| `docs/` | 模块化设计与自动化彩排报告 |
| `.workbuddy/memory/` | 工作日志与项目长期记忆 |

## 跑

```bash
python3 tools/run.py check          # 全量自检（8 个动作见 run.py list）
python3 -m pytest -q tools/tests    # 单测
```

## 状态

2026-10-25 完成四层模块化重构（`run.py → actions → checks → domain → core`，方向单向）。
`归档/` 不入库（含 Obsidian 插件二进制），资料库本身也不在本仓库。
