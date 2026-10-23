"""CGD1 live GATT protocol, shared by HA and the command-line sender."""
from __future__ import annotations

import asyncio
import secrets
import struct
from dataclasses import dataclass

CHARACTERISTIC = "00001f1f-0000-1000-8000-00805f9b34fb"


class ProtocolError(Exception):
    """Firmware rejected a command or a live session failed."""


@dataclass(frozen=True)
class Capabilities:
    codecs: int
    rate: int
    capacity: int
    max_volume: int


@dataclass(frozen=True)
class Status:
    state: int
    error: int
    token: int
    received: int
    consumed: int
    volume: int
    underruns: int


class LiveClient:
    def __init__(self, client):
        self.client = client
        self.token = secrets.randbelow(65535) + 1
        self.sequence = 0
        self.sent = 0
        self._pending = None
        self._command_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._data_error = None

    def _notification(self, _sender, data):
        if len(data) < 3 or data[0] != 0x90:
            return
        if data[1] == 0x32 and data[2]:
            self._data_error = ProtocolError(f"DATA rejected: {data[2]}")
        if self._pending and data[1] == self._pending[0]:
            future = self._pending[1]
            if not future.done():
                future.set_result(bytes(data))

    async def connect(self):
        await self.client.start_notify(CHARACTERISTIC, self._notification)

    async def command(self, sub, payload=b""):
        async with self._command_lock:
            future = asyncio.get_running_loop().create_future()
            self._pending = (sub, future)
            try:
                async with self._write_lock:
                    await self.client.write_gatt_char(
                        CHARACTERISTIC, bytes((0x90, sub)) + payload, response=False
                    )
                reply = await asyncio.wait_for(future, 5)
                if reply[2]:
                    raise ProtocolError(f"Command {sub:02x}: status {reply[2]}")
                return reply
            finally:
                self._pending = None

    async def capabilities(self):
        data = await self.command(0x30)
        if len(data) != 16 or data[3] != 1:
            raise ProtocolError("Unsupported live protocol; install CGD1 v10.0")
        codecs, rate, capacity, volume = struct.unpack_from("<IIHB", data, 4)
        if rate != 16000 or not 512 <= capacity <= 65535 or volume != 5:
            raise ProtocolError("Invalid live capabilities")
        return Capabilities(codecs, rate, capacity, volume)

    async def start(self, codec, volume):
        await self.command(0x31, struct.pack("<HBIB", self.token, codec, 16000, volume))

    async def status(self):
        if self._data_error:
            raise self._data_error
        data = await self.command(0x33)
        if len(data) != 20:
            raise ProtocolError("Truncated live status")
        return Status(*struct.unpack_from("<BBHIIBI", data, 3))

    async def send(self, data):
        # 20-byte GATT values work with the firmware's default ATT MTU.
        # This deliberately does not assume MTU/DLE support from a proxy.
        for offset in range(0, len(data), 14):
            part = data[offset:offset + 14]
            packet = bytes((0x90, 0x32)) + struct.pack("<HH", self.token, self.sequence) + part
            async with self._write_lock:
                await self.client.write_gatt_char(CHARACTERISTIC, packet, response=False)
            self.sequence = (self.sequence + 1) & 65535
            self.sent += len(part)

    async def finish(self):
        await self.command(0x34, struct.pack("<HI", self.token, self.sent))

    async def stop(self):
        await self.command(0x35, struct.pack("<H", self.token))

    async def volume(self, value):
        await self.command(0x36, struct.pack("<HB", self.token, value))

    def credit(self, status, capacity):
        if status.token != self.token or status.error or status.state == 4:
            raise ProtocolError(f"Live session ended: state={status.state}, error={status.error}")
        if status.received > self.sent or status.consumed > status.received:
            raise ProtocolError("Invalid byte counters")
        outstanding = self.sent - status.consumed
        if outstanding > capacity:
            raise ProtocolError("Receiver queue overflow")
        return capacity - outstanding
