"""Strict wire validation shared by both WebSocket services."""
import json

NATIVE_STARTUP_SECONDS = 5.0

def ai_timeout_seconds(config):
    """Allow native initialization separately from its full thinking budget."""
    overhead = NATIVE_STARTUP_SECONDS + 1.5 if config.get('engine') == 'pikafish' else 1.5
    return config['timeLimitMs'] / 1000 + overhead

class Problem(Exception):
    def __init__(self,code,message):
        super().__init__(message); self.code=code

def error(request_id,code,message):
    return dict(protocolVersion=1,type='error',requestId=request_id,code=code,message=message)

def envelope(raw):
    if not isinstance(raw,str): raise Problem('INVALID_MESSAGE','仅接收 JSON 文本消息')
    try: data=json.loads(raw)
    except (ValueError,RecursionError): raise Problem('INVALID_MESSAGE','JSON 无效')
    if not isinstance(data,dict): raise Problem('INVALID_MESSAGE','消息必须是对象')
    if type(data.get('protocolVersion')) is not int or data['protocolVersion']!=1:
        raise Problem('INVALID_MESSAGE','不支持的协议版本')
    rid=data.get('requestId')
    if not isinstance(rid,str) or not 1<=len(rid)<=128:
        raise Problem('INVALID_MESSAGE','requestId 须为 1—128 字符')
    return data

def options(data):
    if not isinstance(data,dict) or not {'maxDepth','timeLimitMs'}<=set(data) or set(data)-{'maxDepth','timeLimitMs','engine'}: raise ValueError('AI 配置字段无效')
    engine=data.get('engine','self')
    if engine not in ('self','pikafish'):raise ValueError('未知 AI 引擎')
    d,t=data['maxDepth'],data['timeLimitMs']
    maximum=128 if engine=='pikafish' else 12
    if type(d) is not int or not 1<=d<=maximum or type(t) is not int or not 100<=t<=10000:
        raise ValueError(f'AI 深度须为 1—{maximum}，时间须为 100—10000ms')
    return dict(maxDepth=d,timeLimitMs=t,**({'engine':'pikafish'} if engine=='pikafish' else {}))

def settings(data):
    if not isinstance(data,dict): raise ValueError('对局配置必须是对象')
    mode,side=data.get('mode'),data.get('humanSide')
    if mode not in ('human_human','human_ai','ai_ai'): raise ValueError('模式无效')
    if (mode=='human_ai' and side not in ('red','black')) or (mode!='human_ai' and side is not None):
        raise ValueError('人类执方配置无效')
    return dict(mode=mode,humanSide=side,redAI=options(data.get('redAI')),blackAI=options(data.get('blackAI')))
