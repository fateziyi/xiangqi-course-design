"""Pure course-v1 rules. Index = row * 9 + column; red is positive."""
from dataclasses import dataclass
import json

Move = tuple[int, int]


def other(side: str) -> str:
    return 'black' if side == 'red' else 'red'


def sign(side: str) -> int:
    return 1 if side == 'red' else -1


def initial_board() -> tuple[int, ...]:
    b = [0] * 90
    back = [5, 4, 3, 2, 1, 2, 3, 4, 5]
    b[:9] = [-p for p in back]
    b[81:] = back
    for i in (19, 25): b[i] = -6
    for i in (64, 70): b[i] = 6
    for c in range(0, 9, 2): b[27+c], b[54+c] = -7, 7
    return tuple(b)


def validate_board(board):
    if not isinstance(board, (list, tuple)) or len(board) != 90:
        raise ValueError('board 必须包含 90 个整数')
    if any(type(p) is not int or not -7 <= p <= 7 for p in board):
        raise ValueError('board 棋子编码无效')
    if board.count(1) != 1 or board.count(-1) != 1:
        raise ValueError('局面必须恰有一个红帅和一个黑将')


def palace(r, c, s):
    return 3 <= c <= 5 and (7 <= r <= 9 if s == 1 else 0 <= r <= 2)


def own_half(r, s):
    return r >= 5 if s == 1 else r <= 4


def key(board, side):
    return json.dumps(list(board), separators=(',', ':')) + '|' + side


