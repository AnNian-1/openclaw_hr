#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 360° 绩效反馈表 DOCX 模板（正式 HR 文书版）。

对齐 raw/_schema.md 字段契约，版面上不出现 JSON key / 入库映射。
"""
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.table import Table
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

OUT = Path(__file__).resolve().parent

DIMS = [
    ("目标达成", "本周期目标 / OKR 的完成度与产出质量"),
    ("专业能力", "专业深度、方案设计与问题解决能力"),
    ("协作沟通", "组内协作、跨组配合与信息同步"),
    ("责任心", "担当意识、靠谱程度与结果负责态度"),
    ("学习成长", "主动学习、经验沉淀与能力提升"),
]

TEMPLATE = {
    "filename": "360-feedback-form-blank.docx",
    "org": "公司人力资源部",
    "subtitle": "2026年版",
    "focus": "评估人代号填 领导1 / 同事1 / 下属1 / 自评；同视角多人用同事1、同事2。禁止填写真实姓名。评分请对照下方标准，评语请写清具体事例，评语中也不要出现评价人真名。",
}

# 配色：沉稳公文蓝灰
NAVY = RGBColor(0x1B, 0x2A, 0x4A)
MUTED = RGBColor(0x4A, 0x55, 0x68)
LIGHT = RGBColor(0x8A, 0x93, 0xA2)
HINT = RGBColor(0xA0, 0xA8, 0xB4)
WARN = RGBColor(0x8A, 0x4B, 0x08)
REQ = RGBColor(0xC4, 0x28, 0x1C)  # 必填星号红
RULE = "1B2A4A"
BORDER = "D8DEE6"
LABEL_BG = "F4F6F9"
BOX_BORDER = "7A8799"   # 下拉提示框边框（稍深，易辨认）
BOX_BG = "EEF2F7"       # 下拉提示框底色

# 字体层级（中文 Windows 常见字体，Word 打开效果稳定）
FONT_TITLE = "黑体"       # 文头大标题
FONT_SECTION = "黑体"     # 一级小节
FONT_BODY = "宋体"        # 正文、说明
FONT_UI = "微软雅黑"      # 表单标签、下拉控件

_CTRL_SEQ = 0


def set_run_font(run, size=10.5, bold=False, color=None, name=FONT_BODY):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    # 西文回落，避免混排时跳字
    run._element.rPr.rFonts.set(qn("w:ascii"), name if name != "黑体" else "Arial")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), name if name != "黑体" else "Arial")
    run.font.size = Pt(size)
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color


def shade_cell(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    for child in list(tcPr):
        if child.tag == qn("w:shd"):
            tcPr.remove(child)
    tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}" w:val="clear"/>'))


def set_cell_borders(cell, color=BORDER, sz="6"):
    tcPr = cell._tc.get_or_add_tcPr()
    for child in list(tcPr):
        if child.tag == qn("w:tcBorders"):
            tcPr.remove(child)
    tcPr.append(parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'  <w:top w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:left w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:bottom w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'  <w:right w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'</w:tcBorders>'
    ))


def set_cell_no_border(cell):
    tcPr = cell._tc.get_or_add_tcPr()
    for child in list(tcPr):
        if child.tag == qn("w:tcBorders"):
            tcPr.remove(child)
    tcPr.append(parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'  <w:top w:val="nil"/><w:left w:val="nil"/>'
        f'  <w:bottom w:val="nil"/><w:right w:val="nil"/>'
        f'</w:tcBorders>'
    ))


def para(doc, text="", *, size=10.5, bold=False, color=None, align=None,
         space_before=0, space_after=4, name=FONT_BODY, line_spacing=1.35):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line_spacing
    if text:
        run = p.add_run(text)
        set_run_font(run, size=size, bold=bold, color=color, name=name)
    return p


def add_runs(p, parts):
    for text, kwargs in parts:
        run = p.add_run(text)
        set_run_font(run, **kwargs)


def add_field_label(paragraph, label, *, required=True, size=10.5, color=NAVY, name=FONT_UI):
    """字段标签；必填项前加红色 *。"""
    if required:
        star = paragraph.add_run("*")
        set_run_font(star, size=size, bold=True, color=REQ, name=name)
    run = paragraph.add_run(label)
    set_run_font(run, size=size, bold=True, color=color, name=name)


def hrule(doc, weight="18"):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(10)
    pPr = p._p.get_or_add_pPr()
    pPr.append(parse_xml(
        f'<w:pBdr {nsdecls("w")}>'
        f'  <w:bottom w:val="single" w:sz="{weight}" w:space="1" w:color="{RULE}"/>'
        f'</w:pBdr>'
    ))


def set_cell_margins(cell, top=60, bottom=60, left=100, right=100):
    """单元格内边距（单位 dxa，20dxa ≈ 1pt）。"""
    tcPr = cell._tc.get_or_add_tcPr()
    for child in list(tcPr):
        if child.tag == qn("w:tcMar"):
            tcPr.remove(child)
    tcPr.append(parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'  <w:top w:w="{top}" w:type="dxa"/>'
        f'  <w:left w:w="{left}" w:type="dxa"/>'
        f'  <w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'  <w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    ))


def insert_nested_table(cell, *, width_dxa=3200):
    """在单元格内插入 1×1 嵌套表，用作下拉提示框。"""
    tbl = parse_xml(
        f'<w:tbl {nsdecls("w")}>'
        f'  <w:tblPr>'
        f'    <w:tblW w:w="{width_dxa}" w:type="dxa"/>'
        f'    <w:tblBorders>'
        f'      <w:top w:val="single" w:sz="12" w:space="0" w:color="{BOX_BORDER}"/>'
        f'      <w:left w:val="single" w:sz="12" w:space="0" w:color="{BOX_BORDER}"/>'
        f'      <w:bottom w:val="single" w:sz="12" w:space="0" w:color="{BOX_BORDER}"/>'
        f'      <w:right w:val="single" w:sz="12" w:space="0" w:color="{BOX_BORDER}"/>'
        f'      <w:insideH w:val="nil"/><w:insideV w:val="nil"/>'
        f'    </w:tblBorders>'
        f'  </w:tblPr>'
        f'  <w:tblGrid><w:gridCol w:w="{width_dxa}"/></w:tblGrid>'
        f'  <w:tr>'
        f'    <w:tc>'
        f'      <w:tcPr><w:tcW w:w="{width_dxa}" w:type="dxa"/></w:tcPr>'
        f'      <w:p/>'
        f'    </w:tc>'
        f'  </w:tr>'
        f'</w:tbl>'
    )
    cell._tc.append(tbl)
    return Table(tbl, cell)


def append_single_select_dropdown(paragraph, *, group: str, options, placeholder="请选择（单选）"):
    global _CTRL_SEQ
    _CTRL_SEQ += 1
    rid = 2000 + _CTRL_SEQ

    def esc(s):
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    display = f"{placeholder}  ▼"
    items = "".join(
        f'<w:listItem w:displayText="{esc(label)}" w:value="{esc(value)}"/>'
        for label, value in options
    )
    sdt = parse_xml(
        f'<w:sdt xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'  <w:sdtPr>'
        f'    <w:alias w:val="{esc(group)}"/>'
        f'    <w:tag w:val="{esc(group)}"/>'
        f'    <w:id w:val="{rid}"/>'
        f'    <w:placeholder><w:docPart w:val="DefaultPlaceholder_{rid}"/></w:placeholder>'
        f'    <w:dropDownList>'
        f'      <w:listItem w:displayText="{esc(display)}" w:value=""/>'
        f'      {items}'
        f'    </w:dropDownList>'
        f'  </w:sdtPr>'
        f'  <w:sdtContent>'
        f'    <w:r>'
        f'      <w:rPr>'
        f'        <w:rFonts w:ascii="{FONT_UI}" w:hAnsi="{FONT_UI}"'
        f'                  w:eastAsia="{FONT_UI}" w:cs="{FONT_UI}"/>'
        f'        <w:sz w:val="21"/>'
        f'        <w:szCs w:val="21"/>'
        f'        <w:color w:val="4A5568"/>'
        f'        <w:shd w:val="clear" w:fill="{BOX_BG}"/>'
        f'      </w:rPr>'
        f'      <w:t>{esc(display)}</w:t>'
        f'    </w:r>'
        f'  </w:sdtContent>'
        f'</w:sdt>'
    )
    paragraph._p.append(sdt)


def add_single_select_row(doc, *, title: str, group: str, options, hint: str = "", required=True):
    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    left = table.rows[0].cells[0]
    left.text = ""
    left.width = Cm(3.8)
    p = left.paragraphs[0]
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(8)
    add_field_label(p, title, required=required)
    shade_cell(left, LABEL_BG)
    set_cell_borders(left)

    right = table.rows[0].cells[1]
    right.text = ""
    right.width = Cm(13.2)
    set_cell_borders(right)
    shade_cell(right, "FFFFFF")
    set_cell_margins(right, top=80, bottom=60, left=100, right=100)

    # 外层段落：给提示框上下留白
    host = right.paragraphs[0]
    host.paragraph_format.space_before = Pt(4)
    host.paragraph_format.space_after = Pt(2)

    # 带边框的下拉提示框（嵌套表）
    box = insert_nested_table(right, width_dxa=3600)
    box_cell = box.rows[0].cells[0]
    shade_cell(box_cell, BOX_BG)
    set_cell_margins(box_cell, top=50, bottom=50, left=120, right=80)
    bp = box_cell.paragraphs[0]
    bp.paragraph_format.space_before = Pt(0)
    bp.paragraph_format.space_after = Pt(0)
    append_single_select_dropdown(bp, group=group, options=options)

    if hint:
        p2 = right.add_paragraph()
        p2.paragraph_format.space_before = Pt(4)
        p2.paragraph_format.space_after = Pt(4)
        run = p2.add_run(hint)
        set_run_font(run, size=9, color=HINT, name=FONT_BODY)

    return table


def write_label_value_row(table, row_idx, label, value_hint="", *, required=True):
    left, right = table.rows[row_idx].cells
    left.text = ""
    p = left.paragraphs[0]
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    add_field_label(p, label, required=required)
    shade_cell(left, LABEL_BG)
    set_cell_borders(left)

    right.text = ""
    p = right.paragraphs[0]
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    if value_hint:
        run = p.add_run(value_hint)
        set_run_font(run, size=10.5, color=HINT, name=FONT_BODY)
    set_cell_borders(right)
    left.width = Cm(3.8)
    right.width = Cm(13.2)


def write_label_dropdown_row(table, row_idx, label, *, group, options, hint="", required=True):
    """基本信息行：左侧标签 + 右侧下拉提示框。"""
    left, right = table.rows[row_idx].cells
    left.text = ""
    p = left.paragraphs[0]
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(8)
    add_field_label(p, label, required=required)
    shade_cell(left, LABEL_BG)
    set_cell_borders(left)
    left.width = Cm(3.8)

    right.text = ""
    right.width = Cm(13.2)
    set_cell_borders(right)
    shade_cell(right, "FFFFFF")
    set_cell_margins(right, top=80, bottom=60, left=100, right=100)

    host = right.paragraphs[0]
    host.paragraph_format.space_before = Pt(4)
    host.paragraph_format.space_after = Pt(2)

    box = insert_nested_table(right, width_dxa=3600)
    box_cell = box.rows[0].cells[0]
    shade_cell(box_cell, BOX_BG)
    set_cell_margins(box_cell, top=50, bottom=50, left=120, right=80)
    bp = box_cell.paragraphs[0]
    bp.paragraph_format.space_before = Pt(0)
    bp.paragraph_format.space_after = Pt(0)
    append_single_select_dropdown(bp, group=group, options=options)

    if hint:
        p2 = right.add_paragraph()
        p2.paragraph_format.space_before = Pt(2)
        p2.paragraph_format.space_after = Pt(4)
        run = p2.add_run(hint)
        set_run_font(run, size=9, color=HINT, name=FONT_BODY)


def add_cover(doc):
    para(doc, TEMPLATE["org"], size=11, color=MUTED, name=FONT_UI,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4, line_spacing=1.2)
    para(doc, "360° 绩效反馈表", size=22, bold=True, color=NAVY, name=FONT_TITLE,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_before=2, space_after=4, line_spacing=1.15)
    para(doc, TEMPLATE["subtitle"], size=12, color=MUTED, name=FONT_UI,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2, line_spacing=1.2)
    hrule(doc, weight="20")

    p = para(doc, "", size=10.5, space_after=4, line_spacing=1.4)
    add_runs(p, [
        ("填写说明：", {"size": 10.5, "bold": True, "color": NAVY, "name": FONT_UI}),
        (TEMPLATE["focus"], {"size": 10.5, "color": MUTED, "name": FONT_BODY}),
    ])
    p = para(doc, "", size=10, space_after=4, line_spacing=1.4)
    add_runs(p, [
        ("*", {"size": 10, "bold": True, "color": REQ, "name": FONT_UI}),
        (" 为必填项。", {"size": 10, "color": MUTED, "name": FONT_BODY}),
    ])
    p = para(doc, "", size=10, space_after=10, line_spacing=1.4)
    add_runs(p, [
        ("评分参考：", {"size": 10, "bold": True, "color": NAVY, "name": FONT_UI}),
        ("5-远超预期　4-超出预期　3-符合预期　2-部分未达　1-明显未达。"
         "考核周期、关系与评分请用下拉框单选（同一行只能选一项）。"
         "评语请写具体事例，勿写综合绩效等级。",
         {"size": 10, "color": MUTED, "name": FONT_BODY}),
    ])


def add_section_title(doc, text):
    para(doc, text, size=13, bold=True, color=NAVY, name=FONT_SECTION,
         space_before=6, space_after=8, line_spacing=1.2)


def add_basic_info(doc):
    add_section_title(doc, "一、基本信息")

    table = doc.add_table(rows=4, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    write_label_value_row(table, 0, "被评估人", "员工1 / 员工2（禁止真实姓名）")
    write_label_value_row(table, 1, "所在岗位")
    write_label_dropdown_row(
        table, 2, "考核周期",
        group="period",
        options=[
            ("2026H1", "2026H1"),
            ("2026H2", "2026H2"),
            ("2026H3", "2026H3"),
            ("2026H4", "2026H4"),
        ],
        hint="季度评价：H1:一季度　H2:二季度　H3:三季度　H4:四季度",
    )
    write_label_value_row(
        table, 3, "评估人代号",
        "领导1 / 同事1 / 下属1 / 自评（同视角多人用同事1、同事2）",
    )

    para(doc, "", space_before=10, space_after=2)
    add_single_select_row(
        doc,
        title="与被评估人关系",
        group="relation",
        options=[
            ("上级", "manager"),
            ("平级同事", "peer"),
            ("下属", "report"),
            ("本人自评", "self"),
        ],
        hint="选项：上级　/　平级同事　/　下属　/　本人自评",
    )
    para(doc, "", space_after=6)


def add_dimension_block(doc, idx, name, tip):
    p = para(doc, "", size=12, space_before=12, space_after=4, line_spacing=1.25)
    add_runs(p, [
        (f"{idx}. {name}", {"size": 12, "bold": True, "color": NAVY, "name": FONT_SECTION}),
        (f"　　{tip}", {"size": 9.5, "color": LIGHT, "name": FONT_BODY}),
    ])

    dim_keys = [
        "goal_achievement",
        "professional_skill",
        "collaboration",
        "responsibility",
        "growth",
    ]
    add_single_select_row(
        doc,
        title="评分",
        group=f"score_{dim_keys[idx - 1]}",
        options=[
            ("5-远超预期", "5"),
            ("4-超出预期", "4"),
            ("3-符合预期", "3"),
            ("2-部分未达", "2"),
            ("1-明显未达", "1"),
        ],
        hint="选项：5-远超预期　/　4-超出预期　/　3-符合预期　/　2-部分未达　/　1-明显未达",
    )

    p = para(doc, "", size=9.5, space_before=6, space_after=3, line_spacing=1.2)
    add_field_label(p, "事实与观察", required=True, size=9.5, color=LIGHT, name=FONT_UI)
    box = doc.add_table(rows=1, cols=1)
    box.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = box.rows[0].cells[0]
    cell.text = ""
    for i in range(4):
        p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.45
        if i == 0:
            run = p.add_run("（请写具体事例，约 50～150 字）")
            set_run_font(run, size=9.5, color=HINT, name=FONT_BODY)
    shade_cell(cell, "FAFBFC")
    set_cell_borders(cell, color="C9D1DC", sz="6")
    box.rows[0].height = Cm(2.8)
    box.rows[0].height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    cell.width = Cm(17.0)


def add_closing(doc):
    add_section_title(doc, "三、总体印象")

    for title, hint, fill in [
        ("主要亮点", "本周期最值得肯定的地方（可跨维度概括）", "F3F7F4"),
        ("改进建议", "希望对方下周期关注或调整的方向（发展性表述即可）", "FFF8F1"),
    ]:
        p = para(doc, "", size=10.5, space_before=6, space_after=3, line_spacing=1.2)
        add_field_label(p, title, required=True, size=10.5, color=NAVY, name=FONT_UI)
        box = doc.add_table(rows=1, cols=1)
        cell = box.rows[0].cells[0]
        cell.text = ""
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.45
        run = p.add_run(f"（{hint}）")
        set_run_font(run, size=9.5, color=HINT, name=FONT_BODY)
        for _ in range(3):
            cell.add_paragraph()
        shade_cell(cell, fill)
        set_cell_borders(cell, color="C9D1DC", sz="6")
        box.rows[0].height = Cm(2.2)
        box.rows[0].height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST

    para(doc, "", space_before=14, space_after=2)
    table = doc.add_table(rows=1, cols=2)
    set_cell_no_border(table.rows[0].cells[0])
    set_cell_no_border(table.rows[0].cells[1])
    left, right = table.rows[0].cells
    left.text = ""
    p = left.paragraphs[0]
    add_field_label(p, "评估人签名：", required=True, size=10.5, color=MUTED, name=FONT_BODY)
    right.text = ""
    p = right.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    add_field_label(p, "提交日期：", required=True, size=10.5, color=MUTED, name=FONT_BODY)
    run = p.add_run("　　年　　月　　日")
    set_run_font(run, size=10.5, color=HINT, name=FONT_BODY)

    para(doc, "", space_before=18, space_after=2)
    hrule(doc, weight="12")
    para(
        doc,
        "本表仅作为绩效面谈与校准会的输入材料，请勿填写综合绩效等级（如 S/A/B/C/D）。"
        "最终评级由直接主管初评、隔级主管复核、部门校准会确认。",
        size=8.5, color=WARN, name=FONT_BODY, space_after=4, line_spacing=1.35,
    )
    para(
        doc,
        f"{TEMPLATE['org']}　·　内部使用",
        size=8.5, color=LIGHT, name=FONT_UI,
        align=WD_ALIGN_PARAGRAPH.CENTER, space_after=0, line_spacing=1.2,
    )


def build():
    global _CTRL_SEQ
    _CTRL_SEQ = 0

    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(2.2)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.2)
        section.right_margin = Cm(2.2)
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)

    style = doc.styles["Normal"]
    style.font.name = FONT_BODY
    style.font.size = Pt(10.5)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_BODY)
    style._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    style._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")

    add_cover(doc)
    add_basic_info(doc)

    add_section_title(doc, "二、分项评价")
    para(
        doc,
        "请对下列五个方面分别用下拉框选择一个分数（单选），并写下您的观察。五个方面请都填写。",
        size=10.5, color=MUTED, name=FONT_BODY, space_after=6, line_spacing=1.4,
    )
    for i, (name, tip) in enumerate(DIMS, start=1):
        add_dimension_block(doc, i, name, tip)

    add_closing(doc)

    path = OUT / TEMPLATE["filename"]
    doc.save(str(path))
    print("wrote", path.name)


def main():
    build()
    print(f"done → {OUT / TEMPLATE['filename']}")


if __name__ == "__main__":
    main()
