# T04 — Simulator results · **ĐỢT 2 (05-09-2026)** · seed 42
**Corpus:** 121 video / 3713 sự kiện / 166.589 khung (CDnet2014 53 · LASIESTA 48 · BMC 20) — dựng bằng `code/build_event_corpus.py` của chính bài này từ detection theo khung hình, ra `data/event_corpus.csv` (sha256 `902d3c552c1f…`). Quy tắc: **sự kiện = dãy cực đại các khung liên tiếp có ≥1 hộp phát hiện**. KHÔNG Orin/INA.

**Chạy lại:**
```
set PINWHEEL_DETECTIONS_DIR=<thư mục detection theo khung hình>
python code\build_event_corpus.py
python code/pinwheel_sim.py     --exp all     # E1, E2, E3          (đợt 1, ~3 phút)
python code/proof_checks.py                   # C1–C6 kiểm chứng minh (~2 phút)
python code/pinwheel_round2.py  --exp all     # E1b, E4–E8 + hình    (~4,5 phút)
```
`code/pinwheel_sim.py` **giữ nguyên byte-identical** so với đợt 1 (bản sao: `code/pinwheel_sim.bak_20260905_round1.py`); đợt 2 nằm hoàn toàn trong `code/pinwheel_round2.py` và `code/proof_checks.py`.

**Mọi số trong bản thảo phải truy về các JSON dưới đây (luật C6).**

| file | nội dung |
|---|---|
| `corpus_meta.json` | 121/3713/166.589 + sha256 nguồn |
| `A3_proof_checks.json` | C1–C6: kiểm máy cho từng định lý (Phần A3) |
| `E1_density_sweep.json` | E1 — schedulability vs mật độ (594 profile) |
| `E1b_admission_conservatism.json` | E1b — giá phải trả của luật kiểm nạp O(1) |
| `E2_trace_frontier.json` | E2 — replay trace, uniform vs shaped |
| `E3_switch_cost.json` | E3 — switch cost |
| `E4_fleet_dimensioning.json` | E4 — số hộp edge cho 121 camera |
| `E5_churn_admission.json` | E5 — kiểm nạp dưới churn |
| `E6_blackout.json` | E6 — escalation blackout (Prop 3) |
| `E7_energy.json` | E7 — năng lượng theo đơn vị E_idle + consolidation gain (lưới r) |
| `E8_sensitivity.json` | E8 — hold-out, per-dataset, cap K_max, baseline round-robin |

Hình: `fig_E1_schedulability` · `fig_E2_frontier` · `fig_E3_switch` · `fig_E4_dimensioning` · `fig_E5_churn` · `fig_E6_blackout` · `fig_E7_energy` · `fig_E8_sensitivity` — mỗi hình **≤ 2 panel**, font ≥ 8 pt, xuất **cả `.pdf` (vector, dùng cho LaTeX) và `.png`**.

---

# PHẦN 0 — KIỂM MÁY CHO CÁC CHỨNG MINH (`proof_checks.py` → `A3_proof_checks.json`)

| Kiểm | Nội dung | Kết quả |
|---|---|---|
| **C1** | Họ {2, 3, M} phải **không** lập lịch được với mọi M (Thm 1(iii)) | **37/37** instance (M = 3…39) unschedulable; ρ nhỏ nhất trong họ = 0,85897 |
| **C2** | Sức chứa dưới switch cost: `N_max(K,s) = max(1, ⌊K/(1+s)⌋)` | **29/29** ô quyết định được khớp **chính xác**; 7 ô còn lại bị chặn ngân sách trạng thái (censored) |
| **C3** | q nhóm model: đủ `N+qs ≤ K`, cần `N+(q−1)s ≤ K` | đủ đúng **130/130**, cần đúng **130/130**; **cả 12 ô trong dải hở đều KHÔNG khả thi** ⇒ có dấu hiệu điều kiện đủ cũng là cần (**chưa chứng minh — chỉ ghi là quan sát**) |
| **C4** | Cor 3: làm tròn harmonic + FFD vào hộp mật độ 1 | 4.000/4.000 instance: đóng gói **hoàn hảo** (`m = ⌈Σ1/K̂⌉`), **mọi hộp** lập lịch được bằng scheduler constructive, `m ≤ ⌈2ρ⌉`. Tỷ số `m/⌈ρ⌉`: **trung bình 1,272 · tối đa 2,000** |
| **C5** | Ngân sách blackout `B = min(K, ℓ⌈(K+ℓ−1)/P_e⌉)` | **297/297** ô không vi phạm. Bản nháp T02 `ℓ(⌊K/P_e⌋+1)` cũng không vi phạm ô nào và chặt hơn ở 4,4% ô — **nhưng không chứng minh được**, nên bài dùng bản chứng minh được |
| **C6** | Greedy marginal allocation vs **duyệt vét cạn** (Thm 3) | 200 instance, N=4, lưới 11 giá trị: greedy **tối ưu ở 70,0%**; sai lệch **trung bình 0,17% · p95 1,08% · tối đa 1,82%** |

