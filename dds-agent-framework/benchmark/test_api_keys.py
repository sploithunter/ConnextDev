#!/usr/bin/env python3
"""Test script to verify API keys for Google Gemini and OpenRouter (Grok 3).

This script tests:
1. GOOGLE_API_KEY - for Google Gemini models
2. OPENROUTER_API_KEY - for accessing Grok 3 via OpenRouter
"""

import os
import sys

def test_google_gemini():
    """Test Google Gemini API key."""
    print("=" * 60)
    print("Testing Google Gemini API Key")
    print("=" * 60)
    
    # Check for both GOOGLE_API_KEY and GEMINI_API_KEY
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    key_name = "GOOGLE_API_KEY" if os.environ.get("GOOGLE_API_KEY") else "GEMINI_API_KEY"
    
    if not api_key:
        print("❌ GOOGLE_API_KEY or GEMINI_API_KEY environment variable not set")
        return False
    
    print(f"✓ {key_name} found (length: {len(api_key)})")
    
    try:
        import google.generativeai as genai
    except ImportError:
        print("❌ google.generativeai package not installed")
        print("   Install with: pip install google-generativeai")
        return False
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        print("✓ Attempting to call Gemini API...")
        response = model.generate_content("Say 'Hello' if you can read this.")
        
        if response and response.text:
            print(f"✓ SUCCESS! Response: {response.text[:100]}")
            return True
        else:
            print("❌ API call succeeded but no response text")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        return False


def test_openrouter_grok():
    """Test OpenRouter API key for Grok 3."""
    print("\n" + "=" * 60)
    print("Testing OpenRouter API Key (Grok 3)")
    print("=" * 60)
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ OPENROUTER_API_KEY environment variable not set")
        return False
    
    print(f"✓ OPENROUTER_API_KEY found (length: {len(api_key)})")
    
    try:
        import openai
    except ImportError:
        print("❌ openai package not installed")
        print("   Install with: pip install openai")
        return False
    
    try:
        client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        
        print("✓ Attempting to call OpenRouter API (Grok 3)...")
        response = client.chat.completions.create(
            model="x-ai/grok-3-beta",
            messages=[
                {"role": "user", "content": "Say 'Hello' if you can read this."}
            ],
            max_tokens=50,
        )
        
        if response and response.choices and response.choices[0].message.content:
            reply = response.choices[0].message.content
            print(f"✓ SUCCESS! Response: {reply[:100]}")
            
            # Show token usage if available
            if response.usage:
                print(f"  Token usage: {response.usage.prompt_tokens} input, "
                      f"{response.usage.completion_tokens} output")
            
            return True
        else:
            print("❌ API call succeeded but no response content")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {type(e).__name__}: {e}")
        return False


def main():
    """Run all API key tests."""
    print("\n🔑 API Key Test Script\n")
    
    # Check if keys are set before testing (check both variable names for Gemini)
    gemini_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    
    if not gemini_key and not openrouter_key:
        print("⚠️  No API keys found in environment variables.")
        print("\nTo test, set the environment variables:")
        print("  export GOOGLE_API_KEY='your-key-here'  (or GEMINI_API_KEY)")
        print("  export OPENROUTER_API_KEY='your-key-here'")
        print("\nThen run this script again.")
        return 1
    
    gemini_ok = test_google_gemini() if gemini_key else None
    openrouter_ok = test_openrouter_grok() if openrouter_key else None
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    if gemini_key:
        print(f"Google Gemini:     {'✓ PASS' if gemini_ok else '❌ FAIL'}")
    else:
        print("Google Gemini:     ⚠️  SKIPPED (GOOGLE_API_KEY or GEMINI_API_KEY not set)")
    
    if openrouter_key:
        print(f"OpenRouter (Grok): {'✓ PASS' if openrouter_ok else '❌ FAIL'}")
    else:
        print("OpenRouter (Grok): ⚠️  SKIPPED (OPENROUTER_API_KEY not set)")
    
    if gemini_ok and openrouter_ok:
        print("\n✅ All API keys are working!")
        return 0
    elif gemini_ok is False or openrouter_ok is False:
        print("\n❌ Some API keys failed. Check the errors above.")
        return 1
    else:
        print("\n⚠️  Some API keys were not tested (not set).")
        return 1


if __name__ == "__main__":
    sys.exit(main())

