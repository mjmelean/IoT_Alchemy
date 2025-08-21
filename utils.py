# utils.py
import random
import string

def generar_serial(prefix="DEV", length=8):
    rand_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}{rand_part}"

def clamp(v, mn, mx):
    return max(mn, min(mx, v))
