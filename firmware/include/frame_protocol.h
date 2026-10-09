#ifndef CONSTELLATION_LAMP_FRAME_PROTOCOL_H
#define CONSTELLATION_LAMP_FRAME_PROTOCOL_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace clp {

// Arduino-independent receiver. The caller owns the RGB back buffer. No heap
// allocation and no partially received frame is ever published by this class.
class FrameParser {
 public:
  FrameParser(uint16_t ledCount, uint8_t* target, size_t capacity,
              uint32_t packetTimeoutMs = 250)
      : ledCount_(ledCount), target_(target), capacity_(capacity),
        timeoutMs_(packetTimeoutMs) {
    reset();
  }

  void setTarget(uint8_t* target, size_t capacity) {
    target_ = target;
    capacity_ = capacity;
    reset();
  }

  uint32_t sequence() const { return completedSequence_; }

  void tick(uint32_t now) {
    if (phase_ != Seeking || magicMatched_ != 0) {
      if (static_cast<uint32_t>(now - lastByteAt_) >= timeoutMs_ ||
          static_cast<uint32_t>(now - packetStartedAt_) >= timeoutMs_) {
        reset();
      }
    }
  }

  // true means a complete count/length/CRC-validated RGB frame is in target_.
  bool feed(uint8_t byte, uint32_t now) {
    tick(now);
    lastByteAt_ = now;
    if (phase_ == Seeking) {
      seek(byte, now);
      return false;
    }
    if (phase_ == Header) {
      header_[headerSize_++] = byte;
      if (headerSize_ == sizeof(header_)) {
        const uint16_t count = read16(header_ + 8);
        const uint16_t length = read16(header_ + 10);
        const uint32_t wantedLength = static_cast<uint32_t>(ledCount_) * 3u;
        if (ledCount_ == 0 || count != ledCount_ || length != wantedLength ||
            target_ == NULL || length > capacity_) {
          recoverHeader(now);
        } else {
          incomingSequence_ = read32(header_ + 4);
          expectedCrc_ = read32(header_ + 12);
          payloadLength_ = length;
          payloadSize_ = 0;
          crc_ = 0xffffffffu;
          phase_ = Payload;
        }
      }
      return false;
    }

    target_[payloadSize_++] = byte;
    crc_ = updateCrc(crc_, byte);
    if (payloadSize_ != payloadLength_) return false;
    const bool valid = (crc_ ^ 0xffffffffu) == expectedCrc_;
    if (valid) completedSequence_ = incomingSequence_;
    reset();
    return valid;
  }

 private:
  enum Phase { Seeking, Header, Payload };
  const uint16_t ledCount_;
  uint8_t* target_;
  size_t capacity_;
  const uint32_t timeoutMs_;
  Phase phase_;
  uint8_t header_[16];
  uint8_t headerSize_;
  uint8_t magicMatched_;
  uint16_t payloadLength_;
  uint16_t payloadSize_;
  uint32_t expectedCrc_;
  uint32_t crc_;
  uint32_t incomingSequence_;
  uint32_t completedSequence_ = 0;
  uint32_t lastByteAt_;
  uint32_t packetStartedAt_;

  static uint16_t read16(const uint8_t* data) {
    return static_cast<uint16_t>(data[0]) |
           static_cast<uint16_t>(static_cast<uint16_t>(data[1]) << 8);
  }

  static uint32_t read32(const uint8_t* data) {
    return static_cast<uint32_t>(data[0]) |
           (static_cast<uint32_t>(data[1]) << 8) |
           (static_cast<uint32_t>(data[2]) << 16) |
           (static_cast<uint32_t>(data[3]) << 24);
  }

  static uint32_t updateCrc(uint32_t crc, uint8_t byte) {
    crc ^= byte;
    for (uint8_t i = 0; i < 8; ++i) {
      const uint32_t mask = 0u - (crc & 1u);
      crc = (crc >> 1) ^ (0xedb88320u & mask);
    }
    return crc;
  }

  void reset() {
    phase_ = Seeking;
    headerSize_ = 0;
    magicMatched_ = 0;
    payloadLength_ = 0;
    payloadSize_ = 0;
    expectedCrc_ = 0;
    crc_ = 0xffffffffu;
    incomingSequence_ = 0;
    lastByteAt_ = 0;
    packetStartedAt_ = 0;
  }

  void seek(uint8_t byte, uint32_t now) {
    static const uint8_t magic[4] = {'C', 'L', 'P', '1'};
    if (byte == magic[magicMatched_]) {
      if (magicMatched_ == 0) packetStartedAt_ = now;
      ++magicMatched_;
      if (magicMatched_ == sizeof(magic)) {
        memcpy(header_, magic, sizeof(magic));
        headerSize_ = sizeof(magic);
        magicMatched_ = 0;
        phase_ = Header;
      }
    } else {
      magicMatched_ = byte == magic[0] ? 1 : 0;
      if (magicMatched_ != 0) packetStartedAt_ = now;
    }
  }

  void recoverHeader(uint32_t now) {
    // Preserve a new magic word or its prefix already consumed by a malformed
    // header. Copy first because feeding the suffix may overwrite header_.
    uint8_t suffix[sizeof(header_) - 1];
    memcpy(suffix, header_ + 1, sizeof(suffix));
    reset();
    for (size_t i = 0; i < sizeof(suffix); ++i) feed(suffix[i], now);
  }
};

// Only a valid published packet may call noteValid(). Noise and partial packets
// have no path to extend the display lifetime. Unsigned subtraction handles
// the Arduino millis() rollover.
class ValidFrameWatchdog {
 public:
  explicit ValidFrameWatchdog(uint32_t timeoutMs) : timeoutMs_(timeoutMs) {}
  void noteValid(uint32_t now) { lastValidAt_ = now; active_ = true; }
  bool mustBlank(uint32_t now) const {
    return active_ && static_cast<uint32_t>(now - lastValidAt_) >= timeoutMs_;
  }
  void didBlank() { active_ = false; }

 private:
  const uint32_t timeoutMs_;
  uint32_t lastValidAt_ = 0;
  bool active_ = false;
};

}  // namespace clp
#endif
