from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import os
import re
from database.operations import save_form_data, phone_occurrence_count, resend_gift_code_sms
from database.connection import init_database_tables
import random
import string
from threading import Thread 
import requests
'''import webbrowser
import threading
import time'''
from database.connection import init_connection
from database.sms_utils import send_gift_code_sms  # Adjust the path as needed
from dotenv import load_dotenv
load_dotenv()
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Testing DB connection...")

print("Testing DB connection...")
engine = init_connection()
print("Engine:", engine)
app = Flask(__name__)
#app.secret_key = os.urandom(24)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
# Required for session management

# SMS Service Credentials
'''SMS_API_URL = os.environ.get("SMS_API_URL")
SMS_USERNAME = os.environ.get("SMS_USERNAME")
SMS_PASSWORD = os.environ.get("SMS_PASSWORD")
SMS_SENDER = os.environ.get("SMS_SENDER")'''

# Initialize database tables
init_database_tables()

'''def open_browser():
    time.sleep(1)  # Wait a moment for the server to start
    webbrowser.open_new('http://127.0.0.1:5000/')'''
# Utility functions
def background_save_and_sms(form_data_copy):
    try:
        save_form_data(form_data_copy)
    except Exception as e:
        print("Error in background task:", e)

def generate_otp():
    """Generate a 6-digit OTP code"""
    return ''.join(random.choices(string.digits, k=6))

def send_sms_otp(phone_number, otp_code):
    """Send OTP via SMS using the specified API"""
    print(f"[DEBUG] OTP for {phone_number}: {otp_code}")
    ''' message = f"Your Ajmal Feedback Form verification code is: {otp_code}"
    url = f"{SMS_API_URL}/SendSMS/SingleSMS/?Username={SMS_USERNAME}&Password={SMS_PASSWORD}"
    payload = {
        "Message": message,
        "MobileNumbers": phone_number,
        "SenderName": SMS_SENDER
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending SMS: {str(e)}")
        return False'''
    return True
def format_uae_number(phone_number):
    """Validate and format UAE phone number"""
    phone_number = ''.join(c for c in phone_number if c.isdigit() or c == '+')
    if phone_number.startswith('+971'):
        return phone_number
    if phone_number.startswith('0'):
        return '+971' + phone_number[1:]
    if phone_number.startswith('971'):
        return '+' + phone_number
    if len(phone_number) == 9 and phone_number.startswith(('50', '54', '55', '56', '58')):
        return '+971' + phone_number
    return None

def handle_store_id(store_id):
    """
    Common handler to validate and set store_id in session.
    """
    # Optional: Validate UUID format
    if store_id and re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', store_id, re.IGNORECASE):
        session['store_id'] = store_id
        session['store_url_id'] = store_id
    else:
        session.pop('store_id', None)
        session.pop('store_url_id', None)

    # Initialize session keys if not already set
    session.setdefault('form_data', {})
    session.setdefault('otp_verified', False)

    return redirect(url_for('language_selection'))
# Routes
# Routes

@app.route('/')
def home():
    store_id = request.args.get('store_id')
    return handle_store_id(store_id)



'''@app.route('/<store_url_id>')
def index(store_url_id):
    # Try to extract UUID from the path
    match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$', store_url_id, re.IGNORECASE)
    store_id = match.group(1) if match else None
    return handle_store_id(store_id)'''

@app.route('/language', methods=['GET', 'POST'])
def language_selection():
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)# logging in ip address
    logger.info(f"User IP: {user_ip}")
    if request.method == 'POST':
        selected_language = request.form.get('language')
        session['language'] = selected_language
        session.setdefault('form_data', {})
        session['form_data']['language'] = selected_language
        session['page'] = 2
        return redirect(url_for('intro'))  # Now goes to gift info page
    return render_template('language.html')


@app.route('/intro')
def intro():
    # Show thank you and gift info, and ask for mobile number if needed
    return render_template('intro.html')


