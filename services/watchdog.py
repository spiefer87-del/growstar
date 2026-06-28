import datetime

import core.context as ctx


def log_event(msg, level="INFO"):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {level}: {msg}\n"

    try:
        with open(ctx.LOG_FILE, "a") as f:
            f.write(line)
    except Exception as e:
        print("❌ Log write error:", e)
