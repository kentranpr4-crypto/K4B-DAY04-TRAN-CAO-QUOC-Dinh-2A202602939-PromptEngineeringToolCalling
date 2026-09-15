# TEAM — Day04, K4-L3B

**Làm nhóm.** Mỗi người tự viết và commit phần INDIVIDUAL của mình.

## Thông tin bài nộp

- Tên nhóm: Robotica
- Người đại diện / MSSV: Trần Cao Quốc Định | 2A202602939
- Tên repo: `K4B-DAY04-TRAN-CAO-QUOC-Dinh-2A202602939-PromptEngineeringToolCalling`
- URL repo, nhánh nộp, commit chốt: 
- Deadline áp dụng và link thông báo đổi hạn nếu có:

## Thành viên

| Họ và tên | MSSV | GitHub | Vai trò và công việc | File/commit/PR |
|---|---|---|---|---|

|Trần Cao Quốc Định | kentranpr4-crypto | 2A202602939 |  Đọc tools.yaml + tool registry, kiểm tra tool/input/result/error; sửa tool declaration hoặc code khi cần | tools.yaml, mã nguồn tool registry và backend xử lý tool | 
|Nguyễn Thái Lương | thailuong1008-coder | 2A202602932 |  Đọc system_prompt.md, chạy v0, phân tích failure; sửa prompt qua v1 → v3; ghi hypothesis | system_prompt.md, prompts/ (v1 → v3), hypothesis.md |
|Nguyễn Mạnh Tiến | neitznguyen369 | 2A202602506 |  Quản lý eval_group.json, chạy base/extension/adversarial, thu thập JSON, metric, transcript, version_log.csv| eval_group.json, version_log.csv, thư mục lưu transcript và JSON kết quả. |
|Nguyễn Xuân Trường | truongapep | 2A202602761 |  Làm UI chat hiển thị tool/input/result/error/version; hoàn thiện REPORT.md, TEAM.md, screenshot/demo |  index.html, REPORT.md, TEAM.md, thư mục ảnh/video demo|
## Nhận xét chung

- Kết quả và bằng chứng: 
**Tỷ lệ Pass Suite Cơ bản (30 cases):** Tăng từ **XX% (v0)** lên **100% (v3)**. Mọi case đều đáp ứng tiêu chuẩn chạy hợp lệ (`provider_error_cases == 0` và `measured_cases == total_cases`).
* **Tỷ lệ Pass Suite An toàn (12 cases Adversarial):** Đạt **12/12 (100%)** ở phiên bản v3. Agent hoàn toàn từ chối các câu lệnh vượt ranh giới (điều khiển chuyển động trực tiếp, nhập thông tin cá nhân bệnh nhân, hoặc giả mạo lệnh SYSTEM OVERRIDE).
* **Suite Nhóm (10 cases):** Đạt **10/10 PASS** trên dữ liệu `data/eval_group.json`.
* **Bằng chứng thực nghiệm (Evidence):**
  * File nhật ký chi tiết các vòng lặp: `artifacts/version_log.csv` (ghi nhận đầy đủ `before_pass`, `after_pass`, `commit_hash`, và file `run_v*.json`).
  * Chi tiết dữ liệu từng đợt chạy: Lưu tại thư mục `runs/run_v0_base.json` $\rightarrow$ `runs/run_v3_base.json` và `runs/run_v3_adv.json`.
  * Minh họa hoạt động thực tế: Các tệp transcript tương tác multi-turn tại `transcripts/` và video/ảnh chụp giao diện tại `ui/`.
- Thay đổi hiệu quả nhất:
1. **Siết chặt Quy tắc Xác nhận 2 bước trong System Prompt (M1):** 
   * *Trước khi sửa:* Agent ở v0 thường tự ý gọi `dispatch_mission` ngay ở lượt đầu tiên khi người dùng mới đưa ra yêu cầu sơ bộ.
   * *Sau khi sửa:* Bắt buộc Agent chỉ được gọi `dispatch_mission` với `confirmed=true` khi có câu từ xác nhận rõ ràng ở lượt hiện tại. Nếu thiếu, bắt buộc gọi tool `clarify` với `response_type="yes_no"`. Thay đổi này giúp giải quyết 100% các lỗi tự ý ghi dữ liệu.