> Trong quá trình C2 công cụ kiểm **bắt được một lỗi của chính nó**: bản đầu tiên quên rằng camera *được phục vụ* cũng già đi qua s slot chuyển đổi (thiếu điều kiện `u_i + 1 + s ≤ K_i`), khiến nó báo "khả thi" cho các cấu hình thực ra không khả thi. Đã sửa. Đây cũng là cái bẫy khi cài scheduler thật.

---

# E1 — Schedulability vs mật độ (đợt 1, không đổi)
594 profile ngẫu nhiên, N∈[3,8], K∈[2,14]; exact = duyệt đồ thị trạng thái.

| bin ρ | decided | exact schedulable | lazy EDF không vi phạm | harmonic 1-base khả thi | unschedulable với ρ≤5/6 |
|---|---|---|---|---|---|
| (0,400;0,500] | 66/66 | 1,00 | 1,00 | 1,00 | 0 |
| (0,500;0,600] | 66/66 | 1,00 | 1,00 | 1,00 | 0 |
| (0,600;0,700] | 66/66 | 1,00 | 0,98 | 1,00 | 0 |
| (0,700;0,750] | 66/66 | 1,00 | 0,79 | 1,00 | 0 |
| (0,750;0,833] | 66/66 | 1,00 | 0,56 | 0,91 | 0 |
| (0,833;0,900] | 66/66 | 1,00 | 0,21 | 0,52 | 0 |
| (0,900;0,950] | 65/66 | 0,71 | 0,05 | 0,23 | 0 |
| (0,950;1,000] | 63/66 | 0,14 | 0,03 | 0,08 | 0 |
| (1,000;1,100] | 59/66 | 0,00 | 0,00 | 0,00 | 0 |

**Đọc:** (a) **0/330 instance ρ ≤ 5/6 bị unschedulable** — khớp Thm 1(ii). (b) EDF **không** phải luật thiết kế an toàn: hỏng 21% ở (0,70;0,75] và 44% ở (0,75;5/6] **trên instance đã chứng minh là schedulable**. (c) harmonic 1-base (constructive, O(N·K)) giữ 100% tới 0,75 và 91% tới 5/6.

# E1b — Giá phải trả của luật kiểm nạp O(1) (MỚI, trả lời R2-11)
*conservatism = P(luật mật độ từ chối | instance thực ra lập lịch được)*

| bin ρ | schedulable | bị 5/6 từ chối | conservatism |
|---|---|---|---|
| ≤ 5/6 (5 bin đầu) | 330 | 0 | **0,00** |
| (0,833;0,900] | 66 | 66 | 1,00 |
| (0,900;0,950] | 46 | 46 | 1,00 |
| (0,950;1,000] | 9 | 9 | 1,00 |
| **tổng** | **451** | **121** | **0,268** |

