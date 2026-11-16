# 三分钟看懂这个项目

业务背景：品牌请博主做推广，运营人员需要把活动和公开作品对应起来，知道哪些资料已核实、哪些需要继续查。

1. 打开首页，选 **NVIDIA · Back to school**。左边两条视频来自 NeoReach 公开案例中的真实链接。初始显示的是有日期的研究快照。
2. 点 **Run agent**。右边会显示实际步骤：读活动说明、查记录、请求 YouTube 元数据、检查证据、写报告。这次会真正调用 Vertex AI。
3. 查看报告。每条结论下面的链接能展开其依据。一个链接返回 404 时，只能说本次没有查到元数据，不能说博主违约或没发视频。
4. 在 **Your review note** 写下核对结果，例如 `Checked the source links; the unavailable metadata needs follow-up.`。点 **Keep for follow-up** 保存。你也可以检查后选择 **Approve report**，但只有证据检查通过的报告能批准。
5. 刷新网页，当前浏览器的审核结果仍会显示。换一个浏览器会得到单独的演示会话。

想快速预览，可以点 **Or explore a saved real run**：它是之前真实模型运行的记录，会显示时间，不会冒充现在重新查了一遍。要自己审核，先运行一次新的 Agent。

第二个 **NVIDIA · Shield launch** 有五条公开视频链接，适合观察“品牌自己发布的视频”和“其他发布者的视频”。点 **Can we rank sales?** 可以测试系统是否承认没有销售数据。

## 每个技术在干什么

| 技术 | 在项目里的工作 |
|---|---|
| Python / FastAPI | 提供网页后面的接口，管理报告和审核 |
| SQLite / SQL | 对应活动、视频、发布者与核验记录；重复导入不产生重复行 |
| Vertex AI | 实际大模型：选择查询工具、解释结果、起草报告 |
| LangGraph | 组织“模型选工具 → 执行工具 → 模型继续”的循环 |
| YouTube oEmbed | 实际读取公开标题和发布者，不包含播放量或销售额 |
| Cloud Run | 运行在线网站 |
| Cloud Storage | 保存每次报告和演示审核记录 |

这里的“Agent”可以自己决定需要查哪些工具；SQL 和接口负责真正查资料；审核由你点击按钮完成。没有使用 UiPath，也没有为这几条结构化记录建立向量数据库。

## 面试时可以怎样介绍

> I built an independent prototype around public creator-campaign evidence. It aligns campaign briefs and video records, uses a LangGraph agent with Vertex AI to call read-only tools, and keeps source evidence with the report. I added a human review step and tested missing metadata, repeated imports and unsupported questions. The data is public; I have not integrated a client's contracts, payments or CRM.

可以把它作为你理解业务并能完成一段工程流程的证据，不把它说成在 NeoReach 做过的商业项目。
