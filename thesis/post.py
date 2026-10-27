import re, sys, os, shutil, zipfile

src, dst = sys.argv[1], sys.argv[2]
work = 'post_tmp'
shutil.rmtree(work, ignore_errors=True)
with zipfile.ZipFile(src) as z:
    z.extractall(work)
p = os.path.join(work, 'word', 'document.xml')
x = open(p, encoding='utf-8').read()

final = re.search(r'<w:sectPr>(.*?)</w:sectPr></w:body>', x, re.S)
inner = final.group(1)
footer = re.search(r'<w:footerReference[^>]*/>', inner).group(0)
pgsz = re.search(r'<w:pgSz[^>]*/>', inner).group(0)
pgmar = re.search(r'<w:pgMar[^>]*/>', inner).group(0)

border = ('<w:pgBorders w:offsetFrom="page">' + ''.join(
    f'<w:{s} w:val="thinThickSmallGap" w:sz="24" w:space="24" w:color="1F3864"/>' for s in ('top', 'left', 'bottom', 'right')) + '</w:pgBorders>')
sect_cover = f'<w:p><w:pPr><w:sectPr>{pgsz}{pgmar}{border}<w:pgNumType w:start="1"/></w:sectPr></w:pPr></w:p>'
sect_front = f'<w:p><w:pPr><w:sectPr>{footer}{pgsz}{pgmar}<w:pgNumType w:fmt="lowerRoman" w:start="1"/></w:sectPr></w:pPr></w:p>'

def repl_marker(x, marker, new):
    m = re.search(r'<w:p>(?:(?!<w:p>).)*?' + marker + r'.*?</w:p>', x, re.S)
    assert m, marker
    return x[:m.start()] + new + x[m.end():]

x = repl_marker(x, 'SECTBREAK_COVER', sect_cover)
x = repl_marker(x, 'SECTBREAK_FRONT', sect_front)
# Thân bài: số trang Ả Rập từ 1
x = x.replace(final.group(0), f'<w:sectPr>{footer}{pgsz}{pgmar}<w:pgNumType w:fmt="decimal" w:start="1"/></w:sectPr></w:body>')

# Bảng: căn giữa, hàng tiêu đề in đậm + lặp lại khi sang trang
x = re.sub(r'(<w:tblW [^>]*/>)(<w:tblLook [^>]*/>)<w:jc w:val="start" />', r'\1<w:jc w:val="center" />\2', x)
x = re.sub(r'<w:pgMar ((?:(?!gutter)[^>])*?)\s*/>', r'<w:pgMar \1 w:gutter="0"/>', x)
def bold_header(m):
    row = m.group(0)
    row = row.replace('<w:r><w:t', '<w:r><w:rPr><w:b /></w:rPr><w:t')
    row = re.sub(r'<w:r><w:rPr>(?!<w:b)', '<w:r><w:rPr><w:b />', row)
    row = row.replace('<w:jc w:val="left" />', '<w:jc w:val="center" />')
    return row
x = re.sub(r'<w:tr><w:trPr><w:tblHeader w:val="true" /></w:trPr>.*?</w:tr>', bold_header, x, flags=re.S)
# bảng nhiều cột: chữ 9,5
def small(m):
    t = m.group(0)
    if t.count('<w:gridCol ') >= 8:
        t = t.replace('<w:pStyle w:val="Compact" />', '<w:pStyle w:val="CompactSmall" />')
        t = t.replace('<w:tblLook ', '<w:tblCellMar><w:left w:w="45" w:type="dxa"/><w:right w:w="45" w:type="dxa"/></w:tblCellMar><w:tblLook ', 1)
    return t
x = re.sub(r'<w:tbl>.*?</w:tbl>', small, x, flags=re.S)
# khoảng cách sau bảng
x = re.sub(r'</w:tbl>((?:<w:bookmark(?:Start|End)[^>]*/>)*)<w:p><w:pPr>(<w:pStyle [^>]*/>)', r'</w:tbl>\1<w:p><w:pPr>\2<w:spacing w:before="200"/>', x)
# ô bảng không bị ngắt giữa trang
x = x.replace('<w:tr><w:tc>', '<w:tr><w:trPr><w:cantSplit/></w:trPr><w:tc>')

open(p, 'w', encoding='utf-8').write(x)
cp = os.path.join(work, '[Content_Types].xml')
c = open(cp, encoding='utf-8').read()
if 'Extension="png"' not in c:
    c = c.replace('<Default ', '<Default Extension="png" ContentType="image/png"/><Default ', 1)
open(cp, 'w', encoding='utf-8').write(c)

stp = os.path.join(work, 'word', 'styles.xml')
st = open(stp, encoding='utf-8').read()
st = st.replace('/>&gt;\n    </w:rPr>', '/></w:rPr>')
def fixq(m):
    b = m.group(0)
    if '<w:qFormat />' in b and b.find('<w:qFormat />') > b.find('<w:pPr>') > 0:
        b = b.replace('<w:qFormat />', '')
        b = b.replace('<w:pPr>', '<w:qFormat /><w:pPr>', 1)
    return b
st = re.sub(r'<w:style .*?</w:style>', fixq, st, flags=re.S)
# Mặc định toàn văn bản: Times New Roman 13 (quy chuẩn UEH), bỏ font theo theme
st = re.sub(r'<w:rFonts [^>]*Theme[^>]*/>', '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman" w:eastAsia="Times New Roman" />', st)
st = st.replace('<w:sz w:val="24" /><w:szCs w:val="24" /><w:lang', '<w:sz w:val="26" /><w:szCs w:val="26" /><w:lang', 1)
thp = os.path.join(work, 'word', 'theme', 'theme1.xml')
if os.path.exists(thp):
    th = open(thp, encoding='utf-8').read()
    th = re.sub(r'<a:latin typeface="[^"]*"', '<a:latin typeface="Times New Roman"', th)
    open(thp, 'w', encoding='utf-8').write(th)
open(stp, 'w', encoding='utf-8').write(st)

sp = os.path.join(work, 'word', 'settings.xml')
s = open(sp, encoding='utf-8').read()
if 'updateFields' not in s:
    m = re.search(r'<w:(hdrShapeDefaults|footnotePr|endnotePr|compat|docVars|rsids)\b', s)
    s = s[:m.start()] + '<w:updateFields w:val="true"/>' + s[m.start():]
open(sp, 'w', encoding='utf-8').write(s)

if os.path.exists(dst): os.remove(dst)
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk(work):
        for f in files:
            full = os.path.join(root, f)
            arc = os.path.relpath(full, work)
            z.write(full, arc)
print('post ok')
