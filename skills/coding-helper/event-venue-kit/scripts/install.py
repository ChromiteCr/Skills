#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""event-venue-kit :: install.py -- write the chosen card into a project.  把选定的牌落到项目里。

    install.py <roll.json> <target-dir> [--force] [--dry-run] [--strict] [--name "Project name"] [--card N]
                                        [--starter --venue data/venue.json]
    install.py <roll.json> <target-dir> --update          after `draw.py adjust`: refresh the generated tokens only

Refuses to run unless a card has been chosen (python3 scripts/draw.py choose N --reason "..." --roll roll.json);
--card N overrides that for a one-off (it never writes history).

Writes (target-dir is the project root; paths relative to it):
  evk/tokens.css            generated from the card: :root{} + the dark block declared twice. When the direction has decorative
                            props (a category motif: leaf label, halftone, shield ...), their switches follow as COMMENTED lines
                            at the end of :root (`/* --prop-leaf: none; */  /* description */`): remove the comment marks around the
                            declaration to switch that prop off.
                            DESIGN.md lists every prop with its off value. --update keeps the lines you have switched on (below).
  evk/base.css              copy of assets/floor/base.css          (structure + floor rules, no colours)
  evk/recipe.css            copy of assets/recipes/<direction>.css  (the direction's component recipes)
  evk/engine/*.js           copies of assets/engine/*.js            (EVK namespace; load order printed at the end)
  evk/venue.schema.json     copy of assets/engine/venue.schema.json
  DESIGN.md                 Google DESIGN.md format (YAML front matter tokens + Overview, Colors, Typography, Layout,
                            Elevation & Depth, Shapes, Components, Do's and Don'ts) plus the extension sections Motion,
                            Bilingual, Map, Wayfinding, and a Roll record with a deviations table. It shows the <html>
                            attribute snippet (data-evk-* incl. data-evk-lead) every page must carry, and the load order
                            (tones, search, spring, sheet, part-nav, wayfind, venue-map, then the starter).
  .evk/roll.json            the roll, with the chosen card, so the project can re-create or re-check it
--starter --venue PATH      also a working site skeleton built from your venue (scripts/starter.py, called as
                            render(venue, card, target, force)): index.html, map.html, e/<id>.html for every entity, data/venue.js,
                            assets/starter.css, assets/starter.js. Static content is rendered at build time (works without JS).
                            Without scripts/starter.py the rest is installed and a message says the skeleton was skipped
                            (--strict: an error, nothing written). Edit venue.json and rebuild with `starter.py` or this flag + --force.
Never overwrites an existing file without --force: all conflicts (the starter's pages included) are listed and nothing is written.
The one exception is .evk/roll.json when it IS the roll you passed in (the usual layout: draw.py wrote it there): that file
is the same file, so it is updated in place, no conflict, no --force.

--update (a project that is already installed, after `draw.py adjust`): rewrites only what the card generates --
evk/tokens.css and .evk/roll.json (with --starter also the starter pages, which still obey --force). base.css, recipe.css, the engine and DESIGN.md are left alone (they may carry your
edits); the DESIGN.md the new card would produce is written to .evk/DESIGN.generated.md, and the <html> attributes are
printed, so you can carry the new Deviations rows and attribute changes over by hand. Refuses if evk/tokens.css is not
one this script wrote (no kit header) unless --force.
What --update keeps of evk/tokens.css (exactly this, nothing else): every `--prop-*: value;` declaration that is LIVE in the
installed file, i.e. not inside a /* comment */ -- the lines you uncommented to switch a decorative prop off, or any `--prop-*` you
set to your own value. Each is copied VERBATIM (your value and your trailing comment) and replaces the generated commented line of
that prop in the regenerated file; a live line for a var the new card has no prop for is kept too, after the props block. Everything
else in tokens.css is regenerated from the card: colour, type, shape and map tokens (hand-edited values are lost: diff with git),
the header, the dark blocks, and the commented props lines (a prop whose line you did not uncomment goes back to ON). The same
rule is written into the project's DESIGN.md (Roll record, Updating). Without --update (a fresh install, or --force over an
installed project) tokens.css is generated from scratch and nothing is carried over.
A kit file that is missing (the kit is incomplete) is skipped with a clear message; --strict turns that into an error.
Afterwards the tokens are linted (lint_floor.py); a floor failure is reported and gives exit code 1.
Exit code: 0 ok; 1 lint failed / --strict and a file missing; 2 usage, no chosen card, or conflicts without --force.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit  # noqa: E402
import draw  # noqa: E402
import lint_floor  # noqa: E402

ENGINE_ORDER = ["tones.js", "search.js", "spring.js", "sheet.js", "part-nav.js", "wayfind.js", "venue-map.js"]


# --------------------------------------------------------------------------------------------------
# DESIGN.md
# --------------------------------------------------------------------------------------------------

def _q(s):
    return '"%s"' % str(s).replace("\\", "\\\\").replace('"', '\\"')


def _yaml(obj, indent=0):
    """Tiny YAML emitter for nested dicts of str / int / float (enough for the front matter)."""
    out = []
    pad = "  " * indent
    for k, v in obj.items():
        if isinstance(v, dict):
            out.append("%s%s:" % (pad, k))
            out.extend(_yaml(v, indent + 1))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append("%s%s: %s" % (pad, k, kit._fmt(v, 4)))
        else:
            s = str(v)
            if s.startswith("#") or s.startswith("{") or any(ch in s for ch in ":,'\"[]&*!|>%@`") or s == "" or s[0] in "-?":
                s = _q(s)
            out.append("%s%s: %s" % (pad, k, s))
    return out


def _rem(px):
    return "%srem" % kit._fmt(px / 16.0, 3)


def step_px(ty, i):
    base_min, base_max = ty["base"]
    ratio = ty["ratio"]
    r_min = max(1.125, round(ratio - 0.05, 3))
    a, b = base_min * r_min ** i, base_max * ratio ** i
    return min(a, b), max(a, b)


def front_matter(card, name, desc):
    p = card["params"]
    pal, ty, sh, lay, mo = p["palette"], p["type"], p["shape"], p["layout"], p["motion"]
    lt, dk = pal["light"], pal["dark"]
    f = ty["fonts"]
    colors = {"primary": lt["a"], "secondary": lt["b"], "tertiary": lt["climb"], "neutral": lt["paper"]}
    for k in kit.COLOR_TOKENS:
        colors[k] = lt[k]
    for k in kit.COLOR_TOKENS:
        colors["dark-" + k] = dk[k]
    typo = {
        "display-hero": {"fontFamily": f["display"]["full_stack"], "fontSize": _rem(step_px(ty, 5)[1]), "fontWeight": ty["display_weight"],
                         "lineHeight": ty["display_leading"], "letterSpacing": "%sem" % kit._fmt(ty["display_track"], 3)},
        "display-title": {"fontFamily": f["display"]["full_stack"], "fontSize": _rem(step_px(ty, 3)[1]), "fontWeight": ty["display_weight"],
                          "lineHeight": ty["display_leading"], "letterSpacing": "%sem" % kit._fmt(ty["display_track"], 3)},
        "row-title": {"fontFamily": f["display"]["full_stack"], "fontSize": _rem(step_px(ty, 0)[1]), "fontWeight": ty["display_weight"], "lineHeight": 1.15},
        "numeral-stat": {"fontFamily": f["display"]["full_stack"], "fontSize": _rem(step_px(ty, 4)[1]), "fontWeight": ty["display_weight"], "lineHeight": 0.9},
        "label-k": {"fontFamily": f["label"]["full_stack"], "fontSize": _rem(step_px(ty, -1)[1]), "fontWeight": ty["label_weight"], "lineHeight": 1.25,
                    "letterSpacing": "%sem" % kit._fmt(ty["label_track"], 3)},
        "cn-gloss": {"fontFamily": f["cjk"]["full_stack"], "fontSize": _rem(step_px(ty, -1)[1] * 0.9), "fontWeight": 500, "lineHeight": 1.3, "letterSpacing": "0.12em"},
        "body-ui": {"fontFamily": f["text"]["full_stack"], "fontSize": _rem(step_px(ty, 0)[1]), "fontWeight": 400, "lineHeight": 1.7},
        "body-reading": {"fontFamily": f["text"]["full_stack"], "fontSize": _rem(step_px(ty, 0)[1] * 1.02), "fontWeight": 400, "lineHeight": 1.85},
    }
    rounded = {"none": "0px", "base": "%dpx" % sh["radius"], "chamfer": "%dpx" % sh["chamfer"], "pill": "9999px"}
    spacing = {"gutter": "%dpx" % lay["gutter"], "gap": "%dpx" % lay["gap"], "row-pad": "%dpx" % lay["row_pad"], "measure-reading": "%dch" % lay["measure"],
               "shell-max": "1120px", "bar-min": "56px", "hit": "44px"}
    comps = {
        "button-primary": {"backgroundColor": "{colors.b}", "textColor": "{colors.on-b}", "typography": "{typography.label-k}", "rounded": "{rounded.base}", "height": "44px", "padding": "0 22px"},
        "button-default": {"backgroundColor": "{colors.a}", "textColor": "{colors.on-a}", "typography": "{typography.label-k}", "rounded": "{rounded.base}", "height": "44px", "padding": "0 22px"},
        "button-quiet": {"backgroundColor": "{colors.paper-2}", "textColor": "{colors.text}", "typography": "{typography.label-k}", "rounded": "{rounded.base}", "height": "44px"},
        "search-field": {"backgroundColor": "{colors.paper-2}", "textColor": "{colors.text}", "rounded": "{rounded.base}", "height": "48px"},
        "list-cell": {"backgroundColor": "{colors.paper}", "textColor": "{colors.a-text}", "typography": "{typography.row-title}", "padding": "%dpx" % lay["row_pad"]},
        "sheet": {"backgroundColor": "{colors.paper}", "textColor": "{colors.text}", "rounded": "{rounded.base}", "padding": "0 18px 16px"},
        "tag": {"textColor": "{colors.a-text}", "rounded": "{rounded.base}"},
    }
    fm = {"version": "alpha", "name": name, "description": desc, "colors": colors, "typography": typo, "rounded": rounded, "spacing": spacing,
          "components": comps,
          "motion": {"spring-duration": "%ss" % kit._fmt(mo["dur"], 2), "spring-bounce": kit._fmt(mo["bounce"], 2), "press-scale": kit._fmt(mo["press"], 3), "fade": "%ss" % kit._fmt(mo["fade"], 2)},
          "map": {"projection": p["map"]["projection"], "material": p["map"]["material"], "token": p["map"]["token"], "pitch": p["map"]["pitch"],
                  "yaw": p["map"]["yaw"], "wall-height": p["map"]["wall_h"], "light": p["map"]["light"], "dim": p["map"]["dim"]}}
    return "---\n" + "\n".join(_yaml(fm)) + "\n---\n"


