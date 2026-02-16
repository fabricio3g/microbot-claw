#!/usr/bin/env python3
import os

print("=== Testing os.makedirs ===")
print("os module dir:", dir(os))

if hasattr(os, "makedirs"):
    print("✅ os.makedirs: AVAILABLE")
else:
    print("❌ os.makedirs: NOT AVAILABLE")
    print("   Will need to use os.mkdir() recursively")
