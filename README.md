# 政策跟踪知识库 · 工作区

管理一个政策知识库：定时收集、存储政策文件，每周输出一篇观点文章，按需生成分析报告。

**规则不在这个仓库。** 唯一规则来源是资料库里的 `AGENTS.md`
（`/Users/Mr_Zhou/Documents/知识库/资料库/AGENTS.md`），本仓库只放它的**工具**。

## 目录

| 路径 | 是什么 |
|---|---|
| `tools/run.py` | 唯一入口（解析参数 → 路由 → 聚合退出码），动作清单见 `run.py list` |
| `tools/pkb/core/` | 机制：路径／读写／frontmatter／Markdown 解析／`Result` 契约 |
| `tools/pkb/domain/` | 口径：黑名单、五领域等枚举、链卡映射、归档周名单——**只住这里** |
| `tools/pkb/checks/` | 各项判定，只返回 `Result` 不打印；`REGISTRY` 是唯一清单 |
| `tools/pkb/actions/` | 动作实现，一模块一动作 |
| `tools/tests/` | 单测：解析／口径与扫描器／契约与分层 |
| `automation-prompts/` | 三个自动化的提示词存档（`旧版/` 归档历史版本） |
| `.workbuddy/memory/` | 工作日志与项目长期记忆 |

## 跑

```bash
python3 tools/run.py check          # 全量自检
python3 tools/run.py list           # 列出全部动作与检查项（不用记数量）
python3 -m pytest -q tools/tests    # 单测
```

**数量不写进本文件**——动作数、检查项数、单测条数写死一次就过期一次，以 `run.py list` 为准。

## 状态

四层单向结构：`run.py → actions → checks → domain → core`，低层不 import 高层。
`归档/` 不入库（含 Obsidian 插件二进制），资料库本身也不在本仓库。
