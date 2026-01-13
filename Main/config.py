import json
import logging
from pathlib import Path

from psnawp_api import PSNAWP
from psnawp_api.core.psnawp_exceptions import PSNAWPAuthenticationError

BASEDIR = Path(__file__).parent
LOG_FOLDER = BASEDIR / "logs"
LOG_FOLDER.mkdir(exist_ok=True)

def configure_logging():
	"""Configura logging (arquivo + stderr)."""
	log_file = LOG_FOLDER / "psn_extractor.log"
	root = logging.getLogger()
	if root.handlers:
		return
	logging.basicConfig(
		level=logging.INFO,
		format="%(asctime)s [%(levelname)s] %(message)s",
		handlers=[
			logging.FileHandler(log_file, encoding="utf-8"),
			logging.StreamHandler(),
		],
	)

def load_npsso_token(config_path: Path | None = None) -> str:
	config_path = config_path or (BASEDIR / "token.json")
	if not config_path.exists():
		logging.error("Token file not found: token.json")
		return ""
	try:
		with open(config_path, "r", encoding="utf-8") as f:
			data = json.load(f)
			value = data.get("np_sso", "")
			return value.strip() if isinstance(value, str) else ""
	except json.JSONDecodeError:
		logging.error("Error decoding JSON from token.json")
		return ""

def loader_config():
	"""Retorna configurações carregadas."""
	npsso_token = load_npsso_token()
	return {
		"BASEDIR": BASEDIR,
		"LOG_FOLDER": LOG_FOLDER,
		"NPSSO_TOKEN": npsso_token,
	}

# Entrypoint simples para teste
if __name__ == "__main__":
	configure_logging()
	logging.info("Config Check: OK")