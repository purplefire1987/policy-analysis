# 项目长期记忆（政策跟踪知识库）

> **本文件不复述规则。** 规则唯一来源＝`/Users/Mr_Zhou/Documents/知识库/资料库/AGENTS.md`（每次任务先读）。这里只记库外事实、位置、踩过的坑与「为什么这么定」的指针。

## 一、位置

- **库**：`/Users/Mr_Zhou/Documents/知识库/资料库`（Obsidian vault），`raw/` 只读。
- **工具**：`/Users/Mr_Zhou/WorkBuddy/2026-09-23-07-58-53/tools/`，统一入口 `run.py`（74 行，只解析参数→路由→聚合退出码）；实现在 `tools/pkb/` 包里。
- **git（10-25 建立）**：只在工作区 init，**资料库未纳入版本控制**。`归档/` 在 `.gitignore` 里（含 .obsidian 插件二进制）。
- **远程（10-25 已连）**：`git@github.com:purplefire1987/policy-analysis.git`（私有），`origin/main` 跟踪已建，12 个提交（首个是 GitHub auto-init 的 README，第二个起是重构）。SSH 密钥 `~/.ssh/id_ed25519`（无口令，供自动化推送），公钥已贴账号级 SSH keys，`ssh -T` 返回 `Hi purplefire1987!`。**推送走 SSH 不走 MCP**：connector 令牌不能建库（403 `Resource not accessible by integration`），且 `push_files` 只能落成单个提交、要把 445 KB 内容全过一遍上下文——只适合改一两个文件。
- **rebase 过的坑**：远端 auto-init 的 `README.md` 与本地同名，rebase 时唯一冲突；两版合并保留（远端那句「管理一个政策知识库…」是仓库描述，别丢）。
- **工作区（10-25 整理后）**：顶层只剩 `tools/`、`automation-prompts/`、`.workbuddy/`、`归档/`。`归档/备份/` 放 8 个 `政策库备份-*`；`归档/旧版/` 放 3 个 `政策库归档-*`（旧版方案与模板／已合并页面／log长条目）；`归档/散件/` 放 log 备份、周观点 W42 补节前快照与样例、空的来源清理报告。**归档只读，不要再往里写。**
- **专家包入口是符号链接，不是副本（10-25 晚改）**：`~/.workbuddy/plugins/.../gov-policy-analyst/skills/policy-kb-tools/scripts` → `/Users/Mr_Zhou/WorkBuddy/2026-09-23-07-58-53/tools`（绝对符号链接）。**物理上只有一份代码，所以没有"同步"这一步，也没有漂移**；`export` 动作已更名 `link`（`pkg/actions/link.py`），`MANIFEST.json` 已废弃删除。`check_docs.check_expert_scripts()` 判**形态**（`core/expert.py` 的四种：link／copy／alien／missing），实体副本即 exit 1 并列出差异。`link` 遇到副本里有改动会拒绝删除，须 `--force`。代价：专家包不自包含，整包拷走跑不起来（本机个人专家，可接受）。
- **已归档勿引用勿重建**：`政策跟踪运营方案`、`政策链总览`、`主题词表`。

## 二、库结构（10-25）

`AGENTS.md` 唯一规则（约 437 行）｜`index.md` 唯一入口（第二节一张表＝15 链＋33 卡归属＋33 受控词）｜`wiki/总览/` 6 页｜`政策卡片/` 33 卡平铺｜`政策链/` 15｜`政策信号/` 15｜`周观点/`、`分析/` 平铺｜`templates/`｜`log.md`（只记决策与事故，置顶，≤80 行）。
三层分类：载体层（产业卡＝内容）／索引层（15 链＝目录）／粗筛层（四领域）。混用是历史归类错误根源。

## 三、三个自动化与专家

- 采集 `d1ca26c1` 每日 09:00／体检 `96885a01` 每 2 天 22:00／周观点 `3ef2d6b6` 周一 **10:30**（10-25 由 08:00 改后，晚于采集窗口收口）。互不通信，**唯一交换介质是文件**（采集写台账→体检读；采集写信号→周观点读）。
- **政务分析助手** `gov-policy-analyst`（`~/.workbuddy/plugins/marketplaces/my-experts/plugins/`）。MD 不复述规则，只写读哪份、跑哪条、边界在哪。改它用 expert-manager skill（头像已生成，勿重跑）。
- 提示词存档 `automation-prompts/`；**改提示词前先给差量等确认**；新建/删除自动化须用户要求。
- **统一入口 ≠ 统一退出码**：按单项判定一律写「看输出里 `xxx.py` 那一行的退出码」。

## 四、tools（10-25 重构为四层，`tools/` 顶层只剩 `run.py`）

