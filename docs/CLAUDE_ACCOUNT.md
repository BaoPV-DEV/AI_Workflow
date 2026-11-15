# Dùng tài khoản Claude (không cần API key)

| Cách | Gói Claude | Làm được | Cài đặt |
|---|---|---|---|
| **Claude Desktop + MCP** | mọi gói | Chat "tìm chủ đề hot và làm video…": Claude tìm xu hướng, viết kịch bản, sửa cảnh, dịch; máy bạn tạo giọng, ảnh xem trước, video | `vf mcp-install` (trình cài tự làm nếu thấy Claude Desktop), thoát hẳn rồi mở lại Claude Desktop |
| **Claude Code** | Pro, Max, Team, Enterprise | Studio và lệnh `vf new`, `vf ideas`, `vf auto`, `vf edit`, `vf translate` tự gọi AI bằng gói của bạn | PowerShell: `irm https://claude.ai/install.ps1 \| iex`, gõ `claude` một lần để đăng nhập |
| **Dán tay** | mọi gói | Lấy prompt → dán vào claude.ai → dán kết quả về Studio | không |
| **API key** | Console (trả theo token) | như Claude Code, có prompt caching | đặt `ANTHROPIC_API_KEY` |

Kiểm tra đang dùng cách nào: `vf brain` (hoặc chip **AI:** ở góc trái Studio).

## Claude Desktop: câu lệnh mẫu

- "Tìm 5 chủ đề đang hot ở Việt Nam, chọn cái an toàn và dễ giải thích nhất, làm video người que 45 giây."
- "Mở video meo_thich_hop, cảnh 3 cho Bo cầm cúp, rồi xuất video."
- "Làm thêm bản tiếng Anh và tiếng Nhật cho video vừa rồi."
- "Cho mình xem ảnh xem trước của video."

Claude Desktop thấy các công cụ: `trending_topics`, `get_guide`, `create_video`, `show_video`, `update_scene`, `add_scene`, `delete_scene`, `set_project`, `list_languages`, `create_translation`, `run_step`, `job_status`, `get_preview`, `list_videos`, `open_studio`.

## Tự động mỗi ngày (cần Claude Code hoặc API key)

```bat
vf auto --geo VN --lang vi --count 2 --langs en,ja
vf schedule --time 07:13 "--count 2 --langs en"
```

`vf auto` lấy xu hướng → AI chấm điểm và loại chủ đề rủi ro (chết chóc, chính trị, tin đồn, trẻ em…) → viết kịch bản (có tra web kiểm chứng) → dịch → giọng → video. Báo cáo ở `workspace\_auto\<ngày>.md`, kèm danh sách sự thật cần kiểm tra lại trước khi đăng.

## Xu hướng lấy từ đâu

Google Trends (theo quốc gia), Wikipedia (bài xem nhiều nhất hôm qua theo ngôn ngữ), Hacker News (công nghệ). Thêm YouTube Most Popular: đặt `trends: {youtube_api_key: "..."}` trong `config/settings.local.yaml`. Kết quả cache 1 giờ.

## Giọng đọc & ngôn ngữ

`tts.engine: auto` dùng edge-tts (giọng Microsoft, miễn phí, cần internet); lỗi thì tự chuyển gTTS. Nếu cả hai lỗi, lệnh báo lỗi rõ ràng (không còn ra video câm). 14 ngôn ngữ có sẵn giọng trong `library/languages.json`: vi, en, en-GB, ja, ko, zh, th, id, es, pt, fr, de, hi, ru. Phụ đề tiếng Nhật/Trung/Thái tự cắt theo ký tự.
