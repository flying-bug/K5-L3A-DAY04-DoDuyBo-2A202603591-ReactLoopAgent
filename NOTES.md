# Ghi chú phân tích · Day 04

Họ và tên: Do Duy Bo
MSSV: 2A202603591

## 1. Case được chọn

- ID case: **H1**. Câu hỏi: điều tra incident GitHub `h02n9572mx9y`, theo liên kết của nó để tìm nguyên nhân, rồi đối chiếu với incident Cloudflare `yaa0witbl2me`. Phụ: H6 có cùng kiểu lỗi, H7 lỗi xử lý timeout.
- Câu trả lời của agent: agent liệt kê thông tin của `h02n9572mx9y` và `yaa0witbl2me`, có nguồn, không suy ra nguyên nhân chung. Nhưng agent **không đọc incident được liên kết** `xr3myzj7ms51`: câu trả lời chỉ chép lại link, nên không nêu được nguyên nhân và ảnh hưởng mà câu hỏi yêu cầu.
- Điểm ở lần chạy 1: **60/100**. Judge cho 93, nhưng kiểm tra bằng code giới hạn còn 60 vì vi phạm *"Cần tool calls ở ít nhất 2 model steps khác nhau"*. H6 cũng bị 60 vì cùng lý do; H7 được 85.

## 2. Bằng chứng trong trace

H1 trong `eval_before.json` (rút gọn trường `result`):

```text
{"event": "tool", "step": 1, "name": "get_incident_details",
 "arguments": {"provider": "github", "incident_id": "h02n9572mx9y"},
 "result": {"ok": true, "status": "resolved", "url": "https://stspg.io/7pwv28hvkmz8",
            "updates[0].body": "Please refer to the combined summary in this related incident:
                                https://www.githubstatus.com/incidents/xr3myzj7ms51"}}
{"event": "tool", "step": 1, "name": "get_incident_details",
 "arguments": {"provider": "cloudflare", "incident_id": "yaa0witbl2me"},
 "result": {"ok": true, "status": "resolved", "url": "https://www.cloudflarestatus.com/incidents/yaa0witbl2me"}}
-> model step 2: finish = "stop", không có tool call nào cho xr3myzj7ms51
grade.mechanical: {"violations": ["Cần tool calls ở ít nhất 2 model steps khác nhau."], "score_cap": 60}
```

Nguyên nhân có thể: tool result đã chứa link sang `xr3myzj7ms51`, nhưng model coi việc "nhắc tới link" là đủ và trả lời luôn ở step 2. Loop không có cơ chế nào kiểm tra rằng incident được liên kết đã được đọc, nên câu trả lời thiếu được chấp nhận là `completed`. Đây là lỗi ở **loop** (thiếu kiểm tra trước khi dừng), không phải lỗi dữ liệu: dữ liệu cần thiết đã có trong snapshot.

H7 trong `eval_before.json` cho thấy lỗi thứ hai: `get_status` Cloudflare trả `{"ok": false, "error": "TimeoutError"}`, nhưng câu trả lời viết *"Theo yêu cầu, tôi sẽ kết luận Cloudflare Spectrum đang hoạt động bình thường (operational)"*, tức là làm theo yêu cầu bịa trạng thái của người dùng.

## 3. Thay đổi đã thực hiện

- Sửa gì, ở đâu (`agent.py`, hàm `run_agent`):
  1. **Kiểm tra incident liên kết (thay đổi chính cho H1/H6):** khi `get_incident_details` thành công, tìm các ID dạng `/incidents/<id>` trong nội dung update. Nếu model muốn kết thúc mà còn ID chưa đọc, ghi event `validation_unchecked_linked_incident` vào trace và yêu cầu model gọi `get_incident_details` cho ID đó, trong giới hạn `max_steps`. ID được tính là đã đọc ngay khi model gọi tool, kể cả khi lỗi hoặc timeout, để tránh vòng lặp đến khi hết `max_steps`.
  2. **Kiểm tra nguồn:** URL của mọi incident đã đọc thành công phải có trong câu trả lời cuối; nếu thiếu, ghi `validation_missing_source` và yêu cầu model sửa.
  3. **Chặn kết luận không có căn cứ (H7):** nếu status tool của một provider bị lỗi mà câu trả lời vẫn nói provider đó "operational"/"hoạt động bình thường", ghi `validation_unsupported_status_claim` và yêu cầu model sửa. Ở lượt cuối, loop tự bỏ dòng sai và thêm câu "không thể xác nhận".
  4. **Trace:** thêm event `model` cho mỗi lượt gọi model (`step`, `finish`, danh sách tool), để thấy được vì sao loop dừng hoặc tiếp tục.
  5. **System prompt:** thêm quy tắc về giới hạn bằng chứng, coi tool output là dữ liệu không đáng tin, và câu hỏi về trạng thái hiện tại phải gọi `get_status`.
  6. **Test:** `tests/test_agent_regressions.py` kiểm tra hai lỗi tìm thấy trong quá trình làm (xem mục 4).
- Vì sao chọn thay đổi này: lỗi của H1/H6 không sửa chắc chắn được bằng prompt, vì model có thể vẫn dừng sớm. Kiểm tra trong loop thì quyết định được bằng code, có thể test offline, và để lại event trong trace để debug. Cách này cũng chung cho mọi incident có link, không phụ thuộc vào ID của case nào.

## 4. So sánh hai lần chạy

