# Mã dựng khóa luận (Word, quy chuẩn UEH)

- `parts/00_front.md` … `parts/08.md`: nội dung (phần đầu, Chương 1–6, tài liệu tham khảo, phụ lục). Sửa nội dung ở đây.
- `img/`: hình trong khóa luận. `charts.py` vẽ Hình 4.2, 4.3, 4.6, 5.1; `diagrams.py` vẽ Hình 3.1, 3.3, 5.2. Hình 3.2, 4.1, 4.4, 4.5 được vẽ từ `pipeline/data/processed` (giá vàng, lợi nhuận các lớp, backtest kịch bản chính).
- `prep.py`: chuyển Markdown sang dạng pandoc, dựng bìa ngoài/bìa trong, Lời cám ơn, mục lục, danh mục, chú thích bảng/hình, chỉ số dưới.
- `mkref.py`: tạo `reference.docx` (A4, lề 3/3/3/2 cm, Times New Roman 13, giãn dòng 1,5, số trang góc dưới phải). Cần `ref0.docx` = `pandoc -o ref0.docx --print-default-data-file reference.docx`.
- `post.py`: ngắt phần (bìa không số trang, phần đầu số La Mã, thân bài từ 1), khung bìa, định dạng bảng, phông mặc định.
- `fill_toc.py`: điền sẵn mục lục và danh mục kèm số trang (Word vẫn cập nhật lại khi mở).
- Chạy: `bash build.sh` -> `final.docx`. Bản đã dựng sẵn: `KhoaLuan_ToiUuDanhMucDaTaiSan_UEH_v4.docx`.
