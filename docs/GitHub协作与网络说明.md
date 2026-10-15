# GitHub 协作与本次上传排查

仓库：https://github.com/fateziyi/xiangqi-course-design

## 2026-10-15 实际排查结果

- 仓库地址、公开状态和账号权限均已真实核对，远端 `main` 与本地提交一致。
- 本机系统代理、用户持久环境变量及当前终端环境均指向 `127.0.0.1:7897`，监听进程为 `com.vortex.helper`。Git 没有额外的代理地址覆盖，没有发现旧端口残留。没有修改系统代理或全局 Git 配置。
- 四组只读对照（当前代理/直连，各自使用默认协议/显式 HTTP/1.1）全部成功，耗时约 1.5—4.2 秒，实际协议均为 HTTP/1.1。这只能证明小请求正常，不能代表大文件上传正常。
- 原始普通 Git 包约 52.30 MiB，上传中曾收到 HTTP 408；移除进程代理后的普通 Git 上传也出现连接重置。故障定位在大包传输阶段，未发现 API 地址错误。具体超时发生在代理、出口网络还是服务端等待环节，现有证据不足以唯一确定，不能据此断言代理程序存在缺陷。
- 权重改为 Git LFS 后，通过服务器提供的存储上传地址发送 50,706,378 字节，约 4 分钟完成；存储返回 HTTP 200，LFS 校验通过。之后标准 Git LFS 客户端确认对象存在，代码推送成功。权重 SHA-256 保持 `7d13d73569a9b571ba0eb20cf1596247bc2a42738967e61afef6482b231e900e`。

处理重点是避免再次将大权重塞入普通 Git 包，而不是随意更换 GitHub 地址。Git LFS 的独立存储上传和校验流程见[官方 Basic Transfer API](https://github.com/git-lfs/git-lfs/blob/main/docs/api/basic-transfers.md)。

## 本机已经应用的项目级配置

```powershell
git config --local http.version HTTP/1.1
git config --local http.postBuffer 104857600
git config --local lfs.concurrenttransfers 1
git config --local lfs.activitytimeout 120
git config --local lfs.dialtimeout 30
git config --local lfs.transfer.maxretries 2
```

以上只存于本项目的 `.git/config`，不影响其他仓库，也不会随克隆传播。缓冲配置用于普通 Git 请求的传输兼容；它不是对网络超时根因的证明，也不能替代 LFS。LFS 活动超时限制无进展等待，不承诺大文件在 120 秒内传完。

没有把 `7897` 硬编码到 Git，因此以后更换代理时应核对 Windows 设置和 `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY`，环境变量变化后重新打开终端。不要使用 `http.sslVerify=false` 绕过证书验证，也不要把令牌写进远程地址。

## 同学首次获取项目

安装 Git for Windows（含 Git LFS）及 README 指定的 Node.js、Python 3.12，然后执行：

```powershell
git lfs install
git clone https://github.com/fateziyi/xiangqi-course-design.git
Set-Location xiangqi-course-design
git lfs pull
git lfs fsck
# 按 README 安装依赖、启动；各自使用功能分支并提交 Pull Request。
```

权重应为 50,706,378 字节；若只得到约百字节的文本，说明拿到的是 LFS 指针，需要完成 `git lfs pull`。本地 `.venv` 和 `node_modules` 不随 Git 分发。公开仓库可以克隆、Fork 并提出 PR；直接向原仓库推送分支需要接受协作者邀请。
