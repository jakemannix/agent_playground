#!/usr/bin/env python3
"""
Quick test to see if OpenAI Responses API handles empty tools arrays gracefully.
"""

import os
import httpx
import json

async def test_empty_tools():
    """Test if empty tools array breaks the API."""
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        return
    
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Test 1: No tools field
    payload_no_tools = {
        "model": "gpt-4o-mini",
        "input": "Say hello",
        "store": False
    }
    
    # Test 2: Empty tools array
    payload_empty_tools = {
        "model": "gpt-4o-mini", 
        "input": "Say hello",
        "tools": [],
        "store": False
    }
    
    async with httpx.AsyncClient() as client:
        try:
            print("🧪 Testing no tools field...")
            response1 = await client.post(
                "https://api.openai.com/v1/responses",
                json=payload_no_tools,
                headers=headers,
                timeout=30.0
            )
            print(f"✅ No tools: {response1.status_code}")
            
            print("🧪 Testing empty tools array...")
            response2 = await client.post(
                "https://api.openai.com/v1/responses", 
                json=payload_empty_tools,
                headers=headers,
                timeout=30.0
            )
            print(f"✅ Empty tools: {response2.status_code}")
            
            if response2.status_code == 200:
                print("🎉 Empty tools array works fine!")
                print("💡 The `if tools:` check is defensive but not strictly necessary")
            else:
                print("❌ Empty tools array causes issues:")
                print(response2.text)
                print("💡 The `if tools:` check is actually needed!")
                
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_empty_tools()) 