# Encrypted Ledger (加密账本)

<div align="center">

```
  _____                               _           _   _               _                    
 | ____|_ __   ___ _ __ _   _ _ __   | |_ ___  __| | | |    ___   __| | __ _  ___ _ __    
 |  _| | '_ \ / __| '__| | | | '_ \  | __/ _ \/ _` | | |   / _ \ / _` |/ _` |/ _ \ '__|   
 | |___| | | | (__| |  | |_| | |_) | | ||  __/ (_| | | |__| (_) | (_| | (_| |  __/ |      
 |_____|_| |_|\___|_|   \__, | .__/   \__\___|\__,_| |_____\___/ \__,_|\__, |\___|_|      
                        |___/|_|                                       |___/              
```

**新一代机构级双核驱动自动化量化加密货币交易与透明双式记账系统**  
🔥 **OKX (欧易 V5) 与 Binance (币安 Futures) 双所平权与智能路由 · 7x24 全球宏观情报与黑天鹅熔断哨兵**  
*Fail-Closed 物理硬拦截 · 因果微积分动力学矩阵 · 对冲基金多模型投委会 · 0.5s 策略快照原子回滚*

</div>

---

## 📖 项目全景与核心架构 (Architectural Overview)

**Encrypted Ledger** 汲取了前代交易系统的实战经验，彻底摆脱了复杂的历史兼容包袱，基于现代 Python 3.11+ 纯异步事件驱动与高性能 SQLite WAL 双式记账引擎构建。系统具备以下五大核心支柱：

### 1. 交易所双核精选 (OKX + Binance Dual-Venue SOR)
- **OKX (欧易 V5)**：主攻确定性波段趋势，利用 OKX 原生 `attachAlgoOrds` 机制实现“开仓即锁硬止损止盈”，杜绝任何物理网络断线导致的单边裸奔；提取独家 Rubik 大数据衍生品多空持仓比。
- **Binance (币安 Futures)**：承担全球最深流动性撮合与极限低滑点执行；智能订单路由（Smart Order Routing, SOR）实时比对两所买卖盘深度与点差，自动选择最优通道。

### 2. 全球 7x24 宏观要闻与黑天鹅分级熔断 (Macro Intelligence & Sentinel)
- 实时嗅探**金十数据 (Jin10)** 宏观要闻流、**新浪财经 7x24** 全球快讯与交易所官方公告；
- 正则级黑天鹅熔断哨兵：监测稳定币（USDT/USDC）恶性脱锚、主流大所挤兑倒闭、公链 51% 停机攻击及地缘极端危机，毫秒级触发三级防御熔断。

### 3. 因果微积分与五大因子矩阵 (Calculus & Factor Engine)
- 严守零未来函数（Zero Lookahead Bias），计算已闭合 K 线；
- 微积分物理量：一阶导数（价格速度 $\frac{dP}{dt}$）、二阶导数（动量加速度 $\frac{d^2P}{dt^2}$）、定积分（$\int |P - EMA|\,dt$ 累积偏离势能）；
- 5大因子矩阵：趋势动量（ADX/RSI）、波动通道（ATR）、成交量突发倍数、盘口 Top-20 订单簿失衡度、聪明钱衍生品溢价。

### 4. Fail-Closed 物理硬拦截管线 (17 项单一事实源风控)
“**认知决策归大模型，资金底线归底座代码**”。任何交易提案必须逐一通过不可跳过的纯 Python 门禁：
1. **4H 宏观大周期顺势铁律**：4H 均线空头严禁开多，多头严禁开空；
2. **AI 置信度门禁**：置信度低于 80% 一律强制观望（HOLD）；
3. **1H ADX 震荡市过滤器**：ADX < 18 判定为无序垃圾行情，禁止建仓；
4. **几何 2.0R 盈亏比门禁**：入场价、止损价与止盈价空间比必须严格 $\ge 2.0$；
5. **同向持仓上限与敞口防线**：单边同向最多 3 仓，单笔保证金硬顶 20%，单日 5% 亏损熔断。

### 5. 加密双式记账本 (The Encrypted Ledger)
- 每一笔保证金占用、浮动盈亏、已实现盈亏、手续费、滑点，均作为平衡分录存入高吞吐 SQLite WAL 数据库；
- 每一笔交易强制锁定开仓时刻的 **策略快照 SHA-256 哈希值**，真正实现“哪笔交易用了哪套策略，毫秒级精准溯源”；
- 支持 0.5s 秒级一键原子回滚到任意历史归档版本。

---

## 📂 项目工程目录规范

```
Encrypted ledger/
├── backend/                        # 现代化异步后端核心服务
│   ├── app/
│   │   ├── api/                    # REST API (auth, market, trading, ledger, risk, system)
│   │   ├── core/                   # 核心配置、Fernet 强加密、安全登录与日志
│   │   ├── database/               # SQLite WAL 双式记账数据库模型
│   │   ├── exchanges/              # OKX V5 & Binance Futures 统一适配层与 SOR 路由
│   │   ├── intelligence/           # 金十/新浪 7x24 宏观快讯嗅探与黑天鹅熔断器
│   │   ├── quant/                  # 微积分因果引擎、五大因子库、宇宙标的池
│   │   ├── council/                # 多模型投委会协调、提示词工作室、自进化记忆
│   │   ├── risk/                   # 17项执行层硬风控、Fail-Closed 物理拦截管线
│   │   ├── ledger/                 # 加密双式记账本、资金台账穿透、策略快照引擎
│   │   ├── scheduler/              # 高可用统一调度中枢 (15M 交易巡检, 10M 新闻, 6H 自省)
│   │   └── main.py                 # FastAPI 入口应用
│   ├── requirements.txt            # 精准锁版本依赖
│   └── run.py                      # 后端启动文件
├── frontend/                       # 现代化操盘终端
│   └── dist/
│       └── index.html              # Bento 资产大屏、微积分因子矩阵、双式账本审计
├── deploy/                         # Linux VPS 一键部署与守护脚本
│   ├── encrypted-ledger.service    # Systemd 守护进程配置
│   ├── start.sh                    # Linux 一键启动脚本
│   └── setup_vps.sh                # VPS 内核优化与环境搭建
├── data/                           # 数据持久化目录 (SQLite 数据库、策略快照库)
│   ├── universe.json               # 交易池配置
│   └── AI_TRADING_MEMORY.md        # 自进化白盒心法记忆
├── env.example                     # 完善的环境变量配置模版 (带详尽中文注释)
├── start.bat                       # Windows 一键启动批处理
└── start.ps1                       # Windows PowerShell 启动脚本
```

---

## 🚀 极速部署指南

### 方式 A：Docker Compose 一键全自动智能部署（⭐ 强烈推荐，适用于 Ubuntu / Debian VPS）

系统内置了全自动化部署自检脚本 `deploy.sh`，能够自动检测系统硬件资源（内存/磁盘）、检测并自动安装缺失的 Docker 与 Docker Compose 插件、配置 2GB Swap 防 OOM 虚拟内存、自动生成高强度安全令牌并一键拉起容器栈：

1. **进入项目根目录并赋予执行权限**：
   ```bash
   chmod +x deploy.sh deploy/*.sh
   ```

2. **执行一键部署脚本**：
   ```bash
   sudo ./deploy.sh
   ```
   *脚本会自动完成：系统环境检测 ➔ Docker/Compose 探测与安装 ➔ 环境变量与持久化目录校验 ➔ 镜像构建 ➔ 容器健康探测与启动报告。*

3. **访问与运维管理**：
   - 🖥️ **量化操盘大屏终端**：`http://<你的VPS公网IP>:8080/`
   - 📑 **交互式 API 文档**：`http://<你的VPS公网IP>:8080/docs`
   - 🔑 **默认初始密码**：`admin` / `Admin123!@#`
   - **日常运维指令**：
     ```bash
     docker compose logs -f          # 查看实时交易与因果微积分日志
     docker compose restart          # 重启服务
     docker compose down             # 停止服务
     docker compose up -d --build    # 更新代码后重新构建并拉起
     ```

---

### 方式 B：Linux VPS Systemd 原生守护部署
1. 将项目放置在 `/opt/encrypted-ledger`；
2. 运行 VPS 系统优化与服务部署脚本：
   ```bash
   chmod +x deploy/*.sh
   sudo ./deploy/setup_vps.sh
   ```
3. 启动后台自愈服务：
   ```bash
   sudo systemctl enable --now encrypted-ledger
   sudo systemctl status encrypted-ledger
   ```

---

### 方式 C：Windows 本地或远程桌面一键启动
1. 复制环境配置模板：`copy env.example .env`
2. 双击运行根目录下的 **`start.bat`** 或在 PowerShell 中执行 `.\start.ps1`
3. 浏览器访问 `http://127.0.0.1:8080/`

---

## 🎛️ 默认交易标的池 (Trading Universe)

系统初始基准内置 10 大主流及高弹性动量标的，**支持在前端管理大屏随时动态添加自定义关注币种**：
- **Tier-1 蓝筹主流**（5x 杠杆，1.8x ATR 宽止损）：`BTC`, `ETH`
- **Tier-2 高弹性动量**（3x 杠杆，2.2x ATR 宽止损）：`SOL`, `XRP`, `DOGE`, `ARB`, `SUI`, `LINK`, `ADA`, `UNI`

---

## 🔒 安全与凭据加密设计

1. **Fernet 工业级对称强加密**：所有交易所 API Key / Secret Key / Passphrase 经由本地 256 位密钥安全加密后持久化，代码与日志中绝不明文打印；
2. **IP 滑动窗口反爆破防线**：管理控制面配备登录频率限制，拦截撞库与暴力破解；
3. **Fail-Closed 默认安全**：未完整配置密钥或网络异常时，系统一律拒绝发单，保持资金 100% 闲置安全。
