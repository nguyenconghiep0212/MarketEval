import os
import sys
import time
import socket
import subprocess
import webview


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Checks if a port is actively accepting TCP connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0


def main():
    streamlit_port = 8501
    ui_path = os.path.join("ui", "main.py")

    # 1. Check if Streamlit server is already running
    if not is_port_open(streamlit_port):
        print("🚀 Starting background Streamlit engine...")
        streamlit_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                ui_path,
                f"--server.port={streamlit_port}",
                "--server.headless=true",
                "--global.developmentMode=false",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait until Streamlit server responds on TCP port 8501
        print("⏳ Waiting for UI engine to initialize...")
        attempts = 0
        while not is_port_open(streamlit_port) and attempts < 20:
            time.sleep(0.5)
            attempts += 1
    else:
        print("⚡ Streamlit is already running on port 8501.")
        streamlit_process = None

    # 2. Launch the native desktop application window
    print("🖥️ Opening MarketEval Desktop Window...")
    window = webview.create_window(
        title="MarketEval — Trading Decision Support System",
        url=f"http://localhost:{streamlit_port}",
        width=1280,
        height=850,
        min_size=(900, 600),
        resizable=True,
    )

    # 3. Start pywebview event loop (blocks until window is closed)
    webview.start()

    # 4. Gracefully terminate Streamlit server when user exits app window
    if streamlit_process:
        print("🛑 Closing background Streamlit process...")
        streamlit_process.terminate()
        streamlit_process.wait()


if __name__ == "__main__":
    main()