# 科研绘图模板适配记录

本目录只保留适合当前无人机巡检项目的模板实现。模板中的模拟数据生成逻辑已全部移除，最终图和中间 CSV 均由项目 `results/` 中的真实求解结果生成。

## 已采用模板

### grouped-circular-heatmap

- 适用原因：项目包含 4 个 Case、3 个问题和多项异量纲指标，适合用分组环形热图比较整体结构。
- 原始来源：`results/input_case*.json`、`results/q1_case*.json`、`results/q2_case*.json`、`results/q3_case*.json`。
- 真实指标：无人机数量、最大工作时间、工作时间极差、单次有效到达平均距离、总等待时间、总绕行距离。
- 派生处理：`distance_per_task_km = total_distance_km / required_task_count`；每个指标仅为着色分别执行 min-max 归一化，原始值完整保存在 CSV。
- 图表数据：`data/grouped_circular_heatmap.csv`，共 12 条 Case-问题记录。
- 脚本：`scripts/make_grouped_circular_heatmap.py`。
- 输出：`outputs/grouped_circular_heatmap_real.pdf`、`.svg`、`.png`。

### correlation-pairgrid

- 适用原因：正式 q1/q2/q3 解共有 60 条无人机路线，可分析路线级变量的分布及相关关系。
- 原始来源：上述 12 个正式结果 JSON 中的 `routes` 和 `metrics.route_metrics`。
- 真实变量：任务数、飞行距离、服务时间、等待时间、绕行距离、总工作时间；散点颜色表示问题编号。
- 图表数据：`data/correlation_pairgrid_routes.csv`，共 60 条路线记录。
- 脚本：`scripts/make_correlation_pairgrid.py`。
- 输出：`outputs/correlation_pairgrid_real.pdf`、`.svg`、`.png`。

## 跳过模板

- `paired-raincloud`：q1/q2/q3 的机队规模和任务分配并不一致，UAV 编号之间不存在严格的一一配对；当前多起点记录也没有为三个问题同时保存同口径的完整分布，因此不强行制作配对图。
- `cv-roc-ci`、`prediction-marginal-grid`、`taylor-diagram`：本题不是分类、预测或多模型拟合评价问题，没有真实预测值、标签或误差序列。
- `multiclass-shap-combo`：没有已训练监督模型及真实 SHAP 值。
- `rf-tpe-surface`：没有 TPE 超参数搜索网格及真实目标函数曲面。
- `grouped-corr-split-violin`：当前不存在具有统计含义的两组独立样本；其相关矩阵部分已由 `correlation-pairgrid` 覆盖。
- `urban-park-cooling-combo`：变量语义与本题不符。
- `nature-chord-diagram`：当前结果没有自然的双向流量或转移矩阵，强行构造会误导。

## 复现

在项目根目录运行：

```powershell
python "绘图复刻/scripts/make_grouped_circular_heatmap.py"
python "绘图复刻/scripts/make_correlation_pairgrid.py"
```