- **分层单向**：`run.py → pkb.actions → pkb.checks → pkb.domain → pkb.core`。低层不许 import 高层。
- **`core` 的规则（10-25 修订）**：`core` **不含口径**（名单/枚举/判据），但**可以有目录名与结构名**（`wiki/政策卡片`、`### 日期 · 标题`）——前者是「规则是什么」，后者是「数据在哪」。原文「不许出现『政策』二字」与必需的路径常量直接冲突，已废。判据是「与 domain 某取值同值」，不是「出现某个词」。
- `pkb/core/`：paths（唯一路径，`TOOLS = parents[2]`）／fs（`py_files(TOOLS)` 是「哪些文件该导出/校验」唯一出口）／fm／md／report（`Verdict` 枚举 + `Result`，**`summary` 无默认值**→「有退出码没摘要」写不出来；`Reporter.to_lines()`）。
- `pkb/domain/`：blacklist（`BLACK`／`BAD_SUBJECT`／`DOC_MUST_MENTION`／`is_bad`）／fields（五领域等枚举）／chains（`FIELD_MAP`）／legacy（`LEGACY_WEEKS`）。**口径只能住这里**。
- `pkb/checks/`：**7 项** + `REGISTRY`（`Spec(name, module, needs_all, flags, fixable)`）。**注册表即清单**，不再按文件名发现；`run()` 返回 `Result`、不打印、不 `sys.exit`。
- **`check_health.py`（10-25 新增）**：采集健康三分状态——`正常`／`已跑但 0 新增`（没采到，别重跑自动化）／`根本没跑`（超 1 天节拍）。另交叉核对「采集灯 vs 日志」（矛盾即 FAIL）与「0 也写 0」（**固定生效日 2026-10-24**，更早的 `—` 只提示；不用滑动窗口，否则违规拖两周自动消失）。
- `pkb/actions/`：8 个动作 + `_proc`（`sh`／`capture` 用 `redirect_stdout` 抓子步骤数字）。
- **摘要行契约**：`Result.summary` 就是 `▸摘要`；明细在 `Result.lines`，打多少由 `actions/check.py` 一层决定（`--only`／`--full`）。
- 动作 8 个：`status／check／fix／plan／week／link／sources／list`（`link` 原叫 `export`，10-25 晚改）。**一模块一动作，文件名即动作名，下划线开头是内部件**（`_proc`／`_snapshot`）；`run.py` 的 `ACTIONS` 与 `pkb/actions/*.py` 由 `test_smoke` 钉住一一对应，`list` 从包里发现模块不手写名单。参数按**真注册**判定，无认领 **exit 2** 并明说结论不含该窗口。扩展方式见 AGENTS 第十节四条（改注册表，不靠命名）。
- `check_docs` 新增**口径单源扫描**：`ast` 取代码里的字符串常量，与 `pkb.domain.__all__` 现读的词典比对，命中即 exit 1；`REQUIRED_FIELDS`（字段名＝读数据的键）排除。词典不另写，domain 加一项自动覆盖。
- `tests/`（**68 条**）：`test_md`（解析）／`test_rules`（口径＋扫描器自测）／`test_health`（三分状态、灯矛盾、无轮次、0也写0）／`test_link`（专家包四态、三类差异、拒绝删除、force 后入口可跑）／`test_smoke`（`Result` 契约、非法输入是 `BAD_INPUT`、导入无副作用、分层不反向、checks 不 `sys.exit`、**单函数 ≤50 行**、**动作模块↔ACTIONS 一一对应**）。
- **CI（10-25 挂上）**：`.github/workflows/ci.yml`，每次 push/PR 跑 pyflakes ＋ **空库** pytest（`POLICY_KB_VAULT` 指空目录＝最强契约输入，六项检查全走「文件不存在」分支）。CI **不跑** `run.py check`（要真库，守门人是体检自动化）。
- `fix` 只修快照、frontmatter 数值、唯一相似断链（≥0.85 单候选）、黑名单来源、副本同步；跳过 log.md；多候选不猜。

## 五、踩过的坑

1. **自愈机制必须被验证过一次才算存在**：`--fix` 正则写全角冒号而库里用半角，从建立起没修成过且不报错。
2. **判据必须是真声明不能是文本包含**（check_docs 因注释含 `--fix` 被误编进修复队列）。
3. **没有校验的副本等于迟早撒谎**：4 次事故全是库外副本漂移；今天起动作表也纳入 check_actions。
4. **单源化本身就是修漏洞**：黑名单合并时发现两份清单已漂移。
5. **静默丢弃比报错危险**：拼错的参数照跑 exit 0，调用方以为窗口核过了。
6. 并行子代理必 429，批量补录走主通道；`%%` 注释不成对会吞正文，用 `<!-- -->`；能点开≠能核验。
7. **判据写进解释性文本里会被自己误伤**：`sys.exit(` 判据被 docstring 里的「原来是 print + sys.exit(2)」误报；`python3 -m pkb…` 写进 AGENTS 说明就被直调正则判成违规。判据认**调用形态**（行首调用／ast 常量），说明文字用描述性措辞。
8. **macOS 是 BSD grep**：`grep "a\|b"` 不支持 `\|` 交替，会静默无输出（排查时白白怀疑文件编码）。用 `grep -E` 或 Grep 工具。
9. **AST 优于逐行正则**：注释/docstring 里举的例不能被当代码；第一版口径扫描把 `docs.py` 自己的 docstring 判成违规。

## 六、三页分工

采集日志管「采到哪天」（**0 也写 0，禁 `—` 与留空**）／运行状态管「跑没跑」（灯）／任务台账管「修没修」（🆕→🟡→⏳→✅／⛔／🚫，只改状态不删行）。台账含三个游标（断档补采、存量队列、清欠进度）。`plan_backlog` 常数 `STOCK_GAP=14／STOCK_BATCH=14／GAP_BATCH=2／GAP_TRIGGER=3／VIEW_DAILY=3／VIEW_WEEKLY=5／CLAIM_PER_CHECK=1`，**领取闸门＝体检节拍**。体检产出＝三页，须写「本期释放了哪页哪批」。

## 七、文档纪律

规则只写一处；同一批事实只列一张表；易变数量不写死；log 只回答「当时为什么这么定」。政策速览按链分布用 1 个 GROUP BY 查询。台账同类项合并并注「原 T-xxx 并入」，不删行。

## 八、遗留（详见任务台账）

观点覆盖率欠账 T-01（102/159）、信号页长期空白 T-02、信号八字段存量 T-12、待核来源 T-16（剩 76 处按批次）、政策原文缺官方链接 T-15。W39–W41 周观点漏采已决定不回补，`--all` 报红属预期。
