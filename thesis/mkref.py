import docx
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

d = docx.Document('ref0.docx')
S0 = d.styles
class _S:
    def __getitem__(self,k):
        for st in S0:
            if st.name==k: return st
        raise KeyError(k)
    def add_style(self,*a): return S0.add_style(*a)
S=_S()
TNR = 'Times New Roman'
BLACK = RGBColor(0, 0, 0)

def font(st, size=13, bold=None, italic=None, color=BLACK):
    f = st.font
    f.name = TNR; f.size = Pt(size); f.color.rgb = color
    if bold is not None: f.bold = bold
    if italic is not None: f.italic = italic
    rpr = st.element.get_or_add_rPr()
    rf = rpr.find(qn('w:rFonts'))
    if rf is None:
        rf = OxmlElement('w:rFonts'); rpr.insert(0, rf)
    for a in ('w:ascii', 'w:hAnsi', 'w:cs', 'w:eastAsia'):
        rf.set(qn(a), TNR)
    for a in ('w:asciiTheme', 'w:hAnsiTheme', 'w:cstheme', 'w:eastAsiaTheme'):
        if rf.get(qn(a)) is not None: del rf.attrib[qn(a)]

def para(st, align=None, before=0, after=6, line=1.5, first=None, left=None, hanging=None, keep_next=None, page_before=None):
    pf = st.paragraph_format
    if align is not None: pf.alignment = align
    pf.space_before = Pt(before); pf.space_after = Pt(after)
    pf.line_spacing = line
    if first is not None: pf.first_line_indent = first
    if left is not None: pf.left_indent = left
    if hanging is not None:
        pf.left_indent = hanging; pf.first_line_indent = -hanging
    if keep_next is not None: pf.keep_with_next = keep_next
    if page_before is not None: pf.page_break_before = page_before

def get(name, base='Normal', typ=WD_STYLE_TYPE.PARAGRAPH):
    try:
        return S[name]
    except KeyError:
        st = S.add_style(name, typ)
        st.base_style = S[base]
        st.quick_style = True
        return st

J = WD_ALIGN_PARAGRAPH.JUSTIFY; C = WD_ALIGN_PARAGRAPH.CENTER; R = WD_ALIGN_PARAGRAPH.RIGHT; L = WD_ALIGN_PARAGRAPH.LEFT

for n in ('Normal', 'Body Text', 'First Paragraph'):
    font(S[n]); para(S[n], J, 0, 6, 1.5)
font(S['Compact'], 12); para(S['Compact'], L, 1, 1, 1.0)
st = get('Compact Small', 'Compact'); font(st, 10); para(st, L, 0, 0, 1.0)
font(S['Block Text'], 13, italic=True); para(S['Block Text'], J, 3, 6, 1.5, left=Cm(1))
S['Block Text'].paragraph_format.right_indent = Cm(1)

# Đề mục
font(S['Heading 1'], 14, True); para(S['Heading 1'], C, 0, 18, 1.5, keep_next=True, page_before=True)
S['Heading 1'].font.all_caps = True
font(S['Heading 2'], 13, True); para(S['Heading 2'], L, 12, 6, 1.5, keep_next=True)
font(S['Heading 3'], 13, True, True); para(S['Heading 3'], L, 6, 6, 1.5, keep_next=True)
for h in ('Heading 4', 'Heading 5'):
    font(S[h], 13, False, True); para(S[h], L, 6, 3, 1.5, keep_next=True)

# Chú thích
font(S['Table Caption'], 13, True, False); para(S['Table Caption'], C, 6, 4, 1.5, keep_next=True)
font(S['Image Caption'], 13, True, False); para(S['Image Caption'], C, 4, 2, 1.5)
font(S['Caption'], 13, True, False)
for n in ('Figure', 'Captioned Figure'):
    para(S[n], C, 6, 0, 1.0, keep_next=True)

