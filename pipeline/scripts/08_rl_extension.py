"""
08_rl_extension.py (đợt 4) - PHỤ LỤC: "RL" đúng bản chất là CONTEXTUAL BANDIT.

QC 13: ở bài toán này hành động (tỷ trọng) không làm thay đổi trạng thái kế tiếp
(trạng thái là tín hiệu thị trường), nên hệ số chiết khấu γ không có ý nghĩa; bản
cũ (Q-learning γ=0,9, 4 trạng thái x 4 hồ sơ cố định, 12-36 mẫu) thực chất là
một contextual bandit, và dải khẩu vị áp sau còn nén hành động lại (RiskOn 75% bị
cắt về 60%, RiskOff 15% bị nâng lên 40%).

Thiết kế mới (chỉ dùng trong phụ lục, KHÔNG nằm trong kiểm định chính):
- Trạng thái (4): momentum 3 tháng trung bình các lớp >= trung vị? x vol 6 tháng
  trung bình >= trung vị? (trung vị tính trên dữ liệu train tại thời điểm quyết định).
- Hành động (3): vị trí của tỷ trọng nhóm rủi ro TRONG dải khẩu vị {sàn, giữa,
  trần}; bên trong mỗi nhóm chia đều -> không còn bị dải nén hành động.
- Phần thưởng: lợi nhuận tháng kế tiếp; giá trị hành động = lợi ích mean-variance
  (trung bình - δ/2 x phương sai) của phần thưởng trong trạng thái đó trên cửa sổ
  mở rộng (tương đương Q-learning với γ = 0 và khám phá đầy đủ).
"""
import numpy as np

MIN_STATE_OBS = 3


def band_actions(lo, hi):
    return [lo, (lo + hi) / 2, hi]


def train_bandit(states, rewards, delta=2.5, n_states=4):
    """states: (T,), rewards: (T, n_actions). Trả về Q (n_states, n_actions);
    trạng thái ít dữ liệu -> ưu tiên hành động giữa."""
    states = np.asarray(states, int)
    rewards = np.asarray(rewards, float)
    n_actions = rewards.shape[1]
    Q = np.zeros((n_states, n_actions))
    for s in range(n_states):
        x = rewards[states == s]
        if len(x) < MIN_STATE_OBS:
            Q[s] = -np.inf
            Q[s, n_actions // 2] = 0.0
            continue
        Q[s] = x.mean(axis=0) - delta / 2 * x.var(axis=0, ddof=1)
    return Q


if __name__ == "__main__":
    rng = np.random.RandomState(0)
    st = rng.randint(0, 4, 40)
    rw = rng.randn(40, 3) * [0.01, 0.02, 0.03] + [0.004, 0.006, 0.008]
    print(np.round(train_bandit(st, rw), 5))
