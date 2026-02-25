# Main/status.py

_callback = None
_last_len = 0

def set_callback(fn):
    global _callback
    _callback = fn

def update(message):
    global _last_len
    if _callback:
        _callback(message)
    padded = message.ljust(_last_len)
    _last_len = len(message)
    print(f"\r{padded}", end="", flush=True)
