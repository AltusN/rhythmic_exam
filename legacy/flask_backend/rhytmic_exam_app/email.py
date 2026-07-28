from threading import Thread
from smtplib import SMTPException
from time import sleep

from flask import render_template, current_app
from flask_mail import Message

from rhytmic_exam_app import mail

#The email stuff shoul be put in a queue and managed that way
 
def send_async_email(app, msg):
    error = False
    with app.app_context():
        try:
            with mail.connect():
                mail.send(msg)
                current_app.logger.info('Mail sent')
        except SMTPException as smtpe:
            current_app.logger.warning("Unable to send email")
            current_app.logger.error(smtpe)
            error = True
        except Exception as e:
            current_app.logger.error(e)
            error = True

    #Try again if there was an error
    if error:
        sleep(10)
        with app.app_context():
            try:
                with mail.connect():
                    mail.send(msg)
            except SMTPException as smtpe:
                current_app.logger.warning("Tried sending again and failed")
                current_app.logger.error(smtpe)
            except Exception as e:
                current_app.logger.error(e)

    

def send_email(subject, sender, recipients, text_body, html_body):
    msg = Message(subject=subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body

    Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start() 