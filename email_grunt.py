"""module containing some general email-related functions"""

import smtplib, socket, sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import config_grunt

standard_error_subject = "%s error on %s" % (
    sys.argv[0], config_grunt.config_dict["unique_host_id"]
)
email_config_dict = config_grunt.config_dict["notifications_email"]

def send(html, subject = None):
    from_address = email_config_dict["from"]
    to_adderss = email_config_dict["to"]
    # create message container - the correct MIME type is multipart/alternative.
    msg = MIMEMultipart('alternative')
    msg['Subject'] = standard_error_subject if subject is None else subject
    msg['From'] = from_address
    msg['To'] = to_address
    msg.attach(MIMEText(html, 'html'))

    # send the message via local SMTP server.
    s = smtplib.SMTP(email_config_dict["smtp_host"])
    s.sendmail(from_address, to_address, msg.as_string())
    s.quit()
