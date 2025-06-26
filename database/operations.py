from datetime import datetime
import traceback
from database.connection import get_db_session
from database.models import Feedback, GiftCode, Store
from database.sms_utils import send_gift_code_sms


def phone_occurrence_count(phone_number):
    """Return how many times a phone number appears in the Feedback table."""
    try:
        session = get_db_session()
        if not session:
            return 0
        count = session.query(Feedback).filter(Feedback.phone == phone_number).count()
        session.close()

        return count
    except Exception as e:
        print(f"[ERROR] Failed to check phone count: {str(e)}")
        print(traceback.format_exc())
        return 0


def save_form_data(form_data):
    """Save feedback form data, assign gift code on first submission, send SMS."""
    try:
        session = get_db_session()
        if not session:
            print("No database session available")
            return False, None, False, "DB connection error"

        phone_number = form_data.get('phone', '').strip()
        if not phone_number:
            return False, None, False, "Missing phone number"

        store_id = (form_data.get('store_id') or '').strip()
        '''if not store_id:
            return False, None, False, "Missing store ID"'''

        # Ensure store exists
        store = None
        if store_id:
            store = session.query(Store).filter_by(store_id=store_id).first()
            if not store:
                generated_link = f"https://yourdomain.com/store/{store_id}"
                store = Store(store_id=store_id, link=generated_link)
                session.add(store)
                session.commit()
                print(f"[INFO] Created new store with ID {store_id}")

        occurrence_count = phone_occurrence_count(phone_number)
        is_first_time = occurrence_count == 0

        # Handle dissatisfaction reason (list or string)
        dissatisfaction_reason = form_data.get('dissatisfaction_reason', '')
        if isinstance(dissatisfaction_reason, list):
            dissatisfaction_reason = ', '.join(dissatisfaction_reason)

        # Get the combined feedback reasons
        dissatisfaction_feedback_reason = form_data.get('dissatisfaction_feedback_reason', [])
        if isinstance(dissatisfaction_feedback_reason, str):
            dissatisfaction_feedback_reason = [dissatisfaction_feedback_reason]

        feedback_record = Feedback(
            timestamp=datetime.now(),
            name=form_data.get('name', ''),
            email=form_data.get('email', ''),
            phone=phone_number,
            language=form_data.get('language', ''),
            nps=int(form_data['nps']) if form_data.get('nps') else None,
            first_visit=form_data.get('first_visit', ''),
            satisfaction=form_data.get('satisfaction', ''),
            satisfaction_reason=form_data.get('satisfaction_reason', ''),
            dissatisfaction_reason=dissatisfaction_reason,
            dissatisfaction_feedback_reason=dissatisfaction_feedback_reason,
            feedback=form_data.get('additional_feedback', ''),
            branch=form_data.get('branch', ''),
            store_id=store_id
        )
        session.add(feedback_record)
        session.flush()
        
        gift_code_value = None
        message = ""

        if is_first_time:
            gift_code = session.query(GiftCode).filter(
                GiftCode.isdelete.is_(False),
                GiftCode.isvalid.is_(False),
                GiftCode.issent.is_(False),
                GiftCode.smsstatus.is_(False)
            ).first()

            if gift_code:
                gift_code_value = gift_code.code
                success, message = send_gift_code_sms(phone_number, gift_code_value)

                if success:
                    gift_code.isdelete = True
                    gift_code.isvalid = True
                    gift_code.issent = True
                    gift_code.smsstatus = True
                    gift_code.timestamp_ = datetime.now()
                    gift_code.store_id = store_id
                else:
                    print(f"[SMS ERROR] {message}")
                    gift_code_value = None
            else:
                message = "No available gift codes"

        session.commit()
        session.close()

        return True, gift_code_value, is_first_time, message

    except Exception as e:
        print(f"[ERROR] save_form_data failed: {str(e)}")
        print(traceback.format_exc())
        return False, None, False, "Error saving form data"


def resend_gift_code_sms(phone_number):
    """Resend the previously sent gift code via SMS if already assigned, else assign and send a new one."""
    try:
        session = get_db_session()
        if not session:
            return False, "DB connection error"

        phone_number = phone_number.strip()
        if not phone_number:
            return False, "Missing phone number"

        # Check if feedback entry exists
        feedback = session.query(Feedback).filter_by(phone=phone_number).order_by(Feedback.timestamp.desc()).first()
        if not feedback:
            session.close()
            return False, "No feedback found for this number"

        # Check if gift code already assigned to this phone
        gift_code = session.query(GiftCode).filter_by(
            store_id=feedback.store_id,
            isdelete=True,
            isvalid=True,
            issent=True,
            smsstatus=True
        ).order_by(GiftCode.timestamp_.desc()).first()

        if gift_code:
            # Resend existing gift code
            success, message = send_gift_code_sms(phone_number, gift_code.code)
            session.close()
            return success, message
        else:
            # Assign a new gift code
            new_code = session.query(GiftCode).filter(
                GiftCode.isdelete.is_(False),
                GiftCode.isvalid.is_(False),
                GiftCode.issent.is_(False),
                GiftCode.smsstatus.is_(False)
            ).first()

            if not new_code:
                session.close()
                return False, "No available gift codes"

            success, message = send_gift_code_sms(phone_number, new_code.code)

            if success:
                new_code.isdelete = True
                new_code.isvalid = True
                new_code.issent = True
                new_code.smsstatus = True
                new_code.timestamp_ = datetime.now()
                new_code.store_id = feedback.store_id
                session.commit()

                session.close()
                return True, "Gift code resent successfully"
            else:
                session.close()
                return False, f"SMS sending failed: {message}"

    except Exception as e:
        print(f"[ERROR] resend_gift_code_sms failed: {str(e)}")
        print(traceback.format_exc())
        return False, "Internal error while resending gift code"
