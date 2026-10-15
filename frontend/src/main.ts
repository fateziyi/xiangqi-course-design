import './style.css';
import {drawBoard} from './board';
import type {State,Move,Mode,AIConfig,Result} from './types';

const $=<T extends HTMLElement=HTMLElement>(id:string)=>document.getElementById(id) as T;
const app=$('app');
app.innerHTML=`<header><a class="brand" href="/" aria-label="弈境首页"><span class="brand-mark">弈</span><span>弈境<small>中国象棋</small></span></a><span id="connection" role="status">正在连接…</span></header>
<main><section class="play-area"><div class="board-heading"><div><h1>方寸之间，落子有道。</h1><p>一盘好棋，从下一步开始。</p></div><span id="mode-label">中国象棋</span></div>
<div class="player black-player"><span class="avatar black">将</span><div><strong>黑方</strong><small id="black-role">等待开局</small></div><span id="black-turn"></span></div>
<div class="board-stage"><div id="board"></div><div id="check-alert" role="status" aria-live="assertive" hidden><span>将军</span></div></div><div class="player"><span class="avatar red">帅</span><div><strong>红方</strong><small id="red-role">等待开局</small></div><span id="red-turn"></span></div>
<div class="board-foot"><span id="move-count">第 0 步</span><span>红方先行 · 点击棋子查看合法落点</span></div></section>
<aside><section class="controls"><h2>对局设置</h2><label for="mode">对战模式</label><select id="mode"><option value="human_ai">人机对战</option><option value="human_human">人人对战</option><option value="ai_ai">AI 对战</option></select>
<div id="side-field"><label for="side">我的执方</label><select id="side"><option value="red">红方 · 先手</option><option value="black">黑方 · 后手</option></select></div>
<div class="ai-fields"><div><label for="red-engine">红方 AI 引擎</label><select id="red-engine"><option value="self">自研算法</option><option value="pikafish">皮卡鱼 · 第三方引擎</option></select><label for="red-ai">思考预算</label><select id="red-ai"><option value="standard">标准 · 1.5 秒</option><option value="basic">基础 · 0.5 秒</option><option value="strong">强力 · 10 秒</option><option value="custom">自定义</option></select><div class="custom" id="red-custom" hidden><label>深度<input id="red-depth" type="number" min="1" max="12" value="4"></label><label>毫秒<input id="red-time" type="number" min="100" max="10000" value="1500"></label></div></div>
<div><label for="black-engine">黑方 AI 引擎</label><select id="black-engine"><option value="self">自研算法</option><option value="pikafish">皮卡鱼 · 第三方引擎</option></select><label for="black-ai">思考预算</label><select id="black-ai"><option value="standard">标准 · 1.5 秒</option><option value="basic">基础 · 0.5 秒</option><option value="strong">强力 · 10 秒</option><option value="custom">自定义</option></select><div class="custom" id="black-custom" hidden><label>深度<input id="black-depth" type="number" min="1" max="12" value="4"></label><label>毫秒<input id="black-time" type="number" min="100" max="10000" value="1500"></label></div></div></div>
<button id="new" class="primary">开始新对局</button><p class="settings-note">设置仅在新局生效</p></section>
<section class="controls"><div class="section-title"><h2>当前对局</h2><span id="control-label">未开始</span></div><div id="status" role="status">选择模式，开始你的第一步。</div><p id="notice" role="alert"></p>
<div class="button-row"><button id="pause">暂停</button><button id="recommend">推荐走法</button></div><div class="button-row"><button id="undo">撤销一步</button><button id="undo-round">撤销一轮</button></div><p id="search-info">推荐走法以绿色标记，不会自动落子。</p></section>
<section class="controls"><div class="section-title"><h2>对局记录</h2><span id="history-count">0 步</span></div><div class="button-row"><button id="export">导出棋谱</button><button id="import">导入棋谱</button></div><input id="file" type="file" accept="application/json,.json" hidden>
<button id="replay" class="wide">查看回放</button><div id="replay-controls" hidden><div class="replay-nav"><button id="first" aria-label="回放起点">起点</button><button id="prev" aria-label="回放上一步">上步</button><button id="next" aria-label="回放下一步">下步</button><button id="last" aria-label="回放终点">终点</button></div><div class="button-row"><button id="branch">从此处继续</button><button id="exit">退出回放</button></div></div></section>
<section class="statistics"><span>本次运行</span><div><p><strong id="red-wins">0</strong>红胜</p><p><strong id="black-wins">0</strong>黑胜</p><p><strong id="draws">0</strong>和棋</p></div></section></aside></main>
<footer><span>中国象棋游戏及其 AI 算法</span><details><summary>课程版规则说明</summary><p>将死与困毙均判负；相同局面及行棋方第三次出现、连续 120 半回合无人吃子判和。未实现竞赛长将长捉裁决。棋谱请主动导出，服务重启不保留内存对局。</p></details></footer>
<dialog id="confirm-dialog" aria-labelledby="confirm-title"><h2 id="confirm-title">确认操作</h2><p id="confirm-message"></p><div class="button-row"><button id="confirm-cancel" autofocus>取消</button><button id="confirm-ok" class="primary">确认继续</button></div></dialog>`;

