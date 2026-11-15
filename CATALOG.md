# CATALOG (sinh tự động bởi `vf catalog` – không sửa tay)

## Templates (visual_type: html_animation)
- **bar_chart** – Biểu đồ cột ngang so sánh 2-6 giá trị, cột mọc lần lượt, cột lớn nhất được tô màu nhấn. | props: title: tiêu đề; bars: [{label, value}] 2-6 cột; unit: đơn vị hiển thị sau số; at: lúc bắt đầu mọc
- **bullet_list** – Tiêu đề + 2-5 ý hiện lần lượt, ý đang nói được làm nổi. | props: title: tiêu đề; items: [chuỗi] 2-5 ý, mỗi ý ≤7 từ; at: [mốc] hiện từng ý (từ trong lời đọc / %), bỏ trống = chia đều; icon: ký tự đầu dòng, mặc định số thứ tự
- **compare_split** – So sánh 2 phía (trước/sau, A vs B). Dọc: trên/dưới; ngang: trái/phải. | props: left: {title, items:[≤4 ý]} phía 1; right: {title, items} phía 2; vs: chữ ở giữa, mặc định 'VS'; winner: left|right|none – phía được tô nổi
- **headline_news** – Bản tin: nhãn BREAKING, tiêu đề lớn, dòng chữ chạy phía dưới, nguồn tin. | props: kicker: nhãn, mặc định 'TIN NÓNG'; headline: tiêu đề ≤10 từ (*từ* để tô); ticker: dòng chữ chạy; source: nguồn tin; image: ảnh nền trong assets/ (tuỳ chọn)
- **kinetic_text** – Chữ động theo giọng đọc: từng cụm từ bật lên đúng lúc được đọc, từ khoá tô màu. Hợp Shorts/hook. Nên tắt phụ đề khi dùng nhiều (render.captions). | props: emphasize: [từ] cần tô màu nhấn; group: số từ mỗi màn (mặc định 3); bg_word: chữ mờ cực lớn phía sau (tuỳ chọn)
- **quote_card** – Trích dẫn: chữ hiện theo nhịp đọc, dấu ngoặc lớn, tên tác giả. | props: quote: câu trích (≤25 từ); author: tác giả / nguồn
- **stat_card** – Một con số lớn đếm lên, kèm nhãn. Dùng mỗi khi lời đọc nêu số liệu. | props: value: số (vd 90); prefix: trước số, vd '$'; suffix: sau số, vd '%'; label: nhãn ngắn; sub: nguồn/ghi chú nhỏ; at: lúc bắt đầu đếm (từ trong lời đọc hoặc %); decimals: số chữ số thập phân
- **stickman_stage** – Sân khấu người que: nhân vật trong cast diễn theo 'acting' của cảnh (đi, chỉ, cầm đồ, cảm xúc, thoại). | props: title: chữ lớn phía trên (≤6 từ, tuỳ chọn); title_at: lúc hiện title; backdrop: plain|studio|room|bedroom|kitchen|bathroom|office|classroom|library|lab|cafe|restaurant|supermarket|shop|hospital|bank|courtroom|museum|gallery|cinema|newsroom|podcast|server_room|factory|garage|gym|spaceship|airport|train_station|subway|bus|street|city_night|alley|rooftop|construction|playground|stadium|park|nature|forest|jungle|waterfall|lake|river|beach|island|underwater|mountain|desert|volcano|cave|arctic|winter_village|farm|village|pagoda|temple|castle|prehistoric|campsite|sky|space|moon|mars|stage|night; time: day|sunset|night – thời điểm (bầu trời, đèn, sao); weather: none|rain|snow|leaves|fog; items: [{emoji|text, x:0-1, y:0-1, size:0-1, at}] đồ vật/biểu tượng hiện ra trên sân khấu | cần: acting trong scene; who = tên trong cast
- **timeline** – Dòng thời gian 2-6 mốc, chấm sáng chạy qua từng mốc. | props: title: tiêu đề; events: [{year, label}] 2-6 mốc, label ≤5 từ; at: [mốc] lúc tới từng mốc (tuỳ chọn)
- **title_card_neon** – Thẻ tiêu đề mở đầu/chương: chữ lớn bật vào, vạch sáng quét, phát sáng nhẹ. | props: heading: tiêu đề chính (≤6 từ, *từ* để tô nổi); subheading: dòng phụ (tuỳ chọn); kicker: nhãn nhỏ phía trên, vd 'CHƯƠNG 1' (tuỳ chọn)

## visual_type khác
- svg_graphic: svg_code (SVG tự vẽ, viewBox theo khung; animation CSS được hỗ trợ)
- image: src (file trong assets/), camera: zoom_in|zoom_out|pan_left|pan_right
- video: src (clip trong assets/) · comfyui: prompt, workflow · color: props.color

## Styles (manifest.style)
- beanie_tech: Beanie Studio Tech – studio trắng, lưới xám, UI kính xanh (AI, công cụ, sự nghiệp)
- classic_dark: Classic Dark – nền đen, nét trắng, màu nhấn neon (tâm lý, triết lý, kể chuyện ngắn)
- classic_light: Classic Light – nền trắng, nét đen, tối đa 3 màu nhấn (giải thích nhanh, tư duy)
- cozy_story: Cozy Storytelling – màu ấm, ánh sáng dịu (chuyện đời thường, cảm xúc)
- historical: Historical Cartoon – giấy cũ, màu cổ điển (lịch sử, văn minh)
- meme_dynamic: Dynamic Meme – nét dày, màu tươi, chữ to viền đen (Shorts giải trí, viral)
- neon_news: Neon News – motion graphics tin nhanh, nền tối, neon cyan/hồng
- retro_tv: Retro TV – màn CRT, scanline, màu bão hoà (tin tức, giật gân, bí ẩn)

## Nhân vật (cast.<Tên>.preset)
classic, faceless, shadow, beanie, cozy, kid, girl, student, teacher, scientist, elder, grandma, boss, chef, gamer, worker, graduate, gentleman, king, soldier

## Acting (scene.acting[] cho stickman_stage)
beat = {at: 'từ trong lời đọc'|'60%'|giây, act, who?, move?, mood?, hold?, say?, face?}
act: stand, walk, run, talk, explain, point, point_up, look, think, head_scratch, wave, cheer, celebrate, jump, clap, thumbs_up, nod, shake_head, shrug, facepalm, arms_crossed, hands_on_hips, sad, cry, laugh, scared, shocked, angry, sit, read, work, phone_call, salute, stretch, sneak, fight, push, carry, present, handshake, hug, give, high_five, eat, dance, sleep, fall, kneel, bow
move: enter_left, enter_right, exit_left, exit_right, left, center, right, stay
mood: neutral, happy, sad, surprised, angry, scared, tired, curious, proud, love, laugh
emote (biểu tượng trên đầu): ! ? ❤ 💡 💢 💧 zzz ♪ ✨ 💦 ...
hold: book, phone, coin, money, gift, bulb, sign, laptop, cup, flag, sword, key, star, trophy, magnifier, map, briefcase, microphone, pen, pizza, umbrella
Tạo nhân vật riêng: cast.<Tên> = {preset?, build slim|normal|round, hair short|long|ponytail|bun|spiky|curly|bald, hair_color, outfit shirt|dress|coat, shirt (màu), hat beanie|cap|crown|helmet|tophat|chef|graduation, accessories [glasses, tie, bowtie, scarf, mustache, beard, headphones, backpack], scale}. Nhân vật đứng yên tự quay mặt về nhau; miệng nhép theo lời khi act là nói/giải thích.