**Đọc:** luật `ρ ≤ 5/6` **không bao giờ nhận nhầm** (0 instance không lập lịch được lọt qua) và **không từ chối nhầm bất kỳ instance nào ở dưới ngưỡng**. Cái giá nằm hoàn toàn ở dải trên 5/6: 121/451 = **26,8%** profile lập lịch được bị từ chối.
⚠ **Caveat bắt buộc in kèm:** 26,8% là con số **theo thiết kế lấy mẫu của E1**, vốn cố ý dồn 4/9 số bin vào dải ρ > 5/6; nó **không** phải xác suất trên một phân bố fleet tự nhiên. Phải nói câu này trong bài.

# E2 — Replay trace: uniform vs shaped-harmonic ở cùng ngân sách ρ* (đợt 1, không đổi)
12 seed × H = 6000 slot, scheduler harmonic (bảo đảm).

| N | ρ* | miss uniform | miss shaped | giảm | bound Lemma 2 (unif/shaped) | #cert (unif/shaped) | latency cert max (unif/shaped) |
|---|---|---|---|---|---|---|---|
| 4 | 0,500 | 0,263 | 0,219 | −17% | 0,266 / 0,213 | 4637 / 5091 | 7 / 62 |
| 4 | 0,667 | 0,219 | 0,171 | −22% | 0,231 / 0,171 | 5081 / 5695 | 5 / 63 |
| 4 | 0,833 | 0,216 | 0,148 | −32% | 0,210 / 0,146 | 5170 / 5982 | 4 / 63 |
| 4 | 1,000 | 0,165 | 0,132 | −20% | 0,181 / 0,132 | 5493 / 6244 | 3 / 63 |
| 6 | 0,500 | 0,455 | 0,304 | −33% | 0,455 / 0,307 | 1541 / 6543 | 11 / 63 |
| 6 | 0,833 | 0,347 | 0,212 | −39% | 0,347 / 0,221 | 6291 / 7936 | 7 / 63 |
| 8 | 0,500 | 0,581 | 0,357 | −39% | 0,580 / 0,373 | 1943 / 7864 | 15 / 63 |
| 8 | 1,000 | 0,379 | 0,215 | −43% | 0,376 / 0,235 | 8093 / 10467 | 7 / 63 |
| 12 | 0,500 | 0,692 | 0,488 | −29% | 0,689 / 0,492 | 2077 / 7487 | 23 / 63 |
| 12 | 1,000 | 0,502 | 0,305 | −39% | 0,498 / 0,315 | 3362 / 13003 | 11 / 63 |

*(bảng đầy đủ 16 dòng trong `E2_trace_frontier.json`)*

**Đọc:** (a) **vi phạm chứng chỉ = 0**: 0/286.100 sự kiện chứng nhận (D ≥ K_i) bị bỏ lỡ trên toàn bộ E2 **với scheduler constructive**; để so sánh, lazy EDF (lười) bỏ lỡ **1.568/343.502**; latency ≤ K_i−1 luôn đúng. (b) shaping giảm miss **17–43%** ở cùng năng lượng và chứng nhận nhiều sự kiện hơn. (c) Lemma 2 dự đoán miss với sai số **≤ 0,02**. (d) lazy EDF vi phạm chứng chỉ ở **296/384** run có profile **không đồng nhất** kể cả khi ρ ≤ 2/3 (trên profile đồng nhất nó suy biến thành round-robin và **0/192** run vi phạm — mẫu số phải nói rõ). (e) **Giá phải trả, không giấu:** camera sự kiện dài nhận K lớn → latency chứng nhận tối đa 63 thay vì 3–23 (xem E8(iii) cho cách cap lại).

# E3 — Switch cost s (đợt 1, không đổi)
N=6, K đồng nhất, lazy EDF có chi phí chuyển. **Prop 2 dự đoán đúng 28/28 ô**: khả thi ⇒ 0 vi phạm; không khả thi ⇒ 8/8 run vi phạm. `N_max(K,s) = ⌊K/(1+s)⌋` (K=12: s=0→12 camera, s=1→6, s=2→4). Kiểm máy độc lập C2 xác nhận công thức chính xác trên 29/29 ô.

---

# E4 — FLEET DIMENSIONING: 121 camera cần bao nhiêu hộp edge? (MỚI)
Toàn bộ 121 video = 121 camera; H = 6000; hai profile (`uniform`: K_i = K_target; `trace_heterogeneous`: K_i tỉ lệ với median duration của chính camera đó, clip [2,64]); ba phương pháp.

