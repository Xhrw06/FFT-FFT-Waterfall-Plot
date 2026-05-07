from core.channel_mapping import ChannelMappingManager
from models.channel_mapping import ChannelMappingProfile, FieldMapping, PrefixMapping, ThrottleConfig
from models.firewater import FireWaterLine


def make_line(values, prefix="imu"):
    return FireWaterLine(str(values), prefix, values, 1.0, True)


def make_profile(fields):
    return ChannelMappingProfile(
        name="test",
        mappings={"imu": PrefixMapping("imu", "IMU", fields=fields)},
        throttle_config=ThrottleConfig(channel="throttle"),
    )


def test_field_mapping_scale_offset():
    profile = make_profile([FieldMapping(0, "throttle", "throttle", scale=2, offset=1), FieldMapping(1, "gz", "fft_primary")])
    manager = ChannelMappingManager(profile)
    sample = manager.apply_mapping(make_line([10, 3]))
    assert sample.channels["throttle"] == 21
    assert sample.channels["gz"] == 3


def test_disabled_and_ignore_fields():
    profile = make_profile([
        FieldMapping(0, "a", "normal", enabled=False),
        FieldMapping(1, "b", "ignore"),
        FieldMapping(2, "gz", "fft_primary"),
        FieldMapping(3, "throttle", "throttle"),
    ])
    sample = ChannelMappingManager(profile).apply_mapping(make_line([1, 2, 3, 4]))
    assert "a" not in sample.channels
    assert "b" not in sample.channels
    assert sample.channels["gz"] == 3


def test_missing_field_fill_none():
    profile = make_profile([FieldMapping(0, "throttle", "throttle"), FieldMapping(1, "gz", "fft_primary")])
    sample = ChannelMappingManager(profile).apply_mapping(make_line([5]))
    assert sample.channels["gz"] is None
    assert sample.flags["gz"] == "missing"


def test_extra_field_auto_name():
    profile = make_profile([FieldMapping(0, "throttle", "throttle")])
    sample = ChannelMappingManager(profile).apply_mapping(make_line([5, 6]))
    assert sample.channels["imu_ch1"] == 6


def test_unknown_prefix_auto_name():
    manager = ChannelMappingManager(ChannelMappingProfile(name="empty"), allow_unknown_prefix=True)
    sample = manager.apply_mapping(make_line([1, 2], "motor"))
    assert sample.channels["motor_ch0"] == 1
    assert sample.channels["motor_ch1"] == 2


def test_unknown_prefix_ignored():
    manager = ChannelMappingManager(ChannelMappingProfile(name="empty"), allow_unknown_prefix=False)
    assert manager.apply_mapping(make_line([1], "motor")) is None


def test_repeated_channel_name_validation():
    profile = make_profile([
        FieldMapping(0, "same", "throttle"),
        FieldMapping(1, "same", "fft_primary"),
    ])
    messages = ChannelMappingManager(profile).validate_profile()
    assert any("重复" in msg.message for msg in messages)


def test_throttle_validation():
    profile = ChannelMappingProfile(
        name="test",
        mappings={"imu": PrefixMapping("imu", fields=[FieldMapping(0, "gz", "fft_primary")])},
    )
    messages = ChannelMappingManager(profile).validate_profile()
    assert any("throttle" in msg.message for msg in messages)


def test_fft_validation():
    profile = ChannelMappingProfile(
        name="test",
        mappings={"imu": PrefixMapping("imu", fields=[FieldMapping(0, "throttle", "throttle")])},
    )
    messages = ChannelMappingManager(profile).validate_profile()
    assert any("FFT" in msg.message for msg in messages)


def test_range_clamp():
    profile = make_profile([
        FieldMapping(0, "throttle", "throttle", min_value=0, max_value=100, out_of_range_policy="clamp"),
        FieldMapping(1, "gz", "fft_primary"),
    ])
    sample = ChannelMappingManager(profile).apply_mapping(make_line([120, 1]))
    assert sample.channels["throttle"] == 100
    assert sample.flags["throttle"] == "clamped_high"
