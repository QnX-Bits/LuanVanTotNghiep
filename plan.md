# Kế hoạch triển khai — PortfolioVN

> **Cập nhật 24/10/2026 (QC đợt 4):** kế hoạch dưới đây là bản gốc khi dựng app. Tham số `PVN_VOL_FLOOR_TIEN_GUI` đã bị bỏ (tiền gửi là tiền mặt nhận phần dư), admin run nay nhận `delta` (PVN_DELTA 1,5/2,5/4) và phí theo lớp hoặc đồng nhất; luồng tư vấn dùng Risk Parity (`PVN_ADVISOR_METHOD`). Chi tiết: `pipeline/SUA_LOI.md`.


## Mục tiêu và căn cứ

Xây dựng website demo nghiên cứu PortfolioVN theo `demo_guideline_portfoliovn(2).md`, dùng pipeline `pipeline/` mà người dùng vừa cung cấp làm nguồn chuẩn. Bộ nguồn đã giải nén có `data/raw` và `data/processed`; các CSV cốt lõi hiện có 63 dòng performance, 63 allocations, 2.394 dòng backtest, 27 kiểm định Holm, 38 kỳ so sánh 7 phương pháp và 666 hàng panel (9 chuỗi, 74 tháng liên tục 07/2020–08/2026). Các kết quả đọc từ V1 khớp spec: HRP/Cân bằng/Trung hạn 9,4142% lợi nhuận năm hóa, 8,4154% biến động, Sharpe 0,5202, drawdown −5,6265%; phân bổ HRP khớp ví dụ 100 triệu. Thị trường 08/2026 có VN-Index 1.727,46, vàng SJC 145.500.000 ₫/lượng, DXG +11,65%, VHM −7,90%. Dữ liệu cổ phiếu đến 17/08/2026, trái phiếu đến 21/08/2026; do đó tháng 08/2026 phải hiện là tạm tính.

Hai chỗ pipeline cần điều chỉnh nhỏ theo spec: `scripts/common.py` đang hard-code phí giao dịch 0,0015; `scripts/09_portfolio_optimization.py` đang hard-code sàn volatility tiền gửi 0,05. Thay bằng `PVN_TRANSACTION_COST` (default `0.0015`) và `PVN_VOL_FLOOR_TIEN_GUI` (default `0.05`), không thay đổi công thức/định nghĩa mô hình. Không chạy `models` hay `all` từ UI; các lần chạy UI chỉ dùng `python run.py --stage backtest --no-open`, chạy trong bản sao tạm của pipeline để thất bại không làm thay đổi CSV của V1 đang active. Kết quả mới phải qua validation rồi mới thành draft; chỉ thao tác kích hoạt phiên bản mới làm đổi active. Không đổi dữ liệu plan snapshot đã lưu.

`LuanVan_App` hiện không sinh `manifest.json`; backend sẽ tạo manifest ứng dụng tại thời điểm nhập phiên bản, chứa commit nguồn nếu xác định được, checksum SHA-256, row counts, tham số, thời điểm dữ liệu thô và trạng thái provisional. Không ghi rằng pipeline tự tạo manifest. Phiên bản V1 lưu bất biến các CSV hiện có. Kết quả/CSV không được phục vụ bằng đường dẫn tùy ý; quyền truy cập theo vai trò/owner được kiểm tra ở API.

## Cách triển khai và kết nối thành phần

