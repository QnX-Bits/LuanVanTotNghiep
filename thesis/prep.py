"""full.md (Docs export) -> thesis_pandoc.md theo quy chuẩn trình bày UEH."""
import re, unicodedata

src = open('full.md', encoding='utf-8').read().split('\n')
# body = từ Chương 1 trở đi
start = next(i for i, l in enumerate(src) if l.startswith('# Chương 1'))
front = src[:start]
body = src[start:]

def section(lines, title):
    i = next(k for k, l in enumerate(lines) if l.strip() == '## ' + title)
    j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith('## ') or lines[k].startswith('# ')), len(lines))
    return [l for l in lines[i + 1:j]]

camdoan = section(front, 'Lời cam đoan')
tomtat = section(front, 'Tóm tắt')
abstract = section(front, 'Abstract')
viettat = section(front, 'Danh mục từ viết tắt')

def raw(xml):
    return ['', '```{=openxml}', xml, '```', '']

def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def cpara(text, size=26, bold=False, caps=False, before=0, after=0, align='center', italic=False):
    rpr = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'
    if bold: rpr += '<w:b/>'
    if italic: rpr += '<w:i/>'
    if caps: rpr += '<w:caps/>'
    rpr += f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    return (f'<w:p><w:pPr><w:pStyle w:val="CoverText"/><w:spacing w:before="{before}" w:after="{after}" w:line="276" w:lineRule="auto"/>'
            f'<w:jc w:val="{align}"/></w:pPr><w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{esc(text)}</w:t></w:r></w:p>')

def pagebreak():
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'

TITLE = 'TỐI ƯU HÓA DANH MỤC ĐA TÀI SẢN CHO NHÀ ĐẦU TƯ VIỆT NAM: SO SÁNH CÁC PHƯƠNG PHÁP PHÂN BỔ TRUYỀN THỐNG VÀ HỌC MÁY'

def cover(inner):
    x = []
    x.append(cpara('BỘ GIÁO DỤC VÀ ĐÀO TẠO', 26, True))
    x.append(cpara('ĐẠI HỌC KINH TẾ THÀNH PHỐ HỒ CHÍ MINH', 26, True))
    x.append(cpara('[TÊN TRƯỜNG THÀNH VIÊN / KHOA]', 26, True))
    x.append(cpara('──────── ✦ ────────', 26, before=60))
    x.append(cpara('[LOGO UEH]', 22, italic=True, before=600, after=600))
    if inner:
        x.append(cpara('[HỌ VÀ TÊN SINH VIÊN]', 28, True, after=600))
    x.append(cpara('KHÓA LUẬN TỐT NGHIỆP', 36, True, before=300 if inner else 600, after=400))
    x.append(cpara(TITLE, 32, True, after=600))
    x.append(cpara('Chuyên ngành: Khoa học dữ liệu', 26, before=200))
    if inner:
        rows = [('Giảng viên hướng dẫn', 'TS. Nguyễn Đăng Cao'), ('Sinh viên thực hiện', '[Họ và tên]'),
                ('Mã số sinh viên', '31231026504'), ('Lớp', '[Mã lớp]'), ('Khóa', '[Khóa]')]
        for k, v in rows:
            x.append(f'<w:p><w:pPr><w:pStyle w:val="CoverText"/><w:tabs><w:tab w:val="left" w:pos="5600"/></w:tabs>'
                     f'<w:spacing w:before="0" w:after="60" w:line="276" w:lineRule="auto"/><w:ind w:left="2600"/><w:jc w:val="left"/></w:pPr>'
                     f'<w:r><w:rPr><w:sz w:val="26"/></w:rPr><w:t xml:space="preserve">{esc(k)}:</w:t></w:r>'
                     f'<w:r><w:rPr><w:sz w:val="26"/></w:rPr><w:tab/></w:r>'
                     f'<w:r><w:rPr><w:b/><w:sz w:val="26"/></w:rPr><w:t xml:space="preserve">{esc(v)}</w:t></w:r></w:p>')
        x.append(cpara('TP. Hồ Chí Minh, tháng 11 năm 2026', 26, before=1000))
    else:
        x.append(cpara('[HỌ VÀ TÊN SINH VIÊN]', 28, True, before=1400))
        x.append(cpara('TP. Hồ Chí Minh – Năm 2026', 26, before=1400))
    return ''.join(x)

