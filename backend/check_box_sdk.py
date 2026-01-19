"""Check box_sdk_gen API"""
from box_sdk_gen import BoxOAuth, OAuthConfig
import inspect

print("=== OAuthConfig parameters ===")
print(inspect.signature(OAuthConfig.__init__))

print("\n=== BoxOAuth parameters ===")
print(inspect.signature(BoxOAuth.__init__))

# Check if there's a way to set tokens
print("\n=== BoxOAuth methods ===")
for name, method in inspect.getmembers(BoxOAuth, predicate=inspect.isfunction):
    if not name.startswith('_'):
        print(f"  {name}: {inspect.signature(method)}")

# Try different imports
print("\n=== Available imports from box_sdk_gen ===")
import box_sdk_gen
for name in dir(box_sdk_gen):
    if not name.startswith('_'):
        print(f"  {name}")
