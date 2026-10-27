"""Điền sẵn nội dung Mục lục / Danh mục hình / Danh mục bảng (kèm số trang từ bản render),
giữ nguyên trường TOC để Word cập nhật lại khi mở."""
import re, sys, os, shutil, zipfile, subprocess

docx_in, pdf, docx_out = sys.argv[1:4]
md = open('thesis_pandoc.md', encoding='utf-8').read().split('\n')
body_start = next(i for i, l in enumerate(md) if l.startswith('# Chương 1'))
heads, figs, tabs = [], [], []
for i, l in enumerate(md[body_start:], body_start):
    m = re.match(r'^(#{1,3}) (.+)$', l)
    if m:
        heads.append((len(m.group(1)), m.group(2).strip()))
    m = re.match(r'^: (Bảng .+)$', l)
    if m: tabs.append(m.group(1).strip())
    m = re.match(r'^!\[(Hình [^\]]+)\]', l)
    if m: figs.append(m.group(1).strip())
    if l.strip() == '::: {custom-style="Image Caption"}':
        figs.append(md[i + 1].strip())
strip_md = lambda s: re.sub(r'[*`]', '', s)

# văn bản từng trang
n = int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', pdf], capture_output=True, text=True).stdout).group(1))
pages = []
for p in range(1, n + 1):
    t = subprocess.run(['pdftotext', '-f', str(p), '-l', str(p), '-layout', pdf, '-'], capture_output=True, text=True).stdout
    pages.append(re.sub(r'\s+', '', t).casefold())
norm = lambda s: re.sub(r'\s+', '', strip_md(s)).casefold()
first_body = next(k for k, t in enumerate(pages) if norm('Chương 1. Giới thiệu') in t and 'mụclục' not in t and k > 3)

def locate(items, key=lambda x: x):
    res, cur = [], first_body
    for it in items:
        target = norm(key(it))[:45]
        k = cur
        while k < n and target not in pages[k]:
            k += 1
        if k == n:
            print('NOT FOUND:', key(it)); res.append((it, ''))
        else:
            res.append((it, str(k - first_body + 1))); cur = k
    return res

H = locate(heads, key=lambda h: h[1])
F = locate(figs)
T = locate(tabs)

def esc(s): return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def entries(rows, instr):
    out = []
    for idx, (lvl, text, pg) in enumerate(rows):
        ppr = f'<w:pPr><w:pStyle w:val="TOC{lvl}"/></w:pPr>'
        begin = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                 f'<w:r><w:instrText xml:space="preserve"> {instr} </w:instrText></w:r>'
                 '<w:r><w:fldChar w:fldCharType="separate"/></w:r>') if idx == 0 else ''
        end = '<w:r><w:fldChar w:fldCharType="end"/></w:r>' if idx == len(rows) - 1 else ''
        out.append(f'<w:p>{ppr}{begin}<w:r><w:t xml:space="preserve">{esc(text)}</w:t></w:r>'
                   f'<w:r><w:tab/></w:r><w:r><w:t>{pg}</w:t></w:r>{end}</w:p>')
    return ''.join(out)

work = 'toc_tmp'
shutil.rmtree(work, ignore_errors=True)
with zipfile.ZipFile(docx_in) as z: z.extractall(work)
p = os.path.join(work, 'word', 'document.xml')
x = open(p, encoding='utf-8').read()

def swap(x, marker, xml):
    m = re.search(r'<w:p><w:pPr><w:pStyle w:val="TOC1"/></w:pPr>(?:(?!</w:p>).)*?' + marker + r'.*?</w:p>', x, re.S)
    assert m, marker
    return x[:m.start()] + xml + x[m.end():]

x = swap(x, 'cập nhật mục lục', entries([(l, strip_md(t), pg) for (l, t), pg in H], 'TOC \\o "1-3" \\h \\z \\u'))
x = swap(x, 'cập nhật danh mục hình', entries([(1, t, pg) for t, pg in F], 'TOC \\h \\z \\t "Image Caption,1"'))
x = swap(x, 'cập nhật danh mục bảng', entries([(1, t, pg) for t, pg in T], 'TOC \\h \\z \\t "Table Caption,1"'))
open(p, 'w', encoding='utf-8').write(x)
if os.path.exists(docx_out): os.remove(docx_out)
with zipfile.ZipFile(docx_out, 'w', zipfile.ZIP_DEFLATED) as z:
    z.write(os.path.join(work, '[Content_Types].xml'), '[Content_Types].xml')
    for root, _, files in os.walk(work):
        for f in files:
            full = os.path.join(root, f); arc = os.path.relpath(full, work)
            if arc != '[Content_Types].xml': z.write(full, arc)
print('toc ok', len(H), len(F), len(T), 'body starts at pdf page', first_body + 1)
