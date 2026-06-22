#!/usr/bin/env micropython
"""
MicroBot Compatibility Test - Run this on your OpenWrt router
Copy to router: scp test_compatibility.py root@ROUTER_IP:/root/
Run on router: micropython test_compatibility.py
"""

print("=" * 50)
print("MicroBot MicroPython Compatibility Test")
print("=" * 50)
print()

issues_found = []

# ========================================
# Test 1: Core Modules
# ========================================
print("[1/8] Testing core modules...")

try:
    import usys as sys
    print("  ✅ usys (sys module)")
except ImportError:
    try:
        import sys
        print("  ✅ sys (standard)")
    except:
        print("  ❌ sys module missing!")
        issues_found.append("sys module")

try:
    import uos as os
    print("  ✅ uos (os module)")
except ImportError:
    try:
        import os
        print("  ✅ os (standard)")
    except:
        print("  ❌ os module missing!")
        issues_found.append("os module")

try:
    import utime as time
    print("  ✅ utime (time module)")
except ImportError:
    try:
        import time
        print("  ✅ time (standard)")
    except:
        print("  ❌ time module missing!")
        issues_found.append("time module")

try:
    import ujson as json
    print("  ✅ ujson (json module)")
except ImportError:
    try:
        import json
        print("  ✅ json (standard)")
    except:
        print("  ❌ json module missing!")
        issues_found.append("json module")

# ========================================
# Test 2: os module features
# ========================================
print()
print("[2/8] Testing os module features...")

print("  os.name:", os.name if hasattr(os, 'name') else "NOT AVAILABLE")
print("  os.getenv:", "✅" if hasattr(os, 'getenv') else "❌ NOT AVAILABLE")
print("  os.system:", "✅" if hasattr(os, 'system') else "❌ NOT AVAILABLE")
print("  os.stat:", "✅" if hasattr(os, 'stat') else "❌ NOT AVAILABLE")
print("  os.mkdir:", "✅" if hasattr(os, 'mkdir') else "❌ NOT AVAILABLE")
print("  os.remove:", "✅" if hasattr(os, 'remove') else "❌ NOT AVAILABLE")

# Critical: os.popen
if hasattr(os, 'popen'):
    print("  os.popen: ✅ AVAILABLE (good!)")
else:
    print("  os.popen: ❌ NOT AVAILABLE (will use temp file fallback)")
    issues_found.append("os.popen (fallback available)")

# Critical: os.getcwd
if hasattr(os, 'getcwd'):
    print("  os.getcwd: ✅ AVAILABLE")
else:
    print("  os.getcwd: ❌ NOT AVAILABLE (will use __file__)")
    issues_found.append("os.getcwd (fallback available)")

# Critical: os.makedirs
if hasattr(os, 'makedirs'):
    print("  os.makedirs: ✅ AVAILABLE")
else:
    print("  os.makedirs: ❌ NOT AVAILABLE (will need recursive mkdir)")
    issues_found.append("os.makedirs (needs fix)")

# Critical: os.path
if hasattr(os, 'path'):
    print("  os.path: ✅ AVAILABLE")
else:
    print("  os.path: ❌ NOT AVAILABLE (will use custom OSPath class)")
    issues_found.append("os.path (fallback available)")

# ========================================
# Test 3: __file__ variable
# ========================================
print()
print("[3/8] Testing __file__ variable...")

try:
    script_file = __file__
    print("  ✅ __file__ =", script_file)

    # Test path extraction
    if "/" in script_file:
        script_dir = script_file.rsplit("/", 1)[0]
    else:
        script_dir = "."
    print("  ✅ Script directory:", script_dir)
except NameError:
    print("  ❌ __file__ NOT AVAILABLE!")
    issues_found.append("__file__ missing")

# ========================================
# Test 4: Shell command execution
# ========================================
print()
print("[4/8] Testing shell command execution...")

def run_command_test(cmd):
    """Test if we can run shell commands"""
    if hasattr(os, "popen"):
        try:
            p = os.popen(cmd)
            result = p.read()
            p.close()
            return result.strip()
        except:
            pass

    # Fallback: use os.system + temp file
    import time
    tmp_file = "/tmp/test_cmd_" + str(int(time.time())) + ".txt"
    try:
        os.system(cmd + " > " + tmp_file + " 2>&1")
        result = ""
        try:
            with open(tmp_file, "r") as f:
                result = f.read()
            os.remove(tmp_file)
        except:
            pass
        return result.strip()
    except Exception as e:
        return "ERROR: " + str(e)

result = run_command_test("echo 'test'")
if "test" in result:
    print("  ✅ Shell command execution works")
    print("     Result:", result[:50])
