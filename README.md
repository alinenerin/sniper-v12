# ⚡ SNIPER V12 QUAD-CHANNEL

Bot de trading automatizado para IQ Option com 4 canais paralelos.

## Arquitetura

| Canal | Mercado | Timeframe | Ciclo | Score Mín |
|-------|---------|-----------|-------|-----------|
| OTC M1 | OTC | 1 min | 57s | 150 |
| OTC M5 | OTC | 5 min | 290s | 160 |
| REAL M1 | Real | 1 min | 57s | 70 |
| REAL M5 | Real | 5 min | 290s | 75 |

## Indicadores

- MACD (configurável por canal)
- RSI (14)
- Bollinger Bands (20, 2σ)
- EMA Cascade (7, 9, 21, 50, 200)
- ATR (14)
- ADX (14)
- Markov Chain (probabilidade transição)
- Shadow Rejection (análise de pavios)

## Proteções

- Stop diário: 4 losses = bot desligado
- Stop sequencial: 3 losses seguidos = pausa 30min
- Cooldown: 120s entre trades no mesmo par
- Trava global: apenas 1 ordem aberta por vez
- Trap Zones: veto nos segundos :02, :17, :32, :47
- ForexFactory: veto 30min antes / 10min depois de evento HIGH
- Finnhub: bloqueio em notícias surpresa

## Integrações

- **IQ Option** → velas tempo real + saldo + execução
- **ForexFactory** → calendário econômico
- **Twelve Data** → DXY (força do dólar)
- **Finnhub** → notícias surpresa

## Deploy no Railway

1. Faça fork ou push deste repo no GitHub
2. Conecte o repo ao Railway
3. Configure as variáveis de ambiente (ver `.env.example`)
4. Deploy automático!

## Variáveis de Ambiente

```
IQ_EMAIL=seu_email
IQ_PASSWORD=sua_senha
IQ_MODE=PRACTICE
TWELVE_DATA_KEY=sua_chave
POLYGON_KEY=sua_chave
FINNHUB_KEY=sua_chave
ENTRY_PERCENT=0.02
PORT=8080
```

## Executar Localmente

```bash
pip install -r requirements.txt
python main.py
```

Dashboard disponível em `http://localhost:8080`
