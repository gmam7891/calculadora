cat > app.py << 'EOF'
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import json, re, subprocess

app = FastAPI(title="Analisador de Slots")

JOGOS = [
    ("Area Link™ Phoenix Firestorm", "Phoenix Firestorm|Area Link.*Phoenix"),
    ("Area Link™ Bank Boss", "Bank Boss|Area Link.*Bank"),
    ("Area Link™ Dragon", "Area Link.*Dragon|Dragon"),
    ("VoltedUP Wild", "VoltedUP Wild|VoltedUP"),
    ("Surge™", "Surge"),
    ("Wacky Panda Power Combo™", "Wacky Panda"),
    ("Squealin Riches 2™", "Squealin Riches"),
    ("Treasures of Mjolnir™", "Mjolnir"),
    ("FlyX™ Cash Turbo™", "FlyX|Cash Turbo")
]

@app.get("/")
def analisar(vod_id: str = "2712188263"):
    try:
        result = subprocess.run([
            "/app/TwitchDownloaderCLI", "info",
            "--id", vod_id,
            "--format", "json"
        ], capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            return HTMLResponse(f"<h2>❌ Erro CLI</h2><pre>{result.stderr}</pre>")

        data = json.loads(result.stdout)
        chapters = data.get('chapters') or []

        html = f"<h1>🎰 Análise VOD {vod_id}</h1><table border='1' cellpadding='10'><tr><th>Jogo</th><th>Tempo (minutos)</th></tr>"
        total_area_link = 0

        for nome, padrao in JOGOS:
            tempo_seg = 0
            regex = re.compile(padrao, re.IGNORECASE)
            for ch in chapters:
                titulo = str(ch.get('title') or ch.get('game') or "")
                if regex.search(titulo):
                    seg = ch.get('length') or ch.get('lengthSeconds') or 0
                    tempo_seg += int(seg)
            minutos = tempo_seg // 60
            html += f"<tr><td>{nome}</td><td align='center'><b>{minutos}</b></td></tr>"
            if "Area Link" in nome:
                total_area_link += minutos

        html += f"</table><h2>Total Família Area Link™: <b>{total_area_link} minutos</b></h2><p>✅ Pronto!</p>"
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f"<h2>❌ Erro: {str(e)}</h2>")
EOF
