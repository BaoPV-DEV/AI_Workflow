from engine import manifest, narration


def test_narration_builds_valid_manifest():
    t = ("Bạn có biết mỗi ngày chúng ta chạm vào điện thoại bao nhiêu lần không? Trung bình một người chạm khoảng 2600 lần "
         "mỗi ngày. Có ba thói quen khiến Mi mất tập trung: thông báo liên tục, lướt video ngắn, và kiểm tra tin nhắn. "
         "Năm 2007 iPhone ra đời, đến năm 2015 điện thoại thông minh phổ biến khắp nơi. Mi đã thử và vui hơn hẳn.")
    m = narration.build(t)
    m["project_id"] = "t"
    kinds = [s["template_name"] for s in m["scenes"]]
    assert kinds[0] == "kinetic_text" and "stat_card" in kinds and "bullet_list" in kinds and "timeline" in kinds
    assert manifest.validate(m) == []
