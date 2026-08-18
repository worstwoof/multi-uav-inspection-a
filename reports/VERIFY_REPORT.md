# 最终验收报告

## 1. 验收结论

**PASS**。四个 Case 的问题一、问题二和问题三正式结果均已生成并通过独立验证；论文已使用 XeLaTeX 成功编译，最终 PDF 已逐页渲染检查。`task-spec.md` 未修改，真实结果文件未修改。

本报告的“最低机队”均按“最低已验证可行机队”理解。结果由固定种子启发式搜索得到，没有精确 MIP 的全局最优性或不可行性证书。

## 2. 工程与论文清单

- 论文源文件：`paper/main.tex`、`paper/sections/*.tex`
- 最终 PDF：`paper/main.pdf`
- 代码目录：`code/`，入口为 `code/run_all.py`，核心校验和几何逻辑在 `code/core.py`
- 结果目录：`results/`，包括 `q1_case*.json`、`q2_case*.json`、`q3_case*.json`、固定原机队对照和 `summary.csv`
- 分析报告：`reports/ANALYSIS_MODELING_REPORT.md`
- 结果报告：`reports/RESULTS_REPORT.md`
- 图示报告：`reports/DRAWIO_REPORT.md`
- 本验收报告：`reports/VERIFY_REPORT.md`
- `submission/` 目录当前不存在；最终可提交论文文件为 `paper/main.pdf`

论文目录顺序为：摘要、目录、问题背景与重述、数据理解与总体思路、模型假设与符号说明、问题一、问题二、问题三、运行稳定性与结果核验、模型评价与结论、参考文献。

## 3. 三问模型与算法

| 问题 | 模型与目标 | 实现方法 |
|---|---|---|
| 问题一 | 统一基地、重复任务展开的 min--max 多旅行商模型；先从理论下界搜索首个可行机队，再最小化 `C=max T_k` | 固定种子多起点构造，relocate、swap、2-opt 修复与局部改进；独立验证后保留 `best_verified` |
| 问题二 | 继承问题一机队和全部硬约束，字典序 `lexmin(C, delta, D)`，其中 `delta=max T_k-min T_k` | 跨路线 relocate、任务块移动、swap、2-opt*、cross-exchange 和局部 2-opt |
| 问题三 | 动态禁飞区的时空路径模型；同时检查线段--圆几何相交、飞行时间重叠、服务和基地停留，目标为 `lexmin(N_3,C_3,delta_3,D,W)` | 时间依赖边函数，比较直飞、安全等待、切线--圆弧绕行和任务重排；不可行时逐架增加无人机 |

任务覆盖统一采用有效到达规则：相邻相同 `Point_ID` 合并，`A-A-A` 计 1 次，`A-B-A` 计 2 次。

## 4. 正式结果核对

### 问题一

| Case | UAV | `Tmax`/h | `Tmin`/h | `delta`/h | 距离/km |
|---|---:|---:|---:|---:|---:|
| Case1 | 5 | 8.7129 | 8.4955 | 0.2174 | 2040.643 |
| Case2 | 2 | 7.9583 | 7.9202 | 0.0382 | 236.233 |
| Case3 | 6 | 8.6125 | 8.5326 | 0.0799 | 2189.495 |
| Case4 | 5 | 8.1378 | 7.7700 | 0.3678 | 1371.655 |

### 问题二

| Case | UAV | `Tmax`/h | `Tmin`/h | `delta`/h | 距离/km |
|---|---:|---:|---:|---:|---:|
| Case1 | 5 | 8.6139 | 8.5243 | 0.0896 | 2028.679 |
| Case2 | 2 | 7.8011 | 7.7984 | 0.0027 | 220.889 |
| Case3 | 6 | 8.5980 | 8.5004 | 0.0976 | 2180.421 |
| Case4 | 5 | 8.1378 | 8.0734 | 0.0644 | 1393.015 |

问题二的四个 Case 均继承问题一机队数量。

### 问题三正式可行结果

