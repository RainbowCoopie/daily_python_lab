# daily_python_lab

每天自动生成一个小而完整的 Python 工程，**编译和测试全绿之后**才提交到 GitHub。
选题围绕自己的技术栈：CPython / FastAPI / 爬虫 / RPA / LLM / CV 标注 / 消息队列。

## 为什么不是随机提交刷绿格子

生成器里有一道硬闸门：新项目必须在 `venv` 里通过 `compileall` + `pytest`，
并且通过密钥扫描，否则当天的运行直接失败、不推任何东西。
所以仓库里出现的每一个目录，都是真能跑、真有测试的东西。

## 工作原理

```
选题(LRU 轮转) → 模板脚手架 → (可选)ollama 补全挑战模块 → 闸门 → 重建索引 → git commit → push
```

- **模板脚手架**：每个主题在 `lab/topics/<slug>.py` 里有完整的源码与测试，纯标准库，离线可跑。
- **LLM 挑战模块**（可选）：主题额外带一份固定测试，本地 ollama 写实现，测试不过就带报错重试，
  还不过就整块丢掉 —— 不可运行的代码进不了仓库。
- **闸门**：`compileall` → 密钥扫描 → `pytest`，任一失败即中止。
- **轮转**：`state/history.json` 记录每次运行，按"最久没写过"选题，不会连着重复。

## 目录

```
lab/
  cli.py        入口: run / dry / status / index
  catalog.py    主题注册表
  topics/       十个主题的规格与模板
  scaffold.py   写盘 + 重建 INDEX.md
  codegen.py    LLM 补全回路
  validate.py   闸门
  publish.py    GitHub 发布
  state.py      运行历史与选题
tools/
  run_daily.ps1      定时任务调用的入口，带日志
  register_task.ps1  注册 Windows 计划任务
projects/        每天生成的项目
INDEX.md         自动维护的项目索引
```

## 日常命令

```powershell
.\.venv\Scripts\python.exe -m lab dry            # 只生成+校验，不提交
.\.venv\Scripts\python.exe -m lab run            # 完整跑一遍并推送（纯模板，不碰显卡）
.\.venv\Scripts\python.exe -m lab run --llm      # 额外让本地 ollama 补全挑战模块（会占显卡，默认关）
.\.venv\Scripts\python.exe -m lab status         # 看历史
```

## 密钥

`GITHUB_TOKEN` 环境变量，或 `%USERPROFILE%\.dsh\secrets\github_token.txt`（已做 ACL 限制）。
token 只出现在 `git push` 的 URL 参数里，不写进 `.git/config`，也不进日志。

## 定时

```powershell
.\tools\register_task.ps1 -Time 09:30
```

任务名 `DailyPythonLab`，每天跑一次，日志落在 `logs/`（保留 30 天）。
