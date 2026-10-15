"""Synchronous authority. No network or rendering dependencies."""
from datetime import datetime
from uuid import uuid4
from engine.rules import Position,legal_moves,in_check,move_json,parse_move
from backend.protocol import Problem,settings

class Game:
    def __init__(self,config):
        self.config=settings(config)
        self.id=str(uuid4()); self.revision=0
        self.created=datetime.now().astimezone().isoformat()
        self.positions=[Position.initial()]; self.moves=[]
        self.control='running'; self.display=0; self.imported=False; self.thinking=None

    @property
    def position(self): return self.positions[-1]

    def human_turn(self):
        return self.config['mode']=='human_human' or (self.config['mode']=='human_ai' and self.position.side==self.config['humanSide'])

    def state(self):
        actual=self.position.result()
        p=self.positions[self.display] if self.control=='replay' else self.position
        moves=legal_moves(p.board,p.side); result=p.result(moves)
        return dict(gameId=self.id,revision=self.revision,**self.config,board=list(p.board),sideToMove=p.side,
                    status='finished' if actual else 'active',control=self.control,inCheck=in_check(p.board,p.side),
                    result=actual,lastMove=move_json(self.moves[self.display-1]) if self.display else None,
                    historyLength=len(self.moves),displayPly=self.display,displayStatus='finished' if result else 'active',
                    displayResult=result,legalMoves=[] if result else list(map(move_json,moves)),thinking=self.thinking)

    def apply(self,move,human=True):
        if self.control!='running' or self.position.result(): raise Problem('INVALID_STATE','当前状态不可落子')
        if human and not self.human_turn(): raise Problem('NOT_HUMAN_TURN','当前由 AI 行棋')
        if move not in legal_moves(self.position.board,self.position.side): raise Problem('ILLEGAL_MOVE','此步不合法或不能解除将军')
        self.positions.append(self.position.play(move,validate=False)); self.moves.append(move)
        self.display=len(self.moves)

    def truncate(self,ply):
        self.moves=self.moves[:ply]; self.positions=self.positions[:ply+1]
        self.display=ply; self.control='paused'

    def command(self,action,payload):
        if action=='move': self.apply(parse_move(payload))
        elif action=='pause':
            if self.control!='running' or self.position.result(): raise Problem('INVALID_STATE','仅运行中的非终局可暂停')
            self.control='paused'
        elif action=='resume':
            if self.control!='paused' or self.position.result(): raise Problem('INVALID_STATE','仅暂停的非终局可继续')
            if self.imported:
                self.id=str(uuid4());self.imported=False;self.created=datetime.now().astimezone().isoformat()
            self.control='running'
        elif action=='undo':
            if self.control=='replay': raise Problem('INVALID_STATE','请先退出回放')
            scope=payload.get('scope')
            if scope not in ('ply','human_turn'): raise ValueError('悔棋范围无效')
            ply=len(self.moves)-1
            if scope=='human_turn':
                if self.config['mode']!='human_ai': raise Problem('INVALID_STATE','撤销一轮仅适用于人机模式')
                ply=next((i for i in range(len(self.moves)-1,-1,-1) if self.positions[i].side==self.config['humanSide']),-1)
            if ply<0: raise Problem('NOTHING_TO_UNDO','没有可撤销的步骤')
            self.truncate(ply)
        elif action in ('enter_replay','seek_replay'):
            if action=='seek_replay' and self.control!='replay': raise Problem('INVALID_STATE','尚未进入回放')
            ply=payload.get('ply')
            if type(ply) is not int or not 0<=ply<=len(self.moves): raise ValueError('回放步数越界')
            self.display=ply; self.control='replay'
        elif action=='exit_replay':
            if self.control!='replay': raise Problem('INVALID_STATE','尚未进入回放')
            self.display=len(self.moves); self.control='paused'
        elif action=='continue_from_replay':
            if self.control!='replay' or self.positions[self.display].result(): raise Problem('INVALID_STATE','只能从非终局的回放节点继续')
            self.truncate(self.display)
            if self.imported:
                self.id=str(uuid4()); self.imported=False; self.created=datetime.now().astimezone().isoformat()
        else: raise Problem('UNSUPPORTED_TYPE','不支持的命令')
        self.revision+=1; self.thinking=None

    def record(self):
        native=any(self.config[side+'AI'].get('engine')=='pikafish' for side in ('red','black'))
        return dict(format='xiangqi-course-record',version=2 if native else 1,ruleset='course-v1',createdAt=self.created,
                    **self.config,moves=list(map(move_json,self.moves)),result=self.position.result())

    @classmethod
    def from_record(cls,data):
        try:
            required={'format','version','ruleset','createdAt','mode','humanSide','redAI','blackAI','moves','result'}
            if not isinstance(data,dict) or set(data)!=required: raise ValueError('棋谱字段缺失或多余')
            if data['format']!='xiangqi-course-record' or type(data['version']) is not int or data['version'] not in (1,2) or data['ruleset']!='course-v1':
                raise ValueError('不支持的棋谱版本或规则集')
            created=data['createdAt']
            if not isinstance(created,str) or len(created)>64 or datetime.fromisoformat(created).utcoffset() is None:
                raise ValueError('createdAt 必须为带时区 ISO 时间')
            moves=data['moves']
            if not isinstance(moves,list) or len(moves)>10000: raise ValueError('moves 必须为不超过 10000 步的数组')
            game=cls(data); game.created=created
            native=any(game.config[side+'AI'].get('engine')=='pikafish' for side in ('red','black'))
            if native != (data['version']==2):raise ValueError('棋谱版本与引擎配置不一致')
            for i,m in enumerate(moves):
                try: game.apply(parse_move(m),human=False)
                except (ValueError,Problem) as e: raise ValueError(f'第 {i+1} 半回合：{e}')
            result=data['result']
            if result is not None:
                if not isinstance(result,dict) or set(result)!={'winner','reason'} or result['winner'] not in ('red','black',None) or result['reason'] not in ('checkmate','stalemate','threefold','no_capture_limit'):
                    raise ValueError('result 字段无效')
            if result!=game.position.result(): raise ValueError('result 与重放结果矛盾')
            game.control='replay'; game.imported=True
            return game
        except (ValueError,TypeError,KeyError,RecursionError) as e:
            raise Problem('INVALID_RECORD',str(e)) from e