| profile | K_target | ρ | cận dưới ⌈ρ⌉ | **Cor 3** harmonic+FFD | FFD@5/6 (heuristic) | EDF-fit (heuristic) | vi phạm |
|---|---|---|---|---|---|---|---|
| uniform | 8 | 15,12 | 16 | **16** (=cận dưới) | 21 | 16 | 0 / 0 / 0 |
| uniform | 12 | 10,08 | 11 | 16 | 13 | 11 | 0 / 0 / 0 |
| uniform | 16 | 7,56 | 8 | **8** | 10 | 8 | 0 / 0 / 0 |
| uniform | 24 | 5,04 | 6 | 8 | 7 | 6 | 0 / 0 / 0 |
| trace-het | 8 | 25,08 | 26 | 27 | 38 | 26 | 0 / 0 / 0 |
| trace-het | 12 | 20,92 | 21 | 23 | 28 | 22 | 0 / **1 camera, 2 sự kiện** / 0 |
| trace-het | 16 | 16,62 | 17 | 21 | 20 | 18 | 0 / 0 / 0 |
| trace-het | 24 | 12,65 | 13 | 16 | 16 | 14 | 0 / 0 / 0 |

**Đọc:**
1. **Cor 3 luôn nằm trong hệ số 1,00–1,45 của cận dưới** (biên chứng minh được là 2), và **đạt đúng cận dưới ở 2/8 cấu hình**.
2. **FFD@5/6 thường TỆ HƠN Cor 3** (dùng nhiều hộp hơn ở 4/8 cấu hình, bằng ở 1/8) — vì dung lượng hộp 5/6 < 1. Ngưỡng 5/6 là *luật kiểm nạp tốt*, **không** phải *luật đóng gói tốt*. Đây là kết quả trái trực giác và phải in ra.
3. **FFD@5/6 gây vi phạm chứng chỉ ở 1 cấu hình**: hộp đó thoả Thm 1(ii) (⇒ *tồn tại* lịch) nhưng **scheduler constructive của ta không tìm được**, phải rơi về EDF → 2 sự kiện chứng nhận bị lỡ. **Đây là "constructive gap" hiện ra bằng số**, không phải lỗi cài đặt.
4. **EDF-fit dùng ít hộp nhất — nhưng con số 0 vi phạm của nó KHÔNG phải bảo đảm**: nó được *fit* chính trên trace và chân trời dùng để đánh giá. Phải viết rõ điều này; nếu không, R2 sẽ bắt.

# E5 — KIỂM NẠP DƯỚI CHURN (MỚI)
Một hộp edge; camera vào theo Bernoulli(λ_in)/slot, ra theo Bernoulli(λ_out·n_active)/slot; K bốc từ {4,6,8,12,16,24,32}; H = 8000; 10 lần lặp. *Một "violation episode" = một camera có cửa sổ trôi qua mà không được phục vụ (bộ đếm reset sau mỗi episode để một sự cố dài không bị đếm nhiều lần).*

| λ_in | chính sách | vi phạm / 1000 slot | từ chối (%) | busy | #camera trung bình |
|---|---|---|---|---|---|
| 0,020 | admit-then-EDF | 0,138 | 2,4 | 0,352 | 2,8 |
| 0,020 | density 5/6 (Cor 2) | 0,025 | 4,4 | 0,316 | 3,0 |
| 0,020 | density 1 harmonic | 0,037 | 3,9 | 0,404 | 4,0 |
| 0,020 | **residue wheel (test + scheduler constructive)** | **0,000** | 9,6 | 0,362 | 2,3 |
| 0,040 | admit-then-EDF | 0,938 | 10,2 | 0,576 | 4,6 |
| 0,040 | density 5/6 | 0,025 | 16,6 | 0,509 | 5,0 |
| 0,040 | density 1 harmonic | 0,250 | 18,6 | 0,641 | 6,5 |
| 0,040 | **residue wheel** | **0,000** | 21,4 | 0,518 | 4,2 |
| 0,080 | admit-then-EDF | **4,000** | 31,2 | 0,778 | 9,0 |
| 0,080 | density 5/6 | 0,375 | 38,4 | 0,660 | 8,0 |
| 0,080 | density 1 harmonic | 0,988 | 37,7 | 0,786 | 7,4 |
| 0,080 | **residue wheel** | **0,000** | 38,9 | 0,644 | 8,4 |

