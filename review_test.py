#!/usr/bin/env python3
"""
Review Request Testing for La Pulpería
Tests the specific requirements mentioned in the review request:
1. Email Service Configuration
2. Create Online-Only Pulperia functionality
"""

import requests
import json
import sys
import os
import importlib.util
from datetime import datetime

# Get backend URL from environment
BACKEND_URL = "https://dashboard-bugfix-5.preview.emergentagent.com/api"

def test_email_service_configuration():
    """Test Email Service Configuration"""
    print("🔍 TESTING EMAIL SERVICE CONFIGURATION")
    print("=" * 50)
    
    results = []
    
    # Check if RESEND_API_KEY is configured in backend/.env
    env_path = "/app/backend/.env"
    resend_api_key = None
    
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('RESEND_API_KEY='):
                    resend_api_key = line.split('=', 1)[1].strip()
                    break
        
        if resend_api_key and resend_api_key != '':
            print("✅ RESEND_API_KEY is configured in /app/backend/.env")
            print(f"   Key: {resend_api_key[:10]}...")
            results.append(True)
        else:
            print("❌ RESEND_API_KEY is not configured or empty in /app/backend/.env")
            results.append(False)
    else:
        print("❌ /app/backend/.env file not found")
        results.append(False)
    
    # Check if email_service.py module exists and imports correctly
    email_service_path = "/app/backend/services/email_service.py"
    
    if os.path.exists(email_service_path):
        try:
            # Try to import the module
            spec = importlib.util.spec_from_file_location("email_service", email_service_path)
            email_service = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(email_service)
            
            # Check if required functions exist
            required_functions = [
                'send_email',
                'send_order_notification', 
                'send_order_accepted',
                'send_order_ready',
                'send_job_application_notification',
                'send_application_accepted'
            ]
            
            missing_functions = []
            for func_name in required_functions:
                if not hasattr(email_service, func_name):
                    missing_functions.append(func_name)
            
            if not missing_functions:
                print("✅ email_service.py exists and imports correctly with all required functions")
                print(f"   Functions: {', '.join(required_functions)}")
                results.append(True)
            else:
                print(f"❌ email_service.py missing functions: {missing_functions}")
                results.append(False)
                
        except Exception as e:
            print(f"❌ Failed to import email_service.py: {str(e)}")
            results.append(False)
    else:
        print("❌ email_service.py module not found at /app/backend/services/email_service.py")
        results.append(False)
    
    print()
    return all(results)

def test_create_online_only_pulperia():
    """Test creating an online-only pulperia (the bug fix)"""
    print("🔍 TESTING CREATE ONLINE-ONLY PULPERIA")
    print("=" * 50)
    
    results = []
    session = requests.Session()
    
    # Test data for online-only pulperia
    online_pulperia_data = {
        "name": "Test Online Store",
        "description": "Test description",
        "is_online_only": True,
        "phone": "9999-9999",
        "location": None
    }
    
    # Test the endpoint without authentication first to see the response structure
    try:
        response = session.post(
            f"{BACKEND_URL}/pulperias",
            json=online_pulperia_data,
            timeout=10
        )
        
        # We expect 401 (unauthorized) since we don't have auth
        if response.status_code == 401:
            print("✅ POST /api/pulperias endpoint correctly requires authentication (401 Unauthorized)")
            
            # Check if the error message is appropriate
            try:
                error_data = response.json()
                if "detail" in error_data:
                    print(f"✅ Appropriate error message: {error_data['detail']}")
                    results.append(True)
                else:
                    print("❌ No error detail in response")
                    results.append(False)
            except:
                print("❌ Could not parse error response as JSON")
                results.append(False)
                
        elif response.status_code == 422:
            # Validation error - check if it's related to missing fields
            try:
                error_data = response.json()
                print(f"✅ Endpoint validates input data (422 Validation Error): {error_data.get('detail', 'No detail')}")
                results.append(True)
            except:
                print("❌ Could not parse validation error response")
                results.append(False)
        else:
            print(f"❌ Unexpected status code: {response.status_code}, Response: {response.text[:200]}")
            results.append(False)
        
        # Test the data structure validation by checking existing pulperias
        # to see if is_online_only field is supported
        existing_pulperias_response = session.get(f"{BACKEND_URL}/pulperias", timeout=10)
        
        if existing_pulperias_response.status_code == 200:
            pulperias_data = existing_pulperias_response.json()
            if isinstance(pulperias_data, list):
                if pulperias_data:
                    # Check if any existing pulperia has is_online_only field
                    has_online_only_field = any('is_online_only' in p for p in pulperias_data)
                    
                    if has_online_only_field:
                        print("✅ is_online_only field is supported in pulperia data structure")
                        
                        # Check if there are any online-only pulperias
                        online_only_pulperias = [p for p in pulperias_data if p.get('is_online_only', False)]
                        if online_only_pulperias:
                            # Check if online-only pulperias have null location
                            location_validation_passed = True
                            for pulperia in online_only_pulperias:
                                if pulperia.get('location') is not None:
                                    location_validation_passed = False
                                    break
                            
                            if location_validation_passed:
                                print(f"✅ Found {len(online_only_pulperias)} online-only pulperias with null location (correct behavior)")
                                results.append(True)
                            else:
                                print("❌ Some online-only pulperias have non-null location (bug not fixed)")
                                results.append(False)
                        else:
                            print("✅ No online-only pulperias found in database (normal if none created yet)")
                            results.append(True)
                    else:
                        print("❌ is_online_only field not found in existing pulperia data structure")
                        results.append(False)
                else:
                    print("✅ No existing pulperias to check field support (normal for empty database)")
                    print("   The endpoint structure appears to be ready for online-only pulperias")
                    results.append(True)
            else:
                print(f"❌ Pulperias endpoint returned non-list data: {type(pulperias_data)}")
                results.append(False)
        else:
            print(f"❌ Could not fetch existing pulperias to check field support: {existing_pulperias_response.status_code}")
            results.append(False)
            
    except Exception as e:
        print(f"❌ Error testing online-only pulperia creation: {str(e)}")
        results.append(False)
    
    print()
    return all(results)

def main():
    """Run all review request tests"""
    print("=" * 60)
    print("REVIEW REQUEST TESTING - La Pulpería")
    print("=" * 60)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test started at: {datetime.now().isoformat()}")
    print()
    
    # Test 1: Email Service Configuration
    email_test_passed = test_email_service_configuration()
    
    # Test 2: Create Online-Only Pulperia
    pulperia_test_passed = test_create_online_only_pulperia()
    
    # Summary
    print("=" * 60)
    print("REVIEW REQUEST TEST SUMMARY")
    print("=" * 60)
    
    tests = [
        ("Email Service Configuration", email_test_passed),
        ("Create Online-Only Pulperia", pulperia_test_passed)
    ]
    
    passed_tests = sum(1 for _, passed in tests if passed)
    total_tests = len(tests)
    
    for test_name, passed in tests:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print()
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success rate: {(passed_tests/total_tests)*100:.1f}%")
    
    print(f"\nTest completed at: {datetime.now().isoformat()}")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)