# 金蝶发票云旗舰版 Python SDK

独立于 Odoo 的 `fapiaozone-sdk`，Python 导入名为 `piaozone`。接口风格参考 `sf-sdk`：
客户端负责认证与公共请求，`client.invoice` 提供开票业务方法。各实例独立保存账号、会话和 token。
这是青岛欧姆维护的第三方 SDK，不是金蝶官方 SDK，也不适用于发票云标准版。

## 安装与使用

```bash
pip install 'git+ssh://git@github.com/jellyfrank/fapiaozone-sdk.git@main'
```

正式部署建议将 `main` 替换为已经验证的完整提交 SHA。尚未发布 PyPI。

```python
import os
from decimal import Decimal
from piaozone import Piaozone

with Piaozone(
    base_url=os.environ['PIAOZONE_BASE_URL'],  # 必须包含租户路径
    app_id=os.environ['PIAOZONE_APP_ID'],
    app_secret=os.environ['PIAOZONE_APP_SECRET'],
    account_id=os.environ['PIAOZONE_ACCOUNT_ID'],
    user=os.environ['PIAOZONE_USER'],
    business_system_code=os.environ['PIAOZONE_SYSTEM_CODE'],
    encryption='base64',  # 或 aes，并传 aes_password
) as client:
    result = client.invoice.query('已持久保存的原请求号', '销方税号')
```

开蓝票调用 `client.invoice.issue_blue(serial_no, payload)`；payload 使用官方字段：
`invoiceType`（01 专票／02 普票）、`sellerName`、`sellerTaxpayerId`、`buyerName`、
`drawer`（乐企必填）、`invoiceDetail`。每行包含 `lineProperty`、`goodsName`、
`revenueCode`、`amount`、`taxRate`；金额与数量建议用 `Decimal`，JSON 保持数值精度。
字段完整性、税目适用性及特殊行业规则由调用方负责校验；SDK 不推断税率、税收编码或优惠政策。

## 已封装范围

- app_token、access_token 获取与到期前刷新，支持 UserName／Mobile。
- BASE64、与官方 Java Sun SHA1PRNG 示例一致的 AES-128-GCM 编解码。
- `ALLE.INVOICE.OPEN` 数电蓝票直接开票、`ALLE.INVOICE.QUERY` 原流水号查询。
- `piaozone.documents.download_documents` 下载 PDF／OFD／XML，支持单 XML ZIP 解包，
  限定 HTTPS 主机白名单、禁止重定向，每文件及解包结果限制 10 MB。
- 通用 `client.call(interface_code, data)` 供其他官方接口扩展。

直接开票不是单据拆分合并接口。红冲、作废、税局登录、人脸认证和回调服务器不在本版封装范围。
使用官方允许的主动轮询路径，不需要开放匿名回调入口。

## 状态与恢复

`success=true/errorCode=0` 仅表示接口受理；是否出票必须查询 `invoiceStatus`。
提交返回的 `data` 按不透明值保留：官方示例为明文流水号，说明却标注需解密；本库不依赖该值判定出票。
查询数据按所配置的编码方式解码，金额保留 `Decimal`。

调用方必须在发送前持久保存全局唯一 `serial_no`（最多 50 字符）。SDK 绝不自动重发，
包括超时、HTTP 错误、token 拒绝和重复号 10127。失败报文保留原 errorCode 供调用方判断；
网络和格式异常分别抛出 `TransportError`／`ProtocolError`，都不能等同于开票失败。
请求受理后响应丢失时，只查询原请求，不生成新号。

账号必须使用金蝶分配的测试或正式租户地址，SDK 不根据域名猜测环境。
下载文件的允许域名必须由管理员根据实际存储域名显式配置，不能直接信任远端报文添加白名单。
下载返回 `Document(name, mimetype, data: bytes)`，不写文件；查询出票与文件下载应分开保存，文件晚到可重试。
HTTP/认证异常不包含原始 URL、凭据或响应体；业务返回报文可能含个人数据，调用方应脱敏审计。

## 验证与官方资料

```bash
pip install -e '.[test]'
pytest
python -m build
```

取得沙箱的独立 API 凭据后，可用只读脚本先验证 SDK 鉴权；网页登录密码不能替代
`appId` 和 `appSecret`。从项目根目录运行，环境变量至少设置
`PIAOZONE_BASE_URL`、`PIAOZONE_APP_ID`、`PIAOZONE_APP_SECRET`、
`PIAOZONE_ACCOUNT_ID`、`PIAOZONE_USER`，手机号登录另设 `PIAOZONE_USER_TYPE=Mobile`：

```bash
python examples/sandbox_smoke.py
```

如有已知的原开票流水号和销方税号，再设置 `PIAOZONE_SYSTEM_CODE` 并传入
`--serial-no`、`--seller-taxpayer-id` 做单张查询。脚本不会开票，也不会打印 token、密钥或发票内容。

离线测试不调用税局、不使用真实税票。没有金蝶租户凭据时，不能据此认定沙箱联调完成。
截至 2026-09-19，检索官方文档及公开代码索引未找到匹配旗舰版接口的可复用 Python SDK；
官方提供 HTTP、Postman 与 Java 加解密示例，因此单独封装本库。

- [直接开票接入指引](https://open-ultimate.piaozone.com/doc-3750584)
- [app_token](https://open-ultimate.piaozone.com/api-145421044)／[access_token](https://open-ultimate.piaozone.com/api-145421045)
- [蓝字直接开票](https://open-ultimate.piaozone.com/api-149332334)／[单张查询](https://open-ultimate.piaozone.com/api-146003726)
- [加解密](https://open-ultimate.piaozone.com/doc-3626887)／[返回码](https://open-ultimate.piaozone.com/doc-3799582)