def ftitle(t):
    """Tiêu đề trang phần đầu (không vào mục lục)."""
    return ['', '::: {custom-style="Front Heading"}', t, ':::', '']

def field_toc(instr, placeholder):
    return ('<w:p><w:pPr><w:pStyle w:val="TOC1"/></w:pPr><w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>'
            f'<w:r><w:instrText xml:space="preserve"> {instr} </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            f'<w:r><w:t>{esc(placeholder)}</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>')

out = []
out += raw(cover(False) + pagebreak() + cover(True))
out += ['', 'SECTBREAK_COVER', '']

out += ftitle('LỜI CÁM ƠN')
out += ['',
 'Để hoàn thành khóa luận này, tôi xin gửi lời cám ơn chân thành đến TS. Nguyễn Đăng Cao, người đã tận tình hướng dẫn, góp ý và định hướng cho tôi trong suốt quá trình thực hiện đề tài, từ việc xác định câu hỏi nghiên cứu, thiết kế phương pháp đến cách trình bày kết quả.',
 '',
 'Tôi xin cám ơn quý Thầy Cô của Đại học Kinh tế Thành phố Hồ Chí Minh đã truyền đạt kiến thức về tài chính, thống kê và khoa học dữ liệu trong những năm học vừa qua, là nền tảng để tôi thực hiện nghiên cứu này.',
 '',
 'Tôi cũng xin cám ơn gia đình và bạn bè đã luôn động viên, hỗ trợ tôi trong thời gian học tập và làm khóa luận.',
 '',
 'Do giới hạn về thời gian, dữ liệu và kinh nghiệm, khóa luận không tránh khỏi thiếu sót. Tôi rất mong nhận được ý kiến đóng góp của quý Thầy Cô để hoàn thiện đề tài.',
 '',
 '::: {custom-style="Signature"}', 'TP. Hồ Chí Minh, ngày … tháng … năm 2026', ':::', '',
 '::: {custom-style="Signature"}', 'Sinh viên thực hiện', ':::', '',
 '::: {custom-style="Signature"}', '[Họ và tên]', ':::', '']
out += raw(pagebreak())

out += ftitle('LỜI CAM ĐOAN')
cd = [l for l in camdoan if l.strip()]
out += ['', cd[0], '']
out += ['::: {custom-style="Signature"}', 'TP. Hồ Chí Minh, ngày … tháng … năm 2026', ':::', '',
        '::: {custom-style="Signature"}', 'Sinh viên ký tên', ':::', '',
        '::: {custom-style="Signature"}', '[Họ và tên]', ':::', '']
out += raw(pagebreak())

out += ftitle('TÓM TẮT')
out += tomtat
out += raw(pagebreak())
out += ftitle('ABSTRACT')
out += abstract
out += raw(pagebreak())

out += ftitle('MỤC LỤC')
out += raw(field_toc('TOC \\o "1-3" \\h \\z \\u', 'Nhấn chuột phải → Update Field (hoặc F9) để cập nhật mục lục.'))
out += raw(pagebreak())

out += ftitle('DANH MỤC CÁC CHỮ VIẾT TẮT VÀ KÝ HIỆU')
out += ['', '::: {custom-style="Sub Heading"}', 'Chữ viết tắt', ':::', '']
out += [l for l in viettat if l.strip()] + ['']
out += ['::: {custom-style="Sub Heading"}', 'Ký hiệu', ':::', '',
 '| Ký hiệu | Ý nghĩa |', '| --- | ---------------- |',
 '| N | Số lớp tài sản trong danh mục |',
 '| w | Véc-tơ tỷ trọng danh mục |',
 '| μ | Véc-tơ lợi nhuận kỳ vọng |',
 '| Σ | Ma trận hiệp phương sai lợi nhuận |',
 '| δ | Hệ số ngại rủi ro |',
 '| π | Lợi nhuận cân bằng ngụ ý trong mô hình Black–Litterman |',
 '| τ | Hệ số vô hướng đo độ không chắc chắn của tiên nghiệm |',
 '| P, Q, Ω | Ma trận chọn tài sản, véc-tơ quan điểm và ma trận độ không chắc chắn của quan điểm |',
 '| ρ | Hệ số tương quan hoặc hệ số tự tương quan bậc một |',
 '| σ_p | Độ lệch chuẩn của lợi nhuận danh mục |',
 '| RC_i | Đóng góp rủi ro của tài sản i |',
 '| SR, ΔSR | Hệ số Sharpe và chênh lệch Sharpe giữa hai danh mục |',
 '| α | Mức ý nghĩa của kiểm định |', '']
out += raw(pagebreak())

out += ftitle('DANH MỤC CÁC SƠ ĐỒ, ĐỒ THỊ')
out += raw(field_toc('TOC \\h \\z \\t "Image Caption,1"', 'Nhấn chuột phải → Update Field (hoặc F9) để cập nhật danh mục hình.'))
out += raw(pagebreak())
out += ftitle('DANH MỤC CÁC BẢNG BIỂU')
out += raw(field_toc('TOC \\h \\z \\t "Table Caption,1"', 'Nhấn chuột phải → Update Field (hoặc F9) để cập nhật danh mục bảng.'))
out += ['', 'SECTBREAK_FRONT', '']

# ---------- thân bài ----------
IMG = {'9c25dc8e-236f': 'img/h41.png', '643e2b62-8c46': 'img/h42.png', '29e0ff93-1649': 'img/h43.png', '5fef881a-9633': 'img/h51.png'}

def table_widths(rows):
    """Đặt số dấu gạch theo độ dài nội dung để pandoc chia độ rộng cột hợp lý."""
    cells = [[c.strip() for c in r.strip().strip('|').split('|')] for r in rows]
    hdr, data = cells[0], cells[2:]
    n = len(hdr)
    lens = []
    for j in range(n):
        col = [r[j] if j < len(r) else '' for r in [hdr] + data]
        tok = max((len(t) for c in col for t in re.sub(r'[*`]', '', c).split()), default=2)
        vals = [len(re.sub(r'[*`]', '', c)) for c in col]
        m = max(vals); avg = sum(vals) / len(vals)
        cap = 22 if n >= 8 else 40
        lens.append(max(tok + (4 if n >= 8 else 5), min(m + 1, int(0.5 * m + 0.5 * avg) + 2, cap), 7))
    sep = '| ' + ' | '.join('-' * l for l in lens) + ' |'
    # đảm bảo pandoc dùng độ rộng tương đối: dòng phải dài hơn --columns
    return [rows[0], sep] + rows[2:]

res = []
i = 0
chap = 0
last_h2 = None
pending_fig = None
while i < len(body):
    l = body[i]
    m = re.match(r'^# Chương (\d+)', l)
    if m:
        chap = int(m.group(1)); last_h2 = 0
    m2 = re.match(r'^## (\d+)\.(\d+) ', l)
    if m2:
        last_h2 = int(m2.group(2))
    if l.startswith('## Tóm tắt Chương'):
        last_h2 += 1
        res.append(f'## {chap}.{last_h2} Tóm tắt chương')
        i += 1; continue
    if l.startswith('```latex'):
        j = i + 1; eq = []
        while not body[j].startswith('```'):
            eq.append(body[j]); j += 1
        res += ['', '$$' + ' '.join(eq).strip() + '$$', '']
        i = j + 1; continue
    # chú thích hình: dòng *Hình x.y ...* ngay trước EMBED -> chuyển xuống dưới ảnh
    mh = re.match(r'^\*(Hình \d+\.\d+\..*)\*$', l.strip())
    if mh:
        k = i + 1
        while k < len(body) and not body[k].strip(): k += 1
        if k < len(body) and body[k].startswith('[IMG '):
            path = body[k][5:].strip(' ]')
            src_note = 'Nguồn: Tác giả thiết kế.' if any(x in path for x in ('framework', 'walkforward', 'h5_flow')) else 'Nguồn: Tác giả tính toán từ dữ liệu nghiên cứu.'
            res += ['', f'![{mh.group(1)}]({path}){{width=16cm}}', '',
                    '::: {custom-style="Source Note"}', src_note, ':::', '']
            i = k + 1; continue
        if k < len(body) and body[k].startswith('[EMBED'):
            ref = re.search(r'node/([\w-]+)', body[k]).group(1)
            res += ['', f'![{mh.group(1)}]({IMG[ref]}){{width=16cm}}', '',
                    '::: {custom-style="Source Note"}', 'Nguồn: Tác giả tính toán từ dữ liệu nghiên cứu.' if ref != '5fef881a-9633' else 'Nguồn: Tác giả thiết kế.', ':::', '']
            i = k + 1; continue
    # chú thích bảng
    mb = re.match(r'^\*(Bảng [A-Z0-9]+\.\d+\..*)\*$', l.strip())
    if mb:
        k = i + 1
        while k < len(body) and not body[k].strip(): k += 1
        if k < len(body) and body[k].startswith('|'):
            j = k; rows = []
            while j < len(body) and body[j].startswith('|'):
                rows.append(body[j]); j += 1
            res += ['', ': ' + mb.group(1), ''] + table_widths(rows) + ['']
            i = j; continue
    if l.startswith('|') and i + 1 < len(body) and body[i + 1].startswith('| ---'):
        j = i; rows = []
        while j < len(body) and body[j].startswith('|'):
            rows.append(body[j]); j += 1
        res += [''] + table_widths(rows) + ['']
        i = j; continue
    # ô chèn ảnh chụp màn hình
    mc = re.match(r'^> \*\*\[CHÈN ẢNH\] (Hình [\d.]+\.[^*]*)\*\*(.*)$', l)
    if mc:
        cap = mc.group(1).strip()
        note = mc.group(2).strip(' —–-')
        res += ['', '::: {custom-style="Image Placeholder"}', f'[CHÈN ẢNH CHỤP MÀN HÌNH: {note}]', ':::', '',
                '::: {custom-style="Image Caption"}', cap, ':::', '']
        i += 1
        while i < len(body) and body[i].strip() in ('>', ''):
            i += 1
        continue
    if l.startswith('# Tài liệu tham khảo'):
        res.append(l); i += 1
        while i < len(body) and not body[i].startswith('# Phụ lục'):
            t = body[i]
            if t.startswith('## '):
                res += ['', '::: {custom-style="Sub Heading"}', t[3:], ':::', '']
            elif t.strip():
                res += ['', '::: {custom-style="Reference Entry"}', t, ':::', '']
            i += 1
        continue
    res.append(l)
    i += 1

out += res
loose = []
for ln in out:
    loose.append(ln)
    if re.match(r'^\s*(- |\d+\. )', ln):
        loose.append('')
out = loose
txt = '\n'.join(out)
txt = re.sub(r'\n{3,}', '\n\n', txt)
# ký hiệu chỉ số dưới trong văn bản (R²_OS, μ_BL, σ_{i,t}...) -> subscript thật của Word
_SUBS = r'(?:\{[^}]+\}|OS|BL|EW|mkt|kk|ij|0,95|0,80|0,3|[ipgkfABmhtns])'
_BASE = r'(R²|SR|RC|[μσρΩΣλπτδγ]|[wrcmyvdzpT])'
def _sub(line):
    if line.startswith('$$') or line.startswith('```'):
        return line
    parts = re.split(r'(`[^`]*`)', line)
    for i, s in enumerate(parts):
        if s.startswith('`'):
            continue
        s = re.sub(r'(?<![A-Za-z0-9_])' + _BASE + r'_(' + _SUBS + r')(?![A-Za-z0-9_])',
                   lambda m: m.group(1) + '~' + m.group(2).strip('{}').replace(' ', '') + '~', s)
        parts[i] = s
    return ''.join(parts)
txt = '\n'.join(_sub(l) for l in txt.split('\n'))
open('thesis_pandoc.md', 'w', encoding='utf-8').write(txt)
print('ok', len(txt))
