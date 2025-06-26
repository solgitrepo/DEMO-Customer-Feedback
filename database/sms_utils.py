import requests
from flask import request
import json
from flask import session
import os
import re
from dotenv import load_dotenv
load_dotenv()
SMS_API_URL = os.environ.get("SMS_API_URL")
SMS_USERNAME = os.environ.get("SMS_USERNAME")
SMS_PASSWORD = os.environ.get("SMS_PASSWORD")
SMS_SENDER = os.environ.get("SMS_SENDER")
def send_gift_code_sms(phone_number, gift_code):
    """Send gift code via SMS using the specified API"""
    if not all([SMS_API_URL, SMS_USERNAME, SMS_PASSWORD, SMS_SENDER]):
            raise RuntimeError("One or more SMS credentials are missing from environment variables.")
    
    """
    Sends the gift code via SMS using the configured SMS API.

    Args:
        phone_number (str): The UAE-formatted recipient phone number.
        gift_code (str): The gift code to be sent.

    Returns:
        tuple: (success (bool), message (str)) – Whether sending was successful and the message to show.
    """
    message = f"Thanks for your feedback! Here's your gift code: {gift_code}. Redeem in-store. Click on below link to check nearby stores https://www.myajmal.com/StoreList. Enjoy! 🎉"
    url = f"{SMS_API_URL}/SendSMS/SingleSMS/?Username={SMS_USERNAME}&Password={SMS_PASSWORD}"
    

    payload = {
        "Message": message,
        "MobileNumbers": phone_number,
        "SenderName": SMS_SENDER
    }
    # Add this near the top of sms_utils.py
    DEBUG_MODE = True  # or False depending on what you want

    try:
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)  # <-- get client IP

        if DEBUG_MODE:
            print(f"[DEBUG] SMS request made by client IP: {client_ip}")
        # Avoid sending SMS in test mode (use session or env flag)
        if 'test_mode' in session and session['test_mode']:
            if DEBUG_MODE:
                print("[DEBUG] Test mode enabled. Skipping actual SMS sending.")
            return True, "Gift code generated (test mode)!"

        response = requests.post(url, data=payload, timeout=10)
        

        if DEBUG_MODE:
            print(f"[DEBUG] Gift code SMS API response: {response.status_code}, Body: {response.text}")

        if response.status_code == 200:
            return True, "Gift code sent successfully!"
        else:
            return False, "We've generated your gift code! (SMS not sent)"
    except Exception as e:
        if DEBUG_MODE:
            print(f"[DEBUG] Exception while sending gift code SMS: {str(e)}")
        return False, "We've generated your gift code! (SMS exception)"