*(λ_in ∈ {0,004; 0,010} cho 0 vi phạm ở mọi chính sách — tải quá nhẹ để phân biệt.)*

**Đọc — đây là kết quả trung tâm của §4 bản thảo:**
1. **admit-then-EDF hỏng đúng như dự đoán**: 4,0 vi phạm/1000 slot ở churn cao.
2. **Chỉ riêng luật kiểm nạp đã giảm vi phạm ~11×** (4,000 → 0,375) nhưng **KHÔNG triệt tiêu**: luật mật độ bảo đảm *tồn tại* lịch, còn lazy EDF chạy online thì không thực hiện được lịch đó.
3. **Chỉ khi ghép luật kiểm nạp VỚI scheduler constructive** (bánh xe thặng dư dyadic 64 slot: mỗi camera nhận một lớp thặng dư cố định, không bao giờ gán lại) thì vi phạm **về đúng 0 ở cả 5 mức churn**.
4. **Giá phải trả**: tỷ lệ từ chối cao hơn (38,9% vs 31,2% của admit-then-EDF ở churn cao) và busy thấp hơn — một phần do **phân mảnh** bánh xe thặng dư sau khi camera rời (cấp phát kiểu buddy). Phải khai điều này.

# E6 — ESCALATION BLACKOUT (Prop 3) (MỚI)
N=6, K đồng nhất ∈ {8,…,32}, ℓ ∈ {2,4,8}, P_e ∈ {50,100,200}, 2 chế độ (`periodic` — chặt nhất; `jittered` — khoảng cách U[P_e, 2P_e)), 8 seed, H = 8000. Scheduler = round-robin **trên dãy con slot khả dụng** (online, không cần biết trước escalation). Ngân sách `B = min(K, ℓ⌈(K+ℓ−1)/P_e⌉)`, `K'' = K − B`.

**Prop 3 dự đoán đúng 144/144 ô** (khả thi ⇒ 0 run vi phạm; không khả thi ⇒ 8/8 run vi phạm), ở cả hai chế độ.

Ví dụ (P_e = 50, periodic):

| ℓ | K | B | K″ | Prop 3 khả thi (K″ ≥ N = 6) | run vi phạm | sự kiện chứng nhận bị lỡ |
|---|---|---|---|---|---|---|
| 2 | 8 | 2 | 6 | ✓ | 0/8 | 0 |
| 4 | 8 | 4 | 4 | ✗ | 8/8 | 2 |
| 4 | 10 | 4 | 6 | ✓ | 0/8 | 0 |
| 8 | 8 | 8 | 0 | ✗ | 8/8 | 640 |
| 8 | 10 | 8 | 2 | ✗ | 8/8 | 587 |
| 8 | 12 | 8 | 4 | ✗ | 8/8 | 3 |
| 8 | 14 | 8 | 6 | ✓ | 0/8 | 0 |

**Đọc:** escalation **trừ thẳng vào cửa sổ chứng chỉ**, không trừ vào mật độ: một lần escalation dài ℓ = 8 slot mỗi P_e = 50 slot làm mất 8 slot của **mọi** cửa sổ, nên K = 12 (K″ = 4) không còn nuôi nổi 6 camera, còn K = 14 (K″ = 6) thì được. Ngân sách chặn trên **không bao giờ lạc quan** trong 144 ô.