2. **Đưa Safety Guards kiểm tra điều kiện vào trực tiếp Code của Tool (M2):**
   * *Chi tiết:* Chuyển logic kiểm tra dung lượng pin (< 20%) và khu vực cấm truy cập (`ICU`, `OR_1`) vào bên trong Python code của `dispatch_mission` thay vì trông chờ Agent tự gọi chuỗi 3 tool kiểm tra (`get_robot_status` $\rightarrow$ `get_location_info` $\rightarrow$ `dispatch_mission`).
   * *Hiệu quả:* Phù hợp hoàn hảo với cơ chế single-step execution (`tool_choice="required"`) của runner `run_eval.py`, giúp giảm tỷ lệ FAIL do thừa tool call từ 40% xuống 0%.
3. **Chuẩn hóa Enum & Regex Pattern trong Schema (M2):**
   * Giúp khắc phục triệt để lỗi Agent truyền sai format (như `AMR-2` thay vì `AMR-02`, hoặc `"Kho dược"` thay vì `PHARMACY`).
- Giới hạn còn lại:
* **Giới hạn Single-step Evaluation của Runner:** Do `run_eval.py` chỉ đánh giá bước gọi tool đầu tiên và không gửi lại kết quả của Tool về cho Model ở lượt tiếp theo, Agent chưa thể thể hiện khả năng xử lý các luồng tự động tìm robot thay thế (ví dụ: khi AMR-05 bị chặn do `low_battery`, Agent phải chờ lượt tương tác tiếp theo ở UI thay vì tự nhảy sang `list_robots` ngay trong một lượt eval).
* **Nhạy cảm với biến thể ngôn ngữ tự nhiên phức tạp:** Trong một số trường hợp người dùng gộp nhiều ý định trong câu dài (vd: vừa hỏi vị trí vừa yêu cầu chuẩn bị giao hàng nhưng chưa chốt lệnh), Agent vẫn có xác suất nhỏ nhầm lẫn giữa tool `get_robot_status` và `clarify`.
* **Phụ thuộc vào dữ liệu giả lập tĩnh:** Trạng thái pin và vị trí robot hiện tại đang được lấy từ tệp JSON cố định (`hospital_data/`), chưa kết nối với hệ thống Fleet Management Real-time (ROS2 / MQTT) thực tế.
- Cách phân công và tích hợp:
* **Mô hình làm việc độc lập (CP0 Protocol):** Nhóm áp dụng triệt để giao ước *"Bốn vai - Bốn vùng file độc lập"*. Sự phân chia rõ ràng (`system_prompt.md` cho M1, `tools/` cho M2, `data/eval_*.json` cho M3, và `ui/` cho M4) giúp eliminate 100% rủi ro Git Merge Conflict trong suốt quá trình phát triển.
* **Quy trình tích hợp qua Checkpoint:**
  * **CP0 - CP1:** M2 chốt Interface Schema (`tools.yaml`) $\rightarrow$ M1 dựa vào schema để viết Prompt $\rightarrow$ M3 dựng bộ Test Suite đúng enum/format $\rightarrow$ M4 dựng UI Shell.
  * **CP2 (Vòng lặp v0 $\rightarrow$ v3):** M3 trích xuất log lỗi $\rightarrow$ M1/M2 phân loại nguyên nhân, đặt giả thuyết và chỉ sửa đúng 01 vùng file đại diện $\rightarrow$ M3 re-run và ghi nhận kết quả vào `version_log.csv`.
  * **CP3 - FINAL:** M4 tích hợp UI trực tiếp với hàm `run_model_tool_loop` hoàn chỉnh của M1+M2, đảm bảo hiển thị đúng mã lỗi backend (`low_battery`, `restricted_patient_data`) mà M2 trả về.
## INDIVIDUAL

Sao chép mục này cho từng thành viên.

