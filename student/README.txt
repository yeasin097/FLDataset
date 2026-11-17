Your lab session — run these on the desktop, in order
=====================================================

Your desktop talks to several targets on your private lab network:
a few normal company websites, plus one or more deliberately vulnerable apps.
Open a terminal on this desktop and run:

  1.  ./normal.sh      Generate normal browsing traffic to the company sites.
                       Browse them in the web browser too. ./stop.sh pauses it.

  2.  ./attack.sh      Network attacks on the company sites (port scan, brute
                       force, flood). One round, then stops by itself.

  3.  ./exploit.sh     REAL exploits on the vulnerable apps: SQL injection,
                       command injection, reverse shell + data exfiltration.
                       One round, then stops by itself.

  4.  ./stop.sh        Return to idle (no traffic) between phases.

Everything is recorded and labeled automatically — you do not need to track
which target or which attack.

Rules: only attack the lab targets shown here. No personal accounts or
passwords inside this desktop. No illegal content.
