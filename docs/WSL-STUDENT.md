# Student Guide — Running the Lab in WSL2 (Windows)

You will run your own small copy of the lab on your Windows laptop inside WSL2
(a Linux environment Windows provides). You generate normal + attack + exploit
traffic for a few weeks, **send your results to the operator**, then uninstall
everything in one command.

> **The one rule you must not break:**
> **Send your collected data BEFORE you uninstall.** Uninstalling WSL deletes
> everything permanently, including your captured data.

Your operator gives you two things:
- your **student number** `N` (e.g. `7`)
- the shared **seed** (e.g. `42`)
- the **kit** (a folder/zip of the project files)

---

## 0. Requirements

- Windows 10 (version 2004+) or Windows 11, with **administrator** rights.
- **Virtualization enabled** in BIOS/UEFI (most modern laptops: on by default).
- ~8 GB free disk and ~4 GB free RAM while the lab runs.
- Internet (to download Docker images the first time, ~6 GB).

---

## 1. Install WSL2 with a dedicated Ubuntu

Open **PowerShell as Administrator** and run:

```powershell
wsl --install -d Ubuntu-24.04
```

Reboot if it asks. On first launch it creates a Linux username/password (your
choice — remember them).

> **Use a distro dedicated to this lab.** In step 7 you will *wipe the whole
> distro*. If `Ubuntu-24.04` is already used for your other work, install a
> separate one instead, e.g. `wsl --install -d Ubuntu` and keep them separate.

Enable systemd so Docker starts automatically. Inside the Ubuntu terminal:

```bash
sudo tee /etc/wsl.conf >/dev/null <<'EOF'
[boot]
systemd=true
EOF
```

Then from **PowerShell**: `wsl --shutdown` and reopen Ubuntu.

---

## 2. Install Docker inside WSL

In the Ubuntu terminal:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 python3-yaml
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Close and reopen the Ubuntu terminal (so the docker group applies), then verify:

```bash
docker ps        # should print an empty table, no error
```

---

## 3. Put the kit in place

Copy the kit the operator gave you into your WSL home. If it's a zip in your
Windows Downloads:

```bash
mkdir -p ~/fl-lab
cd ~/fl-lab
unzip "/mnt/c/Users/<YourWindowsName>/Downloads/fl-lab.zip" -d .
```

Set your number and seed (replace with yours):

```bash
export FLLAB_N=7
export FLLAB_SEED=42
```

> Keep the project **inside** the WSL filesystem (`~/fl-lab`), **not** on
> `/mnt/c/...` — it is much faster and capture works better there.

---

## 4. First-time setup (one command)

```bash
cd ~/fl-lab
./scripts/student.sh "$FLLAB_N" setup
```

This builds and starts your stack (first run downloads ~6 GB and builds the
toolbox — give it 10–20 minutes). When it finishes it prints your desktop URL,
for example:

```
https://localhost:30007     user: s007     password: see students.csv
```

Open that in your browser. The certificate is self-signed → click
**Advanced → Proceed**. You now have your lab desktop.

---

## 5. Daily work (~30–45 min/day, ~3 weeks)

Each day, drive the phases from the Ubuntu terminal (you can also browse the
sites yourself in the desktop browser during `normal`):

```bash
cd ~/fl-lab
./scripts/student.sh "$FLLAB_N" normal     # start normal browsing traffic
# ... use it for a while, browse the sites in the desktop ...
./scripts/student.sh "$FLLAB_N" stop       # pause

./scripts/student.sh "$FLLAB_N" attack     # one round of network attacks
./scripts/student.sh "$FLLAB_N" exploit    # one round of real exploits
./scripts/student.sh "$FLLAB_N" status     # see containers + recent labels
```

Mix it up over the weeks: mostly normal traffic, with a few attack/exploit
rounds per session. Everything is labeled automatically — you don't track
anything.

> `exploit` needs the vulnerable app (DVWA) to be warmed up. If `status` shows
> exploit rows with exit codes `-1`/`-2`, wait a minute and run `exploit` again.

To free your laptop between days you can stop the stack and restart later:

```bash
./scripts/student.sh "$FLLAB_N" down       # stop (your data is kept)
./scripts/student.sh "$FLLAB_N" setup      # start again another day
```

---

## 6. Finish: collect and SEND your data

When your collection period ends:

```bash
cd ~/fl-lab
./scripts/student.sh "$FLLAB_N" collect
```

It writes a file like `~/fllab-s007-20261130-1530.tgz` and prints its path.
From Windows you can find it at:

```
\\wsl$\Ubuntu-24.04\home\<your-linux-user>\fllab-s007-....tgz
```

**Send that file to your operator** (email/upload as instructed). Wait for them
to confirm they received it.

---

## 7. Uninstall — only after your data is confirmed received

Stop the stack, then from **PowerShell**:

```powershell
wsl --unregister Ubuntu-24.04
```

That deletes the entire lab distro — all containers, images, and files — and
reclaims the disk. Optionally remove WSL itself from *Windows Features* if you
don't use it for anything else.

---

## Troubleshooting

**`docker ps` says "Cannot connect to the Docker daemon".**
`sudo systemctl start docker` (or you skipped the systemd step in §1).

**Toolbox build fails with `Temporary failure resolving 'http.kali.org'`.**
Docker's build DNS. Fix it once:
```bash
sudo mkdir -p /etc/docker
echo '{"dns": ["8.8.8.8", "1.1.1.1"]}' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
./scripts/student.sh "$FLLAB_N" setup
```

**`wsl --install` fails / "virtualization not enabled".**
Enable Virtualization (Intel VT-x / AMD-V) and, if present, "Virtual Machine
Platform" in BIOS/UEFI, then retry.

**Port 300NN already in use.** Something else uses that port. Tell your operator;
they can reassign your number or base port.

**Out of memory / laptop very slow.** Run only one phase at a time and
`./scripts/student.sh N down` when not actively collecting. The desktop image is
large (~5 GB) and needs ~2 GB RAM while running.

**Desktop won't load.** Give it a minute after `setup`; the desktop container
takes time to start. Then refresh `https://localhost:300NN` and accept the
self-signed certificate.
