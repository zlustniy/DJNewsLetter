from djnewsletter.mail import DJNewsLetterEmailMessage


def send_email(**kwargs):
    message = DJNewsLetterEmailMessage(**kwargs)
    message.send()
