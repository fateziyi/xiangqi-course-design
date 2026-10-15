"""Transparent UCI adapter. Pikafish is third-party, not our search algorithm."""
import asyncio
import json
import os
from pathlib import Path
import re
import sys
import time

from engine.rules import Position, legal_moves, move_json, parse_move
from backend.protocol import NATIVE_STARTUP_SECONDS

ROOT=Path(__file__).resolve().parents[1]
HOME=ROOT/'third_party/pikafish'
EXE=HOME/'Pikafish-Windows-x86-64-universal.exe'
NETWORK=HOME/'pikafish.nnue'
VERSION='Pikafish 2026-09-06'
PIECES={1:'k',2:'a',3:'b',4:'n',5:'r',6:'c',7:'p'}


def uci_move(move):
    return ''.join(chr(97+i%9)+str(9-i//9) for i in move)


def from_uci(text):
    if not re.fullmatch('[a-i][0-9][a-i][0-9]',text):raise ValueError('Invalid UCI move')
    return parse_move({'from':(9-int(text[1]))*9+ord(text[0])-97,
                       'to':(9-int(text[3]))*9+ord(text[2])-97})


def fen(board,side,no_capture=0):
    rows=[]
    for row in range(10):
        text='';empty=0
        for p in board[row*9:row*9+9]:
            if not p:empty+=1;continue
            if empty:text+=str(empty);empty=0
            letter=PIECES[abs(p)];text+=letter.upper() if p>0 else letter
        if empty:text+=str(empty)
        rows.append(text)
    return '/'.join(rows)+(' w ' if side=='red' else ' b ')+f'- - {no_capture} 1'


def history_command(position):
    """Reconstruct every transition, rather than silently discarding draws."""
    if not position.keys:raise ValueError('Pikafish requires position history')
    raw,side=position.keys[0].rsplit('|',1)
    board=tuple(json.loads(raw))
    initial_clock=max(0,position.no_capture-len(position.keys)+1)
    p=Position(board,side,initial_clock,(position.keys[0],));moves=[]
    for target_key in position.keys[1:]:
        if p.no_capture>=120 or p.keys.count(p.keys[-1])>=3:
            raise ValueError('Pikafish history continues after course draw')
        raw,target_side=target_key.rsplit('|',1);target=tuple(json.loads(raw))
        changed=[i for i,(a,b) in enumerate(zip(p.board,target)) if a!=b]
        if len(changed)!=2:raise ValueError('Pikafish history has no unique move')
        sources=[i for i in changed if p.board[i] and not target[i]]
        if len(sources)!=1:raise ValueError('Pikafish history has invalid source')
        start=sources[0];end=next(i for i in changed if i!=start);move=(start,end)
        # The public service already checks key syntax. Here verify actual
        # legal transitions as well, including side, captures and king safety.
        p=p.play(move)
        if p.board!=target or p.side!=target_side:raise ValueError('Pikafish history transition mismatch')
        moves.append(uci_move(move))
    if p.board!=position.board or p.side!=position.side or p.no_capture!=position.no_capture:
        raise ValueError('Pikafish history does not match current position')
    return 'position fen '+fen(board,side,initial_clock)+(' moves '+' '.join(moves) if moves else '')


def parse_info(line):
    tokens=line.split()
    if not tokens or tokens[0]!='info' or 'pv' not in tokens or 'score' not in tokens:return None
    if 'lowerbound' in tokens or 'upperbound' in tokens:return None
    try:
        if 'multipv' in tokens and tokens[tokens.index('multipv')+1]!='1':return None
        depth=int(tokens[tokens.index('depth')+1]);nodes=int(tokens[tokens.index('nodes')+1])
        i=tokens.index('score');kind,amount=tokens[i+1],int(tokens[i+2])
        if kind not in ('cp','mate'):return None
        score=amount if kind=='cp' else (1 if amount>=0 else -1)*(100000-min(999,2*abs(amount)))
        pv=[from_uci(m) for m in tokens[tokens.index('pv')+1:]]
        return dict(completedDepth=depth,nodes=nodes,score=score,pv=pv)
    except (ValueError,IndexError):return None


async def search(position,options):
    started=time.monotonic();moves=legal_moves(position.board,position.side)
    terminal=position.result(moves)
    if terminal:
        return dict(move=None,search=dict(completedDepth=0,nodes=0,elapsedMs=0,
            score=-100000 if terminal['winner'] else 0,pv=[],engine='pikafish',engineVersion=VERSION))
    if not EXE.is_file() or not NETWORK.is_file():raise RuntimeError('Pikafish executable or NNUE file missing')
    proc=None;phase='初始化'
    async def run():
        nonlocal proc,phase
        async def send(text):
            proc.stdin.write((text+'\n').encode());await proc.stdin.drain()
        async def read():
            raw=await proc.stdout.readline()
            if not raw:raise RuntimeError(f'Pikafish exited unexpectedly ({proc.returncode})')
            line=raw.decode('utf-8',errors='replace').strip()
            if 'CRITICAL ERROR' in line:raise RuntimeError(line)
            return line
        async def until(expected):
            while await read()!=expected:pass
        async with asyncio.timeout(NATIVE_STARTUP_SECONDS):
            # Long imported histories must not block cancellation on the event loop.
            command=await asyncio.to_thread(history_command,position)
            flags={'creationflags':0x08000000} if sys.platform=='win32' else {}
            spawn=asyncio.create_task(asyncio.create_subprocess_exec(str(EXE),cwd=HOME,
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,**flags))
            try:proc=await asyncio.shield(spawn)
            except asyncio.CancelledError:
                proc=await spawn;raise
            await send('uci');await until('uciok')
            await send(f'setoption name Threads value {min(4,max(1,(os.cpu_count() or 2)//2))}')
            await send('setoption name Hash value 128')
            await send('setoption name EvalFile value '+str(NETWORK))
            await send('ucinewgame');await send('isready');await until('readyok')
            await send(command)
        thinking=time.monotonic()
        phase='搜索'
        startup_ms=round((thinking-started)*1000)
        # Like the Python worker's search telemetry, thinking time excludes
        # process/model startup. Outer timeout still bounds the entire request.
        async with asyncio.timeout(options['timeLimitMs']/1000+1.0):
            await send(f'go depth {options["maxDepth"]} movetime {options["timeLimitMs"]} searchmoves '+' '.join(map(uci_move,moves)))
            info_by_move={}
            while True:
                line=await read()
                if line.startswith('bestmove '):
                    best=from_uci(line.split()[1]);break
                info=parse_info(line)
                if info and info['pv']:info_by_move[info['pv'][0]]=info
            if best not in moves:raise RuntimeError('Pikafish returned an illegal best move')
            info=info_by_move.get(best,dict(completedDepth=0,nodes=0,score=0,pv=[best]))
            p=position;pv=[]
            for move in info['pv']:
                if p.result():break  # course-v1 terminal may precede native rules
                if move not in legal_moves(p.board,p.side):raise RuntimeError('Pikafish returned an illegal PV')
                pv.append(move);p=p.play(move,validate=False)
            if not pv or pv[0]!=best:raise RuntimeError('Pikafish PV disagrees with best move')
            await send('quit')
            return dict(move=move_json(best),search=dict(**{k:v for k,v in info.items() if k!='pv'},
                elapsedMs=round((time.monotonic()-thinking)*1000),startupMs=startup_ms,
                totalElapsedMs=round((time.monotonic()-started)*1000),pv=list(map(move_json,pv)),
                engine='pikafish',engineVersion=VERSION))
    try:
        return await run()
    except TimeoutError as exc:
        raise TimeoutError(f'皮卡鱼{phase}超时，请重试或检查本机负载。') from exc
    finally:
        if proc and proc.returncode is None:
            try:proc.terminate()
            except ProcessLookupError:pass
            await proc.wait()
