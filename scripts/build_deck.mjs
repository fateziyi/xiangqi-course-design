// Run a copy inside .runtime/deck with node_modules linked to Codex bundled packages.
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {Presentation,PresentationFile,FileBlob} from '@oai/artifact-tool';

const root=process.cwd();
const skill='C:/Users/86195/.codex/plugins/cache/openai-primary-runtime/presentations/26.1011.11113/skills/presentations';
const runtime='C:/Users/86195/.cache/codex-runtimes/codex-primary-runtime/dependencies';
process.env.RUNTIME_NODE_MODULES=path.join(runtime,'node/node_modules');
const build=path.join(root,'.runtime/deck');
const p=Presentation.create({slideSize:{width:1280,height:720}});
const ink='#282C28',muted='#697267',red='#A83E35',green='#437060',paper='#F8F9F6';
function text(slide,value,x,y,w,h,size=28,color=ink,bold=false){
  const shape=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  shape.text=value;shape.text.style={fontSize:size,typeface:'Microsoft YaHei',color,bold};shape.text.insets=0;return shape;
}
function rect(slide,x,y,w,h,color){return slide.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill:color,line:{fill:'none',width:0}})}
function slide(title,note){
  const s=p.slides.add();s.background.fill=paper;
  rect(s,64,60,6,48,red);text(s,title,90,58,1100,70,38,ink,true);
  text(s,String(p.slides.items.length).padStart(2,'0'),1160,660,50,24,14,muted);
  s.speakerNotes.text=note;return s;
}
function rows(s,items,y=170){items.forEach(([heading,body],i)=>{const yy=y+i*132;text(s,heading,90,yy,1040,40,26,red,true);text(s,body,90,yy+46,1080,75,24,ink)})}

let s=slide('中国象棋游戏及其 AI 算法','课程依据：2-题目.pdf 第1—3页；SPEC.md。个人姓名、学号及实际贡献需在正式提交前本人确认。');
text(s,'弈境',90,180,700,110,76,red,true);
text(s,'网页交互 · 权威规则 · 独立搜索服务',94,315,1060,60,30);
text(s,'专业课程设计 II   B230405',94,420,1000,50,24,muted);
text(s,'双引擎演示版   2026年10月12日',94,476,1000,50,24,muted);

s=slide('课题目标与功能范围','来源：2-题目.pdf 课题二；SPEC.md C01—C09。战胜教师仅通过现场实战确认。');
rows(s,[['三种对战模式','人人、人机、AI 对 AI；人机可选执红或执黑'],['规则与交互','合法目标、推荐起终点、将军、胜负及本次运行统计'],['对局留存','JSON 保存与导入、逐步回放、撤销一步与人机撤销一轮']]);

s=slide('模块架构与责任边界','来源：docs/design.md；engine/rules.py、backend/server.py、ai/server.py。');
const cols=[['网页界面','TypeScript + SVG','显示状态与接收操作'],['对局服务','Python · 8765','校验命令并维护权威局面'],['独立 AI','Python · 8766','自研进程 / UCI 原生引擎']];
cols.forEach((a,i)=>{const x=90+i*388;rect(s,x,200,350,5,i===2?green:red);text(s,a[0],x,230,350,55,30,ink,true);text(s,a[1],x,310,350,45,24,muted);text(s,a[2],x,375,350,90,24)});
text(s,'WebSocket / JSON',290,525,800,45,26,green,true);
text(s,'对局与 AI 复用同一规则引擎，前端不重复实现规则',90,590,1100,40,24);

s=slide('合法走法与终局判定','来源：engine/rules.py；tests/test_rules.py；SPEC.md 第4节。');
rows(s,[['两层检查','先检查棋子几何与阻挡，再模拟落子检查己方将帅安全'],['攻击检测独立','处理马腿、象眼、炮架、九宫、过河及将帅照面'],['明确的课程版裁决','将死与困毙判负；三次重复或 120 半回合无吃子判和']]);

s=slide('自研算法与第三方引擎','来源：ai/search.py、engine/evaluation.py、backend/pikafish.py；https://github.com/official-pikafish/Pikafish/releases/tag/Pikafish-2026-09-06 。Pikafish 及预训练 NNUE 权重来自第三方，来源与分别适用的许可见 third_party/pikafish/PROVENANCE.md。');
rows(s,[['自研搜索','PVS、迭代窗口、静态搜索、完整应将及历史安全缓存'],['自研评估与规则加速','机动性、阶段马炮价值与王区压力；预计算棋盘几何'],['皮卡鱼 · 第三方引擎','Pikafish 2026-09-06，UCI 适配；不冒充自研或自训']]);

