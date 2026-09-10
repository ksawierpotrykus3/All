from mvp.simulator.game import GameSimulator


def test_game_simulator_importable():
    sim = GameSimulator()
    assert sim is not None
    assert hasattr(sim, "apply_variant")
    assert hasattr(sim, "handle_click")
    assert hasattr(sim, "get_current_frame_raw")
    assert hasattr(sim, "reset_to_chat")
    assert hasattr(sim, "strict_alert_hit")


def test_apply_variant_default():
    sim = GameSimulator()
    sim.apply_variant("default")
    assert sim.current_variant["bot_config"] == "38_cps"


def test_game_simulator_images_loaded_and_frames_rendered():
    sim = GameSimulator()
    assert all(img is not None for img in sim.images.values())

    # Frames are 1:1 with the configured viewport (the window is forced to 16:9,
    # so the returned frame == the game content == real-game geometry).
    sim.set_viewport_size(800, 600)
    raw_frame = sim.get_current_frame_raw()
    assert raw_frame is not None
    assert raw_frame.shape[:2] == (600, 800)

    cropped = sim.get_current_frame_cropped(800, 600)
    assert cropped.shape == (600, 800, 3)


def test_game_simulator_fallback_when_images_missing(tmp_path):
    sim = GameSimulator(data_dir=tmp_path)
    assert all(img is not None for img in sim.images.values())
    raw_frame = sim.get_current_frame_raw()
    assert raw_frame is not None
    assert raw_frame.shape == (1080, 1920, 3)
