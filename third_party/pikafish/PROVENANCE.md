# Pikafish 来源与打包说明

此目录包含第三方引擎，绝非本小组自行设计的搜索算法。

- 官方仓库：https://github.com/official-pikafish/Pikafish
- 固定发布版：Pikafish 2026-09-06。
- 发布地址：https://github.com/official-pikafish/Pikafish/releases/tag/Pikafish-2026-09-06
- 原始发布包：https://github.com/official-pikafish/Pikafish/releases/download/Pikafish-2026-09-06/Pikafish.2026-09-06.7z
- 对应源码：https://github.com/official-pikafish/Pikafish/archive/refs/tags/Pikafish-2026-09-06.zip ，已随附 `Pikafish-2026-09-06-source.zip`，未修改引擎源码或权重。
- 作者见 `AUTHORS`，代码许可见 `Copying.txt`（GPL v3），权重另适用 `NNUE-License.md`，该权重许可注明未经许可不得商用。不能将权重许可误说成 GPL。
- 本项目适配器为 `backend/pikafish.py`；Python 服务负责 UCI 协议桥接、历史重建、合法性校验和进程生命周期，界面、规则、记录、推荐和回放继续由本项目维护。

SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| Pikafish-Windows-x86-64-universal.exe | `0d57d64c212e78f96cba9e5e4f140d8872f8faa42ea631a27ab6c5db08509da3` |
| pikafish.nnue | `7d13d73569a9b571ba0eb20cf1596247bc2a42738967e61afef6482b231e900e` |
| Pikafish-2026-09-06-source.zip | `0dd14eb1d1fc1144c7a98ec824461eaf2d451a16013046652c60a2e95972ce23` |

文件均下载于 2026-10-12。校验值用于识别本次已下载文件，不是发行方签名或对独立发布摘要的核验。

请保留本目录全部许可、作者、来源和对应源码材料再打包交付。自研模式不依赖本目录。正式验收是否允许使用第三方引擎应向教师确认；报告和答辩必须明确区分自研与第三方部分。
