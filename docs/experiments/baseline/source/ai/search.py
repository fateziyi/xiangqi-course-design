"""Own Negamax / Alpha-Beta / iterative deepening, no external engine."""
import time
from engine.rules import legal_moves,sign,move_json
from engine.evaluation import evaluate,VALUES

MATE=100000
class BudgetExpired(Exception):pass

class Search:
    def __init__(self,deadline):self.deadline=deadline;self.nodes=0

    def check(self):
        if time.monotonic()>=self.deadline:raise BudgetExpired()

    def ordered(self,p,moves,preferred=None):
        return sorted(moves,key=lambda m:(m==preferred,10*VALUES[abs(p.board[m[1]])]-VALUES[abs(p.board[m[0]])] if p.board[m[1]] else -1000),reverse=True)

    def negamax(self,p,depth,alpha,beta,ply,preferred=None):
        self.check();self.nodes+=1
        moves=legal_moves(p.board,p.side)
        result=p.result(moves)
        if result:return (-MATE+ply if result['winner'] else 0),[]
        if depth==0:return sign(p.side)*evaluate(p.board),[]
        best=-MATE*2;line=[]
        for move in self.ordered(p,moves,preferred):
            score,pv=self.negamax(p.play(move,validate=False),depth-1,-beta,-alpha,ply+1)
            score=-score
            if score>best:best,line=score,[move]+pv
            alpha=max(alpha,score)
            if alpha>=beta:break
        return best,line

def search(position,options):
    started=time.monotonic();worker=Search(started+options['timeLimitMs']/1000)
    moves=legal_moves(position.board,position.side)
    result=position.result(moves)
    best=None if result else worker.ordered(position,moves)[0]
    pv=[] if best is None else [best]
    score=(-MATE if result and result['winner'] else 0) if result else sign(position.side)*evaluate(position.board)
    completed=0
    if not result:
        for depth in range(1,options['maxDepth']+1):
            try:value,line=worker.negamax(position,depth,-MATE*2,MATE*2,0,best)
            except BudgetExpired:break
            score,pv,completed=value,line,depth;best=line[0]
            if score>=MATE-100:break
    return dict(move=move_json(best),search=dict(completedDepth=completed,nodes=worker.nodes,
                elapsedMs=round((time.monotonic()-started)*1000),score=score,pv=list(map(move_json,pv))))
