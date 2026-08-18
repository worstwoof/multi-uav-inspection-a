from pathlib import Path
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "figures"
FONT = FontProperties(fname="C:/Windows/Fonts/NotoSansSC-VF.ttf")
FONT_BOLD = FontProperties(fname="C:/Windows/Fonts/NotoSansSC-VF.ttf", weight="bold")

COLORS = {
    "input": "#E8F1FA",
    "method": "#FFF1DC",
    "decision": "#FBE5E5",
    "output": "#E6F4EA",
    "validation": "#EEE8F7",
    "text": "#25364A",
    "edge": "#526579",
    "accent": "#1F6F8B",
}


def label(ax, x, y, s, size=11, bold=False, ha="center", va="center"):
    ax.text(x, y, s, fontproperties=FONT_BOLD if bold else FONT,
            fontsize=size, color=COLORS["text"], ha=ha, va=va,
            linespacing=1.35)


def box(ax, x, y, w, h, s, kind="method", size=10.5, radius=0.025):
    patch = FancyBboxPatch((x, y), w, h,
                           boxstyle=f"round,pad=0.012,rounding_size={radius}",
                           linewidth=1.4, edgecolor=COLORS["accent"],
                           facecolor=COLORS[kind])
    ax.add_patch(patch)
    label(ax, x + w / 2, y + h / 2, textwrap.fill(s, 17), size=size)
    return (x, y, w, h)


def diamond(ax, x, y, w, h, s, size=9.5):
    pts = [(x + w / 2, y + h), (x + w, y + h / 2),
           (x + w / 2, y), (x, y + h / 2)]
    ax.add_patch(Polygon(pts, closed=True, linewidth=1.4,
                         edgecolor=COLORS["accent"], facecolor=COLORS["decision"]))
    label(ax, x + w / 2, y + h / 2, textwrap.fill(s, 11), size=size)
    return (x, y, w, h)


def center(node):
    x, y, w, h = node
    return x + w / 2, y + h / 2


def boundary_point(node, toward):
    """Return the point where a center-to-center ray leaves a node."""
    cx, cy = center(node)
    dx, dy = toward[0] - cx, toward[1] - cy
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return cx, cy
    x, y, w, h = node
    scales = []
    if abs(dx) > 1e-9:
        scales.append((w / 2) / abs(dx))
    if abs(dy) > 1e-9:
        scales.append((h / 2) / abs(dy))
    scale = min(scales)
    return cx + dx * scale, cy + dy * scale


def arrow(ax, a, b, text=None, rad=0.0, color=None, start=None, end=None):
    target_center = center(b) if end is None else end
    source_center = center(a) if start is None else start
    x1, y1 = boundary_point(a, target_center) if start is None else start
    x2, y2 = boundary_point(b, source_center) if end is None else end
    p = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                        mutation_scale=13, linewidth=1.25,
                        color=color or COLORS["edge"],
                        connectionstyle=f"arc3,rad={rad}")
    ax.add_patch(p)
    if text:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        label(ax, mx, my + 0.035, text, size=8.5)


