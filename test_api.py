#!/usr/bin/env python3
"""
Test script for YMSD Sleeper API

This script tests the API endpoints to ensure they're working correctly.
Run this after deploying the API to validate functionality.
"""

import requests
import json
import sys
from typing import Dict, Any


def test_endpoint(url: str, expected_status: int = 200) -> Dict[str, Any]:
    """Test an API endpoint and return the response"""
    try:
        response = requests.get(url, timeout=30)
        print(f"GET {url}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == expected_status:
            print("✅ PASS")
            try:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)[:200]}...")
                return data
            except:
                print(f"Response: {response.text[:200]}...")
                return {"text": response.text}
        else:
            print("❌ FAIL")
            print(f"Expected: {expected_status}, Got: {response.status_code}")
            print(f"Response: {response.text}")
            return {"error": f"Status {response.status_code}"}
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: {e}")
        return {"error": str(e)}
    
    print()


def main():
    """Run API tests"""
    if len(sys.argv) != 2:
        print("Usage: python test_api.py <api_url>")
        print("Example: python test_api.py https://abc123.execute-api.us-east-1.amazonaws.com/dev")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    print(f"🧪 Testing YMSD Sleeper API at: {base_url}")
    print("=" * 60)
    
    # Test endpoints
    endpoints = [
        ("/", "Root endpoint"),
        ("/v1/health", "Health check"),
        ("/v1/version", "Version info"),
        ("/v1/versions", "Available versions"),
        ("/v1/cache/status", "Cache status"),
        ("/v1/weekly-stats?limit=5", "Weekly stats (limited)"),
        ("/v1/weekly-stats?season=2024&limit=3", "Weekly stats (filtered)"),
    ]
    
    results = {}
    
    for endpoint, description in endpoints:
        print(f"\n🔍 Testing: {description}")
        url = f"{base_url}{endpoint}"
        results[endpoint] = test_endpoint(url)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    
    passed = 0
    failed = 0
    
    for endpoint, result in results.items():
        if "error" in result:
            print(f"❌ {endpoint}: FAILED")
            failed += 1
        else:
            print(f"✅ {endpoint}: PASSED")
            passed += 1
    
    print(f"\nTotal: {passed + failed}, Passed: {passed}, Failed: {failed}")
    
    if failed > 0:
        print("\n⚠️  Some tests failed. Check the API deployment and configuration.")
        sys.exit(1)
    else:
        print("\n🎉 All tests passed! The API is working correctly.")


if __name__ == "__main__":
    main()