- **Frontend:** React 18, Vite, TypeScript, React Router, i18next và Recharts; gọi API tương đối `/api/...`, tự chọn VI mặc định hoặc EN. Chart (time-series, cumulative returns, paired allocations, Sharpe, 12-month result dot strip) có nút chuyển sang bảng dữ liệu. Frontend không tính lại metrics tồn tại trong CSV; chỉ hiển thị chúng và gọi các pure-function API cho nghiệp vụ phát sinh theo spec.
- **Backend:** FastAPI + Pydantic v2 + SQLAlchemy/Alembic, chạy Python 3.13 trong image triển khai; API, kiểm tra vai trò/ownership, nhập phiên bản, snapshot kế hoạch và các phép tính thuần theo spec. Development dùng listener FastAPI nội bộ và Vite trên runtime port 3000; production dùng FastAPI phục vụ API và static bundle React trên cùng listener 3000.
- **Dữ liệu bền vững:** dùng managed MySQL đã bật cho project; development và published dùng chung DB nên migrations chỉ theo hướng additive, seed idempotent, không xóa/reset trong lúc phát triển. Lưu manifest, trạng thái version, plan/news/audit và snapshot CSV nén theo version trong DB; staging/run CSV tạm thời trong thư mục làm việc. Data files source được nhập sang V1 bất biến, không đọc trực tiếp file nguồn cho các plan đã lưu.
- **Pipeline:** `pipeline/` chứa source/data user gửi, sửa đúng hai biến môi trường nêu trên. Admin chỉ khởi chạy stage `backtest` với một job tại một thời điểm; runner copy pipeline sang thư mục tạm, truyền floor 2/5/8% và transaction cost 0–0,50%, thu log, kiểm tra đầu ra, đóng gói thành version draft; lỗi không ảnh hưởng active. Không thực thi stage thu thập dữ liệu hoặc `models`/`all` từ UI. Lịch sử phân tích sensitivity dùng CSV do pipeline sinh.
- **Vai trò:** passcode demo theo spec mở role switcher Investor/Reviewer/Admin; không dùng Manus OAuth vì spec đã chọn passcode demo. Server áp quyền cho mọi request; Reviewer read-only; Investor chỉ xem plan của mình và tin đã publish; Admin có quyền vận hành được nêu trong spec. Passcode chỉ phục vụ demo, không được quảng bá là xác thực tài khoản thật; README cảnh báo ai biết passcode đều có thể chọn Admin.
- **Tin:** monthly briefs và notable moves tạo bằng template xác định từ panel; mỗi số gắn series/tháng/raw/display value, nguồn và version. Không dùng LLM hay third-party feed. Bài thủ công được sanitize và kiểm tra nguồn HTTPS.
- **Kiến trúc lưu trữ:** lịch sử pipeline immutable theo version. Plan tạo bằng version đang active sẽ giữ answer/profile/ack/weights/target split/execution/rules/prices/metrics/risk/date/why; version sau không tính lại plan cũ. Share token ngẫu nhiên có thể revoke; share DTO loại bỏ tên, user-id và answers. IPS render được in A4; share IPS ẩn tên/answers.

## Cấu trúc project dự kiến

```text
pipeline/                     Pipeline Python, raw/processed CSV và README user cung cấp
  scripts/                    Pipeline nghiên cứu; hai biến env được đọc từ common/optimizer
  data/raw/                   Dữ liệu thô 6 lớp/9 chuỗi
  data/processed/             CSV V1 đã cung cấp
backend/
  app/api/                    API auth, markets, news, advisor, plans, analysis, admin
  app/domain/                 profiling, VND allocation, execution, risk, rebalance/drift, news
  app/data/                   CSV schema/validation, immutable version import và manifest
  app/models/                 SQLAlchemy entities + migration history
  app/services/               access control, version activation, pipeline subprocess, audit
  tests/                      pytest cho pure functions, imports, roles, snapshots
frontend/
  src/app/                    routing, API client, shell và role/language state
  src/components/             ticker, mega-menu, tables, charts, disclaimers, shared controls
  src/features/               markets, news, advisor, plans/IPS, analysis, admin, about
  src/locales/                VI/EN translations
  src/assets/logo.svg         Wordmark và biểu trưng
  public/manus-routes.json    Route manifest đầy đủ cho website
  tests/                      formatters, direction, volatility và navigation
results/                      staging/version exports dùng lúc import; DB là bản lưu bền vững
Dockerfile                    build React + chạy FastAPI trên cổng 3000
README.md                     cách chạy, passcode demo, users, reset, giới hạn và bảo mật demo
plan.md / TODO.md             kế hoạch và các outcome/acceptance còn mở
```

## Thiết kế giao diện

