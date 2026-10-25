# 项目长期记忆（政策跟踪知识库）

> **本文件不复述规则。** 规则唯一来源＝`/Users/Mr_Zhou/Documents/知识库/资料库/AGENTS.md`（每次任务先读）。这里只记库外事实、位置、踩过的坑与「为什么这么定」的指针。

## 一、位置

- **库**：`/Users/Mr_Zhou/Documents/知识库/资料库`（Obsidian vault），`raw/` 只读。
- **工具**：`/Users/Mr_Zhou/WorkBuddy/2026-09-23-07-58-53/tools/`，统一入口 `run.py`。
- **工作区（10-25 整理后）**：顶层只剩 `tools/`、`automation-prompts/`、`.workbuddy/`、`归档/`。`归档/备份/` 放 8 个 `政策库备份-*`；`归档/旧版/` 放 3 个 `政策库归档-*`（旧版方案与模板／已合并页面／log长条目）；`归档/散件/` 放 log 备份、周观点 W42 补节前快照与样例、空的来源清理报告。**归档只读，不要再往里写。**
- **专家包部署副本**：`~/.workbuddy/plugins/.../gov-policy-analyst/skills/policy-kb-tools/scripts/` 是 `tools/*.py` 的部署副本，由 `run.py export` 生成并写 `MANIFEST.json`（sha256）；`check_docs` 每次体检比对，漂移即 exit 1。**源永远是 `tools/`**，不许在专家包内改了再同步回来。
- **已归档勿引用勿重建**：`政策跟踪运营方案`、`政策链总览`、`主题词表`。

## 二、库结构（10-25）

`AGENTS.md` 唯一规则（约 437 行）｜`index.md` 唯一入口（第二节一张表＝15 链＋33 卡归属＋33 受控词）｜`wiki/总览/` 6 页｜`政策卡片/` 33 卡平铺｜`政策链/` 15｜`政策信号/` 15｜`周观点/`、`分析/` 平铺｜`templates/`｜`log.md`（只记决策与事故，置顶，≤80 行）。
三层分类：载体层（产业卡＝内容）／索引层（15 链＝目录）／粗筛层（四领域）。混用是历史归类错误根源。

## 三、三个自动化与专家

- 采集 `d1ca26c1` 每日 09:00／体检 `96885a01` 每 2 天 22:00／周观点 `3ef2d6b6` 周一 08:00。互不通信，**唯一交换介质是文件**（采集写台账→体检读；采集写信号→周观点读）。
- **政务分析助手** `gov-policy-analyst`（`~/.workbuddy/plugins/marketplaces/my-experts/plugins/`）。MD 不复述规则，只写读哪份、跑哪条、边界在哪。改它用 expert-manager skill（头像已生成，勿重跑）。
- 提示词存档 `automation-prompts/`；**改提示词前先给差量等确认**；新建/删除自动化须用户要求。
- **统一入口 ≠ 统一退出码**：按单项判定一律写「看输出里 `xxx.py` 那一行的退出码」。

## 四、tools（14 文件，10-25 重构）

- `lib.py` 机制层（路径／`read`／`parse_fm`／`extract_sections`／`table_rows`／`parse_date`／`iso_week`／`Reporter`／`summary`）。判据：同一件事出现两处以上就搬进来；**口径不进 lib**（黑名单单列 `source_blacklist.py`）。
- **摘要行契约**：每个 `check_*.py` 调 `lib.summary()` 输出 `▸摘要: …`，入口只认这一行；明细走 `--only <名字>`，`--full` 只用于排查脚本自身。
- 6 个 `check_*`：structure（唯一带 --fix，含体积警告）／views（覆盖率恒 0）／signals（断档）／week_coverage（`--week`）／analysis／docs（文档＋log＋域名＋库内不得直调脚本＋**动作表三处同集合**，刻意无 --fix）。
- 其余：`refresh_snapshot`（只写 index，体检须先于 structure）／`clean_sources`（默认 dry-run）／`plan_backlog`／`status_report`／`week_sources`（周索引＋行号，省 99% 读入）／`export_expert`（同步专家包副本）／`run.py`（只调度）。
- 动作 8 个：`status／check／fix／plan／week／export／sources／list`。参数按**真注册**判定，无认领 **exit 2** 并明说结论不含该窗口。扩展约定见 AGENTS 第十节四条。
- `fix` 只修快照、frontmatter 数值、唯一相似断链（≥0.85 单候选）、黑名单来源；跳过 log.md；多候选不猜。

## 五、踩过的坑

1. **自愈机制必须被验证过一次才算存在**：`--fix` 正则写全角冒号而库里用半角，从建立起没修成过且不报错。
2. **判据必须是真声明不能是文本包含**（check_docs 因注释含 `--fix` 被误编进修复队列）。
3. **没有校验的副本等于迟早撒谎**：4 次事故全是库外副本漂移；今天起动作表也纳入 check_actions。
4. **单源化本身就是修漏洞**：黑名单合并时发现两份清单已漂移。
5. **静默丢弃比报错危险**：拼错的参数照跑 exit 0，调用方以为窗口核过了。
6. 并行子代理必 429，批量补录走主通道；`%%` 注释不成对会吞正文，用 `<!-- -->`；能点开≠能核验。

## 六、三页分工

采集日志管「采到哪天」（**0 也写 0，禁 `—` 与留空**）／运行状态管「跑没跑」（灯）／任务台账管「修没修」（🆕→🟡→⏳→✅／⛔／🚫，只改状态不删行）。台账含三个游标（断档补采、存量队列、清欠进度）。`plan_backlog` 常数 `STOCK_GAP=14／STOCK_BATCH=14／GAP_BATCH=2／GAP_TRIGGER=3／VIEW_DAILY=3／VIEW_WEEKLY=5／CLAIM_PER_CHECK=1`，**领取闸门＝体检节拍**。体检产出＝三页，须写「本期释放了哪页哪批」。

## 七、文档纪律

规则只写一处；同一批事实只列一张表；易变数量不写死；log 只回答「当时为什么这么定」。政策速览按链分布用 1 个 GROUP BY 查询。台账同类项合并并注「原 T-xxx 并入」，不删行。

## 八、遗留（详见任务台账）

观点覆盖率欠账 T-01（102/159）、信号页长期空白 T-02、信号八字段存量 T-12、待核来源 T-16（剩 76 处按批次）、政策原文缺官方链接 T-15。W39–W41 周观点漏采已决定不回补，`--all` 报红属预期。