class Controller:
    def __init__(self): self.game=None; self.results={}

    def stats(self):
        return dict(redWins=sum(r['winner']=='red' for r in self.results.values()),
                    blackWins=sum(r['winner']=='black' for r in self.results.values()),
                    draws=sum(r['winner'] is None for r in self.results.values()))

    def reconcile(self):
        g=self.game
        if not g or g.imported: return
        result=g.position.result()
        if result: self.results[g.id]=result
        else: self.results.pop(g.id,None)

    def state(self):
        return dict(protocolVersion=1,type='state',game=self.game.state() if self.game else None,stats=self.stats())

    def validate_version(self,request):
        gid,rev=request.get('gameId'),request.get('revision')
        if self.game:
            if gid!=self.game.id or type(rev) is not int or rev!=self.game.revision: raise Problem('STALE_STATE','局面已变化，请基于最新状态操作')
        elif gid is not None or rev is not None: raise Problem('STALE_STATE','当前尚无对局')

    def dispatch(self,request):
        action=request.get('action'); payload=request.get('payload')
        if not isinstance(payload,dict): raise ValueError('payload 必须为对象')
        rid=request['requestId']
        if action=='hello': return self.state(),False
        self.validate_version(request)
        if action=='new_game': self.game=Game(payload)
        elif action=='import_record': self.game=Game.from_record(payload.get('record'))
        else:
            if not self.game: raise Problem('NO_GAME','请先创建对局')
            if action=='export_record': return dict(protocolVersion=1,type='record',requestId=rid,record=self.game.record()),False
            if action=='recommend':
                if self.game.thinking or (self.game.control=='running' and not self.game.human_turn() and not self.game.position.result()):
                    raise Problem('INVALID_STATE','自动行棋时不能请求推荐')
                return None,False
            self.game.command(action,payload)
        self.reconcile()
        return dict(protocolVersion=1,type='ack',requestId=rid),True
