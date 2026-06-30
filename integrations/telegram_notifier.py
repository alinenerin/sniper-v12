"""
Telegram Notifier - Envia notificações de sinais e trades
"""
import os
import requests
import threading
from datetime import datetime

class TelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id)
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
    def send_message(self, text, parse_mode="HTML"):
        """Envia mensagem de forma assíncrona para não bloquear o bot"""
        if not self.enabled:
            return
        threading.Thread(target=self._send, args=(text, parse_mode), daemon=True).start()
    
    def _send(self, text, parse_mode):
        try:
            requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode
                },
                timeout=10
            )
        except Exception as e:
            print(f"[TELEGRAM] Erro ao enviar: {e}")
    
    def notify_signal(self, channel, pair, direction, score, min_score):
        """Notifica quando um sinal é detectado"""
        emoji = "🟢" if direction == "CALL" else "🔴"
        msg = (
            f"{emoji} <b>SINAL DETECTADO</b>\n\n"
            f"📊 Canal: {channel}\n"
            f"💱 Par: {pair}\n"
            f"📈 Direção: <b>{direction}</b>\n"
            f"🎯 Score: {score}/{min_score}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send_message(msg)
    
    def notify_trade_opened(self, channel, pair, direction, amount):
        """Notifica quando uma ordem é executada"""
        emoji = "🟢" if direction == "CALL" else "🔴"
        msg = (
            f"{emoji} <b>TRADE EXECUTADO</b>\n\n"
            f"📊 Canal: {channel}\n"
            f"💱 Par: {pair}\n"
            f"📈 Direção: <b>{direction}</b>\n"
            f"💰 Valor: R$ {amount:.2f}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send_message(msg)
    
    def notify_trade_result(self, pair, direction, result, profit, balance):
        """Notifica o resultado do trade"""
        if result == "WIN":
            emoji = "✅"
            result_text = f"+R$ {profit:.2f}"
        else:
            emoji = "❌"
            result_text = f"-R$ {abs(profit):.2f}"
        
        msg = (
            f"{emoji} <b>RESULTADO: {result}</b>\n\n"
            f"💱 Par: {pair}\n"
            f"📈 Direção: {direction}\n"
            f"💰 {result_text}\n"
            f"🏦 Saldo: R$ {balance:.2f}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send_message(msg)
    
    def notify_protection(self, protection_type, details):
        """Notifica quando uma proteção é ativada"""
        msg = (
            f"🛡️ <b>PROTEÇÃO ATIVADA</b>\n\n"
            f"⚠️ Tipo: {protection_type}\n"
            f"📝 {details}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send_message(msg)
    
    def notify_veto(self, channel, pair, reason):
        """Notifica quando um sinal é vetado"""
        msg = (
            f"🚫 <b>SINAL VETADO</b>\n\n"
            f"📊 Canal: {channel}\n"
            f"💱 Par: {pair}\n"
            f"❌ Motivo: {reason}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send_message(msg)
    
    def notify_daily_summary(self, total_trades, wins, losses, profit, balance):
        """Resumo diário"""
        winrate = (wins / total_trades * 100) if total_trades > 0 else 0
        emoji = "📈" if profit >= 0 else "📉"
        
        msg = (
            f"📋 <b>RESUMO DO DIA</b>\n\n"
            f"📊 Total trades: {total_trades}\n"
            f"✅ Wins: {wins}\n"
            f"❌ Losses: {losses}\n"
            f"🎯 Win Rate: {winrate:.1f}%\n"
            f"{emoji} Lucro: R$ {profit:.2f}\n"
            f"🏦 Saldo: R$ {balance:.2f}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send_message(msg)
    
    def notify_startup(self, mode, pairs):
        """Notifica quando o bot inicia"""
        pairs_text = ", ".join(pairs[:5])
        if len(pairs) > 5:
            pairs_text += f" +{len(pairs)-5} mais"
        
        msg = (
            f"🚀 <b>SNIPER V12 INICIADO</b>\n\n"
            f"⚙️ Modo: {mode}\n"
            f"💱 Pares: {pairs_text}\n"
            f"📊 Canais: 4 (OTC M1, OTC M5, Real M1, Real M5)\n"
            f"🛡️ Proteções: Ativas\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send_message(msg)
    
    def notify_shutdown(self, reason):
        """Notifica quando o bot para"""
        msg = (
            f"⚠️ <b>SNIPER V12 PARADO</b>\n\n"
            f"📝 Motivo: {reason}\n"
            f"🕐 {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send_message(msg)


# Instância global
notifier = TelegramNotifier()
