# OpenClaw 本机微信推送契约核查

核查日期：2026-07-10

## 结论摘要

本机没有可直接调用的 OpenClaw 微信群 webhook。已安装的标准 OpenClaw 和 QClaw 都没有为当前项目提供经过验证的 HTTP 接口地址、群标识和 JSON 契约。

标准 OpenClaw 本地文档明确说明：微信通道由外部包 `@tencent-weixin/openclaw-weixin` 提供，当前能力元数据支持私聊和媒体，**没有声明群聊能力**。

## 本机环境

- OpenClaw CLI：`/opt/homebrew/bin/openclaw`
- 版本：`2026.6.11`
- Gateway：LaunchAgent 正在运行，仅监听本机 `127.0.0.1:18789`
- Gateway 配置：`~/.openclaw/openclaw.json`
- Gateway 启动项：`~/Library/LaunchAgents/ai.openclaw.gateway.plist`
- 标准 OpenClaw 配置中没有微信 channel，也没有启用 `openclaw-weixin` 插件。
- QClaw 配置中 `wechat-access` 已启用且存在 WebSocket 地址，但可读配置中没有可用 token、guid 或 userId。
- QClaw 相关日志是加密文件，未提取或输出其中的凭证。

## 1. 真实接口地址

**未找到，且当前安装不对外提供这个接口。**

- `http://127.0.0.1:18789/` 是 Gateway 控制界面/协议端口，不是微信群 webhook。
- Gateway 主要使用本地 WebSocket RPC，不是“POST Markdown 到微信群”的公开契约。
- OpenClaw `webhooks` CLI 当前只列出 Gmail Pub/Sub 辅助功能；自动化 webhook 文档是入站任务触发，不是微信出站 webhook。
- QClaw `wechat-access` 使用 WebSocket 通道，本机配置、启动脚本和可读文档都没有暴露 HTTP webhook。

## 2. 请求方法

**无可确认的 HTTP 请求方法。**

标准 OpenClaw 的正常出站消息路径是 channel plugin 内部 outbound contract，从 CLI 角度由以下形式发起：

```text
openclaw message send --channel <channel> --target <target> --message <text>
```

微信外部插件再内部调用腾讯 iLink API。这不等于对项目公开一个 HTTP POST 契约。

## 3. 请求 JSON 格式

**未找到可用于微信群的公开 JSON 格式。**

项目当前通用适配层所支持的 `{"group":"...","text":"..."}` 或 `{"group":"...","content":"..."}` 只是候选格式，**不是本机 OpenClaw/QClaw 已验证的真实契约**。在获得提供方文档前不应启用。

## 4. 群名称或群 ID

OpenClaw 通用 CLI 在 channel plugin 支持 directory 时可以使用：

```text
openclaw directory groups list --channel <channel>
openclaw directory groups members --channel <channel> --group-id <id>
```

但当前 `openclaw-weixin` 未声明群聊能力，且本机标准 OpenClaw 没有安装该插件。因此：

- 当前不能通过 OpenClaw directory 获取微信群 ID。
- QClaw 本地配置中也没有群名称或群 ID。
- `guid` 和 `userId` 是 QClaw 账号/设备身份字段，不能当作微信群 ID。

## 5. Token、Header 或签名

- OpenClaw Gateway 有自己的认证 token，用于 Gateway WebSocket/控制访问；它不是微信群 webhook token。
- `openclaw-weixin` 通过二维码登录，由插件内部保存账号凭证并处理 Tencent iLink API 认证。
- QClaw `wechat-access` 依赖内部 channel token/WebSocket 认证，但可读配置中没有可供本项目使用的 token。
- 没有本地文档证明微信群接口需要哪个 HTTP Header 或签名算法，不能猜测 Authorization、Cookie 或签名字段。

本报告没有记录任何完整 token、Cookie、Authorization 值、WebSocket 地址或其他密钥。

## 证据来源

- `/opt/homebrew/lib/node_modules/openclaw/docs/channels/wechat.md`
- `/opt/homebrew/lib/node_modules/openclaw/docs/cli/message.md`
- `/opt/homebrew/lib/node_modules/openclaw/docs/cli/directory.md`
- `/opt/homebrew/lib/node_modules/openclaw/docs/automation/webhook.md`
- `~/.openclaw/openclaw.json`（仅核对键名与存在性）
- `~/.qclaw/openclaw.json`（仅核对键名与存在性）
- `~/Library/LaunchAgents/ai.openclaw.gateway.plist`
- `/Applications/QClaw.app/Contents/Resources/app.asar`（仅核对通道类型与字段线索）

## 最终回答

### A. 能否直接推送微信群

**不能。** 本机没有经过验证的微信群出站接口，而本地文档明确说当前微信插件未声明群聊能力。

### B. 缺少什么

1. 明确支持微信群出站发送的 provider/插件或机器人。
2. 该 provider 的正式接口地址、请求方法、JSON 格式和认证方式。
3. 可发送的目标微信群 ID，以及获取/授权该 ID 的受支持流程。

### C. 下一步最少操作

先向实际微信接入提供方确认“是否支持群聊出站”。如果腾讯后续版本的 `@tencent-weixin/openclaw-weixin` 声明了群聊能力，最少浥程是：安装/升级插件 → 二维码登录 → 用 `openclaw directory groups list --channel openclaw-weixin` 确认群 ID → 先做 `openclaw message send --dry-run`。

如果该插件仍不支持群聊，则需要另外获取一个明确支持群聊的微信/企业微信机器人 webhook 及官方契约；在此之前不应启用项目的 OpenClaw 推送开关。
