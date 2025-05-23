#!/usr/bin/python3
import sys, socket
from configparser import ConfigParser

def main():
    cfg = ConfigParser()
    cfg.read('config.ini')
    PORT  = cfg.getint('server','port')
    OUT_F = cfg.get('file','file')   # 输出文件名仍从 [file] 段读

    MPTCP_PROTO = 262
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM, MPTCP_PROTO)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('0.0.0.0', PORT))      # 绑定所有接口
    srv.listen(1)
    print(f"[Free5GC] Listening on port {PORT} ...")

    while True:
        conn, addr = srv.accept()
        print(f"[Free5GC] Connection from {addr}, saving to '{OUT_F}'")
        try:
            with open(OUT_F, 'wb') as f:
                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    f.write(data)
            print(f"[Free5GC] Received '{OUT_F}' complete")
        except Exception as e:
            print(f"[Free5GC] Recv error: {e}")
        finally:
            conn.close()

if __name__ == '__main__':
    main()