@app.route('/start_survey', methods=['POST'])
def start_survey():
    # Begin the actual survey here
    return redirect(url_for('first_visit'))


@app.route('/first-visit', methods=['GET', 'POST'])
def first_visit():
    form_data = session.get('form_data', {})
    visited_pages = session.get('visited_pages', {})

    if request.method == 'POST':
        form_data['first_visit'] = request.form.get('first_visit')
        visited_pages['first_visit'] = True

        # Explicitly assign the entire objects back to session
        session['form_data'] = form_data
        session['visited_pages'] = visited_pages
        session.modified = True

        return redirect(url_for('satisfaction'))
    
    previous_first_visit = session.get('form_data', {}).get('first_visit', '')
    return render_template('first_visit.html', previous_first_visit=previous_first_visit)

    ''' 'first_visit.html',
        previous_first_visit=session['form_data'].get('first_visit', ''),
        visited_first_visit_page=session['visited_pages'].get('first_visit', False)
    )'''


@app.route('/satisfaction', methods=['GET', 'POST'])
def satisfaction():
    session.setdefault('form_data', {})
    session.setdefault('visited_pages', {})

    if request.method == 'POST':
        session['form_data']['satisfaction'] = request.form.get('satisfaction')
        session['visited_pages']['satisfaction'] = True
        session.modified = True
        return redirect(url_for('satisfaction_reason'))

    return render_template(
        'satisfaction.html',
        previous_satisfaction=session['form_data'].get('satisfaction', ''),
        visited_satisfaction_page=session['visited_pages'].get('satisfaction', False)
    )


@app.route("/satisfaction_reason", methods=["GET", "POST"])
def satisfaction_reason():
    if request.method == "POST":
        session.setdefault('form_data', {})

        satisfaction = session['form_data'].get('satisfaction')

        # If the user is dissatisfied
        if satisfaction == "No":
            reason = request.form.get("dissatisfaction_reason", "").strip().lower()
            reason_text = request.form.get("dissatisfaction_reason_text", "").strip()

            session['form_data']['dissatisfaction_reason'] = reason
            session['form_data']['dissatisfaction_reason_text'] = reason_text
            session.modified = True

            # Redirect based on dissatisfaction reason
            if reason == "product":
                return redirect(url_for("product_feedback"))
            elif reason == "staff":
                return redirect(url_for("staff_feedback"))
            elif reason == "ambience":
                return redirect(url_for("ambience_feedback"))
            else:
                return redirect(url_for("additional_feedback"))

        # If the user is satisfied
        else:
            satisfaction_reason = request.form.get("satisfaction_reason", "").strip()
            session['form_data']['satisfaction_reason'] = satisfaction_reason
            session.modified = True

            print("Satisfaction-related data being saved:", session['form_data'])
            return redirect(url_for('additional_feedback'))

    # For GET requests - retrieve saved values if any
    form_data = session.get('form_data', {})
    visited = session['visited_pages'].get('satisfaction_reason', False)
    return render_template(
        "satisfaction_reason.html",
        satisfaction=form_data.get('satisfaction', ''),
        dissatisfaction_reason=form_data.get('dissatisfaction_reason', ''),
        dissatisfaction_reason_text=form_data.get('dissatisfaction_reason_text', ''),
        satisfaction_reason=form_data.get('satisfaction_reason', ''),
        visited_satisfaction_reason_page=visited
    )


@app.route("/product_feedback", methods=["GET", "POST"])
def product_feedback():
    if request.method == "POST":
        session.setdefault('form_data', {})
        # Get the selected reason and add it to the combined feedback reasons
        selected_reason = request.form.get("dissatisfaction_feedback_reason")
        if selected_reason:
            if 'dissatisfaction_feedback_reason' not in session['form_data']:
                session['form_data']['dissatisfaction_feedback_reason'] = []
            if selected_reason not in session['form_data']['dissatisfaction_feedback_reason']:
                session['form_data']['dissatisfaction_feedback_reason'].append(selected_reason)
        session.modified = True
        print("Saved product reasons:", session['form_data'])
        return redirect(url_for("additional_feedback"))
    
    language = session.get('form_data', {}).get('language', 'English')
    dissatisfaction_feedback_reason = session.get('form_data', {}).get('dissatisfaction_feedback_reason', [])
    print(session['form_data'])
    return render_template("product_feedback.html", language=language, dissatisfaction_feedback_reason=dissatisfaction_feedback_reason)



