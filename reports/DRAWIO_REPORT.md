# DrawIO 图示生成报告

## 图示清单

| 文件 | 类型 | 来源依据 | 用途 | 状态 |
|---|---|---|---|---|
| `figures/fig_roadmap.drawio` / `.pdf` | 整体技术路线图 | `ANALYSIS_MODELING_REPORT.md` 第 1、3、11 节；三问继承关系 | 展示“数据标准化 → 问题一 → 问题二 → 问题三 → 独立验证 → 结果输出”主线 | 已完成 |
| `figures/fig_flow_q1.drawio` / `.pdf` | 问题一求解流程图 | 第 5 节；理论下界、最低可行机队、可行优先 | 说明任务展开、下界起点、增机判定和 `C=max T_k` 优化 | 已完成 |
| `figures/fig_flow_q2.drawio` / `.pdf` | 问题二求解流程图 | 第 6 节；固定 `N_min`、字典序 `(C,δ,D)`、跨路线邻域 | 说明均衡优化、候选接受和停止条件 | 已完成 |
| `figures/fig_flow_q3.drawio` / `.pdf` | 问题三动态禁飞处理流程图 | 第 7 节；线段-圆几何判断、时间重叠、等待/绕行/重排、增机 | 说明动态禁飞区的几何—时间联合决策与时刻传播 | 已完成 |
| `figures/fig_model.drawio` / `.pdf` | 统一模型结构/变量关系图 | 第 3、4、5、6、7、9 节；任务、路线、时间、目标和验证器接口 | 展示统一任务集合、路线决策、时间依赖边和三问目标关系 | 已完成 |

每张图同时生成 `.svg`，便于后续编辑或矢量化排版。现有 `figures/` 中的 `q1_routes`、`q3_dynamic_routes`、`work_hours`、`case_comparison`、`multistart_convergence` 仍作为 Python 真实数据图保留，本阶段没有用 DrawIO 重画。

## 未生成图示及原因

- `fig_pipeline` 未单独生成：数据读取、单位换算和任务展开已经在 `fig_roadmap` 的输入层、`fig_flow_q1` 的前两步和 `fig_model` 的数据层中完整表达，单独再画会重复。
- 未生成统计图、路线图、收敛曲线、柱状图、热力图或分布图：这些属于阶段 3 的真实数据图，不属于 DrawIO 解释性图示。

## 导出与自检记录

- 已保留 5 个可编辑 `.drawio` 源文件，XML 均通过解析检查。
- 本机未找到 `drawio`、`draw.io` 或 `draw.io.exe` 命令，因此没有伪称使用 DrawIO CLI 导出。
- 使用 `code/export_drawio_pdfs.py` 按与源文件一致的节点、文字、颜色和连线规范生成同名 PDF/SVG；PDF 是论文可引用版本，源文件可直接在 diagrams.net 中继续编辑或重新导出。
- 5 个 PDF 和 5 个 SVG 均已生成且文件大小大于 0；使用 Poppler 临时栅格化检查后确认中文字体、节点边框、箭头方向和主要文字没有明显重叠。
- 导出脚本只生成 `figures/fig_*.pdf` 和 `figures/fig_*.svg`，未读取或修改 `results/`、`solver.py`、`reports/RESULTS_REPORT.md` 的真实数值。

## 给论文阶段的嵌入建议

| 图 | 建议章节 | 建议 caption |
|---|---|---|
| `fig_roadmap.pdf` | 问题重述或模型总览 | 三个子问题的统一技术路线 |
| `fig_model.pdf` | 符号说明/模型假设 | 任务集合、路线变量、时空约束与目标的关系 |
| `fig_flow_q1.pdf` | 问题一模型与算法 | 问题一的最低可行机队与最大工作时间求解流程 |
| `fig_flow_q2.pdf` | 问题二模型与算法 | 固定机队下的字典序负载均衡流程 |
| `fig_flow_q3.pdf` | 问题三模型与算法 | 动态禁飞区的几何—时间联合处理流程 |

