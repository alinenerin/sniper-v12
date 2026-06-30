import logging
import threading
from flask import Flask, render_template_string, jsonify
from datetime import datetime

logger = logging.getLogger(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sniper V12 - Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, sans-serif; 
            background: #0a0e17; 
            color: #e0e0e0; 
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #1a1f2e, #0d1117);
            border-radius: 12px;
            margin-bottom: 20px;
            border: 1px solid #30363d;
        }
        .header h1 { color: #58a6ff; font-size: 24px; }
        .header .mode { 
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            margin-top: 10px;
            font-weight: bold;
        }
        .mode-hybrid { background: #1f6feb33; color: #58a6ff; border: 1px solid #1f6feb; }
        .mode-otc { background: #f0883e33; color: #f0883e; border: 1px solid #f0883e; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 20px;
        }
        .card h3 { color: #58a6ff; margin-bottom: 10px; font-size: 14px; text-transform: uppercase; }
        .stat { font-size: 28px; font-weight: bold; }
        .stat-green { color: #3fb950; }
        .stat-red { color: #f85149; }
        .stat-blue { color: #58a6ff; }
        .stat-yellow { color: #d29922; }
        .channel-status {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 0;
            border-bottom: 1px solid #21262d;
        }
        .channel-dot {
            width: 10px; height: 10px;
            border-radius: 50%;
        }
        .dot-active { background: #3fb950; box-shadow: 0 0 8px #3fb95066; }
        .dot-inactive { background: #f85149; }
        .dot-paused { background: #d29922; }
        .signals-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        .signals-table th, .signals-table td {
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid #21262d;
        }
        .signals-table th { color: #8b949e; font-weight: normal; }
        .win { color: #3fb950; }
        .loss { color: #f85149; }
        .pending { color: #d29922; }
        .protection-bar {
            background: #21262d;
            border-radius: 5px;
            padding: 10px 15px;
            margin: 5px 0;
            display: flex;
            justify-content: space-between;
        }
        .refresh-btn {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #1f6feb;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
        }
        .refresh-btn:hover { background: #388bfd; }
    </style>
</head>
<body>
    <div class="header">
        <h1>⚡ SNIPER V12 QUAD-CHANNEL</h1>
        <div class="mode" id="mode-badge">Carregando...</div>
    </div>

    <div class="grid">
        <div class="card">
            <h3>💰 Saldo</h3>
            <div class="stat stat-blue" id="balance">--</div>
        </div>
        <div class="card">
            <h3>📊 Win Rate</h3>
            <div class="stat stat-green" id="winrate">--</div>
        </div>
        <div class="card">
            <h3>📈 Trades Hoje</h3>
            <div class="stat" id="trades-today">--</div>
        </div>
        <div class="card">
            <h3>💵 P&L Hoje</h3>
            <div class="stat" id="pnl">--</div>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h3>🔌 Canais Ativos</h3>
            <div id="channels-list"></div>
        </div>
        <div class="card">
            <h3>🛡️ Proteções</h3>
            <div id="protections-info"></div>
        </div>
    </div>

    <div class="card" style="margin-top: 15px;">
        <h3>📋 Últimos Sinais</h3>
        <table class="signals-table">
            <thead>
                <tr>
                    <th>Hora</th>
                    <th>Canal</th>
                    <th>Par</th>
                    <th>Direção</th>
                    <th>Score</th>
                    <th>Valor</th>
                    <th>Resultado</th>
                </tr>
            </thead>
            <tbody id="signals-body"></tbody>
        </table>
    </div>

    <button class="refresh-btn" onclick="loadData()">🔄 Atualizar</button>

    <script>
        async function loadData() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                
                // Mode badge
                const badge = document.getElementById('mode-badge');
                badge.textContent = data.mode;
                badge.className = 'mode ' + (data.mode === 'HYBRID' ? 'mode-hybrid' : 'mode-otc');
                
                // Stats
                document.getElementById('balance').textContent = '$' + (data.balance || 0).toFixed(2);
                document.getElementById('winrate').textContent = (data.stats.win_rate || 0).toFixed(1) + '%';
                document.getElementById('trades-today').textContent = data.stats.total_trades || 0;
                
                const pnl = document.getElementById('pnl');
                const pnlValue = data.pnl || 0;
                pnl.textContent = (pnlValue >= 0 ? '+' : '') + '$' + pnlValue.toFixed(2);
                pnl.className = 'stat ' + (pnlValue >= 0 ? 'stat-green' : 'stat-red');
                
                // Channels
                const channelsList = document.getElementById('channels-list');
                channelsList.innerHTML = '';
                for (const ch of data.channels) {
                    const dotClass = ch.running ? 'dot-active' : (data.stats.is_paused ? 'dot-paused' : 'dot-inactive');
                    channelsList.innerHTML += `
                        <div class="channel-status">
                            <div class="channel-dot ${dotClass}"></div>
                            <span>${ch.name}</span>
                            <span style="margin-left:auto;color:#8b949e;">${ch.total_signals} sinais</span>
                        </div>
                    `;
                }
                
                // Protections
                const protInfo = document.getElementById('protections-info');
                protInfo.innerHTML = `
                    <div class="protection-bar"><span>Losses hoje</span><span>${data.stats.daily_losses}/${data.daily_stop_limit}</span></div>
                    <div class="protection-bar"><span>Losses seguidos</span><span>${data.stats.sequential_losses}/${data.seq_stop_limit}</span></div>
                    <div class="protection-bar"><span>Bot pausado</span><span>${data.stats.is_paused ? '⚠️ SIM' : '✅ NÃO'}</span></div>
                    <div class="protection-bar"><span>Ordem ativa</span><span>${data.stats.active_order ? '🔄 SIM' : '—'}</span></div>
                `;
                
                // Signals
                const tbody = document.getElementById('signals-body');
                tbody.innerHTML = '';
                for (const sig of (data.recent_signals || []).reverse()) {
                    const resultClass = sig.win === true ? 'win' : sig.win === false ? 'loss' : 'pending';
                    const resultText = sig.win === true ? '✅ WIN' : sig.win === false ? '❌ LOSS' : '⏳';
                    const time = new Date(sig.time).toLocaleTimeString('pt-BR');
                    tbody.innerHTML += `
                        <tr>
                            <td>${time}</td>
                            <td>${sig.channel}</td>
                            <td>${sig.pair}</td>
                            <td>${sig.direction}</td>
                            <td>${sig.score}</td>
                            <td>$${(sig.amount || 0).toFixed(2)}</td>
                            <td class="${resultClass}">${resultText}</td>
                        </tr>
                    `;
                }
            } catch (e) {
                console.error('Error loading data:', e);
            }
        }
        
        loadData();
        setInterval(loadData, 10000); // Auto-refresh every 10s
    </script>
</body>
</html>
"""


def create_dashboard(port, bot_state):
    """Create and start the Flask dashboard server.
    
    Args:
        port: Port number for the web server
        bot_state: Dictionary with references to bot components
    """
    app = Flask(__name__)
    app.config['JSON_SORT_KEYS'] = False

    @app.route('/')
    def index():
        return render_template_string(DASHBOARD_HTML)

    @app.route('/api/status')
    def api_status():
        try:
            protections = bot_state.get("protections")
            iq_client = bot_state.get("iq_client")
            channels = bot_state.get("channels", [])
            mode = bot_state.get("mode", "UNKNOWN")

            # Get balance
            balance = 0
            if iq_client:
                balance = iq_client.get_balance()

            # Get channel statuses
            channel_statuses = []
            recent_signals = []
            for ch in channels:
                status = ch.get_status()
                channel_statuses.append(status)
                recent_signals.extend(status.get("recent_signals", []))

            # Sort signals by time
            recent_signals.sort(key=lambda x: x.get("time", ""), reverse=True)
            recent_signals = recent_signals[:20]

            # Calculate P&L
            pnl = sum(s.get("profit", 0) for s in recent_signals if "profit" in s)

            # Protection stats
            stats = protections.get_stats() if protections else {}

            return jsonify({
                "mode": mode,
                "balance": balance,
                "stats": stats,
                "channels": channel_statuses,
                "recent_signals": recent_signals,
                "pnl": pnl,
                "daily_stop_limit": protections.daily_stop_limit if protections else 4,
                "seq_stop_limit": protections.sequential_stop_limit if protections else 3,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Dashboard API error: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/health')
    def health():
        return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

    def run_server():
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

    thread = threading.Thread(target=run_server, daemon=True, name="Dashboard")
    thread.start()
    logger.info(f"Dashboard started on port {port}")
    return app