# E7 — NĂNG LƯỢNG THEO ĐƠN VỊ E_idle VÀ CONSOLIDATION GAIN
Năng lượng mỗi slot đo theo **đơn vị năng lượng slot nghỉ** `E_idle`, nên mô hình tuyến tính chỉ
còn **một tham số**: `e(a) = 1 + a(r − 1)` với `r = E_active / E_idle`. **Không có hằng số đo nào
của bất kỳ nền tảng nào được dùng; không có phép đo phần cứng nào trong bài.** Lưới
`r ∈ {3, 10, 30}`, giá trị chính **r = 10**. So sánh: 1 accelerator chia sẻ ở busy fraction a, với
**N accelerator riêng** (mỗi cái vẫn tốn 1 đơn vị idle, tổng duty active = ρ):

`G = (N + ρ(r − 1)) / (1 + a(r − 1))`

| N | ρ* | busy | e / camera-frame (chia sẻ) | e / camera-frame (N riêng) | **consolidation gain** (r = 10) |
|---|---|---|---|---|---|
| 4 | 0,500 | 0,432 | 1,22 | 1,97 | **1,61×** |
| 4 | 1,000 | 0,787 | 2,02 | 2,77 | **1,37×** |
| 6 | 0,500 | 0,490 | 0,90 | 1,73 | **1,92×** |
| 6 | 1,000 | 0,900 | 1,52 | 2,35 | **1,55×** |
| 8 | 0,500 | 0,496 | 0,68 | 1,56 | **2,28×** |
| 8 | 1,000 | 0,976 | 1,22 | 2,10 | **1,72×** |
| 12 | 0,500 | 0,500 | 0,46 | 1,38 | **3,00×** |
| 12 | 1,000 | 0,999 | 0,83 | 1,75 | **2,10×** |

**Gain theo r:** r = 3 → 2,00–6,50× · **r = 10 → 1,30–3,00×** · r = 30 → 1,06–1,71×.

**Đọc:** gộp fleet lên **một** accelerator dùng chung tiết kiệm **1,30–3,00×** năng lượng ở r = 10, và
lợi ích **tăng theo N** vì thứ bị loại bỏ là `(N−1)·E_idle` — chi phí idle, không phải chi phí suy
luận. Kết luận định tính này **không phụ thuộc r**. Ở N = 12, ρ* = 0,5: **0,46** đơn vị E_idle mỗi
camera-frame thay vì 1,38.

# E8 — SENSITIVITY (MỚI)

### (i) Shaping KHÔNG oracle — hold-out theo thời gian (trả lời R2-5) ⚠ mục quan trọng nhất
Chia timeline mỗi camera làm đôi; học K_i trên nửa **đầu**, đánh giá trên nửa **sau**. Chỉ dùng **61/121 video** có ít nhất một sự kiện ở mỗi nửa (60 video còn lại không tách được — phải khai).

| N | ρ* | miss uniform | miss shaped **oracle** | miss shaped **hold-out** | gain oracle | **gain hold-out** |
|---|---|---|---|---|---|---|
| 6 | 0,500 | 0,556 | 0,476 | 0,514 | −14,5% | **−7,6%** |
| 6 | 0,833 | 0,451 | 0,365 | 0,427 | −19,1% | **−5,3%** |
| 8 | 0,500 | 0,645 | 0,553 | 0,579 | −14,3% | **−10,2%** |
| 8 | 1,000 | 0,456 | 0,391 | 0,447 | −14,4% | **−1,9%** |
| 12 | 0,833 | 0,634 | 0,501 | 0,535 | −21,0% | **−15,7%** |
| 12 | 1,000 | 0,556 | 0,459 | 0,493 | −17,5% | **−11,4%** |

*(12/12 ô; bảng 6 seed ở trên là bản rút gọn — số đầy đủ 12 seed trong JSON.)*

**Kết luận:** **shaping vẫn thắng ở 12/12 ô khi không có oracle** — trung bình **−12,3%** hold-out so với **−19,4%** oracle. Nghĩa là **khoảng 36% lợi ích của shaping là do oracle**; 64% còn lại sống sót ngoài mẫu. Đây là con số phải in trong bài, không được chỉ in số oracle.