def _contrast_line(t, fg, bg):
    return "%.2f:1" % kit.contrast(t[fg], t[bg])


def html_open_tag(p):
    """The <html> start tag every page needs: lang follows the lead language; data-evk-* from kit.root_attrs (incl. lead) plus
    the three colours EVK.tones reads when it cannot read the stylesheets."""
    lt, dk = p["palette"]["light"], p["palette"]["dark"]
    lang = "zh-CN" if (p.get("lead") or "en") == "zh" else "en"
    attrs = ["lang=\"%s\"" % lang] + ["%s=\"%s\"" % (k, v) for k, v in kit.root_attrs(p)]
    attrs += ["data-evk-paper=\"%s\"" % lt["paper"], "data-evk-ink=\"%s\"" % lt["text"], "data-evk-night=\"%s\"" % dk["paper"]]
    return "<html " + "\n      ".join(attrs) + ">"


def load_order_html(starter=False):
    """The <link>/<script> block every page loads, in the order the engine needs (search.js is part of it; so is the starter's
    data/venue.js + assets/starter.js when the skeleton is installed)."""
    lines = ['<link rel="stylesheet" href="evk/tokens.css">', '<link rel="stylesheet" href="evk/base.css">', '<link rel="stylesheet" href="evk/recipe.css">']
    if starter:
        lines.append('<link rel="stylesheet" href="assets/starter.css">')
        lines.append('<script src="data/venue.js"></script>')
    lines += ['<script src="evk/engine/%s"></script>' % n for n in ENGINE_ORDER]
    if starter:
        lines.append('<script src="assets/starter.js"></script>')
    return "\n".join(lines)


