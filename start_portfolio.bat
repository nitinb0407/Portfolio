@echo off
title Nitin B Portfolio Backend Server
cd /d "%~dp0"
echo ==============================================================
echo        Starting Nitin B Portfolio Full-Stack Server
echo ==============================================================
echo Website & API URL : http://localhost:8000
echo Mobile / Wi-Fi URL: http://172.16.0.112:8000
echo Database          : contact_messages.db
echo Log File          : contact_submissions.log
echo ==============================================================
python server.py
pause
