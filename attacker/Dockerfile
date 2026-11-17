FROM kalilinux/kali-rolling
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        nmap hydra hping3 nikto gobuster python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY lists /opt/lists
COPY scheduler.py /opt/scheduler.py
CMD ["python3", "-u", "/opt/scheduler.py"]
