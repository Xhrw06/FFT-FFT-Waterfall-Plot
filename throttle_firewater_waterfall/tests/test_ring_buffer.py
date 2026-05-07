from processing.ring_buffer import MultiChannelRingBuffer, RingBuffer


def test_ring_buffer_capacity_and_recent():
    buf = RingBuffer(3)
    for i in range(5):
        buf.append(i, i * 10)
    data = buf.get_recent(3)
    assert data.timestamps.tolist() == [2, 3, 4]
    assert data.values.tolist() == [20, 30, 40]


def test_time_range():
    buf = RingBuffer(5)
    for i in range(5):
        buf.append(i, i)
    data = buf.get_time_range(1, 3)
    assert data.values.tolist() == [1, 2, 3]


def test_multi_channel_buffer():
    buf = MultiChannelRingBuffer(2)
    buf.append("gz", 0, 1)
    buf.append("gx", 0, 2)
    assert buf.channels() == ["gx", "gz"]
