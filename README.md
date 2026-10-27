# PortfolioVN

Cổng thông tin dữ liệu thị trường tháng và công cụ nghiên cứu phân bổ đa tài sản cho demo học thuật UEH. Giao diện VI/EN, backend FastAPI, React/Vite, SQLAlchemy, SQLite local và MySQL/Postgres-ready.

## Demo

- Passcode mặc định: `UEH2026`.
- Hồ sơ demo: An Nguyễn (Investor, VI), Bình Trần (Investor, EN), Hội đồng Reviewer (read-only) và Admin.
- Người có passcode có thể chọn bất kỳ vai trò demo nào, gồm Admin. Không nhập dữ liệu cá nhân/nhà đầu tư thật; thay passcode và cấu hình `DEMO_SESSION_SECRET` trước mọi deployment ngoài buổi demo.
- App không kết nối giá intraday, broker, thanh toán, tin bên thứ ba, email, push hoặc chatbot.

## Nguồn dữ liệu / phiên bản

Ứng dụng đọc các CSV pipeline trong `pipeline/data/processed/`; không tạo lại chỉ số backtest. V1 active là kết quả **sau QC đợt 5** (nhãn `07/2026 · δ 2,5 · phí theo lớp`): panel 02/2016–07/2026 (126 tháng), 5 lớp nghiên cứu (cổ phiếu qua ETF E1VFVN30, cổ phiếu BĐS = rổ 4 doanh nghiệp vốn hóa lớn nhất cập nhật đầu mỗi năm, vàng SJC, trái phiếu = NAV quỹ DCBF, tiền gửi Vietcombank là tiền mặt nhận phần dư), giai đoạn kiểm tra 02/2018–07/2026 (102 tháng). Gói raw có giá cổ phiếu đến 17/08/2026 và trái phiếu đến 21/08/2026, nhưng **tháng 08/2026 chưa trọn nên bị loại khỏi panel**. Giá vàng SJC trước 08/2022 chỉ có điểm neo (6 tháng trước 2020, 4 tháng 2020–2022); các tháng giữa được dựng lại từ giá vàng thế giới × tỷ giá IMF × chênh lệch SJC nội suy, theo chế độ point-in-time, và gắn cờ trong `data_quality`. Kế hoạch thực hiện mua các mã trong rổ BĐS năm hiện hành (`re_basket_current.csv`). Nhãn phiên bản và mốc dữ liệu được tính từ panel, không hardcode. Manifest ghi nguồn, phạm vi, checksum, row counts và validation.

Luồng tư vấn dùng **Risk Parity** (`PVN_ADVISOR_METHOD`, mặc định `RiskParity`) — chọn theo cơ sở lý thuyết, không theo Sharpe backtest. Tỷ trọng nhóm rủi ro do dải khẩu vị quyết định (thiết kế hai tầng); mỗi lớp tối đa 50%, phần vượt chuyển về tiền gửi.

`results/v2-delta4/` là bản chạy cô lập `PVN_DELTA=4 python run.py --stage backtest --no-open` trên dữ liệu đợt 5 (δ của Markowitz/BL = 4), được seed thành V2 draft để minh họa quy trình draft → activate. Pipeline gốc và dữ liệu V1 không bị ghi đè; số liệu V2 chỉ công bố sau khi Admin activate.

## Chạy local

Yêu cầu Node 22/pnpm và Python 3.13 (phiên bản ghim trong `pipeline/requirements.txt`). Dùng SQLite local để không ghi vào database dùng chung:

```bash
pnpm install
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt -r pipeline/requirements.txt
export DATABASE_URL=sqlite:///./portfolio_demo.db
export COOKIE_SECURE=false  # Chỉ chạy localhost HTTP (cookie SameSite=Lax); Preview HTTPS giữ COOKIE_SECURE=true mặc định.
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Ở terminal khác:

```bash
pnpm --dir frontend dev
```

Vite mở cổng 3000 và proxy `/api` tới FastAPI cổng 8000. Để build UI:

```bash
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend build
```

## Kiểm thử an toàn

Các test backend ghi vào DB; không chạy test trên database managed dùng chung với Preview/production. Lệnh này bắt buộc trỏ sang file SQLite tạm:

```bash
TEST_DB="sqlite:////tmp/pvn-test-$RANDOM.sqlite"
DATABASE_URL="$TEST_DB" PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests
```

## Tái chạy nghiên cứu

Runner Admin chỉ chạy stage `backtest`, trong bản sao cô lập, tối đa một job cùng lúc. Tham số: δ (hệ số ngại rủi ro Markowitz/BL) 1,5 / 2,5 (mặc định) / 4; phí giao dịch theo lớp (mặc định: cổ phiếu/ETF/BĐS 0,20%, vàng 1,0%, tiền gửi/trái phiếu 0,30%) hoặc một mức đồng nhất 0–0,50%. Tham số "sàn biến động tiền gửi" đã bỏ theo QC (tiền gửi là tiền mặt, không có phương sai). Một run hợp lệ tạo snapshot bất biến; failed/invalid không đổi active version. Xem `pipeline/README.md`, nhật ký sửa lỗi `pipeline/SUA_LOI.md` (đợt 4 = phản hồi biên bản QC) và `pipeline/docs/data_request_qc.md` (dữ liệu còn thiếu).

## Quyền riêng tư và giới hạn

Role và ownership được quyết định ở backend. Investor chỉ đọc plan của chính mình; truy cập chéo trả 404. Public share link dùng token ngẫu nhiên 256-bit, có thể revoke và không đưa câu trả lời, tên hay user ID ra ngoài. Reviewer chỉ đọc màn hình rà soát; Admin có thể chạy pipeline, sửa nội dung và reset demo. Nút reset có xác nhận; đừng dùng trên một môi trường chứa dữ liệu khác.

Kế hoạch là snapshot bất biến theo phiên bản dữ liệu/rules tại thời điểm tạo; giá tham chiếu cuối tháng chỉ để minh họa đơn vị mua, chưa gồm phí/thuế và không phải giá khớp. Proxy/mã công cụ là phục vụ nghiên cứu, không phải khuyến nghị mua. **Thông tin tham khảo dựa trên dữ liệu lịch sử, không phải khuyến nghị đầu tư.** Một sản phẩm thật cần rà soát pháp lý về tư vấn phù hợp và cấp phép dữ liệu thị trường/tin tức.