- **Design movement:** chủ nghĩa hiện đại Thụy Sĩ/typographic grid của báo cáo nghiên cứu thể chế, được diễn giải thành cổng dữ liệu tài chính Việt Nam — không sao chép sản phẩm nào.
- **Core principles:** nguồn gốc con số luôn nhìn thấy; thứ bậc bằng chữ/số và đường kẻ thay vì trang trí; trung tính trước hiệu suất; cùng một dữ liệu/cách định dạng trên bảng, chart, bài báo và IPS.
- **Color philosophy:** trắng và đen tạo cảm giác rõ ràng/kiểm chứng; xám chia lớp thông tin; chỉ xanh cho mức tăng, đỏ cho giảm hoặc cảnh báo như spec; không tô nền màu cả khối. Mã màu nền: `#0A0A0A`, `#FFFFFF`, `#F4F4F5`, viền `#E4E4E7`, chữ phụ `#52525B`, disabled `#A1A1AA`, gain `#15803D`, loss/warning `#B91C1C`.
- **Layout paradigm:** bố cục editorial lệch trục: hero 2/3 cho market ledger và 1/3 cho advisor entry; trang nội dung dùng rail phụ cho nguồn/chú giải và bảng chính; tối đa 1200px, trên mobile xếp dọc; ticker cuộn snap và bảng lớn cuộn trong khung.
- **Signature elements:** (1) utility bar đen với mốc dữ liệu/provisional; (2) market ledger số tabular và sparkline một nét; (3) chip nét đứt `Tạm tính` và thanh allocation solid/outline target-vs-executed.
- **Interaction philosophy:** mọi thay đổi phản hồi ngay và có văn bản mô tả; form từng nhóm/câu có Back, state không mất khi chuyển ngôn ngữ; mega-menu hoạt động hover/click/Enter/Escape; giảm chuyển động khi `prefers-reduced-motion`; focus 2px đen có viền offset trắng, touch target ≥48px.
- **Animation:** nhanh, tối giản (fade/slide 120–180ms cho menu/filter, transition chiều rộng cho thanh phân bổ); không nhấp nháy/auto-scroll; không animate giá như live vì dữ liệu tháng.
- **Typography:** Inter tự host là họ sans duy nhất theo spec, phân cấp 15px body/14px table/600 headings/11pt IPS, số dùng `tabular-nums`; mã kế hoạch và số liệu nhỏ vẫn cùng họ chữ để giữ quy ước một family.
- **Brand essence:** “Cổng dữ liệu và lập kế hoạch phân bổ có thể kiểm chứng cho demo nghiên cứu thị trường Việt Nam — nối thẳng số liệu tháng với rủi ro bằng VND và đơn vị thực hiện.” Tính cách: chuẩn xác, điềm tĩnh, minh bạch.
- **Brand voice:** câu ngắn, khách quan, xưng “bạn”, không hype/đảm bảo. Ví dụ: “Dữ liệu theo tháng, không phải thời gian thực.” / “Đây là kết quả quá khứ, không phải dự báo.”
- **Wordmark/logo:** `Portfolio` regular + `VN` bold kèm mark sáu vạch ledger đại diện sáu lớp, file SVG một chỗ để thay thế; bản trắng ở footer.
- **Signature brand color:** đen mực `#0A0A0A`, màu sở hữu duy nhất ngoài các ngoại lệ gain/loss/warning mà spec đã quy định.

## Hành trình và màn hình

Global shell gồm `/login`, trang chủ, mega-menu Thị trường/Tin tức/Tư vấn/Phân tích/Về dự án, search không dấu, ticker sáu lớp, breadcrumbs và footer. Thị trường có overview, trang riêng cho sáu lớp; tin có list/detail + facts/sources; advisor đi qua 4Tolerance → 3Capacity → Horizon → Profile review → Amount → Result; plan list/detail/frozen snapshot/drift/refresh/share/print; Analysis gồm compare/methodology/sensitivity/models; About gồm giới thiệu/data sources/disclaimer; Admin gồm versions/runs/logs/news/execution rules/audit/reset. Bộ route đầy đủ được khai báo trong manifest và giữ đồng bộ với React Router.

## Nghiệp vụ then chốt cần giữ đúng

Scoring, horizon cap và W1–W4 theo spec; lựa chọn profile cao hơn một mức cần acknowledgment `ack-v1`; amount 1.000.000–100.000.000.000 VND; exact largest-remainder allocation theo thứ tự sáu lớp; execution units: fund step 1.000đ/min 100.000đ, BĐS/ETF lô 100, vàng theo chỉ, deposit nhận leftovers; cảnh báo deviation >2pp và ngưỡng amount tối thiểu; VND drawdown + stress months + mọi cửa sổ 12 tháng; rebalance theo horizon, drift >5pp; source-to-screen/chip provisional; below-deposit honesty note; 27 statistical tests với Holm; mọi chart có view-as-table; VI/EN cho mọi chuỗi và print. Các ví dụ kỳ vọng V1 trong spec sẽ được tái tạo trực tiếp từ CSV và kiểm tra trước khi hiển thị.

## Phụ thuộc và giới hạn triển khai

Project WebDev hiện bật Server và Managed Database, runtime Preview port 3000, repo managed bởi Manus, auto-publish đang tắt. Không tự bật auto-publish. Development/production chia sẻ DB nên chỉ migration additive/seed idempotent, không reset dữ liệu trong lúc kiểm tra. Dependencies Node dùng pnpm đã pin và khai báo rõ lifecycle build scripts trước lần cài đầu. Docker container build đủ cả Vite bundle và FastAPI. Pipeline requirements ghim phiên bản trong ZIP; môi trường hiện tại là Python 3.12.3 trong khi README pipeline ghi Python 3.13, vì vậy runner container sẽ dùng Python 3.13 và local kiểm tra tương thích trên môi trường hiện có; không đổi pin để chạy qua lỗi. Publication tách biệt khỏi checkpoint; chỉ báo URL published khi có kết quả publish thành công. Nội dung dựa dữ liệu lịch sử, không phải tư vấn đầu tư; sản phẩm thực cần duyệt suitability/licence dữ liệu.