# Kiểu riêng
st = get('Front Heading'); font(st, 14, True); para(st, C, 0, 18, 1.5, keep_next=True)
st = get('Sub Heading'); font(st, 13, True); para(st, L, 12, 6, 1.5, keep_next=True)
st = get('Signature'); font(st, 13, italic=False); para(st, C, 0, 0, 1.5, left=Cm(8))
st = get('Source Note'); font(st, 13, italic=True); para(st, C, 0, 10, 1.5)
st = get('Reference Entry'); font(st, 13); para(st, J, 0, 6, 1.5, hanging=Cm(1))
st = get('Image Placeholder'); font(st, 12, italic=True, color=RGBColor(0x59, 0x59, 0x59)); para(st, C, 12, 2, 1.15, keep_next=True)
ppr = st.element.get_or_add_pPr()
bdr = OxmlElement('w:pBdr')
for side in ('top', 'left', 'bottom', 'right'):
    e = OxmlElement(f'w:{side}'); e.set(qn('w:val'), 'dashed'); e.set(qn('w:sz'), '6'); e.set(qn('w:space'), '24'); e.set(qn('w:color'), '7F7F7F'); bdr.append(e)
sp_=ppr.find(qn('w:spacing'))
sp_.addprevious(bdr) if sp_ is not None else ppr.append(bdr)
st = get('Cover Text'); font(st, 13); para(st, C, 0, 0, 1.15)
st.element.set(qn('w:styleId'), 'CoverText')

# Mục lục
for k in range(1, 4):
    st = get(f'TOC {k}')
    font(st, 13, bold=(k == 1))
    para(st, L, 3 if k == 1 else 0, 3, 1.5, left=Cm(0.6 * (k - 1)))
    st.paragraph_format.tab_stops.add_tab_stop(Cm(15.9), alignment=2, leader=1)  # right, dots

font(S['Verbatim Char'], 13)
font(S['Hyperlink'], 13)
S['Hyperlink'].font.underline = False

# Trang và lề
sec = d.sections[0]
sec.page_width = Cm(21.0); sec.page_height = Cm(29.7)
sec.top_margin = Cm(3); sec.bottom_margin = Cm(3); sec.left_margin = Cm(3); sec.right_margin = Cm(2)
sec.header_distance = Cm(1.25); sec.footer_distance = Cm(1.25)
ft = sec.footer; ft.is_linked_to_previous = False
p = ft.paragraphs[0]; p.alignment = R
p.style = S['Normal']
p.paragraph_format.line_spacing = 1.0; p.paragraph_format.space_after = Pt(0)
r = p.add_run()
for typ, txt in (('begin', None), (None, ' PAGE '), ('separate', None), (None, '1'), ('end', None)):
    if typ:
        e = OxmlElement('w:fldChar'); e.set(qn('w:fldCharType'), typ); r._r.append(e)
    elif txt.strip() == 'PAGE':
        e = OxmlElement('w:instrText'); e.set(qn('xml:space'), 'preserve'); e.text = txt; r._r.append(e)
    else:
        e = OxmlElement('w:t'); e.text = txt; r._r.append(e)
r.font.name = TNR; r.font.size = Pt(13)

# Kiểu bảng "Table": viền đơn, chữ 11
tbl = S['Table']
tpr = tbl.element.find(qn('w:tblPr'))
if tpr is None:
    tpr = OxmlElement('w:tblPr'); tbl.element.append(tpr)
for old in tpr.findall(qn('w:tblBorders')): tpr.remove(old)
b = OxmlElement('w:tblBorders')
for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
    e = OxmlElement(f'w:{side}'); e.set(qn('w:val'), 'single'); e.set(qn('w:sz'), '4'); e.set(qn('w:space'), '0'); e.set(qn('w:color'), '000000'); b.append(e)
lk=tpr.find(qn('w:tblCellMar'))
if lk is None: lk=tpr.find(qn('w:tblLook'))
lk.addprevious(b) if lk is not None else tpr.append(b)
font(tbl, 12)
d.save('reference.docx')
print('ref ok')
