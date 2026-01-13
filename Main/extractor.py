import json
import logging
import re
import unicodedata
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

from config import loader_config
from psnawp_api import PSNAWP
from psnawp_api.core.psnawp_exceptions import PSNAWPAuthenticationError

# Configurações Globais
CONFIG = loader_config()
NPSSO_TOKEN = CONFIG["NPSSO_TOKEN"]

# --- AJUSTE DE SENSIBILIDADE ---
# Só considera "Bug de Telemetria" se tiver MAIS de 15 horas jogadas e NENHUM troféu.
# Isso preserva jogos testados (2h, 5h, 10h) mas remove bugs de Rest Mode (200h+ sem troféu).
GHOST_PLAYTIME_THRESHOLD = 54000  # 15 horas (em segundos)

def format_duration(seconds: float | int | None) -> str:
    if not seconds or seconds <= 0:
        return "0h 0m"
    try:
        total_minutes = int(seconds // 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours}h {minutes}m"
    except Exception:
        return "0h 0m"

def _normalize_string(value: str) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("®", "").replace("™", "").replace("℠", "")
    text = text.casefold()
    # Mantém letras, números e espaços, remove pontuação
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def _get_platform_str(title_obj: Any) -> str:
    """Extrai plataforma de forma segura, testando múltiplos atributos conhecidos da API."""
    platforms = getattr(title_obj, "title_platforms", None)
    if not platforms:
        platforms = getattr(title_obj, "platforms", None)
    
    if not platforms:
        return "UNKNOWN"
        
    if isinstance(platforms, list):
        return ", ".join(sorted(platforms))
    return str(platforms)

def _build_playtime_registry(title_stats) -> Tuple[Dict[str, float], float]:
    playtime_map: Dict[str, float] = {}
    total_lifetime: float = 0.0

    print("--> [ETL] Processando estatísticas de tempo (Title Stats)...")
    
    for title in title_stats:
        try:
            duration = float(title.play_duration.total_seconds())
        except Exception:
            duration = 0.0

        if duration > 0:
            raw_name = getattr(title, "name", "") or getattr(title, "title_name", "") or ""
            norm_key = _normalize_string(raw_name)
            
            if norm_key:
                current_max = playtime_map.get(norm_key, 0.0)
                playtime_map[norm_key] = max(current_max, duration)
                
            total_lifetime += duration

    return playtime_map, total_lifetime

def _safe_percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 1)

def extract_ultimate_data(
    *,
    npsso_token: str,
    out_path: Path | None = None,
    include_playtime: bool = True
) -> Path:
    psn = PSNAWP(npsso_token)
    client = psn.me()
    logging.info(f"Iniciando extração para: {client.online_id}")
    print(f"--> [SYSTEM] Usuário Autenticado: {client.online_id}")

    # 1. Pipeline de Playtime
    playtime_map: Dict[str, float] = {}
    total_seconds_lifetime: float = 0.0
    
    if include_playtime:
        try:
            title_stats = client.title_stats()
            playtime_map, total_seconds_lifetime = _build_playtime_registry(title_stats)
        except Exception as e:
            logging.error(f"Erro ao baixar playtime: {e}")
            print("--> [WARN] Falha no módulo de Playtime. Continuando apenas com troféus.")

    # 2. Pipeline de Troféus
    print("--> [NETWORK] Baixando lista completa de troféus...")
    trophy_titles = client.trophy_titles(limit=None)

    deduplicated_library: Dict[Tuple[str, str], Dict[str, Any]] = {}
    total_platinums_count = 0

    print("--> [ETL] Sanitizando entradas e cruzando dados...")

    for title in trophy_titles:
        raw_name = getattr(title, "title_name", "Unknown Title")
        norm_name = _normalize_string(raw_name)
        
        platform_str = _get_platform_str(title)
        
        seconds_played = playtime_map.get(norm_name, 0.0)

        earned = title.earned_trophies
        defined = title.defined_trophies
        total_trophies = defined.bronze + defined.silver + defined.gold + defined.platinum
        earned_total = earned.bronze + earned.silver + earned.gold + earned.platinum
        progress_percent = _safe_percent(earned_total, total_trophies)

        # --- LÓGICA ANTI-FANTASMA ---
        if seconds_played > GHOST_PLAYTIME_THRESHOLD and earned_total == 0:
            logging.warning(f"Detectado Bug de Telemetria (Ghost): {raw_name} - {format_duration(seconds_played)} removidos.")
            seconds_played = 0.0 
        
        game_obj = {
            "title": raw_name,
            "platform": platform_str,
            "is_platinum_earned": earned.platinum > 0,
            "playtime": {
                "seconds": round(seconds_played, 2),
                "hours": round(seconds_played / 3600, 2),
                "formatted": format_duration(seconds_played),
            },
            "trophies": {
                "progress": f"{progress_percent}%",
                "progress_float": progress_percent,
                "breakdown": {
                    "plat": earned.platinum,
                    "gold": earned.gold,
                    "silver": earned.silver,
                    "bronze": earned.bronze,
                },
            },
        }

        # --- DEDUPLICAÇÃO ---
        dedup_key = (norm_name, platform_str)

        if dedup_key in deduplicated_library:
            existing = deduplicated_library[dedup_key]
            # Prioriza progresso maior
            if game_obj["trophies"]["progress_float"] > existing["trophies"]["progress_float"]:
                 deduplicated_library[dedup_key] = game_obj
            # Se progresso igual, prioriza tempo jogado (se não for zero)
            elif game_obj["trophies"]["progress_float"] == existing["trophies"]["progress_float"]:
                 if game_obj["playtime"]["seconds"] > existing["playtime"]["seconds"]:
                     deduplicated_library[dedup_key] = game_obj
        else:
            deduplicated_library[dedup_key] = game_obj

    # 3. Output Final
    final_library_list = []
    platinum_collection = []

    for game in deduplicated_library.values():
        del game["trophies"]["progress_float"] # Limpeza
        final_library_list.append(game)
        
        if game["is_platinum_earned"]:
            platinum_collection.append(game)
            total_platinums_count += 1

    final_library_list.sort(key=lambda x: x['title'])

    library_data = {
        "metadata": {
            "user": client.online_id,
            "total_playtime_seconds": total_seconds_lifetime,
            "total_playtime_formatted": format_duration(total_seconds_lifetime),
            "total_platinums": total_platinums_count,
            "total_games_unique": len(final_library_list),
        },
        "platinum_collection": platinum_collection,
        "full_library": final_library_list,
    }

    if out_path is None:
        out_path = Path(__file__).resolve().parent / f"psn_full_dump_{client.online_id}.json"
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(library_data, f, indent=4, ensure_ascii=False)

    print(f"\n--> [SUCCESS] Extração Completa.")
    print(f"--> Jogos Processados: {len(final_library_list)}")
    print(f"--> Arquivo: {out_path}")
    
    return out_path

if __name__ == "__main__":
    try:
        extract_ultimate_data(npsso_token=NPSSO_TOKEN)
    except Exception as e:
        print(f"ERROR: {e}")