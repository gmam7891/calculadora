import time
import argparse
import logging
from datetime import datetime
from src.twitch_client import TwitchClient
from src import storage
from dotenv import load_dotenv
import os

# ===================== CONFIGURAÇÃO DE LOG =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

load_dotenv()

VIRTUAL_CASINO_GAME_ID = "45517"   # ID oficial da categoria "Virtual Casino" na Twitch

def load_streamers_file(path: str):
    if not os.path.exists(path):
        logger.warning(f"Arquivo {path} não encontrado!")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip().lower() for line in f if line.strip() and not line.startswith("#")]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channels-file", default="streamers.txt", help="Arquivo com lista de canais")
    parser.add_argument("--interval", type=int, default=300, help="Intervalo entre coletas em segundos (padrão 5 minutos)")
    args = parser.parse_args()

    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")
    db_path = os.getenv("APP_DB_PATH", "./data/app.db")

    if not client_id or not client_secret:
        logger.error("TWITCH_CLIENT_ID e TWITCH_CLIENT_SECRET não encontrados no .env")
        return

    tc = TwitchClient(client_id, client_secret)
    conn = storage.connect(db_path)
    storage.init_db(conn)

    logger.info("🚀 Coletor de Virtual Casino iniciado")
    logger.info(f"Intervalo: {args.interval}s | Arquivo: {args.channels_file}")

    while True:
        try:
            channels = load_streamers_file(args.channels_file)
            if not channels:
                logger.warning("Nenhum canal carregado. Verifique streamers.txt")
                time.sleep(args.interval)
                continue

            logger.info(f"Verificando {len(channels)} canais...")

            live_streams = tc.get_streams_by_logins(channels)

            saved_count = 0
            skipped_count = 0

            for login, stream in live_streams.items():
                try:
                    viewer_count = int(stream.get("viewer_count", 0))
                    game_id = stream.get("game_id")
                    game_name = stream.get("game_name", "Desconhecido")

                    if game_id != VIRTUAL_CASINO_GAME_ID:
                        logger.info(f"⏭️  {login} ignorado (categoria: {game_name} - {game_id})")
                        skipped_count += 1
                        continue

                    # Salva apenas Virtual Casino
                    storage.save_live_sample(
                        conn=conn,
                        channel=login,
                        viewers=viewer_count,
                        game_id=game_id,
                        game_name=game_name
                    )
                    saved_count += 1
                    logger.info(f"✅ {login} | {viewer_count:,} viewers | Virtual Casino")

                except Exception as e:
                    logger.error(f"Erro ao processar {login}: {e}")

            logger.info(f"Rodada finalizada → Salvos: {saved_count} | Ignorados: {skipped_count}")

        except Exception as e:
            logger.error(f"Erro geral no loop: {e}")

        time.sleep(args.interval)

if __name__ == "__main__":
    main()
