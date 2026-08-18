# 待办事项

## 阶段 1：项目扫描与计划建立

- [x] 完整读取 `task-spec.md`，确认原文件未被修改。
- [x] 递归扫描当前目录，盘点题目、附件、数据、代码、结果、图片和参考格式压缩包。
- [x] 完整读取 A 题 PDF（3 页）及附件 1、附件 2 的全部工作表。
- [x] 读取并分析参考 LaTeX 工程的 `main.tex`、全部章节、README、图片目录和已编译 PDF 元数据。
- [x] 核验已有 `result1.xlsx`、`result2.xlsx`、`result3.xlsx` 的汇总指标、原始路线条目、有效到达段、点 ID 范围和 9 h/禁飞标志。
- [x] 创建 `reports/`、`code/`、`results/`、`figures/`、`paper/sections/` 工程骨架。
- [x] 创建 `plan.md`，记录后续阶段输入、输出、依赖关系和风险。

## 后续阶段清单

- [x] 1. 赛题分析与建模设计 - `2analysis-modeling` -> `reports/ANALYSIS_MODELING_REPORT.md`
- [x] 2. 编程实现和图表生成 - `3coding-visual` -> `code/`、`results/`、`reports/RESULTS_REPORT.md`、真实数据图
- [x] 3. 流程与架构图绘制 - `4drawio` -> `figures/*.drawio`、非数据图 PDF、`reports/DRAWIO_REPORT.md`
- [x] 4. 竞赛论文撰写 - `5writing` -> `paper/main.tex`、`paper/sections/`
- [x] 5. 验证和验收 - `6verity` -> `reports/VERIFY_REPORT.md`、验收后的 `paper/main.pdf`

## 关键复核项

- [x] 阶段 2 明确理论下界、最低可行无人机数、三问连续建模主线及多次巡检解释。
- [x] 根据有效到达规则复核已有结果：相邻相同 Point_ID 合并，A-A-A 计 1 次，A-B-A 计 2 次；已有三份结果均存在有效到达缺口。
- [x] 阶段 3 对四个 Case 运行可复现求解并通过任务完成、回基地、9 h 和动态禁飞验证；重点复核现有 `result3.xlsx` Case2-4 超时问题。正式 q1/q2/q3 均通过独立验证；固定原机队的 Case2-4 动态对照保留为 `infeasible_under_9h`。
- [x] 阶段 4 严格区分真实数据图和非数据型流程/架构图。
- [x] 阶段 5 继承参考 LaTeX 版式，不复制 B 题内容，且所有数值来自 `results/`。
- [x] 阶段 6 完成数值、图表、交叉引用、字体、页面布局和 PDF 逐页检查。
