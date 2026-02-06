# Main/status.py

_callback = None

def set_callback(fn):
    global _callback
    _callback = fn

def update(message):
    if _callback:
        _callback(message)
    print(f"\r{message}", end="", flush=True)
