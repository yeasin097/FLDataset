FROM kalilinux/kali-rolling
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        nmap hydra hping3 nikto gobuster curl ca-certificates python3 \
    && rm -rf /var/lib/apt/lists/*
COPY lists /opt/lists
COPY runner.py /opt/runner.py
CMD ["python3", "-u", "/opt/runner.py"]