def design_md(roll, card, idx, name=None, starter=False):
    p = card["params"]
    nm = card.get("name") or {}
    pal, ty, sh, mp, mo, lay = p["palette"], p["type"], p["shape"], p["map"], p["motion"], p["layout"]
    lt, dk = pal["light"], pal["dark"]
    f = ty["fonts"]
    lead = p.get("lead") or "en"
    first, second = ("cn", "en") if lead == "zh" else ("en", "cn")
    lang = "zh-CN" if lead == "zh" else "en"
    title = name or "%s (%s)" % (nm.get("en") or card["direction"], card["direction"])
    desc = "%s — %s" % (p.get("mechanism", ""), p.get("idea", ""))
    out = [front_matter(card, title, desc)]
    out.append("# %s · DESIGN.md\n" % title)
    out.append("> event-venue-kit 抽牌结果的落地规格。方向 `%s`，预设码 `%s`，种子 %s。改动写进末尾的「Deviations」表；`python3 scripts/draw.py decode %s` 能还原这张牌。地板规则（对比度、触控、焦点、减弱动效、隐私）与方向无关，见 skill 的 `references/floor.md`。\n" % (
        card["direction"], card["code"], card.get("card_seed"), card["code"]))
    out.append("## Overview\n")
    out.append("*概览：这个方向是什么，从哪来，哪些是身份。*\n")
    out.append("**机制 / mechanism：** %s。%s\n" % (p.get("mechanism", ""), p.get("idea", "")))
    if p.get("specimen_note"):
        out.append("**首页与实体页的感觉：** %s\n" % p["specimen_note"])
    if p.get("richness"):
        out.append("**让它饱满的做法（不靠装饰）/ richness：**\n\n" + "\n".join("- %s" % x for x in p["richness"]) + "\n")
    out.append("**这个项目的物理依据：** （写一件来自活动盘点清单的实物，说明为什么这个方向接得住它。选牌时的理由：%s）\n" % (roll.get("reason") or "未记录"))

    out.append("## Colors\n")
    out.append("*色彩：按令牌说话，不按颜色名：结构墨 `--a`，行动/现在/在哪的强调墨 `--b`，垂直移动 `--climb`（图形）与 `--climb-text`（文字），其余是纸与灰。浅色与深色用同一组令牌名。*\n")
    out.append("配色结构 `%s`，深色地面 `%s`（原生地面：%s）。这张牌实际抽到的取值（浅色）：纸 `--paper` %s，结构墨 `--a` %s，强调墨 `--b` %s，上下楼 `--climb` %s（文字版 `--climb-text` %s）。文字里提到颜色时用令牌名或这些取值，不要凭印象写颜色名。\n" % (
        pal["structure"], pal["dark_mode"], pal["ground"], lt["paper"], lt["a"], lt["b"], lt["climb"], lt["climb-text"]))
    fam = kit.family_text(p)
    if fam:
        out.append("**色相家族 / hue family（抽牌时定的，这个方向的几种可能之一）：** %s。换成别的家族等于换一张牌；要改某个颜色用 `draw.py adjust b=#hex --reason \"…\"`。\n" % fam)
    out.append("| 令牌 | 浅色 | 深色 | 职责 |\n|---|---|---|---|")
    roles = {"paper": "页底", "paper-2": "次级面：面板、地图地面、按下的行", "rule": "细线（只画线，不当文字）", "text": "正文", "sub": "次级文字，次语言",
             "a": "结构墨：标题条、选中填充", "a-text": "`--a` 作文字", "on-a": "`--a` 填充上的字", "b": "强调墨：行动、现在、在哪",
             "b-text": "`--b` 作文字", "on-b": "`--b` 填充上的字", "climb": "上下楼的图形（路线里的楼梯、电梯段，对地图地面 ≥ 3:1）",
             "climb-text": "上下楼的文字（步骤里的“上楼”等），与 `--climb` 同色相，对 `--paper` 与 `--paper-2` ≥ 4.5:1", "focus": "焦点环"}
    for k in kit.COLOR_TOKENS:
        out.append("| `--%s` | %s | %s | %s |" % (k, lt[k], dk[k], roles[k]))
    out.append("")
    out.append("实体（展商、学校、展位）的颜色由一个输入色派生七个角色，用 `python3 scripts/tones.py \"#hex\"` 或 `EVK.tones`：`--e --e-text --e-on --e-soft --e-line --e-dk --e-soft-dk`，由 `base.css` 映射成 `--e-fill --e-ink --e-tint`。\n")
    out.append("**对比度（已按地板规则核过，浅 / 深）：**\n")
    out.append("| 检查 | 浅 | 深 | 下限 |\n|---|---|---|---|")
    for cid, fg, bg, need, rule in kit.FLOOR_CHECKS:
        out.append("| %s | %s | %s | %g |" % (cid, _contrast_line(lt, fg, bg), _contrast_line(dk, fg, bg), need))
    out.append("| heading/body（`--a-text` 对 `--paper`，括号内为 `--text`） | %s（%s） | %s（%s） | ≥ 4.5，且生成器令它 ≥ 正文 − %g；< 正文的 80 %% 时 lint 警告 |" % (
        _contrast_line(lt, "a-text", "paper"), _contrast_line(lt, "text", "paper"), _contrast_line(dk, "a-text", "paper"),
        _contrast_line(dk, "text", "paper"), kit.HEADING_SLACK))
    out.append("")
    tuned = kit.floor_notes(p)
    frozen = [x for x in kit.user_adjustments(p) if kit.is_keep_record(x)]
    if tuned:
        out.append("**floor-tuned**：生成器为满足地板规则自己走的地方（自动，不是你要求的）：\n\n" + "\n".join("- %s" % kit.adjust_text(x) for x in tuned) + "\n")
    if frozen:
        out.append("**冻结在包络之外**（`--keep` 要求的，已记入 `adjusted`）：\n\n" + "\n".join("- %s" % kit.adjust_text(x) for x in frozen) + "\n")

    out.append("## Typography\n")
    out.append("*字体：展示字说名字与数字，标签字说导视，正文字读长文；中文用设备字，回落选同一流派。*\n")
    out.append("| 角色 | 字体 | 类别 | 说明 |\n|---|---|---|---|")
    for role, desc_ in (("display", "名字、数字、章标题"), ("label", "标签、按钮、导视"), ("text", "正文"), ("num", "数字与编号"), ("cjk", "中文（次语言、标签旁）"), ("cjk_display", "中文展示")):
        ft = f[role]
        out.append("| %s | %s | %s | %s |" % (role, ft["name"], ft.get("class", ""), desc_))
    out.append("")
    out.append("标签：`%s`，字距 %sem，字重 %s，伸展 %s。展示：字重 %s，字距 %sem，行高 %s。字号阶梯等比 %s，基准 %s–%s px：\n" % (
        ty["label_case"], kit._fmt(ty["label_track"], 3), ty["label_weight"], ty["label_stretch"], ty["display_weight"], kit._fmt(ty["display_track"], 3),
        kit._fmt(ty["display_leading"], 3), kit._fmt(ty["ratio"], 3), kit._fmt(ty["base"][0]), kit._fmt(ty["base"][1])))
    out.append("| 步 | 手机 → 桌面 | CSS |\n|---|---|---|")
    for i in range(-1, 6):
        a, b = step_px(ty, i)
        out.append("| `--step-%d` | %.1f → %.1f px | `%s` |" % (i, a, b, ty["scale"][str(i)]))
    out.append("\n字体文件不随包：Latin 字体按 `font-display: swap` 自托管并裁出用到的字符，预加载不超过 2 个；不为 CJK 下载网页字体（地板 F27、F09）。\n")

    out.append("## Layout\n")
    out.append("*版式：手机优先，单栏，页边 %dpx。*\n" % lay["gutter"])
    out.append("- 密度 `%s`：页边 %d px，间隔 %d px，行内边距 %d px，阅读行宽 %dch。\n- 壳最大宽 `--wrap`（默认 1120px）；栏最小高 56px；触控目标 ≥ 44px。\n- 断点是一个实例（760 平板、880 弹层变卡片、980 阅读栏），可换。\n" % (
        p["density"], lay["gutter"], lay["gap"], lay["row_pad"], lay["measure"]))
    out.append("## Elevation & Depth\n")
    out.append("*深度：面的层次靠纸色与细线，浮起的面最多一个染色阴影。*\n")
    out.append("- 层级：`--paper`（地面）→ `--paper-2`（面板、地图地面）→ 弹层（`--evk-shadow`，浅色里染结构墨，深色里加深并加一圈细线）。\n- 细线 `--rule`，线宽 `--hair` 1px、`--rule-2` %dpx、`--rule-3` %dpx，块开头的粗线 `--rule-cap` %dpx。\n- 纹理 `%s`。\n" % (
        sh["rule_2"], sh["rule_3"], sh["rule_cap"], p["texture"]))
    out.append("## Shapes\n")
    out.append("*形状：语言 `%s`。*\n" % sh["language"])
    out.append("- `--radius` %d px，`--chamfer` %d px（切角用 `clip-path`，焦点环用 inset 阴影，见 `base.css`）。\n- 分隔线母题 `%s`；实体页头 `%s`；地图标记 `%s`；数字样式 `%s`；阅读导航 `%s`。\n- 以上枚举在 `<html>` 上以属性表达，recipe 按它切换（见 Components）。\n" % (
        sh["radius"], sh["chamfer"], p["divider"], p["entity_header"], p["entity_token"], p["numerals"], p["nav"]))
    out.append("## Components\n")
    out.append("*组件：类名与标记是契约（`evk-` 前缀），`base.css` 给结构与无障碍，`recipe.css` 给这个方向的外观。*\n")
    out.append("`<html>` 属性（写进每个页面的 `<html>`，recipe 与引擎按它切换；`data-evk-lead` 决定哪种语言在双语对里领头）：\n\n```html\n%s\n```\n" % html_open_tag(p))
    out.append("加载顺序（样式表在 `<head>`，脚本在 `<body>` 末尾；`search.js` 在 `tones.js` 之后、`spring.js` 之前，引擎彼此依赖，别重排）：\n\n```html\n%s\n```\n" % load_order_html(starter))
    out.append("| 组件 | 标记 | 说明 |\n|---|---|---|")
    for a, b, c in (
        ("栏与导航", "`header.evk-bar > a.evk-brand + nav.evk-nav > a.evk-k`", "吸顶栏；当前页 `aria-current`"),
        ("双语对", "`span.evk-k > span.%s + span.%s`" % (first, second), "%s主、%s辅：第一个子元素是主语言（由 `data-evk-lead=\"%s\"` 定，全站一致）；辅语同位置同灰档" % (
            "中文" if lead == "zh" else "英文", "英文" if lead == "zh" else "中文", lead)),
        ("分隔线", "`hr.evk-divider`", "方向的分隔母题：%s" % p["divider"]),
        ("按钮", "`.evk-btn` `--primary` `--quiet`", "primary 用 `--b`，默认用 `--a`；按下 `scale(--press-scale)`"),
        ("房号·展位标签", "`span.evk-tag`", "tabular 数字；小字部分 `small`"),
        ("欢迎与数字条", "`section.evk-welcome > .evk-stats > .evk-stat`", "数字用展示字，说明用双语对"),
        ("实体网格", "`ul.evk-grid > li > a.evk-cell`", "`--e*` 内联在 cell 上；`.evk-mark` 为徽章或首字母"),
        ("实体页头", "`header.evk-entity-head`", "形态：%s" % p["entity_header"]),
        ("数字条", "`.evk-strip > .evk-num`", "每格有限定语位置"),
        ("分部", "`section.evk-part[data-part]`", "`EVK.partNav` 自动生成阅读导航，呈现：%s" % p["nav"]),
        ("底部弹层", "`.evk-sheet` + `EVK.Sheet`", "非模态；可打断；拖动 1:1；Escape 关闭"),
        ("地图", "`.evk-map > canvas` + `EVK.VenueMap`", "令牌驱动，静止不重绘"),
        ("分段与搜索", "`.evk-seg[role=tablist]` `input.evk-search`", "输入框 ≥ 16px")):
        out.append("| %s | %s | %s |" % (a, b, c))
    out.append("")
    props = kit.props_of(p)
    if props:
        out.append("**装饰母题 / props（可关）：** 这个方向的类别母题来自它借用的那套真实物件（机制），不是每个活动都有对应的东西。默认全开。盘点清单里没有依据的就关掉（例如没有植物，就不挂叶形标签），有依据的才留。每一项是一个 `--prop-*` 变量，recipe 读它；关闭值如下。\n")
        out.append("| 母题 | 变量 | 关闭值 | 是什么 |\n|---|---|---|---|")
        for pr in props:
            out.append("| `%s` | `%s` | `%s` | %s |" % (pr["name"], pr["var"], pr["off"], pr["what"].replace("|", "/")))
        out.append("")
        out.append("关一项只改一处：`evk/tokens.css` 末尾（`:root` 里）有写好的注释行 `/* --prop-x: 关闭值; */`，去掉声明外面的 `/*` `*/` 即可，例如 `%s: %s;`（后面的说明自成一条注释，不用动）；也可以在 `recipe.css` 之后加一条 `:root { %s: %s; }`。关掉的写进下面的 Deviations 表（`install.py --update` 会把 tokens.css 里已经打开的 `--prop-*` 行原样带到新文件，规则见 Roll record 的 Updating）。\n" % (
            props[0]["var"], props[0]["off"], props[0]["var"], props[0]["off"]))
    out.append("## Do's and Don'ts\n")
    out.append("**Do（这个方向的写法）：**\n")
    for x in (p.get("richness") or []):
        out.append("- %s" % x)
    for x in (p.get("watch") or []):
        out.append("- 留意漂移：%s" % x)
    out.append("")
    out.append("**Don't（只有地板规则：无障碍、正确、隐私）：**\n")
    for x in ("正文对比度 < 7:1、次级字 < 4.5:1、强调色字版 < 4.5:1（小字只用 `--a-text` `--b-text` `--climb-text`，不用填充色 `--a` `--b` `--climb` 写字）。",
              "颜色单独承载状态（当前、已读、爬升、选中至少再有一个通道：形状、长度、标签、虚实）。",
              "触控目标 < 44px；无替代的 `outline:none`；`:hover` 不放进 `@media (hover:hover)`。",
              "静止时仍在跑 `requestAnimationFrame`；动效不尊重 `prefers-reduced-motion`。",
              "编造楼层与房间；示意图不写“示意”；放学生姓名、班级等个人信息；随包放无授权的校徽、照片、字体。",
              "运行时请求第三方域名（字体、脚本、统计、瓦片）。"):
        out.append("- %s" % x)
    out.append("")
    out.append("## Motion\n")
    out.append("*动效：一个招牌动作（物理弹簧），其余反馈 ≤ 200 ms。*\n")
    out.append("```yaml\nmotion:\n  spring: {duration: %ss, bounce: %s}     # --spring-dur / --spring-bounce; EVK.Spring stiffness=(2π/dur)², damping=4π(1−bounce)/dur\n  press: %s                                  # --press-scale\n  fade: %ss                                  # --fade-dur\n  character: %s\n```\n" % (
        kit._fmt(mo["dur"], 2), kit._fmt(mo["bounce"], 2), kit._fmt(mo["press"], 3), kit._fmt(mo["fade"], 2), kit.motion_bucket(mo["dur"], mo["bounce"])))
    out.append("规则（不随抽牌变）：从当前位置与速度接手；松手按投影落点决定；离开比进入快；`prefers-reduced-motion` 下状态照样到达，只去掉插值；静止后不留 `transform`。\n")
    out.append("## Bilingual\n")
    out.append("*双语：主语言领，次语言紧随；谁灰、谁黑、谁大写，规则固定。*\n")
    out.append("- **主语言：%s**（抽牌时定为 `lead=%s`，写在 `<html data-evk-lead=\"%s\">`；要改，用 `python3 scripts/draw.py adjust lead=%s --reason \"…\"` 再 `install.py --update`，不要手改）。\n"
               "- 标记：每个双语部件写 `span.evk-k > span.%s + span.%s`，**第一个子元素是主语言，最后一个是辅语**。两层样式分开写：**层级层**（字号、字重、颜色、先后）看位置，`.evk-k > :first-child` 为主、`.evk-k > :last-child:not(:first-child)` 为辅；**字体层**（字体族、大小写、字距、断行）看 `.en` / `.cn` / `:lang()`。层级不写在 `.en` / `.cn` 上，所以换主语言不用改一行 CSS。\n"
               "- 主语言更响：名义字号 ≥ 辅语 1.1 倍，颜色用 `--text`；辅语用 `--sub`，位置、灰档、字体族、字距在所有部件里一致，辅语不转大写。\n"
               "- 标签全大写设置：`--label-case: %s`；中文用 `--f-cjk`（%s），展示用 `--f-cjk-display`（%s）。\n"
               "- 成段中文：`line-break: strict`，行高 ≥ 1.7，行宽 ≤ 40em，不两端对齐；汉字与拉丁、数字之间补空格（`EVK.spaced`）。名字：英文用 `word-break: keep-all`，中文名用 `line-break: strict` + `text-wrap: balance`，不要对中文用 keep-all。\n"
               "- 地图标签：`VenueMap` 选项 `lead` 默认读 `<html data-evk-lead>`，主语言一行在前、更大。\n"
               "- 两种语言同时可见；只有 brief 明说单语才用切换。\n" % (
                   "中文" if lead == "zh" else "英文", lead, lead, "en" if lead == "zh" else "zh", first, second, ty["label_case"],
                   f["cjk"].get("name", ""), f["cjk_display"].get("name", "")))
    out.append("## Map\n")
    out.append("*地图：手写 canvas，令牌驱动；材质与投影来自抽牌。*\n")
    out.append("```yaml\nmap:\n  projection: %s\n  material: %s\n  token: %s\n  pitch: %s\n  yaw: %s\n  wall-height: %s\n  light: %s\n  dim: %s\n  label-case: %s\n```\n" % (
        mp["projection"], mp["material"], mp["token"], kit._fmt(mp["pitch"]), kit._fmt(mp["yaw"]), kit._fmt(mp["wall_h"], 2), mp["light"], kit._fmt(mp["dim"], 2), mp["label_case"]))
    out.append("地图颜色全部读 `--m-*` 令牌（浅 / 深）：\n")
    out.append("| 令牌 | 浅 | 深 |\n|---|---|---|")
    for k in kit.MAP_COLOR_TOKENS:
        out.append("| `--%s` | %s | %s |" % (k, lt[k], dk[k]))
    out.append("\n`--m-select` 是选中的**边线**（对 `--m-slab` ≥ 3:1），`--m-select-fill` 是选中的**淡染**（`--m-room` 朝 `--m-select` 混 10–16 %，无对比度下限）：引擎用 fill 填、用 select 描边，不要拿 `--m-select` 铺满整间房。\n")
    out.append("`--m-cap` 是地图的墨线（墙帽、环、针、图标描线），对 `--m-slab` ≥ 7:1（浅 %.1f / 深 %.1f）；`--m-wall` 对 `--m-slab` ≥ 3:1（浅 %.1f / 深 %.1f）。生成器沿明度走到这两个值，`lint_floor.py` 查它们（墨线 < 4.5 不过，< 7 警告）。\n" % (
        kit.contrast(lt["m-cap"], lt["m-slab"]), kit.contrast(dk["m-cap"], dk["m-slab"]), kit.contrast(lt["m-wall"], lt["m-slab"]), kit.contrast(dk["m-wall"], dk["m-slab"])))
    out.append("楼层、房间、门、楼梯来自平面图或使用者确认的数据（`evk/venue.schema.json`）；开放区（走廊、大厅）与挑空（`void` 块）见 schema；没有平面图就画示意并标“示意”。\n")
    out.append("## Wayfinding\n")
    out.append("*导视：同一份数据既出线也出字；每步一句；路线画在所有楼层之后。*\n")
    out.append("- 路线颜色：线 `--m-route`（%s），晕边 `--m-route-halo`，流动虚线 `--m-dash`，爬升段 `--m-climb`（%s，并带“Up to 3F / 上楼到 3F”标签）；步骤里爬升的**文字**用 `--climb-text`（%s），不用 `--climb`。\n- 步骤列表 `ol.evk-steps`：当前步 `.is-current`，楼梯步 `.is-climb`；颜色之外还有序号方块、左条、文字，不靠单独的颜色。\n- `EVK.wayfind.create(venue)`：`starts()`、`plan(startId, entityId)`、`describe(plan, \"zh\"|\"en\"|\"both\")`；任何起点到任何实体都应有路线，数据层面穷举测试。\n- 文案与搜索规则见 skill 的 `references/wayfinding-copy.md`。\n" % (lt["m-route"], lt["m-climb"], lt["climb-text"]))
    if starter:
        out.append("## Starter pages\n")
        out.append("*页面骨架：`install.py --starter --venue` 从 `venue.json` 和这张牌长出来的一套能用的页面；在它上面改，不要从零写胶水代码。*\n")
        out.append("| 文件 | 内容 |\n|---|---|")
        for a, b in (("`index.html`", "栏与导航、欢迎（活动名、日期、地点；缺的值写“待定 / TBA”，不编造）、数字条、地图预览、搜索 + 楼层筛选 + 实体网格"),
                     ("`map.html`", "地图、楼层分段、路线弹层（起点 = 入口、门厅、房间、开放区；终点用 `EVK.search`；上一步 / 全览 / 下一步 + 朗读区）、房间与实体弹层、URL 状态 `?s= ?r= ?f= ?to= ?from=`、最近起点存 localStorage、无 JS 时的静态名录"),
                     ("`e/<id>.html`", "每个实体一页：页头（本方向的 `%s` 形态）、数据条（来自 `entity.facts`）、分部（来自 `entity.parts`，没有就放一段标“示意”的占位）、聚焦该实体的小地图、“怎么走”链接、上下翻页" % p["entity_header"]),
                     ("`data/venue.js`", "`window.EVK_VENUE = …`：venue.json 的脚本副本，让页面能从 `file://` 打开。改了 venue.json 要重建"),
                     ("`assets/starter.css` `assets/starter.js`", "版式胶水（只用令牌）与行为；`starter.js` 开头的 UI 词典是页面上所有词的来源")):
            out.append("| %s | %s |" % (a, b))
        out.append("\n重建（改了 venue.json 之后）：`python3 scripts/starter.py data/venue.json .evk/roll.json .`（已有文件要加 `--force`；你改过的页面先备份）。浏览器会缓存样式和脚本：重建后给资源地址加 `?v=` 或强制刷新。\n")
    out.append("## Roll record\n")
    out.append("| 项 | 值 |\n|---|---|")
    out.append("| 方向 | %s |" % card["direction"])
    out.append("| 预设码 | `%s` |" % card["code"])
    out.append("| 牌种子 / 抽牌种子 | %s / %s |" % (card.get("card_seed"), roll.get("seed")))
    out.append("| 标签 | %s |" % (", ".join(roll.get("tags", [])) or "-"))
    out.append("| 冻结（--keep） | %s |" % (", ".join("%s=%s" % (k, ",".join(v) if isinstance(v, list) else v) for k, v in (roll.get("keep") or {}).items()) or "无"))
    out.append("| steer / canon | %s / %s |" % (roll.get("steer") or "-", "是" if roll.get("canon") else "否"))
    out.append("| 主语言 lead | %s |" % ("zh 中文主" if lead == "zh" else "en 英文主"))
    out.append("| 与原站相似度 | %.2f |" % card["similarity_to_canon"])
    out.append("| 选择理由 | %s |" % (roll.get("reason") or "未记录"))
    if roll.get("rerolls"):
        out.append("| 重抽 | %s |" % "; ".join("%s: %s" % (r.get("seed"), r.get("reason")) for r in roll["rerolls"]))
    out.append("")
    out.append("### Deviations\n")
    out.append("方向内手调的参数写在这里（日期、改了什么、为什么、怎么改回去）。`draw.py adjust` 记下的改动已列在下面；你在页面层做的覆盖也补在这里。\n")
    out.append("| 日期 | 改动 | 理由 | 还原 |\n|---|---|---|---|")
    rows = [x for x in (p.get("adjusted") or []) if isinstance(x, dict) and not kit.is_keep_record(x)]
    for x in rows:
        out.append("| %s | `%s`：%s → %s | %s | `python3 scripts/draw.py adjust %s=%s --reason \"…\"` |" % (
            x.get("date") or "", x.get("key"), x.get("from"), x.get("to"), (x.get("reason") or "").replace("|", "/"), x.get("key"), x.get("from")))
    out.append("|  |  |  |  |" if not rows else "")
    out.append("")
    out.append("### Updating\n")
    out.append("`draw.py adjust` 之后跑 `install.py --update`：只重写 `evk/tokens.css` 和 `.evk/roll.json`；`base.css`、`recipe.css`、引擎和这份 DESIGN.md 不动（新的 DESIGN.md 另存为 `.evk/DESIGN.generated.md`，把新的 Deviations 行手抄过来）。"
               "**tokens.css 里保留的只有一样：** 每一条没有被注释掉的 `--prop-*: 值;` 行（你为关掉某个道具去掉注释的，或你给 `--prop-*` 写的自己的值）。它们连值带行尾注释**原样**带到新文件里，替换那一项生成的注释行；这张牌没有对应道具的 `--prop-*` 行也会留在道具块后面。"
               "**其余全部按牌重新生成**：颜色、字体、形状、地图令牌（手改过的值会丢，用 git 对照）、文件头、深色块，以及没有去掉注释的道具行（回到默认开）。\n")
    return "\n".join(out)


