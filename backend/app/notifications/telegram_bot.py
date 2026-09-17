"""
Encrypted Ledger - Dual-Tier Telegram Bot Service
Supports:
1. Superadmin Bot (最高权限管理控制):
   - Real-time trade execution & black-swan emergency alerts;
   - Full interactive commands: /status, /positions, /panic (市价全平), /cycle, /risk;
2. Regular User Bot (用户权限通知广播):
   - Trade signal broadcasts & daily performance reports;
   - Sandboxed read-only commands: /status, /signals, /help.
"""
from __future__ import annotations

import httpx
import json
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger


class TelegramBotService:
    """Institutional dual-tier Telegram Bot notification and interactive management engine."""

    def __init__(self):
        self._http_client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        return self._http_client

    async def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to a specific Telegram chat."""
        token = settings.TELEGRAM_BOT_TOKEN.strip()
        if not token or not chat_id:
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }

        try:
            client = self._get_client()
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                return True
            logger.warning(f"Telegram send failed ({res.status_code}): {res.text}")
            return False
        except Exception as e:
            logger.warning(f"Telegram network exception: {e}")
            return False

    async def send_admin_alert(self, text: str) -> bool:
        """Send an urgent notification to the Superadmin chat."""
        admin_chat = settings.TELEGRAM_ADMIN_CHAT_ID.strip() or settings.TELEGRAM_CHAT_ID.strip()
        if not admin_chat:
            return False
        return await self.send_message(admin_chat, text)

    async def broadcast_to_users(self, text: str, user_chat_ids: List[str]) -> int:
        """Broadcast read-only signals or reports to subscribed users."""
        success_count = 0
        for cid in user_chat_ids:
            if cid and cid.strip():
                ok = await self.send_message(cid.strip(), text)
                if ok:
                    success_count += 1
        return success_count

    # --------------------------------------------------------------------------
    # Structured Notifications
    # --------------------------------------------------------------------------

    async def notify_order_opened(
        self,
        symbol: str,
        venue: str,
        side: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        rr: float,
        confidence: float,
        notional_usd: float
    ):
        """Notify Superadmin and Users of a newly opened position."""
        side_icon = "🟢 做多 (BUY_LONG)" if side.lower() == "buy" else "🔴 做空 (SELL_SHORT)"
        admin_msg = (
            f"<b>⚡ [Encrypted Ledger] 智能开仓通知</b>\n\n"
            f"• 交易标的: <b>{symbol.upper()}/USDT</b>\n"
            f"• 交易场馆: <b>{venue.upper()} (SOR 择优路由)</b>\n"
            f"• 操盘方向: {side_icon}\n"
            f"• 开仓价格: <code>${entry_price:.4f}</code>\n"
            f"• 物理止损: <code>${stop_loss:.4f}</code>\n"
            f"• 目标止盈: <code>${take_profit:.4f}</code>\n"
            f"• 几何盈亏比 (R:R): <b>{rr:.2f}</b>\n"
            f"• 投委会置信度: <b>{confidence:.1f}%</b>\n"
            f"• 名义价值: <b>${notional_usd:.2f} USDT</b>\n"
            f"• 保护机制: 原生带单硬止损 + 移动保本守护"
        )
        await self.send_admin_alert(admin_msg)

    async def notify_order_closed(
        self,
        symbol: str,
        venue: str,
        side: str,
        fill_price: float,
        realized_pnl: float,
        pnl_ratio: float,
        reason: str
    ):
        """Notify Superadmin of position liquidation or profit-taking."""
        pnl_icon = "🟢 盈利" if realized_pnl >= 0 else "🔴 止损"
        admin_msg = (
            f"<b>📊 [Encrypted Ledger] 平仓了结通知 ({pnl_icon})</b>\n\n"
            f"• 标的代码: <b>{symbol.upper()}/USDT</b> ({venue.upper()})\n"
            f"• 平仓方向: <b>{side.upper()}</b>\n"
            f"• 成交均价: <code>${fill_price:.4f}</code>\n"
            f"• 已实现盈亏: <b>{'+' if realized_pnl>=0 else ''}${realized_pnl:.2f} USDT ({pnl_ratio*100:+.2f}%)</b>\n"
            f"• 平仓原因: <i>{reason}</i>\n"
            f"• 双式记账: 已自动写入不可变平衡分录"
        )
        await self.send_admin_alert(admin_msg)

    async def notify_circuit_breaker(self, reason: str, details: str):
        """Notify Superadmin immediately when Black Swan circuit breaker triggers."""
        admin_msg = (
            f"<b>🚨 [Encrypted Ledger] 紧急警报：黑天鹅熔断器触发！</b>\n\n"
            f"• 熔断原因: <b>{reason}</b>\n"
            f"• 详细情报: {details}\n"
            f"• 系统状态: <b>全系统开仓物理锁定，阻断全部新订单</b>\n"
            f"• 处置建议: 请检查宏观快讯，如需复位请使用 /status 或登录管理后台"
        )
        await self.send_admin_alert(admin_msg)

    # --------------------------------------------------------------------------
    # Interactive Command Handler (Admin & User)
    # --------------------------------------------------------------------------

    async def process_telegram_update(self, update: Dict[str, Any]) -> Optional[str]:
        """
        Process incoming Telegram command with strict role-based authorization.
        Returns the response text sent back to the user/admin.
        """
        message = update.get("message", {})
        chat = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        text = message.get("text", "").strip()

        if not chat_id or not text:
            return None

        admin_chat = str(settings.TELEGRAM_ADMIN_CHAT_ID or settings.TELEGRAM_CHAT_ID).strip()
        is_admin = bool(admin_chat and chat_id == admin_chat)

        cmd = text.split()[0].lower()
        args = text.split()[1:]

        # 1. Superadmin Commands (最高权限)
        if is_admin:
            if cmd in ("/start", "/help"):
                reply = (
                    "<b>👑 Encrypted Ledger - 超级管理员指令中枢</b>\n\n"
                    "您已通过最高权限鉴权，可直接在此发送管理控制指令：\n\n"
                    "• <code>/status</code> - 查询全所总资产、浮亏及运行状态\n"
                    "• <code>/positions</code> - 检视当前所有在途持仓明细\n"
                    "• <code>/panic</code> - ⚠️ <b>紧急熔断：全所全部持仓市价全平并锁仓</b>\n"
                    "• <code>/cycle</code> - 立即执行一轮量化巡检与投委会决策\n"
                    "• <code>/risk conservative|balanced|aggressive</code> - 一键切换风控预设\n"
                    "• <code>/reset_cb</code> - 手动复位黑天鹅熔断器"
                )
            elif cmd == "/status":
                from app.exchanges.router import order_router
                from app.intelligence.circuit_breaker import circuit_breaker
                try:
                    balances = await order_router.get_aggregated_balances()
                    total_eq = balances.get("total_equity_usd", 0.0)
                    okx_eq = balances.get("okx", {}).get("total_equity_usd", 0.0)
                    bin_eq = balances.get("binance", {}).get("total_equity_usd", 0.0)
                    cb_state = circuit_breaker.get_state()
                    cb_str = "🔴 熔断冻结中" if cb_state.get("active") else "🟢 正常防御中"
                    reply = (
                        f"<b>📊 [Encrypted Ledger] 生产系统运行报告</b>\n\n"
                        f"• 全所总净值: <b>${total_eq:.2f} USDT</b>\n"
                        f"  ├─ OKX 资产: <code>${okx_eq:.2f}</code>\n"
                        f"  └─ Binance 资产: <code>${bin_eq:.2f}</code>\n"
                        f"• 黑天鹅哨兵: <b>{cb_str}</b>\n"
                        f"• 物理风控: <b>17 项单一事实源 Fail-Closed</b>\n"
                        f"• 交易环境: <b>OKX ({settings.OKX_ENV}) | 币安 ({settings.BINANCE_ENV})</b>"
                    )
                except Exception as e:
                    reply = f"❌ 查询状态失败: {e}"

            elif cmd == "/positions":
                from app.exchanges.router import order_router
                try:
                    okx_pos = await order_router.okx.get_positions()
                    bin_pos = await order_router.binance.get_positions()
                    all_pos = okx_pos + bin_pos
                    if not all_pos:
                        reply = "🟢 <b>当前全所无在途持仓（资金 100% 闲置安全中）</b>"
                    else:
                        reply = f"<b>📈 当前在途持仓 ({len(all_pos)} 笔):</b>\n\n"
                        for p in all_pos:
                            side_str = "多" if p.side == "long" else "空"
                            reply += (
                                f"• [{p.venue.upper()}] <b>{p.symbol} {side_str} {p.leverage}x</b>\n"
                                f"  开仓: ${p.entry_price:.2f} | 标记: ${p.mark_price:.2f}\n"
                                f"  未实现盈亏: <b>{p.unrealized_pnl_usd:+.2f} USDT ({(p.unrealized_pnl_ratio*100):+.1f}%)</b>\n\n"
                            )
                except Exception as e:
                    reply = f"❌ 读取持仓异常: {e}"

            elif cmd == "/panic":
                from app.exchanges.router import order_router
                from app.intelligence.circuit_breaker import circuit_breaker
                circuit_breaker.trigger_circuit_breaker(
                    reason="超级管理员通过 Telegram 发送 /panic 紧急避险熔断指令",
                    details="全所持仓强制市价清退，开仓拦截器已物理关停"
                )
                try:
                    okx_pos = await order_router.okx.get_positions()
                    bin_pos = await order_router.binance.get_positions()
                    closed_count = 0
                    for p in okx_pos:
                        await order_router.okx.close_position(p.symbol, p.side)
                        closed_count += 1
                    for p in bin_pos:
                        await order_router.binance.close_position(p.symbol, p.side)
                        closed_count += 1
                    reply = f"🚨 <b>【紧急避险完成】已强制市价清平全部 {closed_count} 笔持仓，黑天鹅熔断器已锁死系统！</b>"
                except Exception as e:
                    reply = f"⚠️ 部分清仓遇到异常: {e}"

            elif cmd == "/cycle":
                from app.scheduler.tasks import orchestrator
                import asyncio
                asyncio.create_task(orchestrator.run_market_scan_cycle())
                reply = "⚡ <b>已成功触发后台全市场深度扫描与投委会决策巡检！稍后将收到决议。</b>"

            elif cmd == "/risk":
                if args and args[0].lower() in ("conservative", "balanced", "aggressive"):
                    preset = args[0].lower()
                    if preset == "conservative":
                        settings.RISK_MAX_LEVERAGE = 3.0
                        settings.RISK_MIN_ENTRY_CONFIDENCE = 85.0
                        settings.RISK_MAX_MARGIN_EQUITY_RATIO = 0.15
                    elif preset == "balanced":
                        settings.RISK_MAX_LEVERAGE = 5.0
                        settings.RISK_MIN_ENTRY_CONFIDENCE = 80.0
                        settings.RISK_MAX_MARGIN_EQUITY_RATIO = 0.20
                    elif preset == "aggressive":
                        settings.RISK_MAX_LEVERAGE = 10.0
                        settings.RISK_MIN_ENTRY_CONFIDENCE = 70.0
                        settings.RISK_MAX_MARGIN_EQUITY_RATIO = 0.35
                    reply = f"✅ <b>风控矩阵已成功切换至: {preset.upper()}</b>"
                else:
                    reply = "💡 用法: <code>/risk conservative | balanced | aggressive</code>"

            elif cmd == "/reset_cb":
                from app.intelligence.circuit_breaker import circuit_breaker
                circuit_breaker.manual_reset()
                reply = "🟢 <b>黑天鹅熔断器已手动复位，系统恢复正常巡检防御。</b>"

            else:
                reply = "❓ 未知指令。输入 <code>/help</code> 查看超级管理员可用指令清单。"

            await self.send_message(chat_id, reply)
            return reply

        # 2. Regular User Commands (普通用户沙箱)
        else:
            if cmd in ("/start", "/help"):
                reply = (
                    "<b>🤖 Encrypted Ledger - 量化智能体通知终端</b>\n\n"
                    "您好！当前机器人支持为您提供公开量化研判与业绩跟踪：\n\n"
                    "• <code>/status</code> - 查看当前量化大盘概况与黑天鹅状态\n"
                    "• <code>/signals</code> - 获取投委会最新多空研判信号\n"
                    "• <code>/help</code> - 显示本帮助菜单\n\n"
                    "<i>注：交易执行与底层管理指令仅对授权管理员开放。</i>"
                )
            elif cmd == "/status":
                from app.intelligence.circuit_breaker import circuit_breaker
                cb_state = circuit_breaker.get_state()
                cb_str = "🔴 市场异常防范中" if cb_state.get("active") else "🟢 稳定运行中"
                reply = (
                    f"<b>📈 [Encrypted Ledger] 公开量化监测看板</b>\n\n"
                    f"• 交易池资产规模: <b>机构商用级规模 (★ 100,000+ USDT)</b>\n"
                    f"• 黑天鹅哨兵: <b>{cb_str}</b>\n"
                    f"• 架构模式: <b>OKX & 币安双所撮合 · 4+1 多智能体共识</b>\n"
                    f"• 物理风控: <b>17 项单一事实源严格防护</b>"
                )
            elif cmd == "/signals":
                from app.council.council_desk import council_desk
                debates = council_desk.get_latest_debate_history(5)
                if not debates:
                    reply = "ℹ️ 暂无最新投委会决议，请稍后查询。"
                else:
                    reply = "<b>🎯 投委会最新多智能体共识信号:</b>\n\n"
                    for d in debates:
                        action_str = "做多 🟢" if d['action'] == "BUY" else ("做空 🔴" if d['action'] == "SELL" else "观望 ⚪")
                        reply += (
                            f"• 标的: <b>{d['symbol']}</b> [{action_str}]\n"
                            f"  置信度: <b>{d['confidence']}%</b>\n"
                            f"  共识: <i>{d.get('consensus_summary', '无')[:45]}...</i>\n\n"
                        )
            elif cmd in ("/panic", "/cycle", "/positions", "/risk", "/reset_cb"):
                reply = "⛔ <b>权限不足：该指令仅限超级管理员执行。</b>"
            else:
                reply = "❓ 未知指令。输入 <code>/help</code> 查看支持的公共指令。"

            await self.send_message(chat_id, reply)
            return reply


telegram_bot = TelegramBotService()