| Case | UAV | `Tmax`/h | `Tmin`/h | `delta`/h | 距离/km | 等待/h | 绕行/km |
|---|---:|---:|---:|---:|---:|---:|---:|
| Case1 | 5 | 8.7400 | 8.6139 | 0.1261 | 2055.201 | 0.000 | 0.000 |
| Case2 | 3 | 7.1608 | 7.1270 | 0.0338 | 458.129 | 1.503 | 0.000 |
| Case3 | 9 | 7.9812 | 7.7593 | 0.2219 | 3269.259 | 0.000 | 0.454 |
| Case4 | 7 | 8.3802 | 8.3109 | 0.0693 | 2376.159 | 0.000 | 0.000 |

固定问题二原机队对照中，Case1 可行；Case2、Case3、Case4 分别达到 10.1388 h、10.4125 h、10.3717 h，状态为 `infeasible_under_9h`，没有混入正式 q3 结果。

## 5. 已完成的验证

- 读取并核对 4 个 Case 的输入 JSON、任务集合、禁飞区和 `run_manifest.json`。
- 对 12 个正式 `q1/q2/q3` JSON 重新调用 `code/core.py` 验证器，全部通过任务覆盖、有效到达次数、相邻重复点、路线闭环、基地出发和返回、距离/时间重算以及 9 h 检查。
- q3 额外通过线段--圆几何、时间窗口重叠、服务点安全、等待传播、绕行记录和基地停留检查。
- 对每条正式路线核对 `task_id` 恰好出现一次；全部任务集合与输入展开任务集合相等。
- 核对问题二 `fleet_count` 与问题一一致，且继承的 `Tmax` 与 q1 JSON 一致。
- 逐行核对 `results/summary.csv` 的 16 条记录与对应 JSON 的机队、时间、距离、等待、绕行和 `valid` 字段，全部一致。
- 核对论文中的 q1/q2/q3 核心数值与 JSON/`RESULTS_REPORT.md`，全部一致。
- 核对 10 个论文 PDF 图件均存在；`paper/figures/` 与 `figures/` 中对应 PDF 的 SHA-256 全部一致。
- 检查论文占位符、内部工作流路径、缺失图片、重复章节、引用键和参考文献键；未发现正文占位符或内部路径泄露，3 个引用键均有对应参考文献。
- 补齐主要图表正文交叉引用；LaTeX 标签和引用无未定义项（`LastPage` 为宏包生成标签）。
- 使用 XeLaTeX 连续编译 3 次，命令返回码均为 0；最终 PDF 为 24 页、A4、约 768 KB。
- `main.log` 最终无 `Undefined`、`Missing`、`Overfull hbox`、`Underfull hbox` 或真正的 LaTeX 错误。日志中的字体信息为 Windows 字体族探测信息，不是缺失字形错误。
- 使用 Poppler 以 120 dpi 将最终 PDF 逐页渲染为 24 张 PNG；无空白页，横向页面为第 5、8、15、19 页，图示和表格无明显越界或重叠。

6verity 的 `writing_check.sh` 在本 Windows 环境直接调用时触发 WSL 挂载错误；将其 Python 检查逻辑在本地运行后，发现的摘要/参考文献“无 section”及相对 `graphicspath` 图片报错属于脚本对 LaTeX 工程的误报，已由上面的编译、文件存在性和交叉引用检查替代确认。该脚本同时因 `summary.csv` 的 UTF-8 BOM 不能按 JSON 解析，这不影响 JSON 真源和独立验证。

## 6. 主要图片

论文实际引用的真实数据图：`q1_routes.pdf`、`q3_dynamic_routes.pdf`、`work_hours.pdf`、`case_comparison.pdf`、`multistart_convergence.pdf`。

论文实际引用的解释性图：`fig_roadmap.pdf`、`fig_model.pdf`、`fig_flow_q1.pdf`、`fig_flow_q2.pdf`、`fig_flow_q3.pdf`。对应的 `.drawio` 可编辑源文件保留在 `figures/`。

## 7. 仍未解决的问题

1. 问题一和问题三的机队数量是固定种子启发式搜索下的最低已验证可行数量，没有精确 MIP 不可行性证书，因此不能声称全局最小。
2. `submission/` 目录尚未单独打包；当前最终论文路径是 `paper/main.pdf`。
3. 原始 `writing_check.sh` 不能在本机通过 WSL 挂载直接运行，验收采用等价本地检查和 XeLaTeX/Poppler 实证结果完成。

