#!/usr/bin/python3
import sys, os, time, threading, pickle, socket, mpsched, torch, shutil
from threading import Event
from configparser import ConfigParser
from replay_memory import ReplayMemory
from agent import Online_Agent, Offline_Agent
from naf_lstm import NAF_LSTM
from datetime import datetime

def main(argv):
    # —— 参数检查 & 保留 scenario —— 
    if len(argv) < 2:
        print("Usage: run_server.sh <CONTINUE_TRAIN> <scenario>")
        sys.exit(1)
    CONTINUE_TRAIN = int(argv[0])
    scenario = argv[1]   # 仅用于日志和训练逻辑

    # —— 读配置（IP/PORT + 要发的文件） —— 
    cfg = ConfigParser()
    cfg.read('config.ini')
    DST_IP        = cfg.get('server','ip')
    DST_PORT      = cfg.getint('server','port')
    MEMORY_FILE   = cfg.get('replaymemory','memory')
    AGENT_FILE    = cfg.get('nafcnn','agent')
    MAX_NUM_FLOWS = cfg.getint('env','max_num_subflows')
    BATCH_SIZE    = cfg.getint('train','batch_size')

    # 这里改成从配置里读 file，而不是 argv[1]
    FILE_TO_SEND  = cfg.get('file','file')

    transfer_event = Event()

    print(f"[UE→Free5GC] CONT={CONTINUE_TRAIN}, scenario='{scenario}', sending='{FILE_TO_SEND}'")

    # —— replay memory & agent 逻辑不动 —— 
    if os.path.exists(MEMORY_FILE) and CONTINUE_TRAIN:
        with open(MEMORY_FILE,'rb') as f:
            try:    memory = pickle.load(f)
            except: memory = ReplayMemory(cfg.getint('replaymemory','capacity'))
    else:
        memory = ReplayMemory(cfg.getint('replaymemory','capacity'))

    if CONTINUE_TRAIN != 1 and os.path.exists(AGENT_FILE):
        os.makedirs("trained_models", exist_ok=True)
        now = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        shutil.move(AGENT_FILE, f"trained_models/agent_{now}.pkl")
    if not os.path.exists(AGENT_FILE) or CONTINUE_TRAIN != 1:
        net = NAF_LSTM(
            gamma=cfg.getfloat('nafcnn','gamma'),
            tau=cfg.getfloat('nafcnn','tau'),
            hidden_size=cfg.getint('nafcnn','hidden_size'),
            num_inputs=cfg.getint('env','k')*MAX_NUM_FLOWS*5,
            action_space=MAX_NUM_FLOWS
        )
        torch.save(net, AGENT_FILE)

    off_agent = Offline_Agent(cfg=cfg, model=AGENT_FILE, memory=memory, event=transfer_event)
    off_agent.daemon = True

    # —— 建立 MPTCP 连接 & 启动 Online_Agent —— 
    MPTCP_PROTO = 262
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, MPTCP_PROTO)
    sock.connect((DST_IP, DST_PORT))

    mpsched.persist_state(sock.fileno())
    on_agent = Online_Agent(fd=sock.fileno(), cfg=cfg, memory=memory, event=transfer_event)
    on_agent.start()
    transfer_event.set()

    # —— 直接发送 file_to_send —— 
    try:
        with open(FILE_TO_SEND, 'rb') as fp:
            while True:
                chunk = fp.read(4096)
                if not chunk:
                    break
                sock.sendall(chunk)
    except Exception as e:
        print(f"[UE] Send error: {e}")

    transfer_event.clear()
    sock.close()

    # —— 保存 replay memory —— 
    with open(MEMORY_FILE,'wb') as f:
        pickle.dump(memory, f)

if __name__ == '__main__':
    main(sys.argv[1:])
