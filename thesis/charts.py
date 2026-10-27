import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, numpy as np
from matplotlib.patches import FancyBboxPatch
plt.rcParams.update({'font.family':'Liberation Serif','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
ACC='#1f5fa8'; MUT='#9aa5b1'
# 4.1
cls=['Cổ phiếu','Cổ phiếu BĐS','Vàng SJC','Trái phiếu']; models=['Elastic Net','LightGBM','MLP']
v={'Elastic Net':[-5.41,1.60,6.73,9.88],'LightGBM':[-4.30,1.05,3.97,16.39],'MLP':[-4.37,-0.92,0.53,16.90]}
col={'Elastic Net':ACC,'LightGBM':'#7fa7d6','MLP':'#c9d6e6'}
fig,ax=plt.subplots(figsize=(6.3,3.4)); x=np.arange(4); w=0.26
for i,m in enumerate(models):
    b=ax.bar(x+(i-1)*w,v[m],w,label=m,color=col[m],edgecolor='#333',linewidth=.5)
    for xi,val in zip(x+(i-1)*w,v[m]): ax.text(xi,val+(0.4 if val>=0 else -0.4),f"{val:.1f}".replace('.',','),ha='center',va='bottom' if val>=0 else 'top',fontsize=9)
ax.axhline(0,color='#333',lw=.8); ax.set_xticks(x); ax.set_xticklabels(cls); ax.set_ylabel('R² ngoài mẫu (%)'); ax.set_ylim(-8,19)
ax.legend(frameon=False,ncol=3,loc='upper left'); fig.tight_layout(); fig.savefig('img/h41.png',dpi=220)
# 4.2 heatmap
M=['EqualWeight','Markowitz','RiskParity','HRP','BlackLitterman','MLP_MVO','RL']
S=[[.33,.37,.49,.25,.29,.38,.14,.16,.20],[.43,.45,.41,.16,.20,.23,.09,.17,.10],[.29,.36,.62,.27,.29,.35,.18,.19,.21],[.08,.16,.50,.22,.24,.28,.19,.20,.20],[.57,.55,.45,.48,.37,.38,.22,.22,.27],[.24,.40,.74,-.02,.33,.61,.09,.26,.38],[.32,.39,.66,.15,.21,.34,.10,.14,.16]]
S=np.array(S); fig,ax=plt.subplots(figsize=(6.3,3.6))
im=ax.imshow(S,cmap='Blues',vmin=-0.1,vmax=0.85,aspect='auto')
for i in range(7):
    for j in range(9): ax.text(j,i,f"{S[i,j]:.2f}".replace('.',','),ha='center',va='center',fontsize=9,color='white' if S[i,j]>0.5 else 'black')
ax.set_yticks(range(7)); ax.set_yticklabels(M); ax.set_xticks(range(9)); ax.set_xticklabels(['Ngắn','Trung','Dài']*3,fontsize=9)
for k,p in enumerate(['Thận trọng','Cân bằng','Tăng trưởng']): ax.text(3*k+1,-0.9,p,ha='center',fontsize=10.5,fontweight='bold')
for k in (2.5,5.5): ax.axvline(k,color='white',lw=3)
ax.add_patch(plt.Rectangle((3.5,-0.5),1,7,fill=False,ec='#c0392b',lw=1.6,ls='--'))
ax.tick_params(length=0); [s.set_visible(False) for s in ax.spines.values()]
fig.tight_layout(); fig.subplots_adjust(top=0.88); fig.savefig('img/h42.png',dpi=220)
# 4.3 stacked
meth=['Equal Weight','Markowitz','Risk Parity','HRP','Black–Litterman']; c2=['Vàng','Cổ phiếu','Cổ phiếu BĐS','Trái phiếu','Tiền gửi']
D=np.array([[37.8,22.2,16.3,15.7,8.1],[15.8,37.6,6.2,40.3,0],[19.7,26.3,16.4,37.4,0.3],[5.6,28.2,21.2,42.7,2.4],[53.8,18.2,15.2,8.0,4.8]])
D=D/D.sum(1,keepdims=True)*100; cc=[ACC,'#5d6d7e','#8e9eab','#bcc6cf','#e3e8ec']
fig,ax=plt.subplots(figsize=(6.3,3.2)); left=np.zeros(5)
for j in range(5):
    ax.barh(meth,D[:,j],left=left,color=cc[j],label=c2[j],edgecolor='white')
    for i in range(5):
        if D[i,j]>=8: ax.text(left[i]+D[i,j]/2,i,f"{D[i,j]:.0f}%",ha='center',va='center',fontsize=9,color='white' if j in(0,1) else 'black')
    left+=D[:,j]
ax.invert_yaxis(); ax.set_xlim(0,100); ax.set_xlabel('Tỷ trọng đóng góp vào tổng lợi nhuận trước phí (%)')
ax.legend(frameon=False,ncol=5,loc='lower center',bbox_to_anchor=(0.42,1.0),fontsize=9.5); fig.tight_layout(); fig.savefig('img/h43.png',dpi=220)
# 5.1 architecture
fig,ax=plt.subplots(figsize=(6.3,3.3)); ax.set_xlim(0,760); ax.set_ylim(372,40); ax.axis('off')
B={'pipe':(24,72,'Pipeline nghiên cứu (Python)',['00–02: thu thập, ghép chuỗi dữ liệu thô','03–04: panel tháng, chuẩn hóa biến','06–08: dự báo ML; 09–19: backtest, kiểm định','Đầu ra: CSV trong data/processed + checksum'],False),
 'ver':(406,72,'Kho kết quả theo phiên bản',['Mỗi lần chạy = một phiên bản bất biến','Manifest: nguồn, phạm vi dữ liệu, checksum','Trạng thái draft → active do Admin kích hoạt','Kế hoạch lưu lại phiên bản đã dùng'],True),
 'api':(24,240,'Backend FastAPI',['domain: khẩu vị, phân bổ VND, rủi ro, lịch','services: tạo kế hoạch, kích hoạt, chạy lại','SQLAlchemy: SQLite local, sẵn sàng MySQL/Postgres','Phân quyền theo vai trò ở phía máy chủ'],False),
 'ui':(406,240,'Giao diện React (Vite), song ngữ',['Thị trường, Tin tức, Phân tích phương pháp','Tư vấn: bảng hỏi → kế hoạch','Kế hoạch: xem, in, chia sẻ liên kết','Quản trị: chạy backtest, phiên bản, nhật ký'],False)}
for k,(x,y,t,ls,main) in B.items():
    ax.add_patch(FancyBboxPatch((x,y),330,104,boxstyle='round,pad=0,rounding_size=8',fc='#e8f0fa' if main else 'white',ec=ACC if main else '#555',lw=1.6 if main else 1))
    ax.text(x+12,y+22,t,fontsize=9.5,fontweight='bold')
    for i,l in enumerate(ls): ax.text(x+12,y+42+i*16,l,fontsize=8)
ar=dict(arrowstyle='->',color='#444',lw=1)
ax.annotate('',xy=(406,124),xytext=(354,124),arrowprops=ar); ax.text(380,116,'CSV',ha='center',fontsize=8,color='#555')
ax.annotate('',xy=(406,292),xytext=(354,292),arrowprops=ar); ax.text(380,284,'JSON',ha='center',fontsize=8,color='#555')
ax.plot([571,571,229],[176,212,212],color='#444',lw=1); ax.annotate('',xy=(229,240),xytext=(229,212),arrowprops=ar); ax.text(560,206,'đọc CSV của phiên bản active',ha='right',fontsize=8,color='#555')
ax.annotate('',xy=(64,176),xytext=(64,240),arrowprops=dict(arrowstyle='->',color='#444',lw=1,ls='--')); ax.text(72,200,'Admin chạy lại',fontsize=8,color='#555')
fig.tight_layout(); fig.savefig('img/h51.png',dpi=220)
