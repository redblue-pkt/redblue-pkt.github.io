"""Decode on the HA host and stream encoded mono audio over BLE to CGD1."""
from __future__ import annotations

import asyncio
from contextlib import suppress
import logging

from bleak import BleakClient
from homeassistant.components import bluetooth, media_source
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass, MediaPlayerEntity, MediaPlayerEntityFeature, MediaPlayerState,
    async_process_play_media_url,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo

from .protocol import LiveClient, ProtocolError

_LOGGER = logging.getLogger(__name__)
DOMAIN = "cgd1_speaker"
# Prefer G.722 (64 kbit/s); all alternatives reuse firmware decoders.
FORMATS = ((8, "g722", "g722", 8000), (4, "pcm_alaw", "alaw", 16000),
           (5, "pcm_mulaw", "mulaw", 16000), (1, "pcm_u8", "u8", 16000),
           (2, "pcm_s16le", "s16le", 32000), (10, "sbc", "sbc", 4000),
           (11, "sbc", "sbc", 7600))


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([CGD1Speaker(entry)])


class CGD1Speaker(MediaPlayerEntity):
    _attr_has_entity_name = True
    _attr_name = "Speaker"
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_should_poll = False
    _unrecorded_attributes = frozenset({"bytes_sent", "bytes_consumed", "buffer_underruns"})
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY_MEDIA | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.VOLUME_SET | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )
    _attr_state = MediaPlayerState.IDLE
    _attr_volume_level = 0.6
    _attr_is_volume_muted = False

    def __init__(self, entry):
        self.address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = self.address + "_speaker"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.address)}, name=entry.data[CONF_NAME],
            manufacturer="Qingping / PVVX", model="CGD1 live audio",
            connections={("bluetooth", self.address)},
        )
        self._task = None
        self._operation_lock = asyncio.Lock()
        self._live = None
        self._volume_changed = False
        self._attr_extra_state_attributes = {"live_protocol": 1}

    async def async_added_to_hass(self):
        self.async_on_remove(bluetooth.async_register_callback(
            self.hass, self._on_advertisement, {"address": self.address},
            bluetooth.BluetoothScanningMode.PASSIVE,
        ))

    def _on_advertisement(self, service_info, change):
        if not self.available:
            self._attr_available = True
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        await self.async_media_stop()

    async def async_media_stop(self):
        async with self._operation_lock:
            await self._stop()

    async def _stop(self):
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._attr_state = MediaPlayerState.IDLE
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume):
        self._attr_volume_level = round(max(0, min(1, volume)) * 5) / 5
        self._volume_changed = True
        self.async_write_ha_state()

    async def async_mute_volume(self, mute):
        self._attr_is_volume_muted = mute
        self._volume_changed = True
        self.async_write_ha_state()

    def _volume(self):
        return 0 if self.is_volume_muted else round(self.volume_level * 5)

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        return await media_source.async_browse_media(
            self.hass, media_content_id,
            content_filter=lambda item: (item.media_content_type or "").startswith("audio/"),
        )

    async def async_play_media(self, media_type, media_id, **kwargs):
        if media_source.is_media_source_id(media_id):
            resolved = await media_source.async_resolve_media(self.hass, media_id, self.entity_id)
            media_id = resolved.url
        url = async_process_play_media_url(self.hass, media_id)
        if not url.startswith(("http://", "https://")):
            raise HomeAssistantError("CGD1 accepts HTTP(S) URLs or HA media sources")
        async with self._operation_lock:
            await self._stop()
            self._attr_media_title = kwargs.get("extra", {}).get("title", "CGD1 audio")
            self._attr_state = MediaPlayerState.BUFFERING
            self._attr_available = True
            self._attr_extra_state_attributes = {"live_protocol": 1}
            self._task = self.hass.async_create_task(self._play(url), "CGD1 live audio")
            self.async_write_ha_state()

    async def _play(self, url):
        client = live = process = None
        started = False
        stderr_task = None
        try:
            device = bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True)
            if device is None:
                raise ProtocolError("CGD1 unavailable through HA Bluetooth")
            client = BleakClient(device)
            await asyncio.wait_for(client.connect(), 20)
            live = LiveClient(client)
            self._live = live
            await live.connect()
            caps = await live.capabilities()
            fmt = next((f for f in FORMATS if caps.codecs & (1 << f[0])), None)
            if fmt is None:
                raise ProtocolError("No supported host encoder for enabled firmware codecs")
            codec, encoder, container, bytes_per_second = fmt
            from homeassistant.components.ffmpeg import get_ffmpeg_manager
            ffmpeg = get_ffmpeg_manager(self.hass).binary
            # Argument vector, never a shell. Do not allow arbitrary local file inputs.
            codec_options = ["-b:a", "32000"] if codec == 10 else ["-msbc", "1"] if codec == 11 else []
            process = await asyncio.create_subprocess_exec(
                ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                "-protocol_whitelist", "http,https,tcp,tls,crypto",
                "-rw_timeout", "10000000", "-i", url, "-vn", "-ac", "1", "-ar", "16000",
                "-c:a", encoder, *codec_options, "-f", container, "pipe:1",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            async def drain_errors():
                tail = b""
                while data := await process.stderr.read(1024):
                    tail = (tail + data)[-4096:]
                return tail
            stderr_task = asyncio.create_task(drain_errors())
            # Read before START: a bad URL cannot leave a live receiver waiting.
            pending = await asyncio.wait_for(process.stdout.read(512), 15)
            if not pending:
                raise ProtocolError("Source contains no decodable audio")
            await live.start(codec, self._volume())
            started = True
            self._volume_changed = False
            last_publish = 0.0
            while True:
                status = await live.status()
                credit = live.credit(status, caps.capacity)
                if status.state == 0:
                    raise ProtocolError("Playback stopped at the clock (button or alarm)")
                self._attr_state = MediaPlayerState.PLAYING if status.state == 2 else MediaPlayerState.BUFFERING
                self._attr_extra_state_attributes = {
                    "live_protocol": 1, "codec": encoder, "sample_rate": caps.rate,
                    "bytes_sent": live.sent, "bytes_consumed": status.consumed,
                    "buffer_underruns": status.underruns,
                }
                if self._volume_changed:
                    await live.volume(self._volume())
                    self._volume_changed = False
                if credit and pending:
                    count = min(credit, len(pending), 512)
                    await live.send(pending[:count])
                    pending = pending[count:]
                if not pending:
                    pending = await asyncio.wait_for(process.stdout.read(512), 10)
                    if not pending:
                        break
                now = asyncio.get_running_loop().time()
                if now - last_publish >= 1:
                    self.async_write_ha_state()
                    last_publish = now
                # Device credits pace writes; do not impose a fixed low bitrate.
                if not credit:
                    await asyncio.sleep(0.02)
                else:
                    await asyncio.sleep(0)
            code = await asyncio.wait_for(process.wait(), 5)
            if code:
                raise ProtocolError("Audio conversion failed")
            await live.finish()
            deadline = asyncio.get_running_loop().time() + caps.capacity / bytes_per_second + 5
            while True:
                status = await live.status()
                live.credit(status, caps.capacity)
                if status.state == 0:
                    break
                if asyncio.get_running_loop().time() > deadline:
                    raise ProtocolError("Receiver did not finish draining")
                await asyncio.sleep(0.05)
            self._attr_state = MediaPlayerState.IDLE
        except asyncio.CancelledError:
            raise
        except Exception as error:
            _LOGGER.warning("CGD1 playback failed: %s", error)
            self._attr_state = MediaPlayerState.IDLE
            if client is None or not client.is_connected:
                self._attr_available = False
            self._attr_extra_state_attributes = {**self._attr_extra_state_attributes, "last_error": str(error)}
        finally:
            if process and process.returncode is None:
                with suppress(ProcessLookupError):
                    process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 2)
                except asyncio.TimeoutError:
                    with suppress(ProcessLookupError):
                        process.kill()
                    await process.wait()
            if stderr_task:
                await stderr_task
            if live and started and client.is_connected:
                with suppress(Exception):
                    await asyncio.wait_for(live.stop(), 2)
            if client:
                with suppress(Exception):
                    await asyncio.wait_for(client.disconnect(), 5)
            self._live = None
            self.async_write_ha_state()
