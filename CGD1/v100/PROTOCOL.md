# CGD1 live protocol v1

GATT characteristic 00001f1f-0000-1000-8000-00805f9b34fb. Existing PVVX command 0x90; all integers little endian. Replies: 90, subcommand, status, payload. Status 0 OK, 1 invalid, 2 busy. DATA success has no reply. All host writes use at most 20 bytes, supporting ATT MTU 23. Payloads below exclude 90/subcommand.

| Subcommand | Request payload | Reply payload after status |
|---|---|---|
| 30 capabilities | empty | version:u8, codecs:u32, rate:u32, queue_capacity:u16, max_volume:u8, flags:u8 (bit0 live) |
| 31 START | token:u16 nonzero, codec:u8, rate:u32=16000, volume:u8 0..5 | empty |
| 32 DATA | token:u16, sequence:u16, encoded bytes (1..14 with 20-byte GATT values) | none on success; error reply otherwise |
| 33 STATUS | empty | state:u8, error:u8, token:u16, received:u32, consumed:u32, volume:u8, underruns:u32 |
| 34 END | token:u16, total_encoded_bytes:u32 | empty |
| 35 STOP | token:u16 | empty |
| 36 VOLUME | token:u16, volume:u8 | empty |

States: 0 idle, 1 buffering, 2 playing, 3 draining, 4 error. Errors: 1 disconnect/OTA, 2 10-second input timeout, 3 decoder/truncated EOF, 4 invalid sequence/overflow/session limit. DATA seq starts at zero and wraps modulo 65536. A session is limited to less than 0xffff0000 encoded bytes. The sender must verify session token and byte counters. Credits = capacity - (locally_sent - remotely_consumed); do not use a stale remote received counter as if in-flight bytes did not exist.

END is accepted only when its total matches received. It drains rather than abruptly discarding queued sound. A separate STATUS transaction also establishes completion of preceding DATA writes. STOP never acts on a different token or on local alarm audio after streaming ended. START is rejected while audio/transfer/migration is busy. The host must cancel a failed session and reconnect; it must not restart automatically after a physical STOP or local alarm.

Codec IDs: 1 PCM8 unsigned; 2 PCM16 signed little endian; 3 legacy raw IMA (initial predictor/index zero, low nibble first, legacy quantizer); 4 A-law; 5 mu-law; 8 G.722; 10 mono SBC, 8 subbands, 16 kHz; 11 mSBC without H2 transport header. Only enabled codec bits are advertised; AMR and removed Telink SBC are absent from live capabilities. There is no CGDA/file header on live DATA. Codec state is continuous across packet boundaries.

Firmware encoded queue has 2048 bytes. Main context copies at most 512 contiguous bytes into the existing decoder cache and decodes at most 128 samples at once into the existing source scratch area. Audio IRQ consumes the existing PWM ring at 16 kHz; it performs no decoding, flash I/O or BLE writes. Receiver queue counters count encoded bytes, not samples. STATUS underruns count missing output sample interrupts, not lost BLE packets.
