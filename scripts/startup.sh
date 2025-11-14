#!/bin/bash

VNC_PASSWD_FILE="/home/headless/.vncpasswd"
if [ ! -f "$VNC_PASSWD_FILE" ]; then
  mkdir -p /home/headless
  echo "vncpassword" | vncpasswd -f > "$VNC_PASSWD_FILE"
  chown headless:headless "$VNC_PASSWD_FILE"
  chmod 600 "$VNC_PASSWD_FILE"
fi

if [ ! -f "/home/headless/.Xauthority" ]; then
  touch /home/headless/.Xauthority
  chown headless:headless /home/headless/.Xauthority
fi

/usr/bin/Xvnc :1 \
    -depth 24 \
    -geometry 1360x768 \
    -rfbport 5901 \
    -auth /home/headless/.Xauthority \
    -rfbauth /home/headless/.vncpasswd \
    -desktop vncdesktop \
    -pn &

sleep 4

export DISPLAY=:1

startxfce4 &

sleep 8

python3 /app/web-app/app.py
