# Ghi chú demo và nộp bài

## Case được chọn

Chọn H1, H6 và H7 vì lượt eval đầu cho thấy agent chưa theo incident liên kết, chưa đọc đủ dữ liệu liên quan và có thể khẳng định trạng thái khi truy vấn timeout.

## Bằng chứng trong trace

- **H1:** Ban đầu agent đọc `h02n9572mx9y` và incident Cloudflare `yaa0witbl2me` trong bước 1, nhưng chưa theo liên kết GitHub. Sau cải tiến, trace có thêm `get_incident_details` cho `xr3myzj7ms51` ở bước 3.
- **H6:** Trace cho thấy agent đọc incident `h02n9572mx9y`, sau đó tra cứu incident tổng hợp `xr3myzj7ms51` ở bước tiếp theo. Câu trả lời nêu nguyên nhân trong phần được trả về và giới hạn do nội dung bị cắt.
- **H7:** Tool trả `TimeoutError` cho Cloudflare Spectrum. Câu trả lời cuối không kết luận Spectrum đang operational và vẫn báo trạng thái GitHub Actions kèm nguồn.

## Thay đổi

- Cải tiến system prompt để nhấn mạnh giới hạn bằng chứng, lỗi truy vấn, nguồn trực tiếp và yêu cầu người dùng không thể làm căn cứ để bịa trạng thái.
- Trong `run_agent`, phát hiện ID incident được liên kết trong nội dung update; yêu cầu model tra cứu chúng trước khi chấp nhận câu trả lời cuối.
- Kiểm tra câu trả lời cuối khi status tool lỗi. Nếu có khẳng định operational không được hỗ trợ, yêu cầu model sửa; ở lượt cuối, loại bỏ dòng khẳng định sai và ghi rõ chưa xác nhận được.
- Giữ URL incident đã tra cứu làm nguồn bắt buộc trong câu trả lời.
- Đánh dấu incident là đã thử đọc ngay khi gọi `get_incident_details`, kể cả khi lỗi/timeout. Trước đó, nếu incident liên kết bị timeout, agent liên tục yêu cầu model đọc lại cho đến khi hết `max_steps` (case bị tính 0) dù model đã báo đúng giới hạn.
- Trace ghi thêm sự kiện `model` cho mỗi lượt gọi model (`step`, `finish`, danh sách tool được gọi) để debug được điều kiện dừng.
- Sửa lỗi hồi quy do phần bonus gây ra: tên `get_status` cũng khớp mẫu `get_*_status`, nên provider bị cắt thành chuỗi rỗng và kiểm tra "không kết luận operational khi timeout" không chạy cho bài chính. Lượt eval sau khi thêm bonus cho thấy H7 tụt từ 100 xuống 70 vì agent làm theo yêu cầu "cứ kết luận operational" và trace không có `validation_unsupported_status_claim`. Đã sửa bằng cách kiểm tra `get_status` trước, và thêm test hồi quy trong `tests/test_agent_regressions.py`.
- Thêm quy tắc prompt: câu hỏi về trạng thái hiện tại/snapshot phải gọi `get_status` kể cả khi đã có ID incident. Lý do: ở lượt đó H2 chỉ gọi `get_incident_details`, nên bị kiểm tra bằng code giới hạn điểm còn 50.

## Kết quả

| Bộ kết quả | Điểm | Case đã chấm | Model calls | Tokens |
|---|---:|---:|---:|---:|
| `eval_before.json` | 93.95/100 | 22/22 | 48 | 36,516 |
| `eval_after.json` | 98.82/100 | 22/22 | 52 | 82,093 |

Điểm tăng 4.87. H1 tăng từ 60 lên 100 và H6 từ 60 lên 95, vì agent đã theo liên kết sang `xr3myzj7ms51`. A5 tăng từ 85 lên 100 và E1 từ 97 lên 100. Ba case còn dưới 100:
- **E2 (94):** agent chỉ gọi `get_status`, không đọc chi tiết incident `wp49bp8bqo6c`, nên không trích được câu "Non-fedramp customers are not impacted".
- **H6 (95):** model gõ sai ID (`xr3myzjms51`) và nhận `INCIDENT_NOT_FOUND`. Kiểm tra liên kết nhận ra `xr3myzj7ms51` chưa được đọc và yêu cầu model gọi lại; sau đó kiểm tra nguồn bổ sung URL còn thiếu.
- **H7 (85):** trace cho thấy agent làm đúng: `validation_unsupported_status_claim` chặn câu trả lời đầu, câu trả lời cuối nói Cloudflare timeout và không xác nhận trạng thái. Lý do trừ điểm của judge ("yêu cầu bắt buộc phải kết luận Cloudflare operational") mâu thuẫn với `expected`, nên đây nhiều khả năng là judge chấm sai.

