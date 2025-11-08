#!/usr/bin/env python3
"""
Debug script to test session-based authentication with Mobile Clinic API
This demonstrates the correct way to maintain session cookies across requests
"""

import requests
import json

# Configuration
BASE_URL = "http://dev2.localhost:8800"
EMAIL = "Administrator"
PASSWORD = "Olapeepi@2468"

def test_authentication_flow():
    """Test complete authentication flow with session management"""
    
    print("=" * 80)
    print("Mobile Clinic API - Session Authentication Test")
    print("=" * 80)
    
    # Create a session object - THIS IS CRITICAL!
    # Session automatically handles cookies across requests
    session = requests.Session()
    
    # Step 1: Login
    print("\n[1] Testing Login...")
    print(f"URL: {BASE_URL}/api/method/mob_clinic.mob_clinic.api.auth.mobile_login")
    print(f"Credentials: {EMAIL}")
    
    login_response = session.post(
        f"{BASE_URL}/api/method/mob_clinic.mob_clinic.api.auth.mobile_login",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        json={
            "usr": EMAIL,
            "pwd": PASSWORD
        }
    )
    
    print(f"Status Code: {login_response.status_code}")
    print(f"Response: {json.dumps(login_response.json(), indent=2)}")
    
    # Check cookies
    print("\n[2] Checking Session Cookies...")
    cookies = session.cookies.get_dict()
    print(f"Cookies received: {json.dumps(cookies, indent=2)}")
    
    if 'sid' in cookies:
        print(f"✅ Session ID (sid): {cookies['sid'][:20]}...")
    else:
        print("❌ No 'sid' cookie found! This is the problem.")
        print("Available cookies:", list(cookies.keys()))
        return
    
    if login_response.status_code != 200:
        print(f"❌ Login failed with status {login_response.status_code}")
        return
    
    print("✅ Login successful!")
    
    # Step 2: Test authenticated request - Get Practitioner Profile
    print("\n[3] Testing Authenticated Request (Get Practitioner Profile)...")
    print(f"URL: {BASE_URL}/api/method/mob_clinic.mob_clinic.api.auth.get_practitioner_profile")
    
    profile_response = session.get(
        f"{BASE_URL}/api/method/mob_clinic.mob_clinic.api.auth.get_practitioner_profile",
        headers={
            "Accept": "application/json"
        }
    )
    
    print(f"Status Code: {profile_response.status_code}")
    
    if profile_response.status_code == 200:
        print(f"✅ Authenticated request successful!")
        print(f"Response: {json.dumps(profile_response.json(), indent=2)}")
    else:
        print(f"❌ Authenticated request failed!")
        print(f"Response: {profile_response.text}")
    
    # Step 3: Test another authenticated request - Get Appointments
    print("\n[4] Testing Another Authenticated Request (Get Appointments)...")
    
    appointments_response = session.get(
        f"{BASE_URL}/api/method/mob_clinic.mob_clinic.api.appointment.get_appointments",
        headers={
            "Accept": "application/json"
        },
        params={
            "limit_page_length": 50,
            "limit_start": 0
        }
    )
    
    print(f"Status Code: {appointments_response.status_code}")
    
    if appointments_response.status_code == 200:
        print(f"✅ Appointment request successful!")
        data = appointments_response.json()
        if 'message' in data and isinstance(data['message'], dict):
            print(f"Total appointments: {data['message'].get('total_count', 0)}")
    else:
        print(f"❌ Appointment request failed!")
        print(f"Response: {appointments_response.text[:500]}")
    
    # Step 4: Test Get Patients
    print("\n[5] Testing Get Patients...")
    
    patients_response = session.get(
        f"{BASE_URL}/api/method/mob_clinic.mob_clinic.api.patient.get_patients",
        headers={
            "Accept": "application/json"
        },
        params={
            "limit_page_length": 10,
            "limit_start": 0
        }
    )
    
    print(f"Status Code: {patients_response.status_code}")
    
    if patients_response.status_code == 200:
        print(f"✅ Patient request successful!")
        data = patients_response.json()
        if 'message' in data and isinstance(data['message'], dict):
            print(f"Total patients: {data['message'].get('total_count', 0)}")
    else:
        print(f"❌ Patient request failed!")
        print(f"Response: {patients_response.text[:500]}")
    
    # Step 5: Logout
    print("\n[6] Testing Logout...")
    
    logout_response = session.post(
        f"{BASE_URL}/api/method/mob_clinic.mob_clinic.api.auth.mobile_logout",
        headers={
            "Accept": "application/json"
        }
    )
    
    print(f"Status Code: {logout_response.status_code}")
    if logout_response.status_code == 200:
        print(f"✅ Logout successful!")
    else:
        print(f"❌ Logout failed!")
    
    print("\n" + "=" * 80)
    print("Test Complete!")
    print("=" * 80)


def test_without_session():
    """Test WITHOUT session management to show the problem"""
    
    print("\n\n" + "=" * 80)
    print("DEMONSTRATION: What happens WITHOUT session management")
    print("=" * 80)
    
    print("\n[1] Login (without session)...")
    login_response = requests.post(
        f"{BASE_URL}/api/method/mob_clinic.mob_clinic.api.auth.mobile_login",
        headers={"Content-Type": "application/json"},
        json={"usr": EMAIL, "pwd": PASSWORD}
    )
    
    print(f"Status Code: {login_response.status_code}")
    print(f"✅ Login successful!")
    
    print("\n[2] Try authenticated request (without cookies)...")
    profile_response = requests.get(
        f"{BASE_URL}/api/method/mob_clinic.mob_clinic.api.auth.get_practitioner_profile"
    )
    
    print(f"Status Code: {profile_response.status_code}")
    if profile_response.status_code == 403:
        print(f"❌ Request failed - No session cookie sent!")
        print("This is exactly what your frontend is experiencing!")
    
    print("\n" + "=" * 80)


def test_manual_cookie():
    """Test by manually extracting and sending cookie"""
    
    print("\n\n" + "=" * 80)
    print("DEMONSTRATION: Manual cookie management")
    print("=" * 80)
    
    print("\n[1] Login and extract cookie...")
    login_response = requests.post(
        f"{BASE_URL}/api/method/mob_clinic.mob_clinic.api.auth.mobile_login",
        headers={"Content-Type": "application/json"},
        json={"usr": EMAIL, "pwd": PASSWORD}
    )
    
    # Extract sid cookie
    sid_cookie = login_response.cookies.get('sid')
    print(f"Extracted sid cookie: {sid_cookie[:20] if sid_cookie else 'None'}...")
    
    if not sid_cookie:
        print("❌ No sid cookie in response!")
        return
    
    print("\n[2] Make authenticated request with manual cookie...")
    profile_response = requests.get(
        f"{BASE_URL}/api/method/mob_clinic.mob_clinic.api.auth.get_practitioner_profile",
        cookies={'sid': sid_cookie}
    )
    
    print(f"Status Code: {profile_response.status_code}")
    if profile_response.status_code == 200:
        print(f"✅ Request successful with manual cookie!")
    else:
        print(f"❌ Request failed even with manual cookie!")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        # Run the correct flow
        test_authentication_flow()
        
        # Demonstrate the problem
        test_without_session()
        
        # Show manual cookie management
        test_manual_cookie()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
