#!/usr/bin/env micropython
# Test what's available in this MicroPython

print("=== Testing MicroPython Modules ===\n")

# Test os module
print("--- os module ---")
try:
    import os

    print("os: OK")
    print("  dir(os):", dir(os))
except Exception as e:
    print("os: ERROR -", e)

# Test os.stat
print("\n--- os.stat ---")
try:
    import os

    st = os.stat(".")
    print("os.stat('.'): OK")
    print("  result:", st)
except Exception as e:
    print("os.stat: ERROR -", e)

# Test os.path
print("\n--- os.path ---")
try:
    import os

    print("hasattr(os, 'path'):", hasattr(os, "path"))
    if hasattr(os, "path"):
        print("  dir(os.path):", dir(os.path))
except Exception as e:
    print("os.path: ERROR -", e)

# Test uos
print("\n--- uos module ---")
try:
    import uos

    print("uos: OK")
    print("  dir(uos):", dir(uos))
except Exception as e:
    print("uos: ERROR -", e)

# Test pathlib (probably not available)
print("\n--- pathlib ---")
try:
    import pathlib

    print("pathlib: OK")
except Exception as e:
    print("pathlib: NOT AVAILABLE -", e)

# Test pwd command
print("\n--- pwd command ---")
try:
    import os

    # Try popen
    if hasattr(os, "popen"):
        p = os.popen("pwd")
        result = p.read()
        p.close()
        print("os.popen('pwd'):", result.strip())
    else:
        print("os.popen: NOT AVAILABLE")
except Exception as e:
    print("pwd: ERROR -", e)

# Test getcwd
print("\n--- getcwd ---")
try:
    import os

    if hasattr(os, "getcwd"):
        print("os.getcwd():", os.getcwd())
    else:
        print("os.getcwd: NOT AVAILABLE")
except Exception as e:
    print("getcwd: ERROR -", e)

# Test __file__
print("\n--- __file__ ---")
try:
    print("__file__:", __file__)
except Exception as e:
    print("__file__: ERROR -", e)

# Test sys
print("\n--- sys module ---")
try:
    import sys

    print("sys: OK")
    print("  sys.argv:", sys.argv)
    print("  sys.path:", sys.path)
except Exception as e:
    print("sys: ERROR -", e)

# Test usys
print("\n--- usys module ---")
try:
    import usys

    print("usys: OK")
    print("  usys.argv:", usys.argv)
except Exception as e:
    print("usys: ERROR -", e)

print("\n=== Test Complete ===")
