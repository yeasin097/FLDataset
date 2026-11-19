# Lightweight toolbox: Debian slim + just the tools we use. Much smaller than a
# full Kali image, and this same image is reused for the capture sidecar
# (it ships tcpdump), so the lab needs only ONE built image and no netshoot pull.
FROM debian:stable-slim
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        nmap hydra hping3 dirb tcpdump iproute2 curl ca-certificates python3 \
    && rm -rf /var/lib/apt/lists/*
COPY lists /opt/lists
COPY runner.py /opt/runner.py
COPY capture.sh /opt/capture.sh
RUN chmod +x /opt/capture.sh
CMD ["python3", "-u", "/opt/runner.py"]
