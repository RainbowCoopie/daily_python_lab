# daily_python_lab

每天一个小而完整的 Python 工程：新写、维护、加固轮着来，**编译和测试全绿之后**才提交到 GitHub。
选题围绕自己的技术栈：Python 后端 / 爬虫 / RPA / LLM / CV 标注 / 数据管道 / 消息队列。

日常怎么跑，见 [DAILY.md](./DAILY.md)。

## 为什么不是随机提交刷绿格子

生成器里有一道硬闸门：任何改动必须在 `venv` 里通过 `compileall` + 密钥扫描 + `pytest`，
否则当天的运行直接失败、不推任何东西。
所以仓库里出现的每一个目录，都是真能跑、真有测试的东西。

## 每天做什么

三种动作轮着来，不重复：

- **新主题** —— 写一个全新工程（实现 + pytest 用例，纯标准库），登记进主题库后发布
- **维护旧项目** —— 挑最久没动过的，补边界测试、修 bug、加一个合理功能
- **流水线改进** —— 改 `lab/` 自己

助手每天 09:30 定时执行（Windows 计划任务 21:00 兜底，只在当天没跑成功时补一个模板项目）。

## 工作原理

```
选题 → 模板脚手架 → 闸门(compileall + 密钥扫描 + pytest) → 重建索引 → git commit → push
```

- **模板脚手架**：每个主题在 `lab/topics/<slug>.py` 里有完整的源码与测试，纯标准库，离线可跑。
- **闸门**：任一项失败即中止，不推送。
- **幂等**：`--if-idle` 保证同一天不会重复提交。
- **LLM 环节**（默认关）：`--llm` 才会调用本地 ollama 补全挑战模块，会占用显卡。

## 目录

```
lab/
  cli.py        入口: run / publish / dry / status / topics / index
  catalog.py    主题注册表
  topics/       主题规格与模板（每天在这里加新的）
  scaffold.py   写盘 + 重建 INDEX.md
  codegen.py    LLM 补全回路（默认不用）
  validate.py   闸门
  publish.py    GitHub 发布
  state.py      运行历史与选题
tools/
  run_daily.ps1      兜底任务入口，带日志
  register_task.ps1  注册 Windows 计划任务
projects/        每天生成的项目
INDEX.md         自动维护的项目索引
DAILY.md         每日工作手册
```

## 日常命令

```powershell
.\.venv\Scripts\python.exe -m lab topics                     # 主题库还剩什么没写
.\.venv\Scripts\python.exe -m lab status                     # 运行历史
.\.venv\Scripts\python.exe -m lab dry --slug <slug>          # 只生成+校验，不提交
.\.venv\Scripts\python.exe -m lab run --slug <slug>          # 生成并发布新主题
.\.venv\Scripts\python.exe -m lab publish -m "说明"          # 维护/改进后发布任意改动
```

## 密钥

`GITHUB_TOKEN` 环境变量，或 `%USERPROFILE%\.dsh\secrets\github_token.txt`（已做 ACL 限制）。
token 只出现在 `git push` 的 URL 参数里，不写进 `.git/config`，也不进日志。

## 定时

```powershell
.\tools\register_task.ps1 -Time 21:00     # 兜底任务
```

任务名 `DailyPythonLab`，每天 21:00 跑，带 `--if-idle`：当天已有成功记录就跳过。
日志落在 `logs/`（保留 30 天）。
