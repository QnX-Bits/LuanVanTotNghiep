#!/usr/bin/env bash
# Dựng khóa luận Word theo quy chuẩn UEH từ các chương Markdown trong parts/.
# Cần: Python 3 (python-docx, matplotlib), pandoc >= 3.1, LibreOffice (soffice) và poppler (pdfinfo, pdftotext).
set -e
cd "$(dirname "$0")"
python3 -c "import glob; open('full.md','w').write('\n'.join(open(x).read().rstrip('\n')+'\n' for x in sorted(glob.glob('parts/*.md'))))"
python3 prep.py
python3 mkref.py
pandoc thesis_pandoc.md -f markdown+subscript+pipe_tables+tex_math_dollars+raw_attribute+fenced_divs -o stage1.docx --reference-doc=reference.docx --columns=10
python3 post.py stage1.docx stage2.docx
rm -rf pdf && mkdir pdf
soffice --headless --convert-to pdf --outdir pdf stage2.docx >/dev/null 2>&1
python3 fill_toc.py stage2.docx pdf/stage2.pdf final.docx
echo "Xong: final.docx"