def setup(title, xlim=(0, 1), ylim=(0, 1), figsize=(14, 5.5)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    label(ax, (xlim[0] + xlim[1]) / 2, ylim[1] - 0.05, title, size=16, bold=True)
    return fig, ax


def save(fig, name):
    FIG_DIR.mkdir(exist_ok=True)
    fig.savefig(FIG_DIR / f"{name}.pdf", bbox_inches="tight", pad_inches=0.12)
    fig.savefig(FIG_DIR / f"{name}.svg", bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


def roadmap():
    fig, ax = setup("无人机巡检问题统一技术路线", figsize=(15, 5.2))
    nodes = [
        box(ax, .03, .38, .14, .28, "题面与附件\nCase、坐标、等级、禁飞窗", "input"),
        box(ax, .22, .38, .15, .28, "数据标准化\n单位换算 + 任务展开\n有效到达约束", "input"),
        box(ax, .42, .38, .15, .28, "问题一\n理论下界 → 最低可行机队\n固定 N 最小化 C", "method"),
        box(ax, .62, .38, .15, .28, "问题二\n继承 N_min\n字典序 (C, δ, D)", "method"),
        box(ax, .82, .38, .15, .28, "问题三\n动态禁飞时空路径\n必要时最小增机", "method"),
        box(ax, .42, .08, .35, .17, "独立验证：任务覆盖、闭环、9 h、\n几何相交、时间重叠、服务点与基地安全", "validation", 9.5),
        box(ax, .82, .08, .15, .17, "结构化结果\n结果表 + 论文图表", "output", 9.5),
    ]
    for a, b in zip(nodes[:5], nodes[1:5]):
        arrow(ax, a, b)
    arrow(ax, nodes[4], nodes[5], start=(.895, .38), end=(.77, .25), rad=.12, text="全流程校验")
    arrow(ax, nodes[2], nodes[5], start=(.495, .38), end=(.57, .25), rad=-.08)
    arrow(ax, nodes[3], nodes[5], start=(.695, .38), end=(.65, .25), rad=.08)
    arrow(ax, nodes[5], nodes[6], start=(.77, .165), end=(.82, .165))
    label(ax, .30, .72, "输入层", size=9, bold=True, ha="left")
    label(ax, .58, .72, "继承式求解层", size=9, bold=True, ha="left")
    label(ax, .42, .02, "三问共享同一任务集合与独立验证口径", size=9)
    save(fig, "fig_roadmap")


def flow_q1():
    fig, ax = setup("问题一：最低可行机队与最小最大工作时间", ylim=(0, 1.05), figsize=(9, 10))
    n0 = box(ax, .32, .86, .36, .08, "读取一个 Case：点、等级、速度、服务时间、H=9 h", "input", 9.5)
    n1 = box(ax, .32, .74, .36, .08, "展开 task_id；同一路线禁止相邻相同 Point_ID\nA-A-A=1 次，A-B-A=2 次", "input", 9.2)
    n2 = box(ax, .32, .62, .36, .08, "计算服务下界与工作量下界\nN_LB = max(N_LB^svc, N_LB^work)", "method", 9.3)
    n3 = box(ax, .32, .49, .36, .08, "从 N=N_LB 构造多起点初始路线\n闭环：基地 → 任务序列 → 基地", "method", 9.3)
    d1 = diamond(ax, .36, .35, .28, .09, "任务覆盖、闭环、\n所有 T_k≤9 h？", 9.0)
    n4 = box(ax, .32, .20, .36, .08, "固定当前 N，局部搜索最小化\nC=max_k T_k", "method", 9.5)
    n5 = box(ax, .32, .07, .36, .08, "独立重算距离与时间，输出 q1_case*.json\n并记录证书状态", "output", 9.3)
    arrow(ax, n0, n1); arrow(ax, n1, n2); arrow(ax, n2, n3); arrow(ax, n3, d1)
    arrow(ax, d1, n4, text="是", start=(.50, .35), end=(.50, .28))
    arrow(ax, n4, n5)
    n_inc = box(ax, .05, .35, .23, .09, "否：N←N+1，重新构造\n不可把未找到写成不可行", "decision", 8.8)
    arrow(ax, d1, n_inc, text="否", start=(.36, .395), end=(.28, .395), rad=.0)
    arrow(ax, n_inc, n3, start=(.28, .395), end=(.32, .53), rad=.22)
    label(ax, .72, .55, "先保证可行，再优化 C", size=9, bold=True, ha="left")
    label(ax, .72, .51, "理论下界 ≠ 最低可行数量", size=9, ha="left")
    save(fig, "fig_flow_q1")


def flow_q2():
    fig, ax = setup("问题二：固定机队的字典序负载均衡", figsize=(11, 7))
    a = box(ax, .04, .64, .19, .16, "输入 q1\nN=N_min、基准路线、C1", "input", 10)
    b = box(ax, .30, .64, .20, .16, "保留 q1 硬约束\n覆盖、闭环、相邻点、9 h\nC≤C1+εC", "input", 9.3)
    c = box(ax, .57, .64, .20, .16, "跨路线邻域\nrelocate / swap / 2-opt*\ncross-exchange", "method", 9.5)
    d = diamond(ax, .83, .67, .13, .11, "可行且\nlex 改善？", 8.2)
    e = box(ax, .57, .35, .20, .16, "接受候选\n按 (C, δ, D) 比较\nδ=C−L", "method", 9.5)
    f = diamond(ax, .30, .38, .16, .10, "达到停止\n条件？", 8.4)
    g = box(ax, .04, .35, .18, .16, "独立验证\n重算 C、L、δ、距离", "validation", 9.2)
    h = box(ax, .04, .08, .40, .13, "输出 q2_case*.json\n记录任务转移与均衡改善来源", "output", 9.3)
    arrow(ax, a, b); arrow(ax, b, c); arrow(ax, c, d)
    arrow(ax, d, e, text="是", start=(.895, .67), end=(.77, .43))
    arrow(ax, d, c, text="否", start=(.83, .725), end=(.77, .72), rad=.18)
    arrow(ax, e, f, start=(.57, .43), end=(.46, .43))
    arrow(ax, f, g, text="是", start=(.30, .43), end=(.22, .43))
    arrow(ax, f, c, text="否：继续邻域搜索", start=(.38, .48), end=(.62, .64), rad=-.2)
    arrow(ax, g, h, start=(.13, .35), end=(.24, .21))
    label(ax, .56, .19, "目标层级：先不恶化 C，再缩小 δ，最后比较总距离 D", size=9, bold=True)
    save(fig, "fig_flow_q2")


def flow_q3():
    fig, ax = setup("问题三：动态禁飞区的几何—时间联合处理", figsize=(15, 8))
    a = box(ax, .03, .66, .16, .16, "输入 q2 路线\n禁飞圆心、半径、\n[t_s,t_e)、t=0 为 8:00", "input", 9.4)
    b = box(ax, .24, .66, .17, .16, "按边传播\n从节点 a 在时刻 t 出发\n计算直飞长度与时间", "method", 9.4)
    c = diamond(ax, .46, .69, .15, .10, "线段与圆\n几何相交？", 8.8)
    d = diamond(ax, .69, .69, .16, .10, "[t_in,t_out]\n与窗口重叠？", 8.8)
    e = box(ax, .91, .66, .06, .16, "直飞\n传播", "output", 8.4)
    f = box(ax, .46, .39, .18, .15, "无时间冲突\n直飞并传播", "output", 9.3)
    g = box(ax, .70, .36, .22, .20, "动态冲突候选\n1. 安全等待\n2. 切线—圆弧绕行\n3. 调整任务顺序", "method", 9.2)
    h = box(ax, .24, .13, .20, .16, "重算服务点与基地\n服务区间、停留区间\n不得落在活动圆内", "validation", 9.1)
    i = box(ax, .50, .13, .18, .16, "选最早安全到达\n记录 path、wait、detour\n更新下一节点时刻", "method", 9.0)
    j = diamond(ax, .75, .16, .15, .10, "所有边与\n返回基地完成？", 8.5)
    k = diamond(ax, .91, .16, .08, .10, "T_k≤9 h？", 7.8)
    l = box(ax, .72, .02, .17, .08, "输出 q3 可行结果", "output", 8.5)
    m = box(ax, .42, .02, .22, .08, "固定机队不可行：N←N+1", "decision", 8.5)
    arrow(ax, a, b); arrow(ax, b, c); arrow(ax, c, d, text="是", start=(.61, .74), end=(.69, .74))
    arrow(ax, c, e, text="否", start=(.61, .69), end=(.91, .74), rad=-.2)
    arrow(ax, d, e, text="否", start=(.85, .69), end=(.91, .74), rad=.0)
    arrow(ax, d, g, text="是", start=(.77, .69), end=(.81, .56))
    arrow(ax, g, h, start=(.70, .43), end=(.44, .22), rad=.08)
    arrow(ax, f, h, start=(.55, .39), end=(.37, .29), rad=-.08)
    arrow(ax, h, i); arrow(ax, i, j); arrow(ax, j, k, text="是", start=(.90, .21), end=(.91, .21))
    arrow(ax, j, i, text="否：下一条边", start=(.75, .21), end=(.68, .21), rad=.25)
    arrow(ax, k, l, text="是", start=(.95, .16), end=(.81, .10), rad=-.12)
    arrow(ax, k, m, text="否", start=(.91, .16), end=(.60, .10), rad=.08)
    arrow(ax, m, a, start=(.53, .10), end=(.11, .66), rad=.18)
    label(ax, .24, .58, "几何判断", size=9, bold=True)
    label(ax, .69, .58, "时间判断", size=9, bold=True)
    label(ax, .42, .34, "任何等待都要重新传播并复核所有禁飞区", size=9, bold=True)
    save(fig, "fig_flow_q3")


def model_structure():
    fig, ax = setup("统一模型结构：任务、路线、时空约束与目标", figsize=(14, 7))
    inp = box(ax, .03, .70, .19, .16, "输入参数\nCase、点坐标、等级频次\nv=55 km/h，s=1/12 h，H=9 h\n禁飞圆与时间窗", "input", 9.0)
    task = box(ax, .29, .70, .19, .16, "任务集合 M\n(i,q), q=1,…,r_i\n唯一 task_id\n相邻相同点禁止", "input", 9.2)
    route = box(ax, .55, .70, .19, .16, "路线决策\n任务分配与访问顺序\n基地闭环\n问题三：等待/绕行", "method", 9.2)
    time = box(ax, .81, .70, .16, .16, "时间传播\nD_k/v + n_k s + w_k\n动态边 Φ_ab(t)", "method", 9.2)
    evaln = box(ax, .16, .38, .22, .16, "路线评价\nD_k、T_k、C=max T_k\nL=min T_k、δ=C−L", "validation", 9.3)
    obj1 = box(ax, .48, .38, .20, .16, "问题一目标\n先最小可行机队\n再 min C", "method", 9.3)
    obj2 = box(ax, .75, .38, .20, .16, "问题二 / 三目标\nlexmin(C,δ,D)\n问题三先 min N", "method", 9.1)
    val = box(ax, .29, .06, .43, .19, "独立验证器\ncoverage · effective visits · closure · distance/time recompute\n9 h horizon · geometry/time/service/base no-fly checks", "validation", 7.4)
    out = box(ax, .78, .08, .19, .15, "结构化输出\nq1/q2/q3 JSON\n结果表与论文图", "output", 9.2)
    arrow(ax, inp, task); arrow(ax, task, route); arrow(ax, route, time)
    arrow(ax, route, evaln, start=(.64, .70), end=(.27, .54), rad=.10)
    arrow(ax, time, evaln, start=(.89, .70), end=(.36, .54), rad=.15)
    arrow(ax, evaln, obj1); arrow(ax, evaln, obj2, start=(.38, .46), end=(.75, .46))
    arrow(ax, obj1, val, start=(.58, .38), end=(.52, .23))
    arrow(ax, obj2, val, start=(.82, .38), end=(.62, .23))
    arrow(ax, val, out, start=(.72, .155), end=(.78, .155))
    label(ax, .03, .60, "数据层", size=9, bold=True, ha="left")
    label(ax, .55, .60, "决策与评价层", size=9, bold=True, ha="left")
    label(ax, .29, .29, "硬约束优先于目标优化", size=9, bold=True)
    save(fig, "fig_model")


if __name__ == "__main__":
    roadmap()
    flow_q1()
    flow_q2()
    flow_q3()
    model_structure()
