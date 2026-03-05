from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import json, re, subprocess, os

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
    cli_path = "/app/TwitchDownloaderCLI"
    output_file = "vod_info.json"
    
    try:
        # Debug: mostra arquivos na pasta
        files = os.listdir("/app")
        
        result = subprocess.run([
            cli_path, "info",
            "--id", vod_id,
            "--format", "json",
            "-o", output_file
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            return HTMLResponse(f"""
                <h2>❌ Erro no TwitchDownloaderCLI</h2>
                <p>Arquivos na pasta: {files}</p>
                <pre>STDERR: {result.stderr}</pre>
                <pre>STDOUT: {result.stdout}</pre>
            """)
        
        with open(output_file) as f:
            data = json.load(f)

        chapters = data.get('chapters') or (data.get('video', {}).get('chapters') if isinstance(data, dict) else [])

        html = f"<h1>🎰 Análise VOD {vod_id}</h1><table border='1' cellpadding='10'><tr><th>Jogo</th><th>Tempo (minutos)</th></tr>"
        total_area_link = 0

        for nome, padrao in JOGOS:
            tempo_seg = 0
            regex = re.compile(padrao, re.IGNORECASE)
            for ch in chapters:
                titulo = str(ch.get('title') or ch.get('game') or ch.get('description') or ch.get('name') or '')
                if regex.search(titulo):
                    seg = ch.get('length') or ch.get('lengthSeconds') or (ch.get('end', 0) - ch.get('start', 0))
                    tempo_seg += int(seg or 0)
            minutos = tempo_seg // 60
            html += f"<tr><td>{nome}</td><td align='center'><b>{minutos}</b></td></tr>"
            if "Area Link" in nome:
                total_area_link += minutos

        html += f"</table><h2>Total Família Area Link™: <b>{total_area_link} minutos</b></h2>"
        html += "<p>✅ Análise concluída com sucesso!</p>"
        return HTMLResponse(html)

    except Exception as e:
        return HTMLResponse(f"""
            <h2>❌ Erro geral</h2>
            <pre>{str(e)}</pre>
            <p>Verifique o log completo no Cloud Run.</p>
        """)
