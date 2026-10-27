import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
plt.rcParams.update({'font.family':'Liberation Serif'})
ACC='#1f5fa8'
def box(ax,x,y,w,h,title,lines,main=False,fs=8.2):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0,rounding_size=6',fc='#e8f0fa' if main else 'white',ec=ACC if main else '#555',lw=1.4 if main else 1))
    ax.text(x+w/2,y+14,title,ha='center',va='center',fontsize=9,fontweight='bold')
    for i,l in enumerate(lines): ax.text(x+8,y+32+i*14,l,fontsize=fs,va='center')
def arrow(ax,x1,y1,x2,y2,ls='-'):
    ax.annotate('',xy=(x2,y2),xytext=(x1,y1),arrowprops=dict(arrowstyle='->',color='#444',lw=1.1,ls=ls))
# 3.1 framework: 4 layers top->bottom with side outputs
fig,ax=plt.subplots(figsize=(6.3,4.9)); ax.set_xlim(0,640); ax.set_ylim(495,0); ax.axis('off')
L=[('1. Tầng dữ liệu',['Giá ETF, rổ BĐS, vàng SJC, NAV DCBF, lãi tiền gửi VCB','Ghép nguồn, kiểm tra độ khớp, dựng vàng point-in-time','Biến đầu vào: động lượng, biến động, kỳ hạn, lãi suất, basis vàng']),
   ('2. Tầng ước lượng và dự báo',['Σ: khử trơn Geltner → EWMA (half-life 18) → co Ledoit–Wolf','μ: Bayes–Stein (Markowitz) hoặc dự báo ML ngoài mẫu','ML: Elastic Net, LightGBM, MLP; kỹ năng R²_OS, Clark–West']),
   ('3. Tầng phân bổ',['7 phương pháp: EW, Markowitz, RP, HRP, BL, MLP_MVO, RL','Ràng buộc: dải khẩu vị, trần 50%/lớp, tiền gửi nhận phần dư','9 kịch bản = 3 khẩu vị × 3 khung thời gian']),
   ('4. Tầng đánh giá',['Backtest walk-forward 02/2018–07/2026, có phí theo lớp','Kiểm định Ledoit–Wolf, Holm, MDE, Deflated Sharpe','Độ nhạy, stationary bootstrap, phân rã đóng góp'])]
for i,(t,ls) in enumerate(L):
    y=10+i*125; box(ax,20,y,440,95,t,ls,main=(i==2))
    if i<3: arrow(ax,240,y+95,240,y+125)
box(ax,490,385,135,95,'Ứng dụng',['PortfolioVN:','khẩu vị → tỷ trọng','→ kế hoạch mua'],fs=8.2)
arrow(ax,460,432,490,432)
fig.tight_layout(); fig.savefig('img/h3_framework.png',dpi=220)
# 3.2 walk-forward timeline
fig,ax=plt.subplots(figsize=(6.3,2.6)); ax.set_xlim(0,640); ax.set_ylim(170,0); ax.axis('off')
ax.plot([20,620],[60,60],color='#333',lw=1)
for x,l in [(20,'02/2016'),(150,'01/2018\n(24 tháng)'),(380,'d'),(440,'d+1'),(620,'07/2026')]:
    ax.plot([x,x],[55,65],color='#333'); ax.text(x,80,l,ha='center',va='top',fontsize=8.5)
ax.add_patch(plt.Rectangle((20,30),360,20,fc='#e8f0fa',ec=ACC)); ax.text(200,40,'Dữ liệu đến cuối tháng d: ước lượng Σ, μ, huấn luyện ML, kỹ năng',ha='center',va='center',fontsize=8.3)
ax.add_patch(plt.Rectangle((380,30),60,20,fc='#fdf2d0',ec='#c9a227')); ax.text(410,40,'r(d+1)',ha='center',va='center',fontsize=8.3)
ax.text(20,125,'Mỗi tháng d: tính tỷ trọng mục tiêu → nếu là tháng tái cân bằng (1/3/12 tháng) thì giao dịch và trừ phí,',fontsize=8.3)
ax.text(20,142,'nếu không thì tỷ trọng trôi theo giá → ghi nhận lợi nhuận tháng d+1 → d tăng thêm 1 tháng và lặp lại.',fontsize=8.3)
fig.tight_layout(); fig.savefig('img/h3_walkforward.png',dpi=220)
# 5.x advisory flow (horizontal steps)
fig,ax=plt.subplots(figsize=(6.3,2.4)); ax.set_xlim(0,660); ax.set_ylim(175,0); ax.axis('off')
S=[('Bảng hỏi',['T1–T4: chấp nhận','C1–C3: khả năng','H: thời gian']),('Đánh giá',['Khẩu vị = mức','thấp nhất của','T, C và trần H']),('Phân bổ',['Tỷ trọng Risk','Parity của phiên','bản active']),('Kế hoạch',['Lệnh mua theo','lô, chỉ vàng,','số tiền']),('Báo cáo',['Rủi ro bằng VND,','lịch tái cân','bằng, giải thích'])]
for i,(t,ls) in enumerate(S):
    x=5+i*131; box(ax,x,20,122,85,t,ls,main=(i==2),fs=7.6)
    if i<4: arrow(ax,x+122,62,x+131,62)
ax.text(10,140,'Cảnh báo W1–W4 hiển thị ở bước Đánh giá; người dùng chỉ được chọn cao hơn khẩu vị hệ thống một bậc và phải xác nhận.',fontsize=8)
ax.text(10,158,'Kế hoạch được lưu thành bản chụp bất biến gắn với phiên bản dữ liệu và quy tắc tại thời điểm tạo.',fontsize=8)
fig.tight_layout(); fig.savefig('img/h5_flow.png',dpi=220)
