---
name: mit-trader
description: 基于 MIT OpenCourseWare 18.S096《Topics in Mathematics with Applications in Finance》公开课方法的交易研究与模拟交易 skill。用户说 /mit-trader research、/mit-trader today、/mit-trader explain <概念>，或者想用课程里的数学（walk-forward 样本外检验、运气检验、GARCH 止损、蒙特卡洛 + Kelly 仓位、VaR）回测策略、出待批交易单、解释概念时使用。默认只写模拟账本，用户对某一笔回复 yes 才执行。
---

# mit-trader

把 MIT 18.S096 公开课里的方法做成三件事：夜里研究策略、每天出待批交易单、用大白话讲概念。
不是 MIT 官方出品，也不构成投资建议。

## 第一次使用（安装）

用户把仓库链接贴给你并说「安装 skill」时，按顺序做：

1 克隆到 skills 目录（Claude Code 读取 `~/.claude/skills/<名字>/SKILL.md`）：
   `git clone <仓库链接> ~/.claude/skills/mit-trader`
   只想在某个项目里用，就放到该项目的 `.claude/skills/mit-trader`。
2 装依赖（建议虚拟环境）：
   `cd ~/.claude/skills/mit-trader && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
3 跑一遍自检（不联网，用合成的测试市场）：`.venv/bin/python tests/test_smoke.py`
4 告诉用户装好了，并提醒：先打开 `config.yaml` 看一眼标的和风控上限。

数据：股票/ETF 默认用 Alpaca 行情（需设置 `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` 环境变量，失败自动退回 yfinance），加密用 ccxt 公共行情（默认 OKX，在 config.yaml 的 `crypto_exchange` 改）。

下面的命令都在 skill 目录里运行，`PY` 指 `.venv/bin/python`（没建虚拟环境就用 `python3`）。

## /mit-trader research

运行：`PY -m mit_trader research`

对 config.yaml 里每个标的、每类策略跑三关，三关全过才 APPROVED，其余 REJECTED：
1 样本外：walk-forward，参数只在训练段挑，在没见过的年份上打分。
2 运气检验：分块置换检验 + Benjamini-Hochberg 校正，再加 deflated Sharpe。
3 成本：扣手续费和滑点后还要达标，成本翻倍后 Sharpe 仍要大于 0。

向用户汇报时：
- 先说 APPROVED 几个、REJECTED 几个，再列表格里最值得注意的几行和「未过」原因。
- 全部 REJECTED 是正常结果，直接说今天没有站得住的策略，不要去放宽门槛凑结果。
- 表里的数是历史检验统计，不要说成收益承诺。
- 结果文件在 `~/.mit-trader/runs/`，通过的写进 `~/.mit-trader/approved.json`。

想先看流程是否正常：`PY -m mit_trader research --planted`（合成市场，埋了一个真实的动量优势，应当只有它被找出来）。

## /mit-trader today

运行：`PY -m mit_trader today`

对 approved.json 里的策略：
1 先检查模拟账本里的止损，再看今天有没有触发信号；
2 GARCH(1,1) 预测一日波动，止损 = k × σ × √持有天数；
3 用样本外日收益做蒙特卡洛（默认 10000 条路径），算 Kelly；Kelly ≤ 0 就不下；
4 实际仓位 = Kelly × kelly_fraction，再按单笔上限、单笔风险、总敞口截断；
5 算组合一日 VaR（历史法 + 参数法），超上限就缩仓或不下；
6 输出交易单，状态 pending_approval，存到 `~/.mit-trader/tickets/<日期>.json`。

把每张交易单原样念给用户：方向、数量、参考价、止损、金额、蒙特卡洛结果、VaR。然后问这一笔要不要执行。

## 批准规则（必须遵守）

- 只有用户针对某一张交易单明确回复 `yes`，才运行：
  `PY -m mit_trader approve <交易单ID> --answer yes`
- 「好」「可以」「ok」、或者笼统的「都下了吧」都不算；要么请用户逐笔回 yes，要么不执行。
- 用户说不要：`PY -m mit_trader reject <交易单ID>`
- 本版本只写模拟账本 `~/.mit-trader/paper_ledger.json`，不接真实券商。用户要求接实盘时，说明这个版本不支持。
- 查看模拟账本：`PY -m mit_trader ledger`

## /mit-trader explain <概念>

运行：`PY -m mit_trader explain <概念>`，可用：kelly、garch、var、walk_forward、luck_test、monte_carlo、cointegration、sharpe、momentum、mean_reversion、costs（中文名也行，比如 凯利、波动率、协整）。

把输出当底稿，按用户要求的难度改写。比如「讲到我 15 岁也能听懂」，就用生活里的例子讲，保留出处那一行（对应的 MIT 讲次或论文）。不要编造课程里没讲的讲次。

## 课程出处（只列在 OCW 讲义里核实过的）

| 用在哪 | 出处 |
|---|---|
| 动量策略类别 | 第 1 讲 Introduction, Financial Terms and Concepts（讲义列出 momentum 类策略） |
| VaR、蒙特卡洛模拟 | 第 7 讲 Value At Risk (VAR) Models |
| 均值回归的时间序列基础 | 第 8 讲 Time Series Analysis I（平稳性、自回归） |
| GARCH(1,1) 止损 | 第 9 讲 Volatility Modeling |
| 协整配对 | 第 12 讲 Time Series Analysis III |
| Sharpe 比率 | 第 14 讲 Portfolio Theory |
| Kelly | Kelly (1956)；第 25 讲讲义在讲增长最优组合时引用 |
| walk-forward、置换检验、BH 校正、deflated Sharpe、突破策略 | 非课程内容，见 concepts/ 里的文献 |

## 定时（可选）

用户要求 24 小时运行时，帮他设 cron 或 Claude Code 定时任务，命令见 README.md 的「定时示例」。只写模拟账本，交易单仍然要逐笔回 yes。