# Geometry is immutable and independent of occupancy. Direction order is kept
# identical to v3 so deterministic fallback and equal-score ordering are stable.
ORTHOGONAL = ((-1,0),(1,0),(0,-1),(0,1))
HORSE_STEPS = ((-2,-1),(-2,1),(2,-1),(2,1),(-1,-2),(1,-2),(-1,2),(1,2))
DIAGONAL = ((-1,-1),(-1,1),(1,-1),(1,1))
RAYS = []
HORSES = []
HORSE_ATTACKERS = []
SMALL_TARGETS = {}
ELEPHANTS = {}
ADVISOR_ATTACKERS = {}
ELEPHANT_ATTACKERS = {}
PAWN_ATTACKERS = {}
KING_ATTACKERS = {}
for start in range(90):
    r,c=divmod(start,9)
    rays=[]
    for dr,dc in ORTHOGONAL:
        ray=[];rr,cc=r+dr,c+dc
        while 0<=rr<10 and 0<=cc<9:
            ray.append(rr*9+cc);rr+=dr;cc+=dc
        rays.append(tuple(ray))
    RAYS.append(tuple(rays))
    horses=[];attackers=[]
    for dr,dc in HORSE_STEPS:
        rr,cc=r+dr,c+dc
        if 0<=rr<10 and 0<=cc<9:
            horses.append((rr*9+cc,(r+(dr//2 if abs(dr)==2 else 0))*9+c+(dc//2 if abs(dc)==2 else 0)))
            attackers.append((rr*9+cc,(rr-(dr//2 if abs(dr)==2 else 0))*9+cc-(dc//2 if abs(dc)==2 else 0)))
    HORSES.append(tuple(horses));HORSE_ATTACKERS.append(tuple(attackers))
    for side in (-1,1):
        SMALL_TARGETS[(1,side,start)] = tuple((r+dr)*9+c+dc for dr,dc in ORTHOGONAL if palace(r+dr,c+dc,side))
        SMALL_TARGETS[(2,side,start)] = tuple((r+dr)*9+c+dc for dr,dc in DIAGONAL if palace(r+dr,c+dc,side))
        deltas=((-side,0),) if own_half(r,side) else ((-side,0),(0,-1),(0,1))
        SMALL_TARGETS[(7,side,start)] = tuple((r+dr)*9+c+dc for dr,dc in deltas if 0<=r+dr<10 and 0<=c+dc<9)
        ELEPHANTS[(side,start)] = tuple(((r+2*dr)*9+c+2*dc,(r+dr)*9+c+dc) for dr,dc in DIAGONAL if 0<=r+2*dr<10 and 0<=c+2*dc<9 and own_half(r+2*dr,side))
        ADVISOR_ATTACKERS[(side,start)] = tuple((r+dr)*9+c+dc for dr,dc in DIAGONAL if 0<=r+dr<10 and 0<=c+dc<9 and palace(r,c,side))
        ELEPHANT_ATTACKERS[(side,start)] = tuple(((r+2*dr)*9+c+2*dc,(r+dr)*9+c+dc) for dr,dc in DIAGONAL if 0<=r+2*dr<10 and 0<=c+2*dc<9 and own_half(r,side))
        pawn=[]
        if 0<=r+side<10:pawn.append((r+side)*9+c)
        if not own_half(r,side):pawn.extend(r*9+cc for cc in (c-1,c+1) if 0<=cc<9)
        PAWN_ATTACKERS[(side,start)] = tuple(pawn)
        KING_ATTACKERS[(side,start)] = tuple(r*9+cc for cc in (c-1,c+1) if 0<=cc<9 and palace(r,c,side))
RAYS=tuple(RAYS);HORSES=tuple(HORSES);HORSE_ATTACKERS=tuple(HORSE_ATTACKERS)


def pseudo_targets(board, start):
    p=board[start]
    if not p:return
    s=1 if p>0 else -1;kind=abs(p)
    if kind in (5,6):
        for ray in RAYS[start]:
            screen=False
            for target in ray:
                occupied=board[target]
                if kind==5:
                    yield target
                    if occupied:break
                elif not screen:
                    if occupied:screen=True
                    else:yield target
                elif occupied:
                    yield target;break
    elif kind==4:
        for target,leg in HORSES[start]:
            if not board[leg]:yield target
    elif kind==3:
        for target,eye in ELEPHANTS[(s,start)]:
            if not board[eye]:yield target
    else:
        yield from SMALL_TARGETS[(kind,s,start)]


def attacked(board, target, enemy):
    """Same v3 attack relation, using precomputed geometry only."""
    rook,cannon=enemy*5,enemy*6
    for direction,ray in enumerate(RAYS[target]):
        screen=False
        for index in ray:
            p=board[index]
            if not p:continue
            if not screen:
                if p==rook or (direction<2 and p==enemy):return True
                screen=True
            else:
                if p==cannon:return True
                break
    horse=enemy*4
    for index,leg in HORSE_ATTACKERS[target]:
        if board[index]==horse and not board[leg]:return True
    pawn=enemy*7
    if any(board[index]==pawn for index in PAWN_ATTACKERS[(enemy,target)]):return True
    if any(board[index]==enemy for index in KING_ATTACKERS[(enemy,target)]):return True
    advisor=enemy*2
    if any(board[index]==advisor for index in ADVISOR_ATTACKERS[(enemy,target)]):return True
    elephant=enemy*3
    return any(board[index]==elephant and not board[eye] for index,eye in ELEPHANT_ATTACKERS[(enemy,target)])


def in_check(board, side):
    s=sign(side)
    return attacked(board, board.index(s), -s)


def legal_moves(board, side, *, captures_only=False, limit=None) -> list[Move]:
    """Same authority for full, capture-only and existence queries.

    Filters act before simulation; they never relax king-safety validation.
    """
    s=sign(side)
    b=list(board)
    king=b.index(s)
    moves=[]
    for f,p in enumerate(b):
        if p*s<=0: continue
        for t in pseudo_targets(b,f):
            captured=b[t]
            if captured*s>0 or abs(captured)==1: continue
            if captures_only and not captured: continue
            b[t],b[f]=p,0
            if not attacked(b,t if abs(p)==1 else king,-s): moves.append((f,t))
            b[f],b[t]=p,captured
            if limit is not None and len(moves)>=limit: return moves
    return moves


def move_json(move):
    return None if move is None else {'from':move[0],'to':move[1]}


def parse_move(data):
    if not isinstance(data,dict) or set(data)!={'from','to'}:
        raise ValueError('走法必须为 from/to 对象')
    f,t=data['from'],data['to']
    if type(f) is not int or type(t) is not int or not 0<=f<90 or not 0<=t<90 or f==t:
        raise ValueError('走法坐标无效')
    return f,t


@dataclass(frozen=True)
class Position:
    board: tuple[int,...]
    side: str = 'red'
    no_capture: int = 0
    keys: tuple[str,...] = ()

    @classmethod
    def initial(cls):
        b=initial_board()
        return cls(b,'red',0,(key(b,'red'),))

    def play(self,move: Move,validate=True):
        if validate and move not in legal_moves(self.board,self.side): raise ValueError('非法走法')
        b=list(self.board); f,t=move; captured=b[t]
        b[t],b[f]=b[f],0
        side=other(self.side)
        return Position(tuple(b),side,0 if captured else self.no_capture+1,self.keys+(key(b,side),))

    def result(self,moves=None):
        moves=legal_moves(self.board,self.side) if moves is None else moves
        if not moves:
            return {'winner':other(self.side),'reason':'checkmate' if in_check(self.board,self.side) else 'stalemate'}
        if self.keys.count(key(self.board,self.side))>=3: return {'winner':None,'reason':'threefold'}
        if self.no_capture>=120: return {'winner':None,'reason':'no_capture_limit'}
        return None

    def wire(self):
        return dict(board=list(self.board),sideToMove=self.side,noCapturePly=self.no_capture,positionKeys=list(self.keys))


def parse_position(data):
    if not isinstance(data,dict): raise ValueError('position 必须是对象')
    b=data.get('board'); validate_board(b)
    side=data.get('sideToMove'); n=data.get('noCapturePly'); keys=data.get('positionKeys')
    if side not in ('red','black'): raise ValueError('sideToMove 无效')
    if type(n) is not int or not 0<=n<=120: raise ValueError('noCapturePly 无效')
    if not isinstance(keys,list) or not 1<=len(keys)<=10001: raise ValueError('positionKeys 无效')
    for k in keys:
        if not isinstance(k,str) or len(k)>400: raise ValueError('局面键无效')
        raw,sep,ks=k.rpartition('|')
        if not sep or ks not in ('red','black'): raise ValueError('局面键格式无效')
        kb=json.loads(raw); validate_board(kb)
        if key(kb,ks)!=k: raise ValueError('局面键不是规范表示')
    if keys[-1]!=key(b,side): raise ValueError('历史末项与当前局面不一致')
    return Position(tuple(b),side,n,tuple(keys))