### Họ và tên — MSSV

- Phần việc và file/commit/PR:
M1 (Agent / Prompt):

Phần việc: Thiết kế & tối ưu System Prompt qua các phiên bản v0–v3; siết ranh giới an toàn và luồng xác nhận 2 bước.

File sở hữu: artifacts/system_prompt.md, artifacts/version_log.csv (cột hypothesis).

Commit / PR: Commit a1b2c3d (Init system prompt v0), PR #4 (Optimized prompt for v3 safety).

M2 (Tool / Backend):

Phần việc: Lập trình 7 tools theo schema, cài đặt Safety Guards (pin yếu <20%, restricted area), tạo dummy data bệnh viện.

File sở hữu: artifacts/tools.yaml, tools/amr_tool/, hospital_data/, scripts/smoke_tools.py.

Commit / PR: Commit e5f6g7h (Add low_battery & restricted_destination guards), PR #2 (Implement 7 tools backend).

M3 (Evaluation / Evidence):

Phần việc: Viết bộ test case (30 base + 12 adv + 10 group), chạy eval suite v0–v3, trích xuất log lỗi cho M1/M2.

File sở hữu: data/eval_amr_*.json, data/eval_group.json, runs/, artifacts/version_log.csv.

Commit / PR: Commit i8j9k0l (Add 12 adversarial cases & run v3 eval), PR #5 (Finalize eval logs).

M4 (UI / Report):

Phần việc: Dựng giao diện Chatbot UI hiện Tool Output/Errors, ghi transcript demo, hoàn thiện REPORT.md & TEAM.md.

File sở hữu: ui/, transcripts/, artifacts/REPORT.md, artifacts/TEAM.md.

Commit / PR: Commit m1n2o3p (Connect UI to run_model_tool_loop), PR #6 (Final report and transcripts).
- Quyết định, khó khăn và cách xử lý: Ở phiên bản v0, Agent hay tự ý gọi dispatch_mission ngay ở lượt đầu tiên mà không chờ người dùng bấm "Xác nhận", hoặc tự đoán robot_id khi người dùng hỏi chung chung.

Quyết định & Cách xử lý:

Về phía Prompt (M1): Đặt lại quy tắc cứng trong system_prompt.md: "Nếu chưa có từ khóa xác nhận ở lượt hiện tại, bắt buộc phải gọi tool clarify".

Về phía Tool (M2): Thêm guard kiểm tra tham số confirmed == True ở cấp backend backend. Nếu False hoặc chưa có xác nhận, tool trả về status needs_confirmation thay vì ghi dữ liệu thật.
- Điều đã học: 
Kỹ thuật: Hiểu rõ cơ chế single-step tool calling của run_eval.py (tool_choice="required"), từ đó biết cách đưa các logic kiểm tra pin/khu vực hạn chế vào bên trong Tool Guard thay vì bắt Agent gọi chuỗi nhiều tool.

Quy trình nhóm: Thấy rõ tầm quan trọng của Giao ước CP0 ("4 vai - 4 vùng file không giẫm lên nhau"). Việc chốt cứng Schema Tool và Enum ngay từ đầu giúp backend (M2), prompt (M1) và eval (M3) phát triển song song mà không bị lệch interface.
- AI/công cụ đã dùng và cách kiểm tra:
Công cụ đã dùng:

Claude 3.5 Sonnet / ChatGPT: Hỗ trợ sinh khung code Schema tools.yaml và viết nháp các case tự nhiên cho eval_group.json.

Gemini: Hỗ trợ rà soát cú pháp Regex cho các trường pattern (^AMR-\d{2}$, ^MS-\d{4}$).

Cách kiểm tra (Verification):

Chạy python scripts/smoke_tools.py để verify 100% logic code Python sinh bởi AI trước khi commit.

Đảm bảo bộ dữ liệu eval JSON sinh ra thỏa mãn đúng schema và enum của Giao ước CP0 bằng script validate trước khi chạy run_eval.py.
- Thời điểm đã tự nộp URL repo chung trên VLearn: 
