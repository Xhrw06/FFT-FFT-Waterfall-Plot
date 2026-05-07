from models.channel_mapping import ThrottleConfig
from models.samples import ChannelSample
from processing.throttle_aligner import ThrottleAligner


def sample(value, timestamp=1.0):
    return ChannelSample(
        timestamp=timestamp,
        prefix="imu",
        channels={"throttle": value},
        raw_values=[value],
        roles={"throttle": "throttle"},
    )


def test_update_config_clears_history():
    aligner = ThrottleAligner(ThrottleConfig(channel="throttle"))
    aligner.observe_channel_sample(sample(50, timestamp=1.0))
    assert aligner.latest() is not None

    aligner.update_config(ThrottleConfig(channel="throttle", input_min=1000, input_max=2000))

    assert aligner.latest() is None
    assert aligner.align(1.0) is None
