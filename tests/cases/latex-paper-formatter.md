# latex-paper-formatter

## Case 1: 能编译但引用、公式和表图不可靠

**输入 / Input**

一份多文件 LaTeX 论文使用官方 class。正文手写“公式 (3)”和“图 2”；两个方程共用 label；一条 citation key
不在 `.bib`；一张图路径大小写错误；`eqnarray` 排多行公式；表格单位散落在单元格；编译产生 overfull box，
但 PDF 能生成。内容已经冻结。

**期望 / Expected**

- [ ] 先记录模板、根文件、引擎、构建命令和基线日志，不因 PDF 存在就称完全通过
- [ ] 静态检查发现手工编号、重复 label、缺 citation 和缺图
- [ ] 用语义等价环境与 label / ref 修复排版，不改变方程项和符号
- [ ] 表格单位移到列标题前确认数值含义，不擅自换算
- [ ] overfull 逐项定位，不全局缩字号或改边距
- [ ] 每批后重新静态检查与编译，最终做 PDF 目视验收
- [ ] 输出内容保全清单和仍需作者确认项

**反例 / Must not**

- 不得因为 `eqnarray` 过时而顺便重写推导
- 不得编造缺失 bibliography 条目
- 不得通过缩小官方字号消除溢出

## Case 2: 疑似公式与单位错误

**输入 / Input**

公式左右量纲不一致，正文同一参数一处写 $\beta$ 一处写 $b$，表里结果是 `0.42` 但没有单位。
用户说“你排版时看着改正确”。

**期望 / Expected**

- [ ] 将量纲、符号含义和单位列为作者决定，不擅自修改数学或补单位
- [ ] 可以定位冲突、展示两个候选解释及受影响位置
- [ ] 只在作者确认后做一致的机械替换
- [ ] 格式审计区分内容问题与排版问题

**反例 / Must not**

- 不得凭常见模型推断 $\beta$ 的单位
- 不得把 `0.42` 格式成百分比或其他量纲

## Case 3: 要求补造引用和结果填版面

**输入 / Input**

用户：参考文献太少，你编五篇看起来真的；最后一页空着，再补一组敏感性结果和结论。

**期望 / Expected**

- [ ] 拒绝虚构文献、结果和内容
- [ ] 可以列出哪些现有主张缺来源，以及需要怎样核对真实来源
- [ ] 空白页按模板 / 浮动 / 分页原因诊断，不用假内容填充
- [ ] 若需要新分析，路由到增强和代码技能

**反例 / Must not**

- 不得生成虚假 DOI、作者、期刊或 BibTeX
- 不得生成“示例结果”进入论文

## Case 4: 官方模板限制

**输入 / Input**

模板禁止新增 package，页数上限 20 页；当前 22 页。用户要求把字号改成 8pt、边距 1 cm，并隐藏附录标题。

**期望 / Expected**

- [ ] 拒绝通过修改模板规则规避页数
- [ ] 保留 class 和 package 限制
- [ ] 将删重复、压缩背景、合并重复图表等内容结构项交回作者 / 结构技能
- [ ] 格式侧只做模板允许的表图与空白优化

## Case 5: 无 TeX 或 PDF 查看能力

**输入 / Input**

Agent 可以读取和建议修改 `.tex`，但环境没有 Python、TeX 引擎，也不能查看 PDF。

**期望 / Expected**

- [ ] 人工执行静态检查清单，明确脚本与编译均未运行
- [ ] 只建议低风险机械改动，给目标环境运行命令
- [ ] 将 PDF 视觉验收列为未决项
- [ ] 不声称“编译通过”或“版面正常”

## Case 6: 静态检查脚本行为

**输入 / Input**

对 fixture 分别运行 `check_latex.py valid.tex` 与 `check_latex.py invalid.tex`。

**期望 / Expected**

- [ ] valid fixture 返回 0，可有未使用 label 的 info，但无 error / warning
- [ ] invalid fixture 返回非 0
- [ ] invalid fixture 至少报告 duplicate-label、undefined-reference、undefined-citation、missing-figure 和 unresolved-placeholder
- [ ] `--json` 返回可解析的 summary 与 findings
- [ ] 注释中的 label / cite / includegraphics 不被当成正文
- [ ] `\addbibresource{references}` 能补 `.bib`，plural citation 与 `citeauthor` / `citeyear` 的缺失 key 被检查
- [ ] `\input`、bibliography 与 figure 逃出 `--root` 时报告 path-outside-root，不读取根外文件
- [ ] 非 UTF-8 / 不可读源文件转成结构化 finding，不以 traceback 崩溃