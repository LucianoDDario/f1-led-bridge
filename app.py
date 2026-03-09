import os
import time
import threading
from flask import Flask
from fastf1.livetiming.client import SignalRClient

app = Flask(__name__)

# Estado global que o ESP32 vai ler
f1_state = {"flag": "GREEN"}

# Mapeamento de status da pista para os seus LEDs
STATUS_MAP = {
    "1": "GREEN",       # Pista limpa
    "2": "YELLOW",      # Bandeira Amarela
    "4": "SAFETY_CAR",  # Safety Car Real
    "5": "RED",         # Bandeira Vermelha (Paralisação)
    "6": "VSC",         # Virtual Safety Car
    "7": "VSC_ENDING"   # VSC terminando
}

# No Render, usamos a pasta /tmp para arquivos temporários
LIVETIMING_FILE = "/tmp/f1_live_data.txt"

def monitor_signalr():
    """Conecta no SignalR da F1 e grava os dados brutos no arquivo"""
    if os.path.exists(LIVETIMING_FILE):
        try:
            os.remove(LIVETIMING_FILE)
        except:
            pass
            
    print("[F1 Bridge] Iniciando cliente SignalR...")
    # O SignalRClient é a parte leve da fastf1 (sem Pandas)
    client = SignalRClient(LIVETIMING_FILE, timeout=60)
    try:
        client.start()
    except Exception as e:
        print(f"Erro no cliente SignalR: {e}")

def parse_logs():
    """Lê o arquivo de log em tempo real e atualiza a variável global"""
    while not os.path.exists(LIVETIMING_FILE):
        time.sleep(1)
        
    print("[F1 Bridge] Arquivo de log detectado. Monitorando status...")
    with open(LIVETIMING_FILE, "r") as f:
        # Vai para o fim do arquivo para pegar apenas o que acontecer agora
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            
            # Procuramos pela mudança de status da pista
            if 'TrackStatus' in line:
                for key, flag_name in STATUS_MAP.items():
                    # Verifica se o código do status está na linha capturada
                    if f"'Status': '{key}'" in line or f'"Status": "{key}"' in line:
                        if f1_state["flag"] != flag_name:
                            f1_state["flag"] = flag_name
                            print(f">>> MUDANÇA DE PISTA: {flag_name}")
                        break

@app.route('/status')
def get_status():
    """Rota que o ESP32 vai chamar via GET"""
    return f1_state["flag"], 200, {'Content-Type': 'text/plain'}

@app.route('/')
def home():
    """Apenas para checar se o servidor está vivo pelo navegador"""
    return f"F1 Bridge Online! Status atual: {f1_state['flag']}"

if __name__ == '__main__':
    # Inicia a thread de conexão com a F1
    t1 = threading.Thread(target=monitor_signalr, daemon=True)
    t1.start()

    # Inicia a thread de leitura do log
    t2 = threading.Thread(target=parse_logs, daemon=True)
    t2.start()

    # Pega a porta que o Render designar, ou usa 5000 localmente
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