### (ii) Ba dataset tách riêng (trả lời R2-3 "foreground-heavy")
Thống kê thời lượng sự kiện: CDnet2014 (2516 sự kiện, median 2, p90 32, mean 32,9) · LASIESTA (936, median 10, p90 10, mean 15,5) · BMC (261, median 4, p90 160, mean 111,7) — **ba luật đuôi rất khác nhau**.

| dataset | gain shaping (N=6 / 8 / 12, trung bình 4 ngân sách) | vi phạm chứng chỉ |
|---|---|---|
| CDnet2014 | −30,1% / −27,1% / −20,6% | 0 / 62.049 sự kiện chứng nhận |
| LASIESTA | −22,5% / −25,5% / −24,0% | 0 |
| BMC | −48,0% / −47,0% / −38,3% | 0 |

**Kết luận:** shaping thắng trên **cả ba** dataset, ở **36/36 ô**, và thắng **mạnh nhất trên BMC** (đuôi dài nhất, p90 = 160 khung) — tức hiệu ứng **không** do "foreground-heavy" mà do **độ tán của luật thời lượng giữa các camera**, đúng như Lemma 2 dự đoán. Vi phạm chứng chỉ = 0 ở mọi dataset.

### (iii) Cap độ trễ chứng chỉ K_max (trả lời R2-8)
| N | ρ* | K_max = 16 | K_max = 32 | K_max = 64 |
|---|---|---|---|---|
| 6 | 0,500 | miss 0,357 · lat ≤ 15 | 0,309 · ≤ 31 | 0,304 · ≤ 63 |
| 6 | 0,833 | 0,237 · ≤ 15 | 0,217 · ≤ 31 | 0,212 · ≤ 63 |
| 6 | 1,000 | 0,197 · ≤ 15 | 0,180 · ≤ 31 | 0,180 · ≤ 63 |

**Kết luận:** hạ trần độ trễ chứng chỉ **4×** (63 → 15 khung) chỉ tốn **+9…+17% miss tương đối**. Trade-off này là *tunable*, không phải bắt buộc — phải đưa vào bài như một tham số thiết kế.

### (iv) Baseline thứ hai: round-robin (trả lời R2-6)
| N | ρ* | RR miss (busy = 1,0) | scheduler ta (busy = ρ*) |
|---|---|---|---|
| 6 | 0,500 | 0,299 | 0,455 (busy 0,50) |
| 6 | 1,000 | 0,299 | 0,299 (busy 1,00) |
| 8 | 0,500 | 0,379 | 0,581 (busy 0,50) |
| 8 | 0,667 | 0,379 | 0,489 (busy 0,67) |

**Kết luận trung thực:** round-robin **không vi phạm chứng chỉ** khi N ≤ K và cho **miss thấp nhất có thể** — vì nó **luôn chạy hết công suất** (busy = 1,0 ở mọi ngân sách). Ở ρ* = 1 scheduler của ta trùng đúng với round-robin. Đóng góp của bài **không** phải "thắng round-robin về miss", mà là: **cho phép chọn một điểm khác trên biên năng lượng–miss mà vẫn giữ chứng chỉ** (ở N=6 ρ*=0,5: một nửa năng lượng, miss 0,455 thay vì 0,299), và **cho phép biết trước bao nhiêu camera là đủ** — điều round-robin không trả lời được khi K không đồng nhất.

---

## Giới hạn đợt 2 (đưa vào Limitations của bản thảo)
- Slot = khung; mọi camera cùng tần số khung. Biến thiên thời gian suy luận được hấp thụ vào s (E3) và vào blackout (E6) như hai mô hình chặn trên, **không** được đo trực tiếp.
- Scheduler 5/6 của Kawamura **chưa cài** (chứng minh là computer-search). Constructive hiện tại = harmonic 1-base + bánh xe thặng dư dyadic. **Chan–Chin 7/10 và Fishburn–Lagarias 3/4 cũng chưa cài** (quyết định phạm vi đợt 2) → "constructive gap" đo được ở E1 (91% ở dải (0,75; 5/6]) và ở E4 (hệ số 1,00–1,45 so với cận dưới).
- Wrap video tuần hoàn để kéo tới H; sự kiện cắt biên bị bỏ; warm-up = K_max (E6: 2·K).
- Hold-out chỉ dùng **61/121** video (số còn lại không có sự kiện ở cả hai nửa).
- E4 "EDF-fit 0 vi phạm" là **fit trên chính trace đánh giá**, không phải bảo đảm.
- E5 churn dùng Poisson/Bernoulli — mô hình quy ước, quét 5 mức để kết luận không phụ thuộc một điểm tham số.
- Năng lượng: **tham số hoá theo r = E_active/E_idle**, không dùng hằng số đo của bất kỳ nền tảng nào; muốn ra joule tuyệt đối thì phải đo trên thiết bị đích — bài này không đo, và không có triển khai end-to-end.


