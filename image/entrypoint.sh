#!/bin/bash
set -e

export PYDEVD_DISABLE_FILE_VALIDATION=1

# Function to find the first free X11 display number
# find_free_display() {
#   for i in {0..99}; do
#     if ! xset -display ":$i" q &>/dev/null; then
#       echo $i
#       return 0
#     fi
#   done
#   echo "No free display found" >&2
#   exit 1
# }

# Find a free display
# FREE_DISPLAY=$(find_free_display)

# Export the environment variable
export DISPLAY=":$DISPLAY_NUM"

echo "Setting DISPLAY to $DISPLAY"

echo "The following environment variables are set:"
echo "HOST_NOVNC_PORT: $HOST_NOVNC_PORT"
echo "HOST_STREAMLIT_PORT: $HOST_STREAMLIT_PORT"

envsubst < /home/computeruse/static_content/index.template.html > /home/computeruse/static_content/index.html

./start_all.sh
./novnc_startup.sh

# Start http_server in the background and log output
python -Xfrozen_modules=off http_server.py > /tmp/server_logs.txt 2>&1 &

# Set default port for Streamlit if not provided
STREAMLIT_SERVER_PORT=${STREAMLIT_SERVER_PORT:-8501}

if [ "$DEBUG" = "1" ]; then
    # Run Streamlit with debugpy for debugging
    echo "🛠️  Starting Streamlit in debug mode with debugpy on port 5678"
    python -Xfrozen_modules=off -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m streamlit run computer_use_demo/streamlit.py > /tmp/streamlit_stdout.log &
else
    # Start Streamlit without debugging
    mkdir -p ~/.streamlit
    echo "[general]" > ~/.streamlit/credentials.toml
    echo "email = \"\"" >> ~/.streamlit/credentials.toml
    echo "🚀 Starting Streamlit on port $STREAMLIT_SERVER_PORT"
    echo "🚀 Starting Streamlit on port $STREAMLIT_SERVER_PORT"
    python -Xfrozen_modules=off -m streamlit run computer_use_demo/streamlit.py > /tmp/streamlit_stdout.log &
fi

echo "✨ Computer Use Demo is ready!"
echo "➡️  Open http://localhost:8080 in your browser to begin"

export DISPLAY=:$DISPLAY_NUM
# Check if WEBSITE_URL is set and not empty
if [ -n "$WEBSITE_URL" ]; then
    # If WEBSITE_URL is set, open it in a new tab along with about:preferences
    firefox-esr --new-tab "$WEBSITE_URL" --new-tab about:preferences --remote-debugging-port=9222 --no-remote
else
    # If WEBSITE_URL is not set, open only about:preferences
    firefox-esr --new-tab about:preferences --remote-debugging-port=9222 --no-remote
fi

# Keep the container running
tail -f /dev/null