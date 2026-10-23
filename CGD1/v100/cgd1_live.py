#!/usr/bin/env python3
"""Send live audio to CGD1 v10.0 without Home Assistant (diagnostic client)."""
import argparse
import asyncio
from contextlib import suppress
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent/'ha/custom_components/cgd1_speaker'))
from protocol import LiveClient

async def play(args):
    from bleak import BleakClient
    async with BleakClient(args.address) as client:
        live=LiveClient(client)
        await live.connect()
        caps=await live.capabilities()
        if not caps.codecs & (1<<8):
            raise RuntimeError('This diagnostic sender requires the existing G.722 decoder')
        process=await asyncio.create_subprocess_exec(
            args.ffmpeg,'-nostdin','-hide_banner','-loglevel','error','-i',args.source,
            '-vn','-ac','1','-ar','16000','-c:a','g722','-f','g722','pipe:1',
            stdout=asyncio.subprocess.PIPE,
        )
        started=False
        try:
            pending=await asyncio.wait_for(process.stdout.read(512),15)
            if not pending:raise RuntimeError('No audio')
            await live.start(8,args.volume);started=True
            while True:
                status=await live.status()
                credit=live.credit(status,caps.capacity)
                if not status.state:raise RuntimeError('Stopped by clock')
                if credit:
                    n=min(credit,len(pending));await live.send(pending[:n]);pending=pending[n:]
                if not pending:
                    pending=await asyncio.wait_for(process.stdout.read(512),10)
                    if not pending:break
                if not credit:await asyncio.sleep(.02)
            if await process.wait():raise RuntimeError('FFmpeg failed')
            await live.finish()
            for _ in range(100):
                status=await live.status();live.credit(status,caps.capacity)
                if not status.state:break
                await asyncio.sleep(.05)
            else:raise RuntimeError('Drain timeout')
            print(f'Finished: {live.sent} bytes; underruns={status.underruns}')
        finally:
            if process.returncode is None:
                with suppress(ProcessLookupError):process.terminate()
                try:await asyncio.wait_for(process.wait(),2)
                except asyncio.TimeoutError:
                    with suppress(ProcessLookupError):process.kill()
                    await process.wait()
            if started and client.is_connected:
                with suppress(Exception):await live.stop()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('address',help='CGD1 Bluetooth MAC')
    parser.add_argument('source',help='Audio file or URL, decoded on this host')
    parser.add_argument('--volume',type=int,choices=range(6),default=3)
    parser.add_argument('--ffmpeg',default='ffmpeg')
    args=parser.parse_args()
    try:asyncio.run(play(args))
    except KeyboardInterrupt:pass
