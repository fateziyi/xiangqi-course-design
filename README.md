# 弈境 中国象棋游戏及其 AI 算法

本机课程设计项目。网页显示棋盘，Python 对局服务维护权威局面，独立 Python AI 服务通过 WebSocket 接收 JSON 并返回着法。功能边界、接口与验收要求见 `SPEC.md`。

当前提供 **自研算法 / 皮卡鱼（第三方引擎）** 两种 AI，红黑可分别选择。自研基础 2/0.5 秒、标准 8/1.5 秒、强力 12/10 秒；皮卡鱼各档深度上限 128、思考预算相同，另有初始化开销。切换后须创建新局，旧棋谱不改参数。第三方代码、权重、许可、作者及对应源码随项目保留。[双引擎使用说明](docs/双引擎使用说明.md)；[第二轮自研升级](docs/第二轮棋力升级.md)。教师实战仍未完成，第三方模式用于验收需教师认可。

## 两人协作

公开仓库：https://github.com/fateziyi/xiangqi-course-design 。同学获得协作者邀请并接受后，可向仓库推送自己的开发分支；无需共享账号或密码。

```powershell
git lfs install
git clone https://github.com/fateziyi/xiangqi-course-design.git
Set-Location xiangqi-course-design
git lfs pull
# 首次按下文安装依赖，然后从最新 main 创建自己的功能分支
git switch main
git pull --ff-only
git switch -c feature/board-interaction
# 修改完成并验证后，明确选择本次改动的文件提交
git add frontend/src/main.ts
git commit -m "Improve board interaction"
git push -u origin feature/board-interaction
```

在 GitHub 创建 Pull Request，目标分支选 `main`，由另一人检查后合并。各自使用不同功能分支，修改相同模块前先沟通；不要强制推送 `main`。每次工作前更新主分支。`AGENTS.md` 和 `SPEC.md` 是共同执行约定，需求变化先更新规格。

首次获取及本机传输故障的实际排查记录见 [GitHub 协作与网络说明](docs/GitHub协作与网络说明.md)。

Git 不包含 `.venv`、`node_modules`、构建输出、运行日志及环境变量文件，新电脑需单独安装依赖。原始课程题目 PDF 和分组名单 DOCX 留在本地，由组内另行获取；公开仓库的需求与实现说明见 `SPEC.md`。皮卡鱼二进制、对应源码与许可文件一并保留，约 48 MB 的权重通过 Git LFS 保存。Git for Windows 通常附带 Git LFS；克隆前执行 `git lfs install`，克隆后执行 `git lfs pull`，确认权重已下载，再安装和启动。不要将 LFS 指针文件误当成权重，也不要只下载 GitHub 源码 ZIP 来代替完整克隆。

## 环境与安装

已验证：Windows、Python 3.12.14、Node 22.20.0、npm 10.9.3。Python 需稳定版 3.12；系统 `python` 可能是 WindowsApps 占位程序，不建议直接使用。

在项目根目录打开 PowerShell。首次安装需要网络：

```powershell
# 若当前计算机有 Codex 的捆绑 Python，脚本可自动定位
.\scripts\setup.ps1
# 其他计算机请显式指定已安装的 Python 3.12
.\scripts\setup.ps1 -Python 'C:\实际安装目录\python.exe'
```

依赖固定在 `requirements.txt` 与 `frontend/package-lock.json`。启动脚本不安装依赖、不联网获取 AI、不需要 API Key。

复制整个项目到另一台电脑后，请先用该电脑的 Python 3.12 执行上述安装命令。脚本会检测随文件夹复制的 `.venv` 是否可用；若失效，先验证指定的 Python，再将旧环境保留为 `.venv.backup-*` 并重建。备份不自动删除。PowerShell 脚本兼容 Windows PowerShell 5.1 和 PowerShell 7。

## 启动与停止

```powershell
.\scripts\start.ps1
```

浏览器访问 `http://127.0.0.1:5173`。保留启动终端，按 Ctrl+C 停止本次启动的三个服务。日志在 `.runtime`。端口被占用时明确报错，不会杀掉其他程序。

