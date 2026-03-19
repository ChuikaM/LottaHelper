import requests
import os

class RecaptchaChecker:
    def __init__(self):
        self.json_response = None

    def token_allowed(self, client_token):
        captcha_secret = os.getenv("RECAPTCHA_SECRET_KEY")
        if not captcha_secret:
            json_response = {
                "status": "failed",
                "msg": "Cant't process captcha"
            }
            code = 500
            return False, json_response, code
        url = 'https://www.google.com/recaptcha/api/siteverify'
        payload = {'secret': captcha_secret, 'response': client_token}
        response = requests.post(url, json=payload)
        if (not response) or ('success' not in response):
            json_response = {
                "status": "failed",
                "msg": "Cant't process captcha"
            }
            code = 500
            return False, json_response, code
        success = response['success']
        if not success:
            json_response = {
                "status": "failed",
                "msg": "Cant't process captcha"
            }
            code = 500
            return False, json_response, code
        return True, None, None