@app.route("/staff_feedback", methods=["GET", "POST"])
def staff_feedback():
    session.setdefault('form_data', {})

    if request.method == "POST":
        # Get selected reason and add it to the combined feedback reasons
        selected_reason = request.form.get("dissatisfaction_feedback_reason")
        if selected_reason:
            if 'dissatisfaction_feedback_reason' not in session['form_data']:
                session['form_data']['dissatisfaction_feedback_reason'] = []
            if selected_reason not in session['form_data']['dissatisfaction_feedback_reason']:
                session['form_data']['dissatisfaction_feedback_reason'].append(selected_reason)
        session.modified = True

        print("Saved staff reasons:", session['form_data'])
        return redirect(url_for("additional_feedback"))

    # GET request - load existing values
    language = session['form_data'].get('language', 'English')
    dissatisfaction_feedback_reason = session.get('form_data', {}).get('dissatisfaction_feedback_reason', [])

    print("Staff feedback form loaded with data:", session['form_data'])
    return render_template("staff_feedback.html", language=language, dissatisfaction_feedback_reason=dissatisfaction_feedback_reason)

@app.route("/ambience_feedback", methods=["GET", "POST"])
def ambience_feedback():
    session.setdefault('form_data', {})

    if request.method == "POST":
        # Get selected reason and add it to the combined feedback reasons
        selected_reason = request.form.get("dissatisfaction_feedback_reason")
        if selected_reason:
            if 'dissatisfaction_feedback_reason' not in session['form_data']:
                session['form_data']['dissatisfaction_feedback_reason'] = []
            if selected_reason not in session['form_data']['dissatisfaction_feedback_reason']:
                session['form_data']['dissatisfaction_feedback_reason'].append(selected_reason)
        session.modified = True

        print("Saved ambience reasons:", session['form_data'])
        return redirect(url_for("additional_feedback"))

    # GET request - load existing values
    language = session['form_data'].get('language', 'English')
    dissatisfaction_feedback_reason = session.get('form_data', {}).get('dissatisfaction_feedback_reason', [])

    print("Ambience feedback form loaded with data:", session['form_data'])
    return render_template("ambience_feedback.html", language=language, dissatisfaction_feedback_reason=dissatisfaction_feedback_reason)


@app.route("/additional_feedback", methods=["GET", "POST"])
def additional_feedback():
    session.setdefault('form_data', {})

    if request.method == "POST":
        # Save additional feedback
        session['form_data']['additional_feedback'] = request.form.get("additional_feedback")
        session.modified = True

        print("Saved additional feedback:", session['form_data'])
        return redirect(url_for("nps"))  # ✅ Redirect to NPS page

    # GET request - retrieve existing feedback if any
    existing_feedback = session['form_data'].get('additional_feedback', '')

    print("Form data at additional_feedback:", session['form_data'])
    return render_template("additional_feedback.html", existing_feedback=existing_feedback)

@app.route('/nps', methods=['GET', 'POST'])
def nps():
    session.setdefault('form_data', {})

    if request.method == 'POST':
        # Save NPS score
        session['form_data']['nps'] = request.form.get('nps')
        session['returning'] = True  # Mark user as returning
        session['page'] = 7
        session.modified = True

        print("NPS data saved:", session['form_data'])
        return redirect(url_for('contact_info'))

    # Pre-fill previous NPS score if user is returning
    previous_nps = session['form_data'].get('nps', '') if session.get('returning') else ''

    print("Form data at NPS:", session['form_data'])
    return render_template('nps.html', previous_nps=previous_nps)


