import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.telegram_client import telegram_send

load_dotenv()

chat_id = os.getenv("TELEGRAM_CHAT_ID_LIVE")
print(f"Enviando mensaje de prueba al chat: {chat_id}")
if not chat_id:
    print("ERROR: TELEGRAM_CHAT_ID_LIVE no está definido en el entorno.")
    sys.exit(1)

msg = "<b>[TEST LIVE ALERT]</b> 🚀 Sincronización de canales de Telegram completada. Este canal ahora recibe todas las alertas intradía en vivo. ¡Todo en orden!"
ok = telegram_send(msg, chat_id=chat_id)
if ok:
    print("✅ Mensaje enviado con éxito.")
else:
    print("❌ ERROR al enviar el mensaje.")
