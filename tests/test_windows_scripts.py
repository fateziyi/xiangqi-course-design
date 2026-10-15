"""Real Windows delivery checks in disposable directories, without live ports."""
import asyncio
import json
from importlib.metadata import distribution
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import urlopen
import zipfile

from engine.rules import Position

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which('powershell.exe')


def ps_quote(path):
    return "'" + str(path).replace("'", "''") + "'"


def free_ports():
    sockets = [socket.socket() for _ in range(3)]
    try:
        for sock in sockets:
            sock.bind(('127.0.0.1', 0))
        return [sock.getsockname()[1] for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()


@unittest.skipUnless(sys.platform == 'win32' and POWERSHELL, 'Windows PowerShell required')
class WindowsDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_shutdown_releases_servers_and_native_descendants(self):
        from websockets.asyncio.client import connect
        with tempfile.TemporaryDirectory(prefix='xiangqi-lifecycle-') as directory:
            work = Path(directory)
            # Only root/log locations differ; execute the actual launcher code.
            source = (ROOT/'scripts/start.ps1').read_text(encoding='utf-8-sig')
            source = source.replace('$projectRoot = Split-Path -Parent $PSScriptRoot',
                                    '$projectRoot = ' + ps_quote(ROOT))
            source = source.replace("$runtimeDir = Join-Path $projectRoot '.runtime'",
                                    '$runtimeDir = ' + ps_quote(work/'logs'))
            script = work/'start.ps1'
            script.write_text(source, encoding='utf-8-sig')
            shutil.copyfile(ROOT/'scripts/windows-job.ps1', work/'windows-job.ps1')
            front, game, ai = free_ports()
            proc = subprocess.Popen([POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass',
                                     '-File', str(script), '-FrontendPort', str(front),
                                     '-GamePort', str(game), '-AIPort', str(ai)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            ws = None
            descendants = []
            try:
                deadline = time.monotonic()+15
                while time.monotonic()<deadline:
                    if proc.poll() is not None:
                        out,err=proc.communicate()
                        self.fail('Launcher exited before services were ready: '+out.decode(errors='replace')+err.decode(errors='replace'))
                    try:
                        ws = await connect(f'ws://127.0.0.1:{ai}', proxy=None, open_timeout=.2)
                        break
                    except (OSError, TimeoutError):
                        await asyncio.sleep(.1)
                self.assertIsNotNone(ws)
                async with connect(f'ws://127.0.0.1:{game}', proxy=None, open_timeout=2) as game_ws:
                    await game_ws.send(json.dumps(dict(protocolVersion=1,type='command',requestId='hello',
                                                       action='hello',payload={})))
                    self.assertEqual(json.loads(await game_ws.recv())['type'],'state')
                def check_frontend():
                    with urlopen(f'http://127.0.0.1:{front}',timeout=2) as response:
                        return response.status
                self.assertEqual(await asyncio.to_thread(check_frontend),200)
                await ws.send(json.dumps(dict(protocolVersion=1,type='search',requestId='lifecycle',
                    gameId='isolated',revision=0,position=Position.initial().wire(),
                    options=dict(engine='pikafish',maxDepth=128,timeLimitMs=10000))))
                # Inspect this launcher's exact process tree, including the native child.
                query = f"""$all=@(Get-CimInstance Win32_Process)
$ids=[System.Collections.Generic.HashSet[int]]::new();[void]$ids.Add({proc.pid})
do {{$added=$false;foreach($p in $all){{if($ids.Contains([int]$p.ParentProcessId) -and $ids.Add([int]$p.ProcessId)){{$added=$true}}}}}} while($added)
@($all | Where-Object {{$ids.Contains([int]$_.ProcessId)}} | Select-Object ProcessId,Name) | ConvertTo-Json -Compress"""
                raw = await asyncio.to_thread(subprocess.check_output,
                    [POWERSHELL, '-NoProfile', '-Command', query])
                descendants = json.loads(raw)
                self.assertTrue(any('Pikafish' in p['Name'] for p in descendants), descendants)
                # Abrupt owner exit also has to work; finally alone is insufficient.
                proc.terminate()
                await asyncio.to_thread(proc.wait, 10)
                await asyncio.sleep(.4)
                ids = ','.join(str(p['ProcessId']) for p in descendants)
                raw = await asyncio.to_thread(subprocess.check_output,
                    [POWERSHELL, '-NoProfile', '-Command',
                     f"@(Get-Process -Id {ids} -ErrorAction SilentlyContinue).Count"])
                self.assertEqual(int(raw.strip()), 0)
                for port in (front,game,ai):
                    with socket.socket() as sock:
                        self.assertNotEqual(sock.connect_ex(('127.0.0.1',port)), 0)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    await asyncio.to_thread(proc.wait, 10)
                if ws is not None:
                    await ws.close()
                proc.communicate()

    async def test_setup_recovers_copied_invalid_environment(self):
        with tempfile.TemporaryDirectory(prefix='xiangqi-migration-') as directory:
            work = Path(directory)
            (work/'scripts').mkdir();(work/'frontend').mkdir()
            shutil.copyfile(ROOT/'scripts/setup.ps1', work/'scripts/setup.ps1')
            shutil.copyfile(ROOT/'requirements.txt', work/'requirements.txt')
            (work/'frontend/package.json').write_text('{"name":"migration-check","version":"1.0.0"}')
            (work/'frontend/package-lock.json').write_text(
                '{"name":"migration-check","version":"1.0.0","lockfileVersion":3,"packages":{"":{"name":"migration-check","version":"1.0.0"}}}')
            (work/'.venv/Scripts').mkdir(parents=True)
            shutil.copyfile(ROOT/'.venv/Scripts/python.exe', work/'.venv/Scripts/python.exe')
            (work/'.venv/pyvenv.cfg').write_text('home = C:\\missing-xiangqi-python\nversion = 3.12.14\n')
            (work/'.venv/keep.txt').write_text('preserve this backup')
            rejected=await asyncio.to_thread(subprocess.run,
                [POWERSHELL,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(work/'scripts/setup.ps1'),
                 '-Python',str(work/'missing-python.exe')],capture_output=True,timeout=10)
            self.assertNotEqual(rejected.returncode,0)
            self.assertTrue((work/'.venv/keep.txt').exists())
            self.assertEqual(list(work.glob('.venv.backup-*')),[])
            # Exercise real pip offline, using a wheel assembled from the
            # already installed, pinned distribution rather than downloading.
            dist=distribution('websockets')
            tag=next(line[5:] for line in dist.read_text('WHEEL').splitlines() if line.startswith('Tag: '))
            wheels=work/'wheels';wheels.mkdir()
            with zipfile.ZipFile(wheels/f'websockets-{dist.version}-{tag}.whl','w') as wheel:
                for entry in dist.files:
                    if entry.parts[0] in ('websockets',f'websockets-{dist.version}.dist-info'):
                        wheel.write(dist.locate_file(entry),str(entry))
            install_env={**os.environ,'PIP_NO_INDEX':'1','PIP_FIND_LINKS':str(wheels),
                         'PIP_DISABLE_PIP_VERSION_CHECK':'1','npm_config_audit':'false','npm_config_fund':'false'}
            base = sys._base_executable
            result = await asyncio.to_thread(subprocess.run,
                [POWERSHELL,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(work/'scripts/setup.ps1'),'-Python',base],
                capture_output=True, timeout=90,env=install_env)
            self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
            backups = list(work.glob('.venv.backup-*'))
            self.assertEqual(len(backups),1)
            self.assertEqual((backups[0]/'keep.txt').read_text(),'preserve this backup')
            result = await asyncio.to_thread(subprocess.run,
                [str(work/'.venv/Scripts/python.exe'),'-c','import sys,websockets; assert sys.version_info[:2]==(3,12); assert websockets.__version__=="15.0.1"'],
                capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