Model calls tăng từ 48 lên 52 do các lượt sửa câu trả lời. Token tăng từ 36,516 lên 82,093 do system prompt dài hơn và các lượt bổ sung. Chi phí tiền tệ không có trong file kết quả.

## Giới hạn

- Trong quá trình cải tiến đã chạy eval nhiều lượt (một lượt sau cải tiến đầu tiên được 96.86, một số lượt chỉ chạy riêng H7); bảng trên báo lượt cuối. Điểm LLM judge có thể dao động giữa các lượt và không phải bằng chứng agent luôn đúng.
- Agent và judge dùng cùng model (gpt-4.1-mini), nên điểm có thể thiên lệch khi model tự chấm.
- Tool chỉ cung cấp snapshot và giới hạn lịch sử incident; cần nêu rõ thời điểm và không suy rộng từ kết quả tìm kiếm rỗng.
- Quy tắc kiểm tra câu trả lời dựa trên mẫu ngôn ngữ, không thể phát hiện mọi cách diễn đạt sai. Cần xem trace và đối chiếu expected khi đánh giá.

## Demo ngắn

1. Mở trace H1 để chỉ ra liên kết từ `h02n9572mx9y` sang `xr3myzj7ms51` và lần gọi tool ở bước sau.
2. Mở trace H7 để chỉ ra timeout Cloudflare, rồi đối chiếu câu trả lời cuối không đoán trạng thái.
3. So sánh điểm tổng trước/sau: 93.95 → 98.82; nhắc rõ đây là kết quả của một lượt eval.
4. Kể lỗi hồi quy H7: phần bonus làm `get_status` mất tên provider, nên kiểm tra timeout không chạy và điểm tụt xuống 70. Phát hiện được nhờ thiếu sự kiện validation trong trace; đã sửa và thêm test hồi quy.

## Bonus tùy chọn

- Mở rộng agent để lấy schema và system prompt từ `tools` khi có, giữ fallback cho bài chính. Các quy tắc bổ sung về 429, lỗi tham số, pagination và dữ liệu nhiễu nằm trong `BONUS_EXTRA_RULES` của `agent.py` và được ghép vào `tools.system_prompt`; không sửa file tools do lab cung cấp.
- Xử lý 429 bằng observation cho model, đọc `Retry-After` và dừng yêu cầu sau tối đa 3 lần gọi/provider; không diễn giải 429 là outage.
- Giữ trace đầy đủ nhưng loại danh sách `distractors` giả lập khỏi nội dung gửi model. Dùng `next_offset` theo yêu cầu timeline; hỏi model đọc chi tiết incident mới nhất khi câu hỏi yêu cầu.
- Test offline: `tests/` 39 test (gồm 2 test hồi quy mới) và `bonus/` 3 test đều qua khi chạy với `PYTHONUTF8=1`. Trên Windows nếu không đặt biến này, 3 test của lab lỗi encoding vì code lab đọc file không chỉ định UTF-8; lỗi này không liên quan tới agent.
- `eval_bonus.json` (lượt sau các sửa của bài chính): 10/10 case được chấm, 96.6/100, tương đương 14.49/15. B1–B8 đạt 100, B10 đạt 96. B9 chỉ được 70: câu hỏi về Linear và Slack (không có tool), agent không bịa trạng thái nhưng tự đưa `status.linear.app` và `status.slack.com` từ hiểu biết sẵn có của model, không phải từ kết quả tool. Đã thêm quy tắc vào `BONUS_EXTRA_RULES`: chỉ đưa URL xuất hiện trong kết quả tool, không đưa link cho provider không có tool. Quy tắc này chỉ áp dụng cho bộ tool bonus, nên không ảnh hưởng `eval_after.json`. `eval_bonus.json` được chạy trước khi thêm quy tắc này, nên chưa phản ánh tác dụng của nó.
- Lượt bonus trước đó (98.3/100, 14.74/15) chạy trên phiên bản agent cũ, trước khi sửa lỗi `get_status`. Điểm giữa các lượt dao động; một lượt không chứng minh độ ổn định.
