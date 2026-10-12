#!/bin/bash

# 1. Hent siste endringer fra Git
cd /home/garasje/Desktop/StreamingHUB && git pull origin main

# 2. Start Spotify og vent litt
spotify &
sleep 5

# 3. Start Chrome mot den lokale filen ved oppstart
google-chrome --kiosk file:///home/garasje/Desktop/StreamingHUB/index.html
