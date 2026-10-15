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


def pseudo_targets(board, start):
    p = board[start]
    if not p: return
    s, kind = (1 if p > 0 else -1), abs(p)
    r, c = divmod(start, 9)
    if kind in (5, 6):
        for dr, dc in ((-1,0),(1,0),(0,-1),(0,1)):
            rr, cc, screen = r+dr, c+dc, False
            while 0 <= rr < 10 and 0 <= cc < 9:
                t = rr*9+cc
                if kind == 5:
                    yield t
                    if board[t]: break
                elif not screen:
                    if board[t]: screen = True
                    else: yield t
                elif board[t]:
                    yield t
                    break
                rr, cc = rr+dr, cc+dc
        return
    if kind == 4:
        for dr, dc in ((-2,-1),(-2,1),(2,-1),(2,1),(-1,-2),(1,-2),(-1,2),(1,2)):
            rr, cc = r+dr, c+dc
            lr, lc = r+(dr//2 if abs(dr)==2 else 0), c+(dc//2 if abs(dc)==2 else 0)
            if 0 <= rr < 10 and 0 <= cc < 9 and not board[lr*9+lc]: yield rr*9+cc
        return
    if kind == 3:
        for dr, dc in ((-2,-2),(-2,2),(2,-2),(2,2)):
            rr, cc = r+dr, c+dc
            if 0 <= rr < 10 and 0 <= cc < 9 and own_half(rr,s) and not board[(r+dr//2)*9+c+dc//2]:
                yield rr*9+cc
        return
    if kind == 2:
        for dr, dc in ((-1,-1),(-1,1),(1,-1),(1,1)):
            if palace(r+dr,c+dc,s): yield (r+dr)*9+c+dc
        return
    if kind == 1:
        for dr, dc in ((-1,0),(1,0),(0,-1),(0,1)):
            if palace(r+dr,c+dc,s): yield (r+dr)*9+c+dc
        return
    deltas = [(-s,0)]
    if not own_half(r,s): deltas += [(0,-1),(0,1)]
    for dr, dc in deltas:
        rr, cc = r+dr,c+dc
        if 0 <= rr < 10 and 0 <= cc < 9: yield rr*9+cc


def attacked(board, target, enemy):
    """Attack relation, independent of the attacker's own king safety."""
    r,c = divmod(target,9)
    for dr,dc in ((-1,0),(1,0),(0,-1),(0,1)):
        rr,cc,screen = r+dr,c+dc,False
        while 0 <= rr < 10 and 0 <= cc < 9:
            p = board[rr*9+cc]
            if p:
                if not screen:
                    if p == enemy*5: return True
                    if p == enemy and dc == 0: return True  # flying generals
                    screen = True
                else:
                    if p == enemy*6: return True
                    break
            rr,cc = rr+dr,cc+dc
    for dr,dc in ((-2,-1),(-2,1),(2,-1),(2,1),(-1,-2),(1,-2),(-1,2),(1,2)):
        rr,cc = r+dr,c+dc
        if 0 <= rr < 10 and 0 <= cc < 9 and board[rr*9+cc] == enemy*4:
            # The horse leg is measured from the attacker, not the target.
            lr,lc = rr-(dr//2 if abs(dr)==2 else 0),cc-(dc//2 if abs(dc)==2 else 0)
            if not board[lr*9+lc]: return True
    rr = r+enemy
    if 0 <= rr < 10 and board[rr*9+c] == enemy*7: return True
    for cc in (c-1,c+1):
        if 0 <= cc < 9 and board[r*9+cc] == enemy*7 and not own_half(r,enemy): return True
    for dr,dc in ((0,-1),(0,1)):
        cc=c+dc
        if 0 <= cc < 9 and board[r*9+cc] == enemy and palace(r,c,enemy): return True
    # Also support structurally valid synthetic test/search positions.
    for dr,dc in ((-1,-1),(-1,1),(1,-1),(1,1)):
        rr,cc=r+dr,c+dc
        if 0<=rr<10 and 0<=cc<9 and board[rr*9+cc]==enemy*2 and palace(r,c,enemy): return True
        rr,cc=r+2*dr,c+2*dc
        if 0<=rr<10 and 0<=cc<9 and board[rr*9+cc]==enemy*3 and own_half(r,enemy) and not board[(r+dr)*9+c+dc]: return True
    return False


def in_check(board, side):
    s=sign(side)
    return attacked(board, board.index(s), -s)


def legal_moves(board, side) -> list[Move]:
    s=sign(side)
    b=list(board)
    king=b.index(s)
    moves=[]
    for f,p in enumerate(b):
        if p*s<=0: continue
        for t in pseudo_targets(b,f):
            captured=b[t]
            if captured*s>0 or abs(captured)==1: continue
            b[t],b[f]=p,0
            if not attacked(b,t if abs(p)==1 else king,-s): moves.append((f,t))
            b[f],b[t]=p,captured
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
