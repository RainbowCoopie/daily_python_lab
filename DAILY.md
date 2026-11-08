# 每日工作手册

这个仓库由助手全权维护。每天一次，按下面的流程走。

## 铁律

1. **闸门必须全绿才提交**：`compileall` + 密钥扫描 + `pytest`。宁可当天不提交，也不推跑不起来的代码。
2. **不占显卡**：流水线默认纯模板。`--llm` 只在用户明确同意时用。
3. **一天一次提交**，message 说清今天做了什么。
4. **每天的东西必须和之前不同**：新主题、新功能、或对旧项目的实质改进。禁止换个名字重复提交。
5. **不改用户的其他项目**，只动本仓库。

## 每天做什么（按优先级挑一个）

### 第 0 步：先去网上找灵感（几乎每天都要做）
不要凭空想，也不要看"50 个 Python 项目"这种榜单——那类选题全是玩具。
要去看**具体的、有点怪的真实东西**：

- Hacker News 的 Show HN / Ask HN（别人做的小工具、抱怨的痛点）
- Wikipedia:Unusual articles —— 怪词条里常藏着数据结构或解析难题
- PyPI 最近更新 / GitHub trending 里的小库，看它的 README 解决了什么
- 厂商文档里的坑（Excel 的 XFD、Unicode 宽度、时区、编码），这些坑每个人都踩过
- Stack Overflow 高票的怪问题、Reddit r/Python 的吐槽

判断标准：**这个东西我自己会不会用三次以上？** 会，才值得写。
选定后在模块 docstring 里写清"灵感来源 + 为什么值得单独做一层"。

### A. 新主题（默认）
技术栈相关的新工程，写成一个主题模块，之后可复用。

1. 按第 0 步找灵感（可以联网，找真实痛点而不是玩具）
2. 在 `lab/topics/<slug>.py` 新建模块，导出：
   `SLUG / TITLE / TAGS / PKG / SUMMARY / STACK_NOTES / NOTES / FILES`
   `FILES` 里必须含**可运行的实现 + pytest 用例**，只用标准库
3. `python -m lab run --slug <slug>` —— 闸门过了会自动提交推送

### B. 维护旧项目
挑最久没动过的那个项目，做一件真事：补边界测试、修 bug、加一个合理功能、拆函数、补文档。
改完 `python -m lab publish -m "..."`。

### C. 流水线改进
改 `lab/` 自己。同样走 `python -m lab publish -m "..."`。

## 命令

```powershell
.\.venv\Scripts\python.exe -m lab topics                    # 主题库使用情况
.\.venv\Scripts\python.exe -m lab run --slug <slug>         # 新主题发布
.\.venv\Scripts\python.exe -m lab dry --slug <slug>         # 只校验不提交
.\.venv\Scripts\python.exe -m lab publish -m "说明"         # 维护/改进后发布
.\.venv\Scripts\python.exe -m lab status                    # 历史
```

## 兜底

Windows 计划任务 `DailyPythonLab`（21:00）会在"今天还没成功跑过"时补一个模板项目。
主力是助手每天 09:30 的定时工作，兜底只在助手没跑的时候生效（`--if-idle`）。

## 选题库现状

见 `INDEX.md`。已完成的主题不再重复写，除非是维护。
