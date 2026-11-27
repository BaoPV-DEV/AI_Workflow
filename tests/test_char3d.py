import json

from engine import char3d


def test_plan_and_estimate():
    jobs = char3d.plan("x", "co_ban", "day")
    assert ["walk", "side", "day"] in jobs and all(len(j) == 3 for j in jobs)
    assert char3d.plan("x", only="talk:front34:night") == [["talk", "front34", "night"]]
    e = char3d.estimate(jobs, "nhap")
    assert e["frames"] == sum(char3d.FRAMES[j[0]] for j in jobs) and e["minutes"] > 0


def test_sprite_sets_and_scene_info(tmp_path, monkeypatch):
    monkeypatch.setattr(char3d, "out_dir", lambda: tmp_path)
    d = tmp_path / "an" / "talk_front34_day"
    d.mkdir(parents=True)
    for i in range(3):
        (d / f"{i:04d}.png").write_bytes(b"x")
    (d / "meta.json").write_text(json.dumps({"anim": "talk", "view": "front34", "light": "day", "frames": 3, "fps": 12,
                                             "loop": True, "size": [270, 360], "height_m": 1.6, "ortho": 2.2,
                                             "feet": [[0.5, 0.9]] * 3, "head": [[0.5, 0.1]] * 3}))
    sets = char3d.sprite_sets("an")
    assert sets[0]["key"] == "talk_front34_day" and sets[0]["frames"] == 3 and sets[0]["base"].startswith("file://")
    info = char3d.scene_info({"An": {"model3d": "an"}, "Bo": {"preset": "classic"}})
    assert list(info) == ["An"] and info["An"]["sets"][0]["anim"] == "talk"
    assert char3d.fingerprint({"An": {"model3d": "an"}})[0][0] == "An"


def test_presets_valid():
    import importlib.util
    spec = importlib.util.spec_from_file_location("mc", char3d.KIT / "make_character.py")
    mc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mc)
    for c in char3d.characters():
        s = char3d.load_spec(c["id"])
        s["renders"] = char3d.plan(c["id"])
        errs, _ = mc.check(s)
        assert not errs, (c["id"], errs)
