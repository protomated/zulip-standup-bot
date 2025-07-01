#!/usr/bin/env python3
"""
Test script to verify that all required modules can be imported.
"""

import sys
import os

# Add the local zulip_bots directory to Python path
sys.path.insert(0, '/app/zulip_bots')
sys.path.insert(0, '/app')

def test_imports():
    """Test importing required modules."""
    print("Testing module imports...")
    print(f"Python path: {sys.path}")
    print(f"Working directory: {os.getcwd()}")

    try:
        print("1. Testing zulip import...")
        import zulip
        print("   ✅ zulip imported successfully")

        print("2. Testing zulip_bots import...")
        import zulip_bots
        print(f"   ✅ zulip_bots imported successfully from {zulip_bots.__file__}")

        print("3. Testing zulip_bots.bots import...")
        import zulip_bots.bots
        print("   ✅ zulip_bots.bots imported successfully")

        print("4. Testing zulip_bots.bots.standup import...")
        import zulip_bots.bots.standup
        print("   ✅ zulip_bots.bots.standup imported successfully")

        print("5. Testing zulip_bots.bots.standup.database import...")
        from zulip_bots.bots.standup import database
        print("   ✅ zulip_bots.bots.standup.database imported successfully")

        print("6. Testing database.init_db function...")
        print(f"   Database init function: {database.init_db}")
        print("   ✅ All imports successful!")

        return True

    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        print("\nDebugging information:")
        print("Available packages:")
        try:
            import pkg_resources
            for package in pkg_resources.working_set:
                print(f"  {package.project_name}=={package.version}")
        except:
            print("  pkg_resources not available")

        print("\nPython sys.path:")
        for path in sys.path:
            print(f"  {path}")

        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
