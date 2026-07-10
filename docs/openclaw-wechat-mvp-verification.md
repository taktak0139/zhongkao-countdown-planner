# OpenClaw 微信日报 MVP 验证

## 当前链路

学生提交 → 生成日报 → OpenClaw webhook → 微信群 → 日志记录。

## 配置方式

- `OPENCLAW_WECHAT_ENABLED`：设为 `1` 时启用推送，其他值均不发送。
- `OPENCLAW_WEBHOOK_URL`：OpenClaw 提供的 webhook 地址。
- `OPENCLAW_WECHAT_GROUP`：目标微信群标识。
- `OPENCLAW_PAYLOAD_MODE`：请求正文字段，支持 `text` 或 `content`，默认 `text`。

根据 OpenClaw webhook 实际文档选择 payload 模式，不要在项目文件中写入真实凭证。

## 启动方式

在启动服务前设置环境变量：

```bash
export OPENCLAW_WECHAT_ENABLED=1
export OPENCLAW_WEBHOOK_URL="<OPENCLAW_WEBHOOK_URL>"
export OPENCLAW_WECHAT_GROUP="<WECHAT_GROUP>"
export OPENCLAW_PAYLOAD_MODE=text
python3 server.py
```

## 手动补发

```bash
python3 tools/send_latest_report.py
```

## 真实验证步骤

1. 配置真实 OpenClaw webhook。
2. 启动 `server.py`。
3. 学生完成一次真实试卷。
4. 确认 `reports/` 生成日报。
5. 确认微信群收到日报。
6. 检查 `logs/openclaw.log`。
7. 推送失败时，确认学生提交仍成功。

## 常见问题

- **OpenClaw 推送未开启**：确认 `OPENCLAW_WECHAT_ENABLED=1`。
- **缺少 webhook**：设置 `OPENCLAW_WEBHOOK_URL`后重启服务。
- **缺少群标识**：设置 `OPENCLAW_WECHAT_GROUP`。
- **webhook 返回非 2xx**：核对 webhook 地址、权限和 payload 模式。
- **本地网络异常**：检查运行服务的机器是否能访问 OpenClaw。
- **日报不存在**：先确认真实试卷已成功提交，再手动补发。
- **微信群未收到但日志显示成功**：HTTP 2xx 只表示 webhook 已接收，需继续检查 OpenClaw 内部路由、群标识和机器人权限。

## 安全说明

- 不提交真实 webhook。
- 不提交 Token、Cookie 或 Authorization 信息。
- 不在日志中记录敏感配置或日报全文。
- 不在公开仓库提交学生隐私。