let state:State={protocolVersion:1,type:'state',game:null,stats:{redWins:0,blackWins:0,draws:0}};
let selected:number|null=null,recommend:Move|null=null,connected=false,ready=false,pending=false;
let socket:WebSocket,retryTimer:ReturnType<typeof setTimeout>|null=null,controlBusy=false;
let sentAt:number|null=null;
let checkTimer:ReturnType<typeof setTimeout>|null=null;
function hideCheck(){
  if(checkTimer)clearTimeout(checkTimer);
  checkTimer=null;$('check-alert').hidden=true;
}
function announceCheck(next:State['game']){
  const previous=state.game;
  const advanced=next&&previous&&next.gameId===previous.gameId&&next.historyLength>previous.historyLength;
  if(!next||next.control==='replay'||next.gameId!==previous?.gameId||next.historyLength<(previous?.historyLength??0))hideCheck();
  if(!advanced||!next.inCheck||next.status!=='active'||next.control!=='running')return;
  hideCheck();const alert=$('check-alert');alert.hidden=false;
  alert.getAnimations().forEach(animation=>animation.cancel());
  // Restart the CSS entrance for a second check before the first has faded.
  void alert.offsetWidth;
  alert.classList.remove('check-enter');void alert.offsetWidth;alert.classList.add('check-enter');
  checkTimer=setTimeout(hideCheck,1400);
}
const val=(id:string)=>$(id) as HTMLSelectElement;
const presets:Record<string,AIConfig>={basic:{maxDepth:2,timeLimitMs:500},standard:{maxDepth:8,timeLimitMs:1500},strong:{maxDepth:12,timeLimitMs:10000}};
const labels:Record<Mode,string>={human_human:'人人对战',human_ai:'人机对战',ai_ai:'AI 对战'};
const reasons:Record<Result['reason'],string>={checkmate:'将死',stalemate:'困毙',threefold:'三次重复局面',no_capture_limit:'连续 120 半回合无吃子'};
function notice(text:string){$('notice').textContent=text}
function ask(message:string):Promise<boolean>{
  const dialog=$('confirm-dialog') as HTMLDialogElement;
  $('confirm-message').textContent=message;dialog.returnValue='cancel';dialog.showModal();
  return new Promise(resolve=>{
    dialog.onclose=()=>resolve(dialog.returnValue==='ok');
    $('confirm-cancel').onclick=()=>dialog.close('cancel');$('confirm-ok').onclick=()=>dialog.close('ok');
  });
}
function command(action:string,payload:object={}){
  if(!connected||!ready||pending)return;
  if(action!=='hello')notice('');
  if(!['hello','recommend','export_record'].includes(action)){pending=true;sentAt=performance.now()}
  socket.send(JSON.stringify({protocolVersion:1,type:'command',requestId:crypto.randomUUID(),action,gameId:state.game?.gameId??null,revision:state.game?.revision??null,payload}));
  render();
}
function render(){
  const g=state.game;
  drawBoard($('board'),g,selected,recommend,onSquare);
  $('connection').textContent=connected&&ready?'服务已连接':controlBusy?'已有页面控制此对局':'连接已断开 · 正在重连';
  $('connection').className=connected&&ready?'online':'';
  $('mode-label').textContent=g?labels[g.mode]:'中国象棋';
  const active=g?.control==='running'&&g.status==='active';
  const human=g&&(g.mode==='human_human'||g.mode==='human_ai'&&g.humanSide===g.sideToMove);
  const who=(side:string)=>g?(g.mode==='human_human'||g.mode==='human_ai'&&g.humanSide===side?'人类棋手':`AI · ${g[(side+'AI') as 'redAI'|'blackAI'].engine==='pikafish'?'皮卡鱼':'自研'}`):'等待开局';
  $('red-role').textContent=who('red');$('black-role').textContent=who('black');
  for(const side of ['red','black'])$(side+'-turn').textContent=g?.sideToMove===side?(g.thinking?'正在思考…':g.control==='replay'?'回放行棋方':active?'轮到行棋':'等待继续'):'';
  const result=g?.displayResult;
  $('status').textContent=!g?'选择模式，开始你的第一步。':result?`${result.winner?(result.winner==='red'?'红方':'黑方')+'获胜':'和棋'} · ${reasons[result.reason]}`:g.control==='replay'?`正在回放第 ${g.displayPly} 步`:g.thinking?`${g.thinking.side==='red'?'红方':'黑方'} AI 正在${g.thinking.purpose==='recommend'?'计算推荐':'思考'}…`:g.control==='paused'?'对局已暂停，点击继续后行棋。':`${g.sideToMove==='red'?'红方':'黑方'}行棋${g.inCheck?' · 将军！请解除将军':''}`;
  $('control-label').textContent=g?(g.control==='replay'?'回放中':g.status==='finished'?'已结束':{running:'进行中',paused:'已暂停',replay:'回放中'}[g.control]):'未开始';
  $('move-count').textContent=`第 ${g?.displayPly??0} 步`;
  $('history-count').textContent=g?.control==='replay'?`${g.displayPly} / ${g.historyLength}`:`${g?.historyLength??0} 步`;
  $('red-wins').textContent=String(state.stats.redWins);$('black-wins').textContent=String(state.stats.blackWins);$('draws').textContent=String(state.stats.draws);
  const disable=(id:string,condition:boolean)=>{($(id) as HTMLButtonElement).disabled=!connected||!ready||pending||condition};
  disable('new',false); disable('import',false);disable('export',!g);
  disable('pause',!g||g.status==='finished'||g.control==='replay');$('pause').textContent=g?.control==='paused'?'继续':'暂停';
  disable('recommend',!g||!!g.thinking||!!active&&!human);disable('undo',!g||!g.historyLength||g.control==='replay');
  disable('undo-round',!g||g.mode!=='human_ai'||g.control==='replay'||g.historyLength<(g.humanSide==='red'?1:2));
  disable('replay',!g||g.control==='replay');$('replay-controls').hidden=g?.control!=='replay';
  for(const id of ['first','prev'])disable(id,!g||g.displayPly===0);
  for(const id of ['next','last'])disable(id,!g||g.displayPly===g.historyLength);
  disable('branch',!g||g.displayStatus==='finished'); disable('exit',!g);
}
function onSquare(i:number){
  const g=state.game;
  if(!g||!connected||!ready||pending||g.control!=='running'||g.status!=='active'||g.mode==='ai_ai'||g.mode==='human_ai'&&g.humanSide!==g.sideToMove)return;
  if(selected!==null&&g.legalMoves.some(m=>m.from===selected&&m.to===i)){
    command('move',{from:selected,to:i});selected=null;recommend=null;notice('');return;
  }
  const p=g.board[i],own=g.sideToMove==='red'?p>0:p<0;
  selected=own&&selected!==i?i:null;render();
}
function connect(){
  socket=new WebSocket(import.meta.env.VITE_GAME_URL||'ws://127.0.0.1:8765');
  socket.onopen=()=>{connected=true;ready=true;pending=false;command('hello')};
  socket.onmessage=e=>{
    const msg=JSON.parse(e.data);
    if(msg.type==='state'){
      announceCheck(msg.game);
      if(state.game?.gameId!==msg.game?.gameId||state.game?.revision!==msg.game?.revision){selected=null;recommend=null;$('search-info').textContent='推荐走法以绿色标记，不会自动落子。'}
      state=msg;ready=true;pending=false;render();
      if(sentAt!==null){performance.clearMeasures('xiangqi-command-roundtrip');performance.measure('xiangqi-command-roundtrip',{start:sentAt,end:performance.now()});sentAt=null}
    }else if(msg.type==='error'){
      pending=false;notice(msg.message);if(msg.code==='CONTROL_BUSY'){controlBusy=true;ready=false;}render();
    }else if(msg.type==='recommendation'){
      if(msg.gameId===state.game?.gameId&&msg.revision===state.game?.revision){recommend=msg.move;$('search-info').textContent=msg.move?`推荐 ${Math.floor(msg.move.from/9)+1}行${msg.move.from%9+1}列 → ${Math.floor(msg.move.to/9)+1}行${msg.move.to%9+1}列 · 深度 ${msg.search.completedDepth} · ${msg.search.elapsedMs}ms`:'终局没有推荐走法';render()}
    }else if(msg.type==='record'){
      const url=URL.createObjectURL(new Blob([JSON.stringify(msg.record,null,2)],{type:'application/json'}));
      const a=document.createElement('a');a.href=url;a.download=`象棋棋谱-${new Date().toISOString().replaceAll(':','-')}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notice('棋谱已导出。');
    }
  };
  socket.onclose=()=>{connected=false;ready=false;pending=false;selected=null;render();if(!controlBusy)retryTimer=setTimeout(connect,1500)};
  socket.onerror=()=>notice('无法连接对局服务，请检查启动终端。');
}
function aiConfig(side:string):AIConfig{
  const engine=val(side+'-engine').value;
  const preset=val(side+'-ai').value;
  const config:AIConfig=preset==='custom'?{maxDepth:Number(($(`${side}-depth`) as HTMLInputElement).value),timeLimitMs:Number(($(`${side}-time`) as HTMLInputElement).value)}:{...presets[preset]};
  if(engine==='pikafish'){config.engine='pikafish';if(preset!=='custom')config.maxDepth=128}
  return config;
}
$('new').onclick=async()=>{
  if(state.game&&!await ask('开始新局将放弃当前未保存对局，是否继续？'))return;
  notice('');command('new_game',{mode:val('mode').value,humanSide:val('mode').value==='human_ai'?val('side').value:null,redAI:aiConfig('red'),blackAI:aiConfig('black')});
};
val('mode').onchange=()=>{$('side-field').hidden=val('mode').value!=='human_ai'};
for(const side of ['red','black'])val(side+'-ai').onchange=()=>{$(side+'-custom').hidden=val(side+'-ai').value!=='custom'};
for(const side of ['red','black'])val(side+'-engine').onchange=()=>{
  const depth=$(`${side}-depth`) as HTMLInputElement;
  const native=val(side+'-engine').value==='pikafish';depth.max=native?'128':'12';
  depth.value=String(native?128:Math.min(12,Number(depth.value)));
};
$('pause').onclick=()=>command(state.game?.control==='paused'?'resume':'pause');
$('recommend').onclick=()=>{notice('');command('recommend')};
$('undo').onclick=()=>command('undo',{scope:'ply'});$('undo-round').onclick=()=>command('undo',{scope:'human_turn'});
$('export').onclick=()=>command('export_record');$('import').onclick=()=>($('file') as HTMLInputElement).click();
($('file') as HTMLInputElement).onchange=async e=>{
  const input=e.target as HTMLInputElement,file=input.files?.[0];input.value='';if(!file)return;
  if(file.size>1048576){notice('棋谱文件超过 1MiB');return}
  if(state.game&&!await ask('导入棋谱将替换当前未保存对局，是否继续？'))return;
  try{command('import_record',{record:JSON.parse(await file.text())})}catch{notice('文件不是有效 JSON 棋谱。')}
};
$('replay').onclick=()=>command('enter_replay',{ply:0});
for(const [id,value] of [['first',()=>0],['prev',()=>state.game!.displayPly-1],['next',()=>state.game!.displayPly+1],['last',()=>state.game!.historyLength]] as const)$(id).onclick=()=>command('seek_replay',{ply:value()});
$('exit').onclick=()=>command('exit_replay');$('branch').onclick=async()=>{if(await ask('将截断此节点之后的步骤并暂停，是否继续？'))command('continue_from_replay')};
window.addEventListener('beforeunload',()=>{if(retryTimer)clearTimeout(retryTimer)});
render();connect();
