#!/usr/bin/env python3
"""
Example HTTP API Client for Browser-Use Shopping
Demonstrates how to call the shopping API server
"""

import requests
import json
import time

def test_api_server():
    """Test the HTTP API server"""
    
    base_url = "http://localhost:8000"
    
    print("🌐 Testing Browser-Use Shopping API")
    print("=" * 50)
    
    # Test 1: Health check
    print("1. Health Check...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✅ API server is healthy")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API server")
        print("   Make sure the server is running: python3 simple_api_server.py")
        return
    
    # Test 2: Get supported sites
    print("\n2. Getting supported sites...")
    try:
        response = requests.get(f"{base_url}/sites")
        if response.status_code == 200:
            sites = response.json()["sites"]
            print(f"✅ Found {len(sites)} supported sites:")
            for site in sites:
                print(f"   - {site['name']} ({site['site']})")
        else:
            print(f"❌ Failed to get sites: {response.status_code}")
    except Exception as e:
        print(f"❌ Error getting sites: {e}")
    
    # Test 3: Get site info
    print("\n3. Getting site information...")
    try:
        response = requests.get(f"{base_url}/sites/instacart")
        if response.status_code == 200:
            site_info = response.json()
            print(f"✅ Site info for {site_info['name']}:")
            print(f"   URL: {site_info['url']}")
            print(f"   Description: {site_info['description']}")
        else:
            print(f"❌ Failed to get site info: {response.status_code}")
    except Exception as e:
        print(f"❌ Error getting site info: {e}")
    
    # Test 4: Shop for items (if API key is set)
    print("\n4. Testing shopping functionality...")
    shopping_data = {
        "items": ["milk", "eggs"],
        "site": "instacart"
    }
    
    try:
        print(f"   Shopping for: {shopping_data['items']} on {shopping_data['site']}")
        response = requests.post(f"{base_url}/shop", json=shopping_data)
        
        if response.status_code == 200:
            result = response.json()
            if result["success"]:
                print("✅ Shopping successful!")
                print(f"   Site: {result['site']}")
                print(f"   Items found: {result['total_items']}")
                print(f"   Total price: ${result['total_price']:.2f}")
                print("   Items:")
                for item in result["items"]:
                    print(f"     - {item['name']}: ${item['price']:.2f}")
            else:
                print(f"❌ Shopping failed: {result['error']}")
        else:
            print(f"❌ Shopping request failed: {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Error during shopping: {e}")
    
    print("\n🎉 API testing complete!")

if __name__ == "__main__":
    test_api_server()