启动器通过 Windows Job Object 管理本次服务及其后代；停止或关闭启动器时一并回收 Python 工作进程和皮卡鱼。皮卡鱼初始化最多等待 5 秒，完成后再开始所选思考预算；初始化耗时不计入标注的 0.5/1.5/10 秒。

```powershell
# 如默认端口已占用，可整套切换；前端自动采用对应对局服务地址
.\scripts\start.ps1 -FrontendPort 5174 -GamePort 8775 -AIPort 8776
```

手动开发启动可分别运行以下命令，三个终端均以项目根目录为起点：

```powershell
.\.venv\Scripts\python.exe -m ai.server
.\.venv\Scripts\python.exe -m backend.server
# 前端终端先进入 frontend
Set-Location frontend
npm.cmd run dev
```

## 使用

1. 选择人人、人机或 AI 对战；人机可选执方。两侧 AI 可分别选基础、标准、强力或自定义深度和时间。设置仅在创建新局时生效。
2. 点击己方棋子显示绿色合法目标，再点击目标落子。红方先行。绿色虚线圆环是推荐起终点，不会自动行棋。
3. 暂停会取消当前搜索；继续按当前局面重新搜索。撤销一步适用所有模式；撤销一轮适用人机，退回最近一次人类行棋前，悔棋后需手动继续。
4. 导出棋谱下载 JSON。导入会校验并逐步合法重放，成功后进入回放；失败保留当前局。回放支持起点、上步、下步、终点及从节点继续。
5. 新局、导入和从回放节点继续前会提示未保存历史或截断后续步骤。重要对局请主动导出。

同一服务只允许一个浏览器控制连接。第二个页面会提示已有控制连接；先关闭原页面再刷新。断连后对局暂停，重连恢复完整局面；服务进程重启后内存对局和本次统计不保留。

## 规则边界

采用 `course-v1`：将死、困毙均判负；相同棋盘与行棋方第三次出现、连续 120 半回合无吃子判和；胜负判定优先于和棋。将帅不能被普通着法吃掉。未实现完整竞赛长将长捉责任方裁决。

## 测试与构建

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\python.exe -m scripts.ai_client
# 独立客户端命令需要先启动 AI 服务
Set-Location frontend
npm.cmd run build
```

集成测试自行启动临时端口的服务，不会接管现有浏览器对局。包含真实 WebSocket、100 半回合 AI 对战、取消、过期消息、非法输入、断连、棋谱与状态恢复测试。

```powershell
# 根目录运行；40 局、双方各执红 20 局，完整保留失败和棋谱
.\.venv\Scripts\python.exe -m scripts.benchmark --workers 6 --output docs/experiments/复测目录
```

`scripts/p0_check.py` 仅记录最初启动骨架验证，不能针对最终 AI 接口运行；最终通信验收以 `tests/test_integration.py` 和 `scripts/ai_client.py` 为准。

## 材料与后续验收

- `docs/design.md`：架构、接口、规则、搜索与记录设计。
- `docs/acceptance.md`：实际验收记录与未完成项。
- [验收准备手册](docs/验收准备手册.md)：现场讲稿、演示步骤、常见追问、代码定位和修改练习。
- `docs/experiments/baseline`：40 局原始数据、环境、源码哈希和汇总。
- `fixtures/mate_one.json`：10 个一步将死测试，含预期着法。
- [可导入棋谱样例](samples/棋谱样例/README.md)：初始、开局、吃子、红胜、黑胜及重复和棋共 6 份 JSON，均通过导入及逐节点回放校验。
- `docs/组长模块报告.md`、`docs/组员模块报告.md`：按责任范围分开的技术报告稿，个人信息与实际参与过程须由本人核实，教师模板发布后排版。
- `docs/答辩演示-双引擎版.pptx`：当前可编辑答辩演示；原 `答辩演示.pptx` 留作升级前历史材料。

自动化棋力实验不能代替战胜指导教师的实战验收。不得在报告中把“待实战”写为“已战胜”。
