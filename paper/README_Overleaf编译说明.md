# A 题 submission LaTeX 工程

本目录由项目中的参考 LaTeX 工程复制建立，只继承版式、页眉页脚、章节组织和 XeLaTeX 编译方式。正文、公式、表格和图片均已替换为 A 题内容。

## 文件结构

- `main.tex`：主入口。
- `sections/`：摘要、问题重述、数据分析、模型、三问求解、稳定性、评价与参考文献。
- `figures/`：论文实际引用的 A 题 PDF 图件。
- `main.pdf`：本地 XeLaTeX 编译生成的论文初稿。

## 编译

在本目录执行两遍：

```powershell
xelatex -interaction=nonstopmode -halt-on-error main.tex
xelatex -interaction=nonstopmode -halt-on-error main.tex
```

Overleaf 中将 `main.tex` 设为 Main document，并选择 XeLaTeX 编译器。
