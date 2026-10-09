"""Run the real native-IDF RGB/GRB limiter on a host C++ compiler."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

from constellation_lamp.seriallink import HardwareProfile, estimate_current_ma, limit_current


ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
#include "output_transform.h"
#include <iostream>
#include <iomanip>
#include <string>
#include <vector>
#include <cstdlib>
int main(int argc, char** argv) {
  if (argc != 5) return 1;
  const unsigned n = std::strtoul(argv[1], nullptr, 10);
  if (!n || n > 1024) return 2;
  const unsigned limit = std::strtoul(argv[2], nullptr, 10);
  const unsigned idle = std::strtoul(argv[3], nullptr, 10);
  const unsigned channel = std::strtoul(argv[4], nullptr, 10);
  std::string hex;
  std::cin >> hex;
  if (hex.size() != n * 6) return 3;
  std::vector<uint8_t> rgb(n * 3), grb(n * 3 + 2, 0xa5);
  for (unsigned i = 0; i < n * 3; ++i)
    rgb[i] = static_cast<uint8_t>(std::strtoul(hex.substr(i * 2, 2).c_str(), nullptr, 16));
  const std::vector<uint8_t> before = rgb;
  const bool limited = clp::rgbToGrbLimited(rgb.data(), grb.data() + 1, n, limit, idle, channel);
  if (before != rgb || grb.front() != 0xa5 || grb.back() != 0xa5) return 4;
  std::cout << (limited ? "1 " : "0 ");
  for (unsigned i = 1; i <= n * 3; ++i)
    std::cout << std::hex << std::setw(2) << std::setfill('0') << static_cast<unsigned>(grb[i]);
  std::cout << '\n';
  return 0;
}
'''


class NativeOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("cl") or shutil.which("g++") or shutil.which("clang++")
        if not compiler:
            raise unittest.SkipTest("A host C++ compiler is required")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)
        source = cls.directory / "output_test.cpp"
        source.write_text(HARNESS, encoding="utf-8")
        cls.exe = cls.directory / "output_test.exe"
        include = ROOT / "firmware-idf" / "main"
        if Path(compiler).stem.lower() == "cl":
            command = [compiler, "/nologo", "/EHsc", "/std:c++14", "/I" + str(include),
                       str(source), "/Fe:" + str(cls.exe), "/Fo:" + str(cls.directory / "output_test.obj")]
        else:
            command = [compiler, "-std=c++14", "-I", str(include), str(source), "-o", str(cls.exe)]
        completed = subprocess.run(command, capture_output=True, text=True, cwd=cls.directory)
        if completed.returncode:
            raise AssertionError(completed.stdout + completed.stderr)

    def convert(self, frame, profile=None):
        profile = profile or HardwareProfile()
        result = subprocess.run([str(self.exe), str(len(frame)), str(int(profile.current_limit_ma)),
                                 str(round(profile.idle_led_ma * 1000)), str(round(profile.channel_ma * 1000))],
                                input=frame.tobytes().hex(), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        limited, hex_rgb = result.stdout.strip().split()
        grb = np.frombuffer(bytes.fromhex(hex_rgb), np.uint8).reshape(len(frame), 3)
        return limited == "1", grb[:, [1, 0, 2]].copy()

    def test_rgb_grb_order_no_extra_gamma_or_brightness(self):
        frame = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255], [1, 2, 3], [127, 64, 32]], np.uint8)
        limited, received_rgb = self.convert(frame)
        self.assertFalse(limited)
        np.testing.assert_array_equal(received_rgb, frame)

    def test_full_white_and_asymmetric_rgb_respect_estimated_budget(self):
        for color in ([255, 255, 255], [255, 128, 64], [0, 255, 20]):
            with self.subTest(color=color):
                frame = np.tile(np.array(color, np.uint8), (268, 1))
                limited, rgb = self.convert(frame)
                self.assertTrue(limited)
                self.assertLessEqual(estimate_current_ma(rgb, HardwareProfile()), 2000)
                expected, _ = limit_current(frame, HardwareProfile())
                self.assertLessEqual(np.max(np.abs(rgb.astype(int) - expected.astype(int))), 1)

    def test_host_limited_frames_are_transmitted_without_second_scaling(self):
        rng = np.random.default_rng(42)
        for _ in range(12):
            frame = rng.integers(0, 256, (268, 3), dtype=np.uint8)
            host, _ = limit_current(frame, HardwareProfile())
            limited, device = self.convert(host)
            self.assertFalse(limited)
            np.testing.assert_array_equal(device, host)

    def test_calibrated_coefficients_and_black_frame(self):
        profile = HardwareProfile(current_limit_ma=500, idle_led_ma=.5, channel_ma=6.5)
        frame = np.full((268, 3), 255, np.uint8)
        limited, rgb = self.convert(frame, profile)
        self.assertTrue(limited)
        self.assertLessEqual(estimate_current_ma(rgb, profile), 500)
        self.assertFalse(self.convert(np.zeros_like(frame), profile)[1].any())

    def test_maximum_frame_size_does_not_overflow_or_modify_source(self):
        frame = np.full((1024, 3), 255, np.uint8)
        limited, rgb = self.convert(frame)
        self.assertTrue(limited)
        self.assertLessEqual(estimate_current_ma(rgb, HardwareProfile()), 2000)


if __name__ == "__main__":
    unittest.main()
