#!/system/bin/sh
# Jio Remote Button Remapper Daemon
# Dynamically reads mappings from /data/local/tmp/remap_config.conf

CONFIG_FILE="/data/local/tmp/remap_config.conf"

load_config() {
    NETFLIX_PKG="app.netmirror.newtv"
    YOUTUBE_PKG="io.gh.reisxd.tizentube.cobalt"
    HOTSTAR_PKG="in.startv.hotstar"
    VOOT_PKG="com.viacom18.tv.voot"

    if [ -f "$CONFIG_FILE" ]; then
        while IFS='=' read -r key val || [ -n "$key" ]; do
            case "$key" in
                NETFLIX_PKG*) NETFLIX_PKG=$(echo "$val" | tr -d '\r\n ') ;;
                YOUTUBE_PKG*) YOUTUBE_PKG=$(echo "$val" | tr -d '\r\n ') ;;
                HOTSTAR_PKG*) HOTSTAR_PKG=$(echo "$val" | tr -d '\r\n ') ;;
                VOOT_PKG*)    VOOT_PKG=$(echo "$val" | tr -d '\r\n ') ;;
            esac
        done < "$CONFIG_FILE"
    fi
}

launch_app() {
    target="$1"
    [ -z "$target" ] && return 0
    if echo "$target" | grep -q "/"; then
        am start -n "$target" >/dev/null 2>&1
    else
        act=$(cmd package resolve-activity --brief "$target" 2>/dev/null | tail -n 1)
        if [ -n "$act" ] && [ "$act" != "null" ] && ! echo "$act" | grep -q "No activity found"; then
            am start -n "$act" >/dev/null 2>&1
        else
            monkey -p "$target" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
        fi
    fi
}

# Initial config load
load_config

# Find Bluetooth remote event node dynamically
EVENT_NODE=""
for ev in /dev/input/event*; do
    DEV_PATH=$(readlink -f /sys/class/input/$(basename "$ev") 2>/dev/null)
    if echo "$DEV_PATH" | grep -q "057A:0062"; then
        EVENT_NODE="$ev"
        break
    fi
done

if [ -z "$EVENT_NODE" ]; then
    EVENT_NODE="/dev/input/event5"
fi

getevent "$EVENT_NODE" | while read -r a b c d; do
    code=""
    val=""
    if [ "$c" = "00000001" ]; then
        code="$b"
        val="$c"
    elif [ "$d" = "00000001" ]; then
        code="$c"
        val="$d"
    fi

    if [ -n "$code" ]; then
        # Reload config in case user changed it without restarting daemon
        load_config
        case "$code" in
            00b9|185) # Netflix button
                launch_app "$NETFLIX_PKG"
                ;;
            00bb|187) # YouTube button
                launch_app "$YOUTUBE_PKG"
                ;;
            00b8|184) # Hotstar button
                launch_app "$HOTSTAR_PKG"
                ;;
            00ba|186) # Voot button
                launch_app "$VOOT_PKG"
                ;;
        esac
    fi
done