---

# ĐỢT 3 (06-09-2026) — BỔ SUNG

## Scheduler mới: **divisor wheel** (cột `wheel_ok` trong E1, scheduler `wheel` trong E2)
Làm tròn mỗi cửa sổ xuống **ước lớn nhất của một wheel length M** (thay vì xuống `a·2^j` như
harmonic 1 cơ số), rồi gán lớp thặng dư **có backtracking**. Quét 387 giá trị M ứng viên (mọi
`a·2^j` — bao trùm cách cũ — cộng mọi số 13-smooth ≤ 2520), thử theo thứ tự mật độ sau làm tròn
tăng dần, lấy M đầu tiên đóng gói được. **Một phép đóng gói thành công CHÍNH LÀ chứng chỉ** (gap =
d_i ≤ K_i đúng bằng định nghĩa) — không viện đến định lý ngoài nào.

| bin ρ | exact | harmonic 1 cơ số | **divisor wheel** | lazy EDF |
|---|---|---|---|---|
| (0,700; 0,750] | 1.00 | 1.00 | **1.00** | 0.79 |
| (0,750; 0,833] | 1.00 | 0.91 | **0.97** | 0.56 |
| (0,833; 0,900] | 1.00 | 0.52 | **0.74** | 0.21 |
| (0,900; 0,950] | 0.71 | 0.23 | **0.36** | 0.05 |

Trên E2: **0/302.224** sự kiện chứng nhận bị lỡ, và dựng được **144/192** run có cửa sổ shaped
trên **lưới nguyên** (harmonic chỉ 129/192) — lưới nguyên cho hàm mục tiêu tốt hơn lưới harmonic
nhưng khó dựng hơn, divisor wheel lấp một phần khoảng đó.

⚠ **KHÔNG phải Chan–Chin 7/10.** Bài gốc trả phí và không nguồn thứ cấp truy cập được nào phát
biểu thuật toán đủ chính xác để cài lại trung thực; một giả thuyết về điều kiện của họ đã bị phản
ví dụ `{2,3,6}` bác bỏ khi kiểm thử, nên dừng thay vì đoán. Giới hạn của divisor wheel: nó chỉ đi
trong lớp **lịch tuần hoàn hoàn hảo**; instance khả thi nhưng không có lịch tuần hoàn hoàn hảo thì
không phương pháp bánh xe nào với tới.

## Sửa tái lập: `exact_schedulable` bỏ ngân sách thời gian thực
Trước đây hàm này dừng theo **đồng hồ** (3 s), nên verdict phụ thuộc tải máy — chạy lại cùng seed
trên máy bận đã lật 5 instance giữa `False` và `None`. Nay ngân sách là **số trạng thái**
(400.000), kết quả tái lập trên mọi máy. Hệ quả: 5 instance trước đây "không quyết định được" nay
quyết định được; **6/594 instance vẫn vượt ngân sách và bị loại khỏi mẫu số** (không giả định theo
hướng nào) — đã ghi vào Limitations của bản thảo.

## Hình
`fig_E3_switch` và `fig_E6_blackout` đã được **gộp** thành `fig_E36_extensions` (2 panel: (a) switch
cost, (b) blackout) theo quyết định CP-B1 mức (b). `fig_E1_schedulability` nay có 4 cột (thêm
divisor wheel). Tổng còn **7 file hình** + 1 sơ đồ vẽ bằng LaTeX = 8 hình trong bài.
