import unittest

from core import Telemetry, parse_packet, engine_reason


class PacketTests(unittest.TestCase):
    def test_parses_helmet_packet(self):
        item = parse_packet("H:1,A:0,D:0,M:245")
        self.assertEqual(item, Telemetry(helmet=True, alcohol=False, drowsy=False, mq3=245))

    def test_parses_vehicle_packet(self):
        item = parse_packet("H:1,A:0,D:0,M:245,ENGINE:1,LINK:1")
        self.assertTrue(item.engine)
        self.assertTrue(item.link)

    def test_rejects_noise(self):
        self.assertIsNone(parse_packet("SMART HELMET STARTED"))
        self.assertIsNone(parse_packet("H:1,A:0"))

    def test_engine_reason_priority(self):
        item = Telemetry(helmet=False, alcohol=True, drowsy=True, mq3=900, engine=False, link=True)
        self.assertEqual(engine_reason(item), "Helmet not detected")
        item.helmet = True
        self.assertEqual(engine_reason(item), "Alcohol detected")


if __name__ == "__main__":
    unittest.main()

