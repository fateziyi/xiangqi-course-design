import type {GameState,Move} from './types';
const names:Record<string,string[]>={red:['','帅','仕','相','马','车','炮','兵'],black:['','将','士','象','马','车','炮','卒']};
const point=(i:number)=>[48+(i%9)*60,48+Math.floor(i/9)*60];
export function drawBoard(host:HTMLElement,g:GameState|null,selected:number|null,recommend:Move|null,onClick:(i:number)=>void){
  const paintStart=performance.now();
  const lines:string[]=[];
  for(let r=0;r<10;r++) lines.push(`<path d="M48 ${48+r*60}H528"/>`);
  for(let c=0;c<9;c++) lines.push(c===0||c===8?`<path d="M${48+c*60} 48V588"/>`:`<path d="M${48+c*60} 48V288 M${48+c*60} 348V588"/>`);
  lines.push('<path d="M228 48L348 168M348 48L228 168M228 468L348 588M348 468L228 588"/>');
  const dots=new Set(g?.legalMoves.filter(m=>m.from===selected).map(m=>m.to));
  const squares=Array.from({length:90},(_,i)=>{
    const [x,y]=point(i),p=g?.board[i]??0,side=p>0?'red':'black';
    const last=g?.lastMove && (i===g.lastMove.from||i===g.lastMove.to);
    const hint=recommend && (i===recommend.from||i===recommend.to);
    return `<g class="square" data-square="${i}" role="button" tabindex="${g?0:-1}" aria-label="${Math.floor(i/9)+1}行${i%9+1}列${p?names[side][Math.abs(p)]:'空位'}">
      <rect x="${x-29}" y="${y-29}" width="58" height="58" fill="transparent"/>
      ${last?`<rect x="${x-25}" y="${y-25}" width="50" height="50" rx="8" class="last"/>`:''}
      ${hint?`<circle cx="${x}" cy="${y}" r="28" class="hint"/>`:''}
      ${p?`<circle cx="${x}" cy="${y+2}" r="24" class="piece-shadow"/><circle cx="${x}" cy="${y}" r="24" class="piece ${side} ${selected===i?'selected':''}"/><circle cx="${x}" cy="${y}" r="19.5" class="piece-ring ${side}"/><text x="${x}" y="${y+1}" class="piece-text ${side}">${names[side][Math.abs(p)]}</text>`:''}
      ${dots.has(i)?`<circle cx="${x}" cy="${y}" r="${p?27:6}" class="${p?'capture-target':'target'}"/>`:''}
    </g>`;
  }).join('');
  host.innerHTML=`<svg viewBox="0 0 576 636" aria-label="中国象棋棋盘" class="chessboard"><rect width="576" height="636" rx="12" class="wood"/><g class="grid">${lines.join('')}</g><text x="168" y="322" class="river">楚 河</text><text x="408" y="322" class="river">汉 界</text>${squares}</svg>`;
  host.querySelectorAll<SVGGElement>('[data-square]').forEach(el=>{
    const click=()=>onClick(Number(el.dataset.square));
    el.onclick=click; el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();click()}};
  });
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
    performance.clearMeasures('xiangqi-board-paint');
    performance.measure('xiangqi-board-paint',{start:paintStart,end:performance.now()});
  }));
}
