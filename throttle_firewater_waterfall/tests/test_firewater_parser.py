from protocol.firewater_parser import FireWaterParser


def test_parse_prefixed_data():
    parser = FireWaterParser()
    line = parser.parse_line("imu:0.01,-0.02,9.81\n", 1.0)
    assert line.valid
    assert line.prefix == "imu"
    assert line.values == [0.01, -0.02, 9.81]


def test_parse_without_prefix():
    parser = FireWaterParser()
    line = parser.parse_line("35.6,3.45", 1.0)
    assert line.valid
    assert line.prefix == ""
    assert line.values == [35.6, 3.45]


def test_parse_empty_prefix():
    parser = FireWaterParser()
    line = parser.parse_line(":1.0,2.0,3.0", 1.0)
    assert line.valid
    assert line.prefix == ""
    assert line.values == [1.0, 2.0, 3.0]


def test_newline_forms():
    parser = FireWaterParser()
    lines = parser.feed(b"a:1\nb:2\r\nc:3\n\r")
    assert [line.prefix for line in lines] == ["a", "b", "c"]
    assert [line.values[0] for line in lines] == [1.0, 2.0, 3.0]


def test_non_numeric_field():
    parser = FireWaterParser()
    line = parser.parse_line("imu:1,x,3", 1.0)
    assert not line.valid
    assert "non_numeric_field" in line.error


def test_empty_line():
    parser = FireWaterParser()
    line = parser.parse_line(" \r\n\t ", 1.0)
    assert not line.valid
    assert line.error == "empty_line"


def test_image_prefix():
    parser = FireWaterParser()
    line = parser.parse_line("image:abcdef", 1.0)
    assert line.is_image_packet
    assert not line.valid


def test_overlong_line_clears_buffer():
    parser = FireWaterParser(max_line_length=8)
    assert parser.feed(b"123456789") == []
    assert parser.buffer_length == 0
    assert parser.line_overflow_count == 1


def test_multi_packet_sticky_lines():
    parser = FireWaterParser()
    lines = parser.feed(b"imu:1,2\nvib:3,4\n")
    assert len(lines) == 2
    assert lines[0].values == [1.0, 2.0]
    assert lines[1].prefix == "vib"


def test_half_packet_buffered():
    parser = FireWaterParser()
    assert parser.feed(b"imu:1,") == []
    lines = parser.feed(b"2\n")
    assert len(lines) == 1
    assert lines[0].values == [1.0, 2.0]


def test_t_slash_gz_two_field_line():
    parser = FireWaterParser()
    lines = parser.feed(b"t/gz:37,12.500000\r\n")
    assert len(lines) == 1
    assert lines[0].valid
    assert lines[0].prefix == "t/gz"
    assert lines[0].values == [37.0, 12.5]


def test_t_slash_gz_split_across_reads():
    parser = FireWaterParser()
    assert parser.feed(b"t/gz:37,") == []
    lines = parser.feed(b"12.5\r\n")
    assert len(lines) == 1
    assert lines[0].valid
    assert lines[0].prefix == "t/gz"
    assert lines[0].values == [37.0, 12.5]
