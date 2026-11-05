@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Whisper en vivo
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ver_whisper.ps1"
