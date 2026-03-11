import os
import time
import threading
from flask import Flask
from fastf1.livetiming.client import SignalRClient

app = Flask(__name__)

# Estado global adicionando um controle de tempo
f1_state = {
    "flag": "OFFLINE",
    "last_update": 0  # Guarda o timestamp (momento) do último dado recebido
}

STATUS_MAP = {
    "1": "GREEN",       # Pista limpa
    "2": "YELLOW",      # Bandeira Amarela
    "4": "SAFETY_CAR",  # Safety Car Real
    "5": "RED",         # Bandeira Vermelha (Paralisação)
    "6": "VSC",         # Virtual Safety Car
    "7": "VSC_ENDING"   # VSC terminando
}

LIVETIMING_FILE = "/tmp/f1_live_data.txt"

def monitor_signalr():
    """Conecta no SignalR da F1. Tenta reconectar continuamente se não houver corrida."""
    while True:
        if os.path.exists(LIVETIMING_FILE):
            try:
                os.remove(LIVETIMING_FILE)
            except:
                pass
                
        print("[F1 Bridge] Tentando iniciar cliente SignalR...")
        client = SignalRClient(LIVETIMING_FILE, timeout=60)
        
        try:
            # O start() é bloqueante. Se não tiver corrida, ele falha e solta uma exceção.
            client.start()
        except Exception as e:
            print(f"[F1 Bridge] Sem corrida ativa no momento ou erro de rede: {e}")
        
        # Aguarda 60 segundos antes de tentar procurar uma corrida de novo
        time.sleep(60)

def parse_logs():
    """Lê o arquivo de log em tempo real e atualiza a variável global"""
    while True:
        if not os.path.exists(LIVETIMING_FILE):
            time.sleep(2)
            continue
            
        print("[F1 Bridge] Arquivo de log detectado. Monitorando status...")
        try:
            with open(LIVETIMING_FILE, "r") as f:
                f.seek(0, os.SEEK_END)
                while True:
                    line = f.readline()
                    
                    if not line:
                        # Se o arquivo foi deletado pela thread de reconexão, sai do loop para reabrir
                        if not os.path.exists(LIVETIMING_FILE):
                            break
                        time.sleep(0.5)
                        continue
                    
                    # Qualquer linha lida significa que a conexão está viva e recebendo dados
                    f1_state["last_update"] = time.time()
                    
                    if 'TrackStatus' in line:
                        for key, flag_name in STATUS_MAP.items():
                            if f"'Status': '{key}'" in line or f'"Status": "{key}"' in line:
                                if f1_state["flag"] != flag_name:
                                    f1_state["flag"] = flag_name
                                    print(f">>> MUDANÇA DE PISTA: {flag_name}")
                                break
        except Exception as e:
            print(f"[F1 Bridge] Erro de leitura de log: {e}")
            time.sleep(2)

@app.route('/status')
def get_status():
    """Rota que o ESP32 vai chamar via GET"""
    # Se passou mais de 60 segundos desde a última atualização, consideramos offline
    is_active = (time.time() - f1_state["last_update"]) < 60
    
    if not is_active:
        # O retorno 503 avisa o ESP32 que não há dados da corrida (httpCode != 200)
        return "OFFLINE", 503, {'Content-Type': 'text/plain'}
        
    return f1_state["flag"], 200, {'Content-Type': 'text/plain'}

@app.route('/')
def home():
    """Apenas para checar se o servidor está vivo pelo navegador"""
    is_active = (time.time() - f1_state["last_update"]) < 60
    status_texto = f1_state['flag'] if is_active else "OFFLINE (Sem corrida no momento)"
    return f"F1 Bridge Online! Status atual: {status_texto}"

if __name__ == '__main__':
    t1 = threading.Thread(target=monitor_signalr, daemon=True)
    t1.start()

    t2 = threading.Thread(target=parse_logs, daemon=True)
    t2.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
