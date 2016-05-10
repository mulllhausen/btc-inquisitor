"""module containing some general email-related functions"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import socket
import sys

standard_error_subject = "%s error on %s" % (sys.argv[0], socket.gethostname())

def send(subject, html):
    from_address = "user@localhost"
    to_address = "me@email.com"

    # create message container - the correct MIME type is multipart/alternative.
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_address
    msg['To'] = to_address
    msg.attach(MIMEText(html, 'html'))

    # send the message via local SMTP server.
    s = smtplib.SMTP('localhost')
    s.sendmail(from_address, to_address, msg.as_string())
    s.quit()