else:
    print("  ❌ Shell command execution FAILED!")
    print("     Result:", result)
    issues_found.append("Shell execution")

# ========================================
# Test 5: File I/O
# ========================================
print()
print("[5/8] Testing file I/O...")

test_file = "/tmp/micropython_test.txt"
try:
    # Write
    with open(test_file, "w") as f:
        f.write("test content\nline 2")
    print("  ✅ File write")

    # Read
    with open(test_file, "r") as f:
        content = f.read()
    if "test content" in content:
        print("  ✅ File read")
    else:
        print("  ❌ File read failed")
        issues_found.append("File read")

    # Delete
    os.remove(test_file)
    print("  ✅ File delete")
except Exception as e:
    print("  ❌ File I/O error:", str(e))
    issues_found.append("File I/O")

# ========================================
# Test 6: JSON parsing
# ========================================
print()
print("[6/8] Testing JSON parsing...")

try:
    test_json = '{"key": "value", "number": 123}'
    parsed = json.loads(test_json)
    if parsed.get("key") == "value":
        print("  ✅ JSON parse")
    else:
        print("  ❌ JSON parse failed")
        issues_found.append("JSON parse")

    # JSON dump
    dumped = json.dumps(parsed)
    if "key" in dumped:
        print("  ✅ JSON dump")
    else:
        print("  ❌ JSON dump failed")
        issues_found.append("JSON dump")
except Exception as e:
    print("  ❌ JSON error:", str(e))
    issues_found.append("JSON")

# ========================================
# Test 7: Required external tools
# ========================================
print()
print("[7/8] Testing required external tools...")

tools = ["curl", "jsonfilter"]
for tool in tools:
    result = run_command_test("which " + tool)
    if result and "not found" not in result.lower():
        print("  ✅", tool, "-", result[:40])
    else:
        print("  ❌", tool, "- NOT FOUND")
        issues_found.append(tool + " missing")

# ========================================
# Test 8: Directory creation
# ========================================
print()
print("[8/8] Testing directory creation...")

test_dir = "/tmp/test_mkdir_recursive/sub/dir"
try:
    if hasattr(os, 'makedirs'):
        os.makedirs(test_dir, exist_ok=True)
        print("  ✅ os.makedirs works")
        # Cleanup
        os.rmdir(test_dir)
        os.rmdir("/tmp/test_mkdir_recursive/sub")
        os.rmdir("/tmp/test_mkdir_recursive")
    else:
        # Need recursive mkdir
        print("  ⚠️ os.makedirs not available, need recursive mkdir")
        parts = test_dir.split("/")
        path = ""
        for part in parts:
            if part:
                path += "/" + part
                try:
                    os.mkdir(path)
                except:
                    pass
        # Check if it worked
        try:
            os.stat(test_dir)
            print("  ✅ Recursive mkdir works")
            # Cleanup
            os.rmdir(test_dir)
            os.rmdir("/tmp/test_mkdir_recursive/sub")
            os.rmdir("/tmp/test_mkdir_recursive")
        except:
            print("  ❌ Recursive mkdir failed")
            issues_found.append("mkdir recursive")
except Exception as e:
    print("  ❌ Directory creation error:", str(e))
    issues_found.append("Directory creation")

# ========================================
# Summary
# ========================================
print()
print("=" * 50)
print("COMPATIBILITY TEST COMPLETE")
print("=" * 50)

if issues_found:
    print()
    print("⚠️  Issues found:", len(issues_found))
    for i, issue in enumerate(issues_found, 1):
        print("   ", i, ".", issue)

    print()
    print("🔧 RECOMMENDATIONS:")

    if "os.popen (fallback available)" in str(issues_found):
        print("   • os.popen missing: Code already has fallback ✓")

    if "os.getcwd (fallback available)" in str(issues_found):
        print("   • os.getcwd missing: Code uses __file__ instead ✓")

    if "os.path (fallback available)" in str(issues_found):
        print("   • os.path missing: Code uses custom OSPath class ✓")

    if "os.makedirs (needs fix)" in str(issues_found):
        print("   • os.makedirs missing: NEEDS FIX - see below")

    if "curl missing" in str(issues_found):
        print("   • Install curl: opkg update && opkg install curl")

    if "jsonfilter missing" in str(issues_found):
        print("   • jsonfilter should be built-in on OpenWrt")
else:
    print()
    print("✅ ALL TESTS PASSED!")
    print("   MicroBot should work without modifications")

print()
print("Next steps:")
print("  1. Copy microbot-ash folder to router:")
print("     scp -r microbot-ash root@ROUTER_IP:/root/")
print()
print("  2. Run the bot:")
print("     ssh root@ROUTER_IP")
print("     cd /root/microbot-ash")
print("     micropython agentwrt.py")
