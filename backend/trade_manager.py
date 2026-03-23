import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from database import SessionLocal
from indicators import compute_confidence, confidence_result_to_dict, ConfidenceResult, ASSET_SYMBOLS
from models import Trade, Settings
from pocket_api import PocketOptionClient

logger = logging.getLogger(__name__)


class TradeManager:
    def __init__(self):
        self.pocket_client: Optional[PocketOptionClient] = None
        self._running: bool = False
        self._scan_task: Optional[asyncio.Task] = None
        self._cooldowns: Dict[str, datetime] = {}
        self._active_trades: Set[str] = set()
        self._ws_broadcast = None  # callback for WebSocket broadcasts

    def _get_db(self) -> Session:
        return SessionLocal()

    def _get_setting(self, db: Session, key: str, default: str = "") -> str:
        setting = db.query(Settings).filter(Settings.key == key).first()
        return setting.value if setting else default

    def _get_all_settings(self) -> dict:
        db = self._get_db()
        try:
            settings = db.query(Settings).all()
            return {s.key: s.value for s in settings}
        finally:
            db.close()

    async def ensure_connected(self) -> bool:
        """Ensure PocketOption client is connected."""
        settings = self._get_all_settings()
        is_demo = settings.get("mode", "demo") == "demo"
        ssid_key = "ssid_demo" if is_demo else "ssid_live"
        ssid = settings.get(ssid_key, "")

        if not ssid:
            logger.warning("No SSID configured — skipping PocketOption connection")
            return False

        if self.pocket_client and self.pocket_client.connected:
            return True

        self.pocket_client = PocketOptionClient()

        # Register trade-closed handler
        async def on_trade_closed(data: dict):
            await self._handle_trade_closed(data)

        self.pocket_client.register_handler("trade_closed", on_trade_closed)

        success = await self.pocket_client.connect(ssid, is_demo)
        return success

    async def _handle_trade_closed(self, data: dict):
        """Update DB when a trade closes on PocketOption."""
        order_id = str(data.get("id", ""))
        profit = float(data.get("profit", 0))
        result = "WIN" if profit > 0 else "LOSS"

        db = self._get_db()
        try:
            trade = db.query(Trade).filter(Trade.order_id == order_id).first()
            if trade:
                trade.result = result
                trade.pnl = profit
                db.commit()
                logger.info(f"Trade {order_id} updated: {result}, P&L: {profit}")

                if self._ws_broadcast:
                    await self._ws_broadcast({
                        "type": "trade_closed",
                        "data": trade.to_dict(),
                    })
        except Exception as e:
            logger.error(f"Error updating trade result: {e}")
        finally:
            db.close()

    async def analyze_asset(self, asset: str) -> ConfidenceResult:
        """Run indicators for a single asset and return confidence result."""
        return await compute_confidence(asset)

    def should_trade(self, asset: str, result: ConfidenceResult, settings: dict) -> tuple[bool, str]:
        """
        Check whether we should trade based on:
        - Confidence threshold
        - Cooldown period (5 minutes since last trade)
        - Max concurrent trades
        - Daily loss limit
        Returns (bool, reason_string)
        """
        try:
            threshold = float(settings.get("confidence_threshold", "70"))
        except ValueError:
            threshold = 70.0

        if result.confidence < threshold:
            return False, f"Confidence {result.confidence:.1f} < threshold {threshold}"

        # Check cooldown
        if asset in self._cooldowns:
            cooldown_end = self._cooldowns[asset]
            if datetime.utcnow() < cooldown_end:
                remaining = (cooldown_end - datetime.utcnow()).seconds
                return False, f"Asset in cooldown for {remaining}s"

        # Check concurrent trades
        try:
            max_concurrent = int(settings.get("max_concurrent_trades", "3"))
        except ValueError:
            max_concurrent = 3

        if len(self._active_trades) >= max_concurrent:
            return False, f"Max concurrent trades ({max_concurrent}) reached"

        # Check daily loss limit
        try:
            daily_limit = float(settings.get("daily_loss_limit", "100"))
        except ValueError:
            daily_limit = 100.0

        daily_loss = self._get_daily_loss()
        if daily_loss >= daily_limit:
            return False, f"Daily loss limit ${daily_limit} reached (current: ${daily_loss:.2f})"

        return True, "OK"

    def _get_daily_loss(self) -> float:
        """Calculate total losses today."""
        db = self._get_db()
        try:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            trades = (
                db.query(Trade)
                .filter(Trade.created_at >= today_start, Trade.result == "LOSS")
                .all()
            )
            return sum(abs(t.pnl) for t in trades if t.pnl is not None)
        finally:
            db.close()

    async def execute_trade(self, asset: str, result: ConfidenceResult, settings: dict) -> Optional[Trade]:
        """Execute a trade: place via pocket_api and save to DB."""
        try:
            trade_size = float(settings.get("trade_size", "10"))
        except ValueError:
            trade_size = 10.0

        is_demo = settings.get("mode", "demo") == "demo"
        expiry_map = {
            "5s": 5,
            "10s": 10,
            "15s": 15,
            "30s": 30,
            "1min": 60,
            "2min": 120,
            "3min": 180,
            "5min": 300,
            "10min": 600,
            "15min": 900,
        }
        expiry_seconds = expiry_map.get(result.expiry, 60)

        db = self._get_db()
        try:
            trade = Trade(
                asset=asset,
                direction=result.direction,
                amount=trade_size,
                entry_time=datetime.utcnow(),
                expiry_seconds=expiry_seconds,
                result="PENDING",
                pnl=0.0,
                mode="demo" if is_demo else "live",
                entry_price=result.price,
                confidence=result.confidence,
            )

            # Try to connect and place real trade
            order_id = None
            connected = await self.ensure_connected()
            if connected and self.pocket_client:
                try:
                    action = "call" if result.direction == "CALL" else "put"
                    order_response = await self.pocket_client.place_trade(
                        asset=asset,
                        amount=trade_size,
                        action=action,
                        expiry_seconds=expiry_seconds,
                        is_demo=is_demo,
                    )
                    if order_response:
                        order_id = str(order_response.get("id", ""))
                        logger.info(f"Trade placed on PocketOption: {order_id}")
                except Exception as e:
                    logger.error(f"PocketOption trade placement error: {e} — saving as simulated")

            trade.order_id = order_id
            db.add(trade)
            db.commit()
            db.refresh(trade)

            # Set cooldown
            try:
                interval_mins = int(settings.get("min_trade_interval", "5"))
            except ValueError:
                interval_mins = 5
            self._cooldowns[asset] = datetime.utcnow() + timedelta(minutes=interval_mins)

            # Track active trade
            self._active_trades.add(str(trade.id))

            # Schedule removal from active trades after expiry
            asyncio.create_task(self._remove_active_trade(str(trade.id), expiry_seconds + 5))

            logger.info(
                f"Trade executed: {asset} {result.direction} ${trade_size} "
                f"({result.expiry}) confidence={result.confidence:.1f}"
            )

            if self._ws_broadcast:
                await self._ws_broadcast({
                    "type": "trade_opened",
                    "data": trade.to_dict(),
                })

            return trade

        except Exception as e:
            logger.error(f"Error executing trade for {asset}: {e}")
            db.rollback()
            return None
        finally:
            db.close()

    async def _remove_active_trade(self, trade_id: str, delay: int):
        """Remove trade from active set after expiry."""
        await asyncio.sleep(delay)
        self._active_trades.discard(trade_id)

    def check_daily_loss(self) -> tuple[bool, float, float]:
        """Returns (limit_hit, current_loss, limit)."""
        settings = self._get_all_settings()
        try:
            daily_limit = float(settings.get("daily_loss_limit", "100"))
        except ValueError:
            daily_limit = 100.0
        current_loss = self._get_daily_loss()
        return current_loss >= daily_limit, current_loss, daily_limit

    def get_stats(self) -> dict:
        """Return win rate, total P&L, trade counts."""
        db = self._get_db()
        try:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            all_trades = db.query(Trade).filter(Trade.result != "PENDING").all()
            today_trades = db.query(Trade).filter(Trade.created_at >= today_start).all()
            today_closed = [t for t in today_trades if t.result != "PENDING"]

            total = len(all_trades)
            wins = sum(1 for t in all_trades if t.result == "WIN")
            losses = sum(1 for t in all_trades if t.result == "LOSS")
            win_rate = (wins / total * 100) if total > 0 else 0.0
            total_pnl = sum(t.pnl for t in all_trades if t.pnl is not None)

            today_total = len(today_trades)
            today_wins = sum(1 for t in today_closed if t.result == "WIN")
            today_pnl = sum(t.pnl for t in today_closed if t.pnl is not None)

            return {
                "total_trades": total,
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 2),
                "total_pnl": round(total_pnl, 2),
                "today_trades": today_total,
                "today_wins": today_wins,
                "daily_pnl": round(today_pnl, 2),
                "active_trades": len(self._active_trades),
            }
        finally:
            db.close()

    async def start_auto_trading(self, broadcast_callback=None):
        """Start the auto-trading scan loop."""
        if self._running:
            logger.warning("Auto-trading already running")
            return

        self._ws_broadcast = broadcast_callback
        self._running = True
        self._scan_task = asyncio.create_task(self._auto_trade_loop())

        db = self._get_db()
        try:
            setting = db.query(Settings).filter(Settings.key == "bot_running").first()
            if setting:
                setting.value = "true"
            else:
                db.add(Settings(key="bot_running", value="true"))
            db.commit()
        finally:
            db.close()

        logger.info("Auto-trading started")

    async def stop_auto_trading(self):
        """Stop the auto-trading scan loop."""
        self._running = False
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass

        db = self._get_db()
        try:
            setting = db.query(Settings).filter(Settings.key == "bot_running").first()
            if setting:
                setting.value = "false"
            else:
                db.add(Settings(key="bot_running", value="false"))
            db.commit()
        finally:
            db.close()

        logger.info("Auto-trading stopped")

    async def _auto_trade_loop(self):
        """Main auto-trading loop that scans assets and places trades."""
        while self._running:
            try:
                settings = self._get_all_settings()

                # Check if auto-trade is enabled
                if settings.get("auto_trade", "false") != "true":
                    await asyncio.sleep(5)
                    continue

                # Check daily loss
                limit_hit, current_loss, limit = self.check_daily_loss()
                if limit_hit:
                    logger.warning(f"Daily loss limit hit: ${current_loss:.2f} >= ${limit:.2f}")
                    if self._ws_broadcast:
                        await self._ws_broadcast({
                            "type": "daily_limit_hit",
                            "data": {"current_loss": current_loss, "limit": limit},
                        })
                    await asyncio.sleep(60)
                    continue

                # Get enabled assets
                enabled_assets_str = settings.get("enabled_assets", "")
                enabled_assets = [a.strip() for a in enabled_assets_str.split(",") if a.strip()]

                if not enabled_assets:
                    await asyncio.sleep(10)
                    continue

                # Scan each asset
                for asset in enabled_assets:
                    if not self._running:
                        break

                    if asset not in ASSET_SYMBOLS:
                        continue

                    try:
                        result = await self.analyze_asset(asset)

                        if self._ws_broadcast:
                            await self._ws_broadcast({
                                "type": "confidence_update",
                                "data": confidence_result_to_dict(result),
                            })
                            if result.price > 0:
                                await self._ws_broadcast({
                                    "type": "price_update",
                                    "data": {
                                        "asset": asset,
                                        "price": result.price,
                                        "price_change_pct": result.price_change_pct,
                                    },
                                })

                        should, reason = self.should_trade(asset, result, settings)
                        if should:
                            trade = await self.execute_trade(asset, result, settings)
                            if trade:
                                logger.info(f"Auto-trade placed: {asset}")

                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        logger.error(f"Error scanning {asset}: {e}")

                    # Brief pause between assets to avoid rate limiting
                    await asyncio.sleep(1)

                # Wait before next scan cycle
                try:
                    refresh_interval = int(settings.get("refresh_interval", "30"))
                except ValueError:
                    refresh_interval = 30

                await asyncio.sleep(refresh_interval)

            except asyncio.CancelledError:
                logger.info("Auto-trading loop cancelled")
                break
            except Exception as e:
                logger.error(f"Auto-trading loop error: {e}")
                await asyncio.sleep(10)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def active_trade_count(self) -> int:
        return len(self._active_trades)