@app.route('/contact', methods=['GET', 'POST'])
def contact_info():
    if request.method == 'POST':
        # Save contact info to session
        session['form_data']['name'] = request.form.get('name')
        session['form_data']['email'] = request.form.get('email')

        # Just get store_id if available — doesn't affect the flow
        store_id = session.get('store_id')
        session['form_data']['store_id'] = store_id  # Optional: attach to form_data

        # Proceed if form data exists (no dependency on store_id)
        if session['form_data']:
            session['submitted'] = True
            return redirect(url_for('verify_phone'))
        else:
            flash('Failed to save your feedback. Please try again.', 'error')
            return redirect(url_for('contact'))
    print("Final form data being saved:", session.get("form_data"))
    return render_template('contact.html')


@app.route('/thank-you', methods=['GET'])
def thank_you():
    store_id = session.get('store_id')
    form_data = session.get('form_data', {})
    if not store_id:
        store_id = request.args.get('store_id')
    if form_data:
        phone = form_data.get('phone')
        
        if not phone:
            flash("Phone number is missing.", "error")
            return redirect(url_for('verify_phone'))

        # Check if this is the first time this phone number is being used
        phone_count = phone_occurrence_count(phone)
        is_first_time = phone_count == 0  # It's first time if count is 0 (before saving)
        
        # First render the thank you page with appropriate message
        template_data = {
            "gift_code": None,
            "is_first_time": is_first_time,
            "sms_message": "Your response has been submitted successfully!"
        }

        # Then handle the background operations
        if store_id:
            form_data['store_id'] = store_id

        # Run background thread for saving + SMS
        form_data_copy = form_data.copy()  # Copy session data for thread
        Thread(target=background_save_and_sms, args=(form_data_copy,)).start()

        return render_template("thank_you.html", **template_data)

    session.clear()
    return redirect('/')

@app.route('/verify-phone', methods=['GET', 'POST'])
def verify_phone():
    if request.method == 'POST':
        phone = request.form.get('phone')
        formatted_phone = format_uae_number(phone)
        if formatted_phone:
            otp = generate_otp()
            session['otp_code'] = otp
            if 'form_data' not in session:
                session['form_data'] = {}
            session['form_data']['phone'] = formatted_phone
            if send_sms_otp(formatted_phone, otp):
                session['otp_sent'] = True
                return redirect(url_for('enter_otp'))
            else:
                flash('Failed to send OTP. Please try again.', 'error')
        else:
            flash('Invalid phone number format. Please enter a valid UAE number.', 'error')
    return render_template('verify_phone.html')

@app.route('/enter-otp', methods=['GET', 'POST'])
def enter_otp():
    if request.method == 'POST':
        if request.form.get('otp') == session.get('otp_code'):
            session['otp_verified'] = True
            return redirect(url_for('thank_you'))
        else:
            flash('Invalid OTP. Please try again.', 'error')

    # 👇 Pass OTP to template ONLY FOR TESTING
    otp_code = session.get('otp_code')  # get current OTP from session
    DEBUG_MODE = True  # in config
    return render_template('enter_otp.html', otp=otp_code if DEBUG_MODE else None)


@app.route('/start-over')
def start_over():
    session.clear()
    return redirect(url_for('language_selection'))  # or your actual starting route

@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    phone = session.get('form_data', {}).get('phone')
    if phone:
        otp = generate_otp()
        session['otp_code'] = otp
        
        otp_sent = send_sms_otp(phone, otp)
        gift_code_sent, gift_code_msg = resend_gift_code_sms(phone)

        if otp_sent or gift_code_sent:
            session['otp_sent'] = True
            flash('OTP has been resent to your phone.', 'info')
        else:
            flash('Failed to resend OTP or gift code. Please try again.', 'error')
    else:
        flash('Phone number missing. Please go back and enter your phone number.', 'error')
        return redirect(url_for('verify_phone'))

    return redirect(url_for('enter_otp'))




if __name__ == '__main__':
    #threading.Thread(target=open_browser).start()
    app.run(debug=True)
   