# --------------------------------------------------------------------------------------------------
# the install
# --------------------------------------------------------------------------------------------------

TOKENS_HEADER = "/* %s" % kit.KIT_NAME      # the first characters of every tokens.css this kit generates


def kept_text(lines, would=False):
    """What --update carried over (or would): the live --prop-* lines, and the rule, in one message."""
    shown = "; ".join(" ".join(x["line"].split()) for x in lines)
    return "%s %s" % ("would keep" if would else "kept",
                      ("%d live --prop-* line(s) of the old evk/tokens.css, verbatim: %s. " % (len(lines), shown) if lines else "no live --prop-* line (none was uncommented). ")
                      + "Everything else in tokens.css is regenerated from the card (hand-edited values are lost: diff with git).")


def plan_files(roll, card, idx, target, name=None, update=False, starter=False):
    """-> (items, missing). items: [(dest Path, kind, source/Content)] kind 'text' | 'copy'.
    update=True: only what the card generates (tokens.css, the roll) plus the regenerated DESIGN.md as .evk/DESIGN.generated.md.
    starter=True: the DESIGN.md also describes the starter pages and their load order."""
    items, missing = [], []
    t = Path(target)
    hdr = "installed card %d  code %s  seed %s" % (idx, card["code"], card.get("card_seed"))
    kept = []
    if update:            # every live --prop-* line of the installed tokens.css is carried over verbatim (kit.live_prop_lines); nothing else is
        try:
            kept = kit.live_prop_lines((t / "evk" / "tokens.css").read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    items.append((t / "evk" / "tokens.css", "text", kit.tokens_css(card["params"], hdr, props_keep=kept)))

    def copy(src, dest):
        if Path(src).exists():
            items.append((dest, "copy", Path(src)))
        else:
            missing.append(str(Path(src).relative_to(kit.SKILL_ROOT)) if str(src).startswith(str(kit.SKILL_ROOT)) else str(src))

    if not update:
        copy(kit.ASSETS_DIR / "floor" / "base.css", t / "evk" / "base.css")
        copy(kit.ASSETS_DIR / "recipes" / ("%s.css" % card["direction"]), t / "evk" / "recipe.css")
        eng = kit.ASSETS_DIR / "engine"
        names = list(ENGINE_ORDER)
        if eng.exists():
            names += sorted(x.name for x in eng.glob("*.js") if x.name not in ENGINE_ORDER)
        for n in names:
            copy(eng / n, t / "evk" / "engine" / n)
        copy(eng / "venue.schema.json", t / "evk" / "venue.schema.json")
        items.append((t / "DESIGN.md", "text", design_md(roll, card, idx, name, starter)))
    else:
        items.append((t / ".evk" / "DESIGN.generated.md", "text", design_md(roll, card, idx, name, starter)))
    r = dict(roll)
    r["chosen"] = roll.get("chosen") if roll.get("chosen") else idx
    items.append((t / ".evk" / "roll.json", "text", json.dumps(r, ensure_ascii=False, indent=1) + "\n"))
    return items, missing


def _same_file(a, b):
    try:
        return Path(a).exists() and Path(b).exists() and os.path.samefile(str(a), str(b))
    except OSError:
        return False


def _write_text(d, text):
    """Write atomically (tmp + replace): safe when the file is also the roll we just read."""
    tmp = d.with_name(d.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(str(tmp), str(d))


STARTER_MISSING = ("install.py: --starter needs scripts/starter.py (the page-skeleton builder), which is not in this kit: the tokens, CSS, "
                   "engine and DESIGN.md are installed, the pages are NOT. Build index.html and map.html from assets/demo/engine-demo.html "
                   "and references/ux-contracts.md, or add starter.py and run this again with --force.")


def load_starter():
    """scripts/starter.py as a module, or None when the kit does not have it (a clear message is printed by the caller).
    A starter.py that exists but fails to import is NOT 'missing': that error is raised."""
    try:
        import starter
    except ModuleNotFoundError as e:
        if e.name == "starter":
            return None
        raise
    return starter if hasattr(starter, "render") else None


def read_venue(path):
    """The project's venue.json as a dict. Raises ValueError with a message for the user."""
    p = Path(path)
    try:
        v = json.loads(p.read_text(encoding="utf-8"))
    except OSError as e:
        raise ValueError("cannot read --venue %s: %s" % (p, e))
    except ValueError as e:
        raise ValueError("--venue %s is not valid JSON: %s" % (p, e))
    if not isinstance(v, dict) or not isinstance(v.get("floors"), list) or not v["floors"] or not isinstance(v.get("entities"), list) or not v["entities"]:
        raise ValueError("--venue %s needs floors and entities (assets/engine/venue.schema.json)" % p)
    return v


def starter_paths(mod, venue, card, target):
    """The files the starter would write under target (render writes nothing here). Uses starter.plan() when it has one,
    else renders into a scratch directory and lists what came out."""
    if hasattr(mod, "plan"):
        return [Path(x) for x in mod.plan(venue, card, Path(target))]
    with tempfile.TemporaryDirectory() as td:
        got = mod.render(venue, card, Path(td), True)
        return [Path(target) / Path(x).resolve().relative_to(Path(td).resolve()) for x in got]


def run(roll_path, target, force=False, dry=False, strict=False, name=None, card_no=None, update=False, out=print,
        starter=False, venue_path=None):
    try:
        roll = draw.read_roll(roll_path)
    except (OSError, ValueError) as e:
        out("install.py: %s" % e)
        return 2
    venue = mod = None
    if starter:
        if not venue_path:
            out("install.py: --starter needs --venue PATH (your data/venue.json: assets/engine/venue.schema.json)")
            return 2
        try:
            venue = read_venue(venue_path)
        except ValueError as e:
            out("install.py: %s" % e)
            return 2
        mod = load_starter()
        if mod is None and strict:
            out(STARTER_MISSING)
            out("install.py: --strict: nothing written")
            return 1
    cards = roll.get("cards") or []
    if card_no:
        if not 1 <= card_no <= len(cards):
            out("install.py: --card must be 1-%d" % len(cards))
            return 2
        card, idx = cards[card_no - 1], card_no
    else:
        card = draw.pick_chosen_card(roll)
        if card is None:
            out("install.py: no card has been chosen in %s.\n  Open the specimens, then: python3 scripts/draw.py choose N --reason \"names one physical thing from the inventory\" --roll %s" % (roll_path, roll_path))
            return 2
        idx = cards.index(card) + 1
    tok = Path(target) / "evk" / "tokens.css"
    if update:
        if not tok.exists():
            out("install.py: --update needs an installed project, and %s does not exist.\n  Install first (without --update)." % tok)
            return 2
        if not tok.read_text(encoding="utf-8", errors="replace").lstrip().startswith(TOKENS_HEADER) and not force:
            out("install.py: %s was not written by this kit (no header): --update refuses to replace a hand-written file; pass --force to do it anyway." % tok)
            return 2
    kept_lines = kit.live_prop_lines(tok.read_text(encoding="utf-8", errors="replace")) if update else []
    items, missing = plan_files(roll, card, idx, target, name, update, bool(mod))
    # a file that IS the roll we were given (the usual layout: draw.py wrote .evk/roll.json inside the project) is updated in
    # place; a file that --update regenerates by design is not a conflict either
    in_place = [d for d, _, _ in items if _same_file(d, roll_path)]
    regenerated = {tok, Path(target) / ".evk" / "DESIGN.generated.md"} if update else set()
    conflicts = [d for d, _, _ in items if d.exists() and d not in in_place and d not in regenerated]
    if mod is not None:        # the starter's pages count too: all conflicts at once, and nothing is written
        try:
            conflicts += [d for d in starter_paths(mod, venue, card, target) if d.exists() and d not in conflicts]
        except (ValueError, KeyError, OSError) as e:
            out("install.py: the starter cannot build pages from %s: %s" % (venue_path, e))
            return 2
    if conflicts and not force:
        out("install.py: refusing to overwrite %d existing file(s) (nothing written):" % len(conflicts))
        for d in conflicts:
            out("  " + str(d))
        out("  pass --force to overwrite, or install into an empty directory"
            + ("" if update else "; after `draw.py adjust`, `--update` refreshes only tokens.css and the roll"
                                 + ("; `starter.py` alone rebuilds the pages" if mod is not None else "")))
        return 2
    if missing:
        out("install.py: kit files missing, skipped: %s%s" % (", ".join(missing), "  (the kit is incomplete)"))
        if strict:
            out("install.py: --strict: nothing written")
            return 1
    for d, kind, src in items:
        if dry:
            out("would write %s%s" % (d, "  (in place: it is the roll you passed)" if d in in_place else ""))
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        if kind == "copy":
            shutil.copyfile(str(src), str(d))
        elif d in in_place:
            _write_text(d, src)
        else:
            d.write_text(src, encoding="utf-8")
        out("wrote %s%s" % (d, "  (in place)" if d in in_place else ""))
    starter_written = []
    if mod is not None:
        try:
            if dry:
                for d in starter_paths(mod, venue, card, target):
                    out("would write %s%s" % (d, "  (overwrites: --force)" if d.exists() else ""))
            else:
                starter_written = [Path(x) for x in mod.render(venue, card, Path(target), force)]
                for d in starter_written:
                    out("wrote %s" % d)
        except FileExistsError as e:        # starter.StarterConflict: nothing was written by the starter
            out("install.py: the starter refused: %s" % e)
            return 2
        except (ValueError, KeyError, OSError) as e:
            out("install.py: the starter could not build the pages: %s" % e)
            return 2
    elif starter:
        out(STARTER_MISSING)
    if dry:
        if update:
            out(kept_text(kept_lines, would=True))
        return 0
    comp = []
    for lab, fn in (("base.css", "base.css"), ("recipe.css", "recipe.css")):
        q = Path(target) / "evk" / fn
        if q.exists():
            comp.append((lab, q.read_text(encoding="utf-8")))
    rep = lint_floor.lint_tokens_text(tok.read_text(encoding="utf-8"), "installed tokens", comp or None)
    out("")
    out(lint_floor.format_reports([rep], quiet=True))
    out("")
    out("card %d  %s  %s" % (idx, card["direction"], card["code"]))
    out(html_open_tag(card["params"]))
    props = kit.props_of(card["params"])
    if props:
        live = kit.live_prop_values(tok.read_text(encoding="utf-8"))
        out("props (decorative motifs, on by default): %s" % ", ".join("%s %s%s" % (x["name"], x["what"], (" [OFF]" if live[x["var"]] == x["off"].strip() else " [%s: %s]" % (x["var"], live[x["var"]])) if x["var"] in live else "") for x in props))
        out("  keep one only if the inventory supports it; to switch one off uncomment its line at the end of :root in evk/tokens.css (e.g. %s: %s;)" % (props[0]["var"], props[0]["off"]))
    if update:
        out("updated: evk/tokens.css and .evk/roll.json. DESIGN.md, base.css, recipe.css and the engine were left alone.")
        out(kept_text(kept_lines))
        out("next: diff DESIGN.md against .evk/DESIGN.generated.md and copy over the new Deviations rows; make every page's <html> carry the attributes above.")
    elif starter_written:
        out("%d starter page/asset files written. Pages load evk/tokens.css, base.css, recipe.css, assets/starter.css, then data/venue.js, the engine (%s) and assets/starter.js." % (
            len(starter_written), ", ".join(ENGINE_ORDER)))
        out("next: open index.html from a server (or file://) in 375 px light and dark; read DESIGN.md; edit venue.json and rebuild with scripts/starter.py; run lint_floor.py on a built page")
    else:
        out("load: evk/tokens.css, evk/base.css, evk/recipe.css; scripts in this order: %s" % ", ".join(ENGINE_ORDER))
        out("next: read DESIGN.md; build pages against references/ux-contracts.md; run lint_floor.py on the built page")
    return 0 if rep.ok else 1


def _selftest():
    kit.REFERENCE_FP_PATH = kit.SCRIPTS_DIR / "__no_reference__.json"   # hermetic: no dependence on other builders' files
    import random
    fails = []

    def ok(cond, msg):
        if not cond:
            fails.append(msg)
            print("  FAIL", msg)

    lib = kit.load_directions(fixture=True)
    roll = draw.build_roll(lib, 5150, 3, ["letter"], {}, None, False, None, False)
    log = []
    with tempfile.TemporaryDirectory() as td:
        rp = Path(td) / "roll.json"
        draw.write_roll(roll, rp)
        tgt = Path(td) / "site"
        # refuses without a chosen card
        rc = run(rp, tgt, out=log.append)
        ok(rc == 2 and not tgt.exists() and any("no card has been chosen" in l for l in log), "refuses without a chosen card, writes nothing")
        roll["chosen"] = 2
        roll["reason"] = "the reply-paid card on the desk"
        draw.write_roll(roll, rp)
        log[:] = []
        rc = run(rp, tgt, out=log.append)
        ok(rc in (0, 1), "install ran (rc=%s)" % rc)
        for rel in ("evk/tokens.css", "DESIGN.md", ".evk/roll.json"):
            ok((tgt / rel).exists(), "wrote %s" % rel)
        css = (tgt / "evk" / "tokens.css").read_text(encoding="utf-8")
        card = roll["cards"][1]
        ok(css == kit.tokens_css(card["params"], "installed card 2  code %s  seed %s" % (card["code"], card.get("card_seed"))), "tokens.css = tokens_css(params)")
        ok(lint_floor.lint_tokens_text(css).ok, "installed tokens pass lint")
        dm = (tgt / "DESIGN.md").read_text(encoding="utf-8")
        ok(dm.startswith("---\nversion: alpha\n") and "\n---\n" in dm[4:], "DESIGN.md has YAML front matter")
        for sec in ("## Overview", "## Colors", "## Typography", "## Layout", "## Elevation & Depth", "## Shapes", "## Components", "## Do's and Don'ts",
                    "## Motion", "## Bilingual", "## Map", "## Wayfinding", "## Roll record", "### Deviations"):
            ok(sec in dm, "DESIGN.md has %s" % sec)
        fm = dm.split("\n---\n")[0]
        for key in ("colors:", "typography:", "rounded:", "spacing:", "components:", "primary:", "paper:"):
            ok(("\n" + key) in fm or ("  " + key) in fm, "front matter has %s" % key)
        ok(card["code"] in dm and "the reply-paid card on the desk" in dm, "DESIGN.md records code and reason")
        saved = json.loads((tgt / ".evk" / "roll.json").read_text(encoding="utf-8"))
        ok(saved["chosen"] == 2, ".evk/roll.json keeps the choice")
        # never overwrites
        before = (tgt / "DESIGN.md").read_text(encoding="utf-8")
        (tgt / "DESIGN.md").write_text("mine", encoding="utf-8")
        log[:] = []
        rc = run(rp, tgt, out=log.append)
        ok(rc == 2 and (tgt / "DESIGN.md").read_text(encoding="utf-8") == "mine" and any("refusing" in l for l in log), "refuses to overwrite")
        rc = run(rp, tgt, force=True, out=log.append)
        ok(rc in (0, 1) and (tgt / "DESIGN.md").read_text(encoding="utf-8") == before, "--force overwrites")
        # dry run
        rc = run(rp, Path(td) / "dry", dry=True, out=log.append)
        ok(rc == 0 and not (Path(td) / "dry").exists(), "--dry-run writes nothing")
        # strict + missing kit files (point ASSETS_DIR nowhere)
        old = kit.ASSETS_DIR
        kit.ASSETS_DIR = Path(td) / "nowhere"
        log[:] = []
        rc = run(rp, Path(td) / "strict", strict=True, out=log.append)
        ok(rc == 1 and not (Path(td) / "strict").exists(), "--strict with missing kit files writes nothing")
        log[:] = []
        rc = run(rp, Path(td) / "partial", out=log.append)
        ok(rc in (0, 1) and (Path(td) / "partial" / "evk" / "tokens.css").exists() and any("missing" in l for l in log), "missing kit files are skipped with a message")
        kit.ASSETS_DIR = old
        # code round trip from the saved roll
        back, warns, info = draw.card_from_code(lib, saved["cards"][1]["code"])
        ok(back["params"] == saved["cards"][1]["params"], "saved roll decodes to the same params")
    # --- FIX-SPEC A6: the roll lives inside the target (.evk/roll.json): updated in place, no conflict, no --force
    #     --update after `draw.py adjust`: tokens + roll only; DESIGN.md and hand-edited kit copies survive
    #     DESIGN.md wording: tokens and sampled values, no colour words, lead language from the roll, no floor numbers that do not exist
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "proj"
        rp = proj / ".evk" / "roll.json"
        roll2 = draw.build_roll(lib, 909, 3, ["letter"], kit.parse_keep(["lead=zh"]), None, False, None, False)
        roll2["chosen"], roll2["reason"] = 2, "the postage-paid reply card"
        draw.write_roll(roll2, rp)
        log = []
        rc = run(rp, proj, out=log.append)
        ok(rc in (0, 1) and not any("refusing" in l for l in log), "in place: the roll inside the target is not a conflict (rc=%s)" % rc)
        ok(any(l.endswith("(in place)") for l in log) and json.loads(rp.read_text(encoding="utf-8"))["chosen"] == 2, "…and it was updated in place")
        ok(not (proj / ".evk" / "roll.json.tmp").exists(), "…atomically (no .tmp left)")
        log[:] = []
        rc = run(rp, proj, out=log.append)
        ok(rc == 2 and any("refusing" in l for l in log) and not any(l.strip().endswith("roll.json") for l in log if l.startswith("  ")), "a second install lists the other files but never the roll itself")
        rc = run(rp, proj, force=True, out=log.append)
        ok(rc in (0, 1), "--force still works")
        dm = (proj / "DESIGN.md").read_text(encoding="utf-8")
        card2 = roll2["cards"][1]
        ok("F29" not in dm and "红线" not in dm, "DESIGN.md names no floor rule that does not exist and no hard-coded colour word")
        rules_ = re.findall(r"(?<![#0-9A-Fa-f])F(\d\d)(?![0-9A-Fa-f])", dm)           # not the F34 inside a hex colour
        ok(rules_ and all(1 <= int(n) <= 27 for n in rules_), "every floor rule number in DESIGN.md exists (F01-F27)")
        ok('data-evk-lead="zh"' in dm and 'lang="zh-CN"' in dm and "span.cn + span.en" in dm and "默认英文主" not in dm, "lead=zh: html snippet, markup order and wording follow the roll")
        ok(card2["params"]["palette"]["light"]["climb-text"] in dm and "--climb-text" in dm and "--m-select-fill" in dm, "DESIGN.md lists climb-text and m-select-fill with their sampled values")
        roll3 = draw.build_roll(lib, 909, 3, ["letter"], {}, None, False, None, False)
        dm_en = design_md(roll3, roll3["cards"][1], 2)
        ok('data-evk-lead="en"' in dm_en and 'lang="en"' in dm_en and "span.en + span.cn" in dm_en and "span.cn + span.en" not in dm_en, "lead=en: the other way round")
        # --update after adjust
        (proj / "evk" / "base.css").write_text("/* my edit */", encoding="utf-8")
        (proj / "DESIGN.md").write_text("# mine\n", encoding="utf-8")
        before_tok = (proj / "evk" / "tokens.css").read_text(encoding="utf-8")
        r_ = draw.read_roll(rp)
        draw.adjust_card(lib, r_, 2, ["b=#0B5FFF", "lead=en"], "brand blue from the logo")
        draw.write_roll(r_, rp)
        log[:] = []
        rc = run(rp, proj, update=True, out=log.append)
        after_tok = (proj / "evk" / "tokens.css").read_text(encoding="utf-8")
        ok(rc in (0, 1) and after_tok != before_tok and "--b: #" in after_tok and 'data-evk-lead="en"' in after_tok, "--update rewrites tokens.css from the adjusted card (rc=%s)" % rc)
        ok((proj / "evk" / "base.css").read_text(encoding="utf-8") == "/* my edit */" and (proj / "DESIGN.md").read_text(encoding="utf-8") == "# mine\n", "…and leaves base.css and DESIGN.md alone")
        gen = (proj / ".evk" / "DESIGN.generated.md")
        ok(gen.exists() and "brand blue from the logo" in gen.read_text(encoding="utf-8") and 'data-evk-lead="en"' in gen.read_text(encoding="utf-8"), "…writes the regenerated DESIGN.md with the Deviations rows to .evk/DESIGN.generated.md")
        ok(any("data-evk-lead" in l for l in log), "…prints the <html> attributes")
        (proj / "evk" / "tokens.css").write_text("/* hand written */", encoding="utf-8")
        log[:] = []
        ok(run(rp, proj, update=True, out=log.append) == 2 and (proj / "evk" / "tokens.css").read_text(encoding="utf-8") == "/* hand written */", "--update refuses a tokens.css this kit did not write")
        log[:] = []
        ok(run(rp, Path(td) / "elsewhere", update=True, out=log.append) == 2, "--update needs an installed project")
        # an older roll (no lead / climb-text / m-select-fill) still installs
        old = json.loads(json.dumps(roll3))
        for c in old["cards"]:
            c["params"].pop("lead", None)
            for sc in ("light", "dark"):
                c["params"]["palette"][sc].pop("climb-text", None)
                c["params"]["palette"][sc].pop("m-select-fill", None)
        old["chosen"] = 1
        op = Path(td) / "old" / "roll.json"
        draw.write_roll(old, op)
        rc = run(op, Path(td) / "oldsite", out=log.append)
        ok(rc in (0, 1) and "--climb-text:" in (Path(td) / "oldsite" / "evk" / "tokens.css").read_text(encoding="utf-8"), "an older roll installs with the new tokens filled in")
    # --- FIX-SPEC-3 B: DESIGN.md load order carries search.js; floor-tuned and frozen values are told apart
    dm_t = design_md(roll3, roll3["cards"][1], 2)
    order_ = [m.group(1) for m in re.finditer(r'evk/engine/([\w-]+\.js)', dm_t)]
    ok(order_ == ENGINE_ORDER and order_.index("search.js") == order_.index("tones.js") + 1, "DESIGN.md loads the engine in order, search.js included: %s" % order_)
    ok("assets/starter.js" not in dm_t and "## Starter pages" not in dm_t, "…and says nothing of the starter unless it is installed")
    dm_s = design_md(roll3, roll3["cards"][1], 2, None, True)
    ok(dm_s.index("data/venue.js") < dm_s.index("evk/engine/tones.js") < dm_s.index("evk/engine/venue-map.js") < dm_s.index("assets/starter.js") and "## Starter pages" in dm_s,
       "with the starter: data/venue.js, the engine, then assets/starter.js; a Starter pages section")
    c_ = json.loads(json.dumps(roll3["cards"][1]))
    c_["params"]["floor_tuned"] = ["light.a: lightness re-fitted to this ground (>= 3:1 vs paper)"]
    c_["params"]["adjusted"] = [kit.keep_record("map.projection", "plan", "exploded", kit.KEEP_REASON + ": outside"),
                                {"key": "map.pitch", "from": 40, "to": 30, "reason": "three floors", "date": "2026-10-23"}]
    dm_a = design_md(roll3, c_, 2)
    ok("**floor-tuned**" in dm_a and "lightness re-fitted" in dm_a.split("**floor-tuned**")[1].split("## Typography")[0], "DESIGN.md lists what the floor rules tuned as floor-tuned")
    ok("冻结在包络之外" in dm_a and dm_a.count("map.pitch") >= 1 and "three floors" in dm_a.split("### Deviations")[1] and "three floors" not in dm_a.split("### Deviations")[0],
       "…frozen values apart, and only `draw.py adjust` edits in the Deviations table")
    ok("m-cap" in dm_t and "≥ 7:1" in dm_t, "DESIGN.md states the map ink contrast")
    # --- FIX-SPEC-4 item 9: props are listed with their off values in DESIGN.md and written as commented lines in tokens.css
    ok("装饰母题" not in dm_t and "--prop-" not in kit.tokens_css(roll3["cards"][1]["params"]), "a direction without props: no props section, no props lines")
    props_ = [{"name": "leaf", "var": "--prop-leaf", "off": "none", "what": "叶形标签"}, {"name": "grain", "var": "--prop-grain", "off": "0", "what": "纸纹"}]
    cp_ = json.loads(json.dumps(roll3["cards"][1]))
    cp_["params"]["props"] = props_
    dm_p = design_md(roll3, cp_, 2)
    sec_ = dm_p.split("装饰母题")[1].split("## Do's and Don'ts")[0] if "装饰母题" in dm_p else ""
    ok("| `leaf` | `--prop-leaf` | `none` | 叶形标签 |" in sec_ and "| `grain` | `--prop-grain` | `0` | 纸纹 |" in sec_ and "去掉声明外面的" in sec_ and "Deviations" in sec_ and "Updating" in sec_,
       "DESIGN.md lists every prop with its var, off value and meaning, and how to switch one off")
    ok(dm_p.index("装饰母题") < dm_p.index("## Do's and Don'ts") and dm_p.index("## Components") < dm_p.index("装饰母题"), "…inside Components")
    with tempfile.TemporaryDirectory() as td:
        rpp = Path(td) / "proj" / ".evk" / "roll.json"
        rollp = json.loads(json.dumps(roll3))
        rollp["cards"][1]["params"]["props"] = props_
        rollp["chosen"] = 2
        draw.write_roll(rollp, rpp)
        log = []
        rc = run(rpp, Path(td) / "proj", out=log.append)
        tk = Path(td) / "proj" / "evk" / "tokens.css"
        t0 = tk.read_text(encoding="utf-8")
        ok(rc in (0, 1) and "/* --prop-leaf: none;" in t0 and "/* --prop-grain: 0;" in t0 and not re.search(r"^\s*--prop-", t0, re.M), "install writes the props as commented lines (all on)")
        ok(lint_floor.lint_tokens_text(t0).ok, "…and the tokens still pass lint")
        ok(any(l.startswith("props (decorative motifs") and "叶形标签" in l for l in log) and any("uncomment its line" in l for l in log), "…and tells what the props are and how to switch one off")
        tk.write_text(t0.replace("/* --prop-leaf: none;", "--prop-leaf: none; /*"), encoding="utf-8")      # the user uncomments one line
        log[:] = []
        rc = run(rpp, Path(td) / "proj", update=True, out=log.append)
        t1 = tk.read_text(encoding="utf-8")
        ok(rc in (0, 1) and re.search(r"^\s*--prop-leaf: none;", t1, re.M) and not re.search(r"^\s*--prop-grain:", t1, re.M) and "/* --prop-grain: 0;" in t1,
           "--update keeps the props you switched off and leaves the others commented")
        ok(any("叶形标签 [OFF]" in l and "纸纹 [OFF]" not in l for l in log), "…and says which are OFF")
        # FIX-SPEC-5 #2: every live --prop-* line comes back VERBATIM (own value, own trailing comment); the rest is regenerated
        mine = ("  --prop-leaf: none;   /* no plants at this fair */\n  --prop-grain: .35;\n  --prop-ghost: 1;  /* from an older card */\n")
        hand = t1.replace("--paper:", "--paper-hand-edit:", 1) if "--paper:" in t1 else t1
        edited = re.sub(r"^\s*--prop-leaf: none;.*$", lambda m: mine.rstrip("\n"), hand, flags=re.M)
        tk.write_text(edited, encoding="utf-8")
        log[:] = []
        rc = run(rpp, Path(td) / "proj", update=True, out=log.append)
        t2 = tk.read_text(encoding="utf-8")
        ok(rc in (0, 1) and "  --prop-leaf: none;   /* no plants at this fair */\n" in t2 and "  --prop-grain: .35;\n" in t2 and "  --prop-ghost: 1;  /* from an older card */\n" in t2,
           "--update carries every live --prop-* line over verbatim: own value, own trailing comment, a var the card has no prop for")
        ok(t2.count("--prop-leaf") == 1 and t2.count("--prop-grain") == 1 and "/* --prop-leaf:" not in t2 and "/* --prop-grain:" not in t2, "…in place of the generated lines, not next to them")
        ok("--paper-hand-edit" not in t2 and "--paper:" in t2, "…while a hand-edited token value is regenerated")
        ok(any(l.startswith("kept 3 live --prop-* line(s)") and "no plants at this fair" in l and "regenerated" in l for l in log), "…and the update says what it kept and what it regenerated: %s" % [l for l in log if l.startswith("kept") or l.startswith("would")])
        ok(any("纸纹 [--prop-grain: .35]" in l for l in log) and any("叶形标签 [OFF]" in l for l in log), "…and shows a prop set to your own value as such")
        log[:] = []
        rc = run(rpp, Path(td) / "proj", update=True, dry=True, out=log.append)
        ok(rc == 0 and any(l.startswith("would keep 3 live --prop-* line(s)") for l in log) and tk.read_text(encoding="utf-8") == t2, "--update --dry-run says what it would keep and writes nothing")
        tk.write_text(t0, encoding="utf-8")
        log[:] = []
        run(rpp, Path(td) / "proj", update=True, out=log.append)
        t3 = tk.read_text(encoding="utf-8")
        ok("/* --prop-leaf: none; */" in t3 and "/* --prop-grain: 0; */" in t3 and not re.search(r"^\s*--prop-", t3, re.M),
           "--update with no live --prop-* line: every prop is back to its commented (ON) line")
        ok(any(l.startswith("kept no live --prop-* line") for l in log), "…and says that nothing was kept")
        hp_ = " ".join(subprocess.run([sys.executable, str(Path(__file__).resolve()), "--help"], capture_output=True, text=True).stdout.split())
        ok("every live (uncommented) `--prop-*: value;` line" in hp_ and "VERBATIM" in hp_ and "regenerated from the card" in hp_, "--help says exactly which prop lines --update preserves")
    # --- FIX-SPEC-3 A4: --starter --venue calls starter.render(venue, card, target, force) and obeys the conflict rules
    import types
    vdir = tempfile.mkdtemp()
    vp = Path(vdir) / "venue.json"
    vp.write_text(json.dumps({"name": {"en": "Test Hall"}, "floors": [{"id": "1F"}], "entities": [{"id": "e1", "name": "E1"}]}), encoding="utf-8")
    calls = []
    fake = types.ModuleType("starter")

    def _plan(venue, card, out_dir):
        return [Path(out_dir) / "index.html", Path(out_dir) / "map.html", Path(out_dir) / "e" / "e1.html"]

    def _render(venue, card, out_dir, force=False):
        calls.append((venue["name"]["en"], card["direction"], Path(out_dir), force))
        paths = _plan(venue, card, out_dir)
        clash = [x for x in paths if x.exists()]
        if clash and not force:
            raise FileExistsError("refusing to overwrite %d existing file(s)" % len(clash))
        for x in paths:
            x.parent.mkdir(parents=True, exist_ok=True)
            x.write_text("<!doctype html>", encoding="utf-8")
        return paths

    fake.plan, fake.render = _plan, _render
    had = sys.modules.get("starter", "absent")
    try:
        sys.modules["starter"] = fake
        with tempfile.TemporaryDirectory() as td:
            rp = Path(td) / "roll.json"
            roll4 = draw.build_roll(lib, 777, 3, [], kit.parse_keep(["lead=zh"]), None, False, None, False)
            roll4["chosen"], roll4["reason"] = 1, "the reply-paid card"
            draw.write_roll(roll4, rp)
            tg = Path(td) / "site"
            log = []
            rc = run(rp, tg, out=log.append, starter=True, venue_path=vp)
            ok(rc in (0, 1) and (tg / "index.html").exists() and (tg / "e" / "e1.html").exists() and (tg / "evk" / "tokens.css").exists(), "--starter: the pages are written next to evk/ (rc=%s)" % rc)
            ok(len(calls) == 1 and calls[0][0] == "Test Hall" and calls[0][1] == roll4["cards"][0]["direction"] and calls[0][2] == tg and calls[0][3] is False,
               "…render(venue, card, target, force) got the venue dict, the chosen card, the target and force=False: %s" % (calls,))
            ok(any(l.startswith("wrote ") and l.endswith("index.html") for l in log), "…each page is reported")
            dm_ = (tg / "DESIGN.md").read_text(encoding="utf-8")
            ok("## Starter pages" in dm_ and "assets/starter.js" in dm_, "…and DESIGN.md describes the starter")
            log[:] = []
            rc = run(rp, tg, out=log.append, starter=True, venue_path=vp)
            ok(rc == 2 and any("refusing" in l for l in log) and any(l.strip().endswith("index.html") for l in log), "a second run lists every conflict, starter pages included, and writes nothing")
            ok(len(calls) == 1, "…without calling render")
            rc = run(rp, tg, force=True, out=log.append, starter=True, venue_path=vp)
            ok(rc in (0, 1) and len(calls) == 2 and calls[1][3] is True, "--force passes force=True to render")
            log[:] = []
            rc = run(rp, Path(td) / "dry", dry=True, out=log.append, starter=True, venue_path=vp)
            ok(rc == 0 and not (Path(td) / "dry").exists() and any("would write" in l and l.endswith("map.html") for l in log) and len(calls) == 2, "--dry-run lists the pages and writes nothing")
            log[:] = []
            ok(run(rp, Path(td) / "nov", out=log.append, starter=True) == 2 and any("--venue" in l for l in log), "--starter without --venue -> 2")
            bad = Path(td) / "bad.json"
            bad.write_text("{", encoding="utf-8")
            ok(run(rp, Path(td) / "badv", out=log.append, starter=True, venue_path=bad) == 2 and not (Path(td) / "badv").exists(), "an unreadable venue -> 2, nothing written")
            # --update with --starter: tokens + the pages, which still obey force
            log[:] = []
            rc = run(rp, tg, update=True, out=log.append, starter=True, venue_path=vp)
            ok(rc == 2 and any("refusing" in l for l in log), "--update --starter still refuses to overwrite the pages without --force")
        # no scripts/starter.py: the rest installs, a clear message, --strict writes nothing
        sys.modules["starter"] = None
        with tempfile.TemporaryDirectory() as td:
            rp = Path(td) / "roll.json"
            draw.write_roll(roll4, rp)
            log = []
            rc = run(rp, Path(td) / "site", out=log.append, starter=True, venue_path=vp)
            ok(rc in (0, 1) and (Path(td) / "site" / "evk" / "tokens.css").exists() and not (Path(td) / "site" / "index.html").exists()
               and any("needs scripts/starter.py" in l for l in log), "no starter.py: tokens, CSS and engine install, the pages are skipped with a clear message")
            log[:] = []
            rc = run(rp, Path(td) / "strict", strict=True, out=log.append, starter=True, venue_path=vp)
            ok(rc == 1 and not (Path(td) / "strict").exists() and any("needs scripts/starter.py" in l for l in log), "…and --strict writes nothing")
    finally:
        if had == "absent":
            sys.modules.pop("starter", None)
        else:
            sys.modules["starter"] = had
    # the real starter.py, if the kit has it, on the demo venue: a whole site installs and lints
    real = load_starter()
    demo = kit.ASSETS_DIR / "demo" / "venue.json"
    if real is not None and demo.exists():
        with tempfile.TemporaryDirectory() as td:
            rp = Path(td) / "roll.json"
            draw.write_roll(roll4, rp)
            log = []
            rc = run(rp, Path(td) / "site", out=log.append, starter=True, venue_path=demo)
            site = Path(td) / "site"
            ok(rc in (0, 1) and (site / "index.html").exists() and (site / "map.html").exists() and (site / "data" / "venue.js").exists()
               and (site / "assets" / "starter.js").exists() and any((site / "e").glob("*.html")), "the real starter.py builds a site from the demo venue (rc=%s)" % rc)
            ok("evk/tokens.css" in (site / "index.html").read_text(encoding="utf-8") and (site / "evk" / "engine" / "search.js").exists(), "…whose pages load the files install.py wrote")
    # name option and yaml quoting
    y = "\n".join(_yaml({"a": {"b": "#FFFFFF", "c": "x: y", "d": 3, "e": 0.5, "f": "plain"}}))
    ok('b: "#FFFFFF"' in y and 'c: "x: y"' in y and "d: 3" in y and "f: plain" in y, "yaml emitter quotes where needed: %r" % y)
    if fails:
        print("install.py selftest: %d FAILED" % len(fails))
        return 1
    print("install.py selftest: ok")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="install.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roll", nargs="?", help="roll.json with a chosen card")
    ap.add_argument("target", nargs="?", help="project directory")
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    ap.add_argument("--dry-run", action="store_true", help="list what would be written")
    ap.add_argument("--strict", action="store_true", help="a missing kit file is an error (nothing written)")
    ap.add_argument("--name", help="project name for DESIGN.md (default: the direction's name)")
    ap.add_argument("--card", type=int, help="install this card even if nothing was chosen (one-off)")
    ap.add_argument("--update", action="store_true", help="already installed, then `draw.py adjust`: rewrite only evk/tokens.css and .evk/roll.json "
                    "(DESIGN.md, base.css, recipe.css and the engine are left alone; the new DESIGN.md goes to .evk/DESIGN.generated.md). "
                    "In tokens.css exactly one thing is kept: every live (uncommented) `--prop-*: value;` line, verbatim, in place of that prop's "
                    "generated line; everything else is regenerated from the card, hand-edited token values included")
    ap.add_argument("--starter", action="store_true", help="also write a working site skeleton built from --venue: index.html, map.html, e/<id>.html, "
                    "data/venue.js, assets/starter.css, assets/starter.js (scripts/starter.py)")
    ap.add_argument("--venue", metavar="PATH", help="your venue.json (assets/engine/venue.schema.json); with --starter the pages are built from it")
    ap.add_argument("--selftest", action="store_true", help="run built-in tests")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if not a.roll or not a.target:
        ap.print_help()
        return 2
    if a.venue and not a.starter:
        print("install.py: note: --venue is only used with --starter (the pages are built from it)", file=sys.stderr)
    return run(a.roll, a.target, a.force, a.dry_run, a.strict, a.name, a.card, a.update, starter=a.starter, venue_path=a.venue)


if __name__ == "__main__":
    sys.exit(main())
