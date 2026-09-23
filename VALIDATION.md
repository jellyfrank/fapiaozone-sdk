# 验证记录

日期：2026-09-19；SDK：0.1.0。

- Python 3.11 隔离虚拟环境：31 项 pytest 测试通过。
- `python -m build`：wheel 与源码包构建成功。
- 使用 Java 8 SUN 提供者运行与官方示例相同的 SHA1PRNG 密钥生成和 AES/GCM/NoPadding，
  测试密码 `synthetic-key`，固定 12 字节 IV；Python 可解密 Java 结果，固定 IV 时生成完全相同密文。
  生成代码见 `tests/fixtures/PiaozoneVector.java`，不含任何业务凭据。
- 覆盖客户端账号隔离、token 缓存与过期刷新、原请求号保留、Decimal JSON 数值、
  超时不重发、重复号／风控／未知错误原样返回、HTTP 错误与重定向、无效认证和编码、
  AES 篡改／错误密码、文件域名白名单、文件延迟、下载大小与 ZIP 解包限制。

全部 HTTP 测试使用 mock，不调用真实开票端点。尚未取得金蝶专属沙箱凭据，
未验证真实租户配置、企业开票资质、税局认证状态或真实票文件。

Odoo 20 集成测试由 Solutions `mommy_fapiao_kingdee` 记录，独立于本 SDK 的离线测试计数。

## 2026-09-23 沙箱连通性检查

- 用户提供的沙箱网页登录已验证可用，并从公开数据中心接口确认了该租户的 `accountId`。
- 同一租户的 `/api/getAppToken.do` 可访问；空参数 POST 返回缺少第三方 `appId`／`appSecret`。
- SDK 新增只读 `examples/sandbox_smoke.py`，支持鉴权及可选单张查询，不调用开票接口；31 项离线测试仍通过。
- 当前尚无该沙箱的独立 API 应用凭据，因此 **没有完成 SDK 真实鉴权、查询或开票测试**。
