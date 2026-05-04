import requests
import os
import logging

class RecaptchaChecker:
    def __init__(self):
        self.json_response = None

    def token_allowed(self, client_token):
        captcha_secret = os.getenv("RECAPTCHA_SECRET_KEY")
        if not captcha_secret:
            return False, {"status": "failed", "msg": "Can't process captcha"}, 500
        
        url = 'https://www.google.com/recaptcha/api/siteverify'
        payload = {'secret': captcha_secret, 'response': client_token}
        try:
            response = requests.post(url, payload)
            if response.status_code != 200:
                return False, {"status": "failed", "msg": "ReCaptcha service error"}, 500
            
            result = response.json()
            if not result.get('success'):
                return False, {"status": "failed", "msg": "Captcha doesn't pass"}, 400
            
            return True, None, None
        
        except Exception as e:
            logging.exception(f"Capthca error: {e}")
            return False, {"status": "failed", "msg": "Internal error"}, 500