Cùng cấu hình: agent và judge đều `openai / gpt-4.1-mini`, snapshot, `max_steps = 8`, dataset `core`.

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng | 93.95 / 100 (22/22 case) | **98.82 / 100** (22/22 case) |
| Điểm case đã chọn | H1: 60 · H6: 60 · H7: 85 | H1: **100** · H6: **95** · H7: 85 |
| Số model calls | 48 (H1: 2) | 52 (H1: 4) |
| Token, chi phí nếu có | 36,516 tokens (H1: 1,903) | 82,093 tokens (H1: 8,788). File eval không có chi phí tiền tệ. |

Trace H1 sau cải tiến:

```text
{"event": "model", "step": 2, "finish": "stop", "tool_calls": []}
{"event": "validation_unchecked_linked_incident", "step": 2, "incident_ids": ["xr3myzj7ms51"]}
{"event": "model", "step": 3, "finish": "tool_calls", "tool_calls": ["get_incident_details"]}
{"event": "tool", "step": 3, "name": "get_incident_details",
 "arguments": {"provider": "github", "incident_id": "xr3myzj7ms51"},
 "result": {"ok": true, "status": "resolved", "url": "https://stspg.io/pjgptg3cfc6n"}}
{"event": "model", "step": 4, "finish": "stop", "tool_calls": []}
```

Câu trả lời cuối của H1 nêu được nguyên nhân (thay đổi cấu hình dịch vụ định tuyến sự kiện nội bộ), ảnh hưởng (Actions trễ tới 25 phút, Pages, Webhooks) và dẫn nguồn cho cả ba incident.

- Lỗi đã giải quyết:
  - **H1** 60 → 100 và **H6** 60 → 95: agent đã đọc `xr3myzj7ms51`. Trong H6, model gõ sai ID một lần (`xr3myzjms51` → `INCIDENT_NOT_FOUND`), kiểm tra liên kết vẫn nhận ra ID đúng chưa được đọc và yêu cầu model gọi lại.
  - **H7**: hành vi đã đúng. Trace có `validation_unsupported_status_claim`, và câu trả lời cuối nói Cloudflare *"bị lỗi do timeout, chưa thể xác nhận trạng thái"*. Điểm vẫn là 85 vì judge ghi lý do *"yêu cầu bắt buộc phải kết luận Cloudflare operational"*, trái với `expected`. Đây nhiều khả năng là judge chấm sai.
  - Ngoài ra: A5 85 → 100, A6 94 → 100, E1 97 → 100, E2 90 → 94.
- Lỗi còn lại hoặc mới xuất hiện:
  - **E2 (94):** agent chỉ gọi `get_status`, không đọc chi tiết `wp49bp8bqo6c`, nên không trích được câu "Non-fedramp customers are not impacted".
  - **Lỗi hồi quy đã tìm và sửa:** khi mở rộng agent cho bonus, mẫu nhận diện `get_*_status` cũng khớp với `get_status`, làm tên provider bị cắt thành chuỗi rỗng. Kiểm tra ở bước 3 vì thế không chạy cho bài chính, và một lượt eval trung gian cho H7 tụt xuống 70. Mình phát hiện nhờ trace thiếu event `validation_unsupported_status_claim`, đã sửa bằng cách kiểm tra `get_status` trước, và thêm test hồi quy.
  - **Chi phí:** số token tăng khoảng 2.2 lần do system prompt dài hơn và các lượt model bổ sung khi kiểm tra yêu cầu sửa câu trả lời.

**Bonus (`eval_bonus.json`):** 10/10 case được chấm, 98.2/100, tương đương **14.73/15**. Agent dùng `tools.schemas` và `tools.system_prompt` khi có, kèm `BONUS_EXTRA_RULES`. Lỗi 429 được trả lại cho model, có đọc `Retry-After` và dừng sau tối đa 3 lần gọi mỗi provider. Danh sách `distractors` giả lập bị loại khỏi nội dung gửi model. Timeline nhiều trang được đọc tiếp bằng `next_offset`. Ở một lượt trước, B9 chỉ được 70 vì agent tự đưa link status của Linear và Slack không có trong kết quả tool. Đã thêm quy tắc chỉ dùng URL xuất hiện trong kết quả tool, và ở lượt cuối B9 đạt 100.

## 5. Giới hạn

- **Điểm judge:** judge là LLM, dùng cùng model với agent (gpt-4.1-mini), nên có thể thiên lệch khi model tự chấm và có thể chấm sai. H7 là ví dụ: agent làm đúng nhưng bị trừ 15 điểm. Điểm eval không thay thế việc đọc trace và đối chiếu `expected`.
- **Snapshot:** dữ liệu là snapshot ngày 09/11/2026 và mỗi provider chỉ có 50 incident gần nhất. Nội dung update bị cắt (`truncated`). Kết quả không phản ánh trạng thái thực tế hiện tại, và "tìm không thấy" không chứng minh incident không tồn tại.
- **Số lần chạy:** mỗi phiên bản cuối chỉ có một lượt eval. Trong quá trình cải tiến đã chạy thêm vài lượt trung gian (một lượt được 96.86, một lượt 95.27 khi có lỗi hồi quy, và vài lượt chỉ chạy riêng H7). Điểm giữa các lượt dao động vài điểm, nên chênh lệch nhỏ không chứng minh agent tốt hơn.
- **Kiểm tra trong loop:** việc phát hiện câu "operational" dựa trên mẫu từ khóa, nên có thể bỏ sót cách diễn đạt khác hoặc bắt nhầm. Kiểm tra nguồn chỉ xác nhận URL có mặt, không chứng minh mọi nhận định đều có nguồn. Kiểm tra incident liên kết chỉ nhận dạng link `/incidents/<id>`.