s=slide('取消搜索与状态一致性','来源：backend/server.py、ai/server.py、tests/test_integration.py。');
rows(s,[['对局 ID 与版本号','新局换 ID，悔棋版本仍递增；过期响应不能污染当前局'],['独立计算进程','网络事件循环保持响应，暂停或切换局面会终止旧搜索'],['异常保留现场','超时、断连或非法 AI 着法暂停对局；错误不改成随机落子']]);

s=slide('棋谱、回放与悔棋','来源：backend/game.py；tests/test_game.py；SPEC.md 第5、8节。');
rows(s,[['棋谱与引擎身份','自研 v1、含皮卡鱼 v2；均从初始局面合法重放'],['回放与实际局面分开','逐步查看不改变统计；从节点继续先确认截断未来步骤'],['完整状态一起恢复','棋盘、行棋方、吃子计数、重复历史和终局统计同步恢复']]);

s=slide('同预算新旧算法对照','来源：docs/第二轮棋力升级.md；docs/experiments/upgrade-v4-final-vs-v3/summary.json 与 metadata.json、40份棋谱。双方均 8/1500，20 个起始前缀配对换色。结果不能换算成人类等级。');
text(s,'40 局自研 v4 对 v3，双方均 8 层上限 / 1.5 秒',90,166,1100,55,30,ink,true);
const summary=JSON.parse(await fs.readFile(path.join(root,'docs/experiments/upgrade-v4-final-vs-v3/summary.json'),'utf8'));
const basicSummary=JSON.parse(await fs.readFile(path.join(root,'docs/experiments/upgrade-v4-final-standard-basic/summary.json'),'utf8'));
if(summary.completed!==40||basicSummary.completed!==40)throw new Error('Complete both experiments before generating final deck');
for(const [i,value,label] of [[0,summary.wins,'胜'],[1,summary.draws,'和'],[2,summary.losses,'负']]){
  text(s,String(value),90+i*370,270,320,110,82,i===0?red:ink,true);text(s,label,94+i*370,395,300,40,26,muted);
}
text(s,`得分率 ${(summary.scoreRate*100).toFixed(1)}%   双方各执红 20 局`,90,485,1100,55,30,green,true);
text(s,`51 项测试通过；自研标准对基础得分率 ${(basicSummary.scoreRate*100).toFixed(1)}%`,90,575,1100,60,23);

s=slide('演示流程与分工','来源：SPEC.md 第9节、docs/组长模块报告.md、docs/组员模块报告.md。责任分工不等于个人独立编写；实际贡献须本人核实。');
rows(s,[['演示顺序','将军提示 → 两种引擎对弈 → 思考中暂停 → 棋谱回放'],['组长责任','架构、象棋规则、AI、通信和系统集成'],['组员责任','界面交互、记录操作、测试验证与操作说明']]);

s=slide('已知边界与现场验收','来源：SPEC.md A08/A13/A14；docs/acceptance.md。不得把待实战写为已战胜。');
rows(s,[['原生引擎对照','皮卡鱼 0.5 秒对自研 1.5 秒，换色 4 局全胜；不等于胜教师'],['规则与数据边界','未实现完整竞赛长将长捉；服务重启不保留内存对局'],['现场需完成','确认第三方模式认可；教师实战；个人贡献及报告核实']]);
s.speakerNotes.text+=' 原生完整对局与独立重放：docs/experiments/pikafish-vs-self-v4-final/verification.json。初始化开销单独记录，4 局不是人类等级测量。';

await fs.mkdir(build,{recursive:true});
for(const [i,s] of p.slides.items.entries()){
  const image=await p.export({slide:s,format:'png',scale:1});
  await fs.writeFile(path.join(build,`slide-${i+1}.png`),new Uint8Array(await image.arrayBuffer()));
}
const candidate=path.join(build,'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidate);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const finalPath=path.join(root,'docs/答辩演示-双引擎版.pptx');
await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath,
  pythonExecutable:path.join(runtime,'python/python.exe'),
  integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
  explicitTotalSlideCount:10,fontPolicy:{basis:'design',families:['Microsoft YaHei']},verifyArtifactToolImport:true,
  receiptPath:path.join(build,'validation-dual-engine.json')});
const imported=await PresentationFile.importPptx(await FileBlob.load(finalPath));
for(const [i,finalSlide] of imported.slides.items.entries()){
  const image=await imported.export({slide:finalSlide,format:'png',scale:1});
  await fs.writeFile(path.join(build,`final-slide-${i+1}.png`),new Uint8Array(await image.arrayBuffer()));
}
console.log(finalPath);
