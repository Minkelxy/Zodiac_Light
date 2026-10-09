"""Run the actual portable C++ receiver against independent Python CRC fixtures.

No network, serial port or board is opened. A host C++ compiler is required;
scripts/run_checks.cmd initializes MSVC on the reference Windows machine.
"""

import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ROOT / "firmware" / "include"
IDF_INCLUDE = ROOT / "firmware-idf" / "main"


def packet(payload, sequence=0, count=None):
    count = len(payload) // 3 if count is None else count
    return struct.pack("<4sIHHI", b"CLP1", sequence, count, len(payload), zlib.crc32(payload)) + payload


def compiler_path():
    requested = os.environ.get("CXX")
    if requested:
        return shutil.which(requested) or (requested if Path(requested).is_file() else None)
    return next((path for name in ("cl", "g++", "clang++") if (path := shutil.which(name))), None)


HARNESS = r'''
#include "frame_protocol.h"
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <string>

static const size_t kMaxBytes = 1024 * 3;
static uint8_t buffers[2][kMaxBytes + 2];
static unsigned front = 0, back = 1;
static size_t bytes = 0;

static void dump(const char* tag, uint32_t sequence = 0) {
  std::cout << tag;
  if (std::strcmp(tag, "FRAME") == 0) std::cout << ' ' << sequence;
  std::cout << ' ';
  for (size_t i = 1; i <= bytes; ++i)
    std::cout << std::hex << std::setfill('0') << std::setw(2)
              << static_cast<unsigned>(buffers[front][i]);
  std::cout << std::dec << '\n';
}

int main(int argc, char** argv) {
  if (argc != 2) return 1;
  const uint16_t count = static_cast<uint16_t>(std::atoi(argv[1]));
  bytes = static_cast<size_t>(count) * 3;
  if (bytes == 0 || bytes > kMaxBytes) return 2;
  std::memset(buffers, 0xa5, sizeof(buffers));
  std::memset(buffers[front] + 1, 0, bytes);
  clp::FrameParser parser(count, buffers[back] + 1, bytes, 250);
  clp::ValidFrameWatchdog watchdog(1000);
  std::string command;
  uint32_t now = 0;
  while (std::cin >> command) {
    if (command == "F") {
      std::string hex;
      std::cin >> now >> hex;
      if (hex.size() % 2 != 0) return 3;
      for (size_t i = 0; i < hex.size(); i += 2) {
        const uint8_t byte = static_cast<uint8_t>(std::strtoul(hex.substr(i, 2).c_str(), NULL, 16));
        if (parser.feed(byte, now)) {
          const unsigned oldFront = front;
          front = back;
          back = oldFront;
          parser.setTarget(buffers[back] + 1, bytes);
          watchdog.noteValid(now);
          dump("FRAME", parser.sequence());
        }
      }
    } else if (command == "T") {
      std::cin >> now;
      parser.tick(now);
    } else if (command == "C") {
      size_t capacity;
      std::cin >> capacity;
      parser.setTarget(buffers[back] + 1, capacity);
    } else if (command == "S") {
      dump("STATE");
    } else {
      return 4;
    }
    if (watchdog.mustBlank(now)) {
      std::memset(buffers[front] + 1, 0, bytes);
      watchdog.didBlank();
      dump("BLACK");
    }
    for (unsigned b = 0; b < 2; ++b) {
      if (buffers[b][0] != 0xa5) return 5;
      for (size_t i = bytes + 1; i < sizeof(buffers[b]); ++i)
        if (buffers[b][i] != 0xa5) return 6;
    }
  }
  return 0;
}
'''


class FirmwareReceiverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler = compiler_path()
        if cls.compiler is None:
            raise unittest.SkipTest("Host C++ compiler unavailable; use scripts/run_checks.cmd for MSVC")
        cls.temporary = tempfile.TemporaryDirectory(prefix="clp-receiver-")
        cls.directory = Path(cls.temporary.name)
        cls.executable = cls.directory / ("receiver.exe" if os.name == "nt" else "receiver")
        result = cls.compile(HARNESS, cls.executable)
        if result.returncode:
            cls.temporary.cleanup()
            raise AssertionError("C++ receiver did not compile:\n" + result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    @classmethod
    def compile(cls, source, destination, defines=()):
        source_file = cls.directory / (destination.stem + ".cpp")
        source_file.write_text(source, encoding="utf-8")
        if Path(cls.compiler).name.lower() in ("cl", "cl.exe"):
            command = [cls.compiler, "/nologo", "/EHsc", "/std:c++14", "/W4",
                       "/I" + str(INCLUDE), "/I" + str(IDF_INCLUDE), "/Fe:" + str(destination),
                       *["/D" + value for value in defines], str(source_file)]
        else:
            command = [cls.compiler, "-std=c++11", "-Wall", "-Wextra", "-pedantic",
                       "-I", str(INCLUDE), "-I", str(IDF_INCLUDE), *["-D" + value for value in defines],
                       str(source_file), "-o", str(destination)]
        return subprocess.run(command, cwd=cls.directory, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=60)

    def run_receiver(self, commands, count=2):
        result = subprocess.run([str(self.executable), str(count)], input="\n".join(commands) + "\n",
                                capture_output=True, text=True, encoding="ascii", timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.splitlines()

    @staticmethod
    def feed(data, now=0):
        return f"F {now} {data.hex()}"

    def test_standard_crc_and_little_endian_sequence(self):
        payload = b"123456789"
        self.assertEqual(zlib.crc32(payload), 0xCBF43926)
        result = self.run_receiver([self.feed(packet(payload, 0x12345678))], count=3)
        self.assertEqual(result, [f"FRAME {0x12345678} {payload.hex()}"])

    def test_fragmented_packet_and_magic_bytes_inside_rgb(self):
        payload = b"CLP1\x00\xff\x80\x00\x01"
        data = packet(payload, 0xFFFFFFFF)
        result = self.run_receiver([self.feed(bytes([byte]), index) for index, byte in enumerate(data)], count=3)
        self.assertEqual(result, [f"FRAME 4294967295 {payload.hex()}"])

    def test_noise_overlap_and_invalid_count_length_recover(self):
        payload = b"\x01\x02\x03\xf0\x80\x00"
        invalid = [struct.pack("<4sIHHI", b"CLP1", 0, count, length, 0)
                   for count, length in ((0, 0), (65535, 65535), (2, 7), (3, 6))]
        data = b"noiseCCLPC" + b"".join(invalid) + packet(payload, 7)
        self.assertEqual(self.run_receiver([self.feed(data)]), [f"FRAME 7 {payload.hex()}"])

    def test_new_magic_and_partial_magic_inside_rejected_header(self):
        payload = bytes(range(6))
        for malformed_prefix in (b"CLP1junk", b"CLP1" + b"x" * 10):
            with self.subTest(prefix=malformed_prefix):
                result = self.run_receiver([self.feed(malformed_prefix + packet(payload, 8))])
                self.assertEqual(result, [f"FRAME 8 {payload.hex()}"])

    def test_bad_crc_cannot_publish_or_modify_the_front_buffer(self):
        initial = bytes(range(6))
        corrupt = bytearray(packet(b"\xff" * 6, 2))
        corrupt[-1] ^= 1
        result = self.run_receiver([self.feed(packet(initial, 1)), self.feed(corrupt, 500), "S",
                                    self.feed(packet(b"\x10" * 6, 3), 600)])
        self.assertEqual(result, [f"FRAME 1 {initial.hex()}", f"STATE {initial.hex()}",
                                  "FRAME 3 " + "10" * 6])

    def test_incomplete_header_and_payload_expire(self):
        data = packet(bytes(range(6)), 9)
        for partial in (data[:5], data[:-1]):
            with self.subTest(partial_length=len(partial)):
                result = self.run_receiver([self.feed(partial, 0), "T 250", self.feed(data, 251)])
                self.assertEqual(result, ["FRAME 9 000102030405"])

    def test_total_packet_deadline_even_with_continuous_slow_bytes(self):
        data = packet(bytes(range(6)), 10)
        commands = [self.feed(bytes([byte]), index * 20) for index, byte in enumerate(data)]
        commands += ["S", self.feed(data, 500)]
        self.assertEqual(self.run_receiver(commands), ["STATE " + "00" * 6, "FRAME 10 000102030405"])

    def test_invalid_traffic_does_not_extend_the_one_second_watchdog(self):
        good = packet(b"\x04" * 6, 1)
        bad = bytearray(good)
        bad[12] ^= 1
        result = self.run_receiver([self.feed(good, 10), self.feed(bad, 900), "T 1009",
                                    self.feed(b"noiseCL", 1010), "T 2000", "S"])
        self.assertEqual(result, ["FRAME 1 " + "04" * 6, "BLACK " + "00" * 6, "STATE " + "00" * 6])

    def test_millis_rollover_for_parser_and_display_watchdog(self):
        data = packet(bytes(range(6)), 12)
        result = self.run_receiver([self.feed(data[:5], 0xFFFFFFCD), "T 201",
                                    self.feed(data, 202), "T 1201", "T 1202"])
        self.assertEqual(result, ["FRAME 12 000102030405", "BLACK " + "00" * 6])
        result = self.run_receiver([self.feed(data, 0xFFFFFFCD), "T 948", "T 949", "T 950"])
        self.assertEqual(result, ["FRAME 12 000102030405", "BLACK " + "00" * 6])

    def test_startup_noise_leaves_black_without_a_published_frame(self):
        self.assertEqual(self.run_receiver([self.feed(b"CLP1garbage", 100), "T 10000", "S"]),
                         ["STATE " + "00" * 6])

    def test_maximum_configured_frame_and_guard_bytes(self):
        payload = bytes((index * 17 + 29) % 256 for index in range(1024 * 3))
        data = packet(payload, 13)
        result = self.run_receiver([self.feed(data[:1000], 0), self.feed(data[1000:2000], 1),
                                    self.feed(data[2000:], 2)], count=1024)
        self.assertEqual(result, [f"FRAME 13 {payload.hex()}"])

    def test_capacity_shortfall_rejects_before_writing_payload(self):
        self.assertEqual(self.run_receiver(["C 5", self.feed(packet(bytes(range(6)))), "S"]),
                         ["STATE " + "00" * 6])

    def test_compile_time_limits_and_exported_scene_consistency(self):
        source = '#include "config.h"\nint main() { return 0; }\n'
        for defines in (("CLP_MAX_LEDS=1",), ("CLP_LOCAL_LEVEL=255",), ("CLP_MODE=4",)):
            with self.subTest(defines=defines):
                result = self.compile(source, self.directory / "invalid.exe", defines)
                self.assertNotEqual(result.returncode, 0)
        if (INCLUDE / "constellation_compact.h").exists():
            result = self.compile(source, self.directory / "invalid-scene.exe", ("CLP_LED_COUNT=1",))
            self.assertNotEqual(result.returncode, 0)

    def test_native_idf_grb_and_current_limit_match_python(self):
        import dataclasses

        import numpy as np

        from constellation_lamp.seriallink import HardwareProfile, limit_current

        source = r'''
#include "output_transform.h"
#include <iostream>
#include <iomanip>
#include <string>
#include <cstdlib>
int main() {
  unsigned count, limit, idle, channel;
  std::string hex;
  while (std::cin >> count >> limit >> idle >> channel >> hex) {
    uint8_t rgb[1024 * 3], grb[1024 * 3];
    if (count == 0 || count > 1024 || hex.size() != count * 6) return 1;
    for (unsigned i = 0; i < count * 3; ++i)
      rgb[i] = static_cast<uint8_t>(std::strtoul(hex.substr(i * 2, 2).c_str(), NULL, 16));
    clp::rgbToGrbLimited(rgb, grb, count, limit, idle, channel);
    for (unsigned i = 0; i < count * 3; ++i)
      std::cout << std::hex << std::setfill('0') << std::setw(2) << static_cast<unsigned>(grb[i]);
    std::cout << std::dec << '\n';
  }
  return 0;
}
'''
        executable = self.directory / ("output.exe" if os.name == "nt" else "output")
        build = self.compile(source, executable)
        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
        rng = np.random.default_rng(4421)
        cases = [(np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], np.uint8), 2000, 1000, 20000),
                 (np.zeros((268, 3), np.uint8), 2000, 1000, 20000),
                 (np.full((268, 3), 255, np.uint8), 2000, 1000, 20000),
                 (rng.integers(0, 256, (268, 3), dtype=np.uint8), 700, 1250, 12000),
                 (rng.integers(0, 256, (1024, 3), dtype=np.uint8), 2000, 1000, 20000),
                 (np.full((268, 3), 255, np.uint8), 268, 1000, 20000)]
        commands, expected = [], []
        for frame, limit, idle, channel in cases:
            profile = dataclasses.replace(HardwareProfile(), current_limit_ma=limit,
                                          idle_led_ma=idle / 1000, channel_ma=channel / 1000, fps=5)
            limited, _ = limit_current(frame, profile)
            expected.append(limited[:, [1, 0, 2]].tobytes().hex())
            commands.append(f"{len(frame)} {limit} {idle} {channel} {frame.tobytes().hex()}")
        result = subprocess.run([str(executable)], input="\n".join(commands) + "\n",
                                capture_output=True, text=True, encoding="ascii", timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(), expected)


if __name__ == "__main__":
    unittest.main()
