import asyncio
import email
import imaplib
import re
import ssl
from _datetime import datetime


async def get_pin(
    email_address,
    email_pass,
    imap_username=None,
    imap_server_host=None,
    imap_server_port=None,
    from_email="noreply@qxbroker.com",
    attempts=30,
    sent_since=datetime.now()
):
    pin_code = None
    imap_username = imap_username or email_address
    imap_server_host = imap_server_host or "imap.gmail.com"
    imap_server_port = imap_server_port or 993
    ssl_context = ssl.create_default_context()
    mail = imaplib.IMAP4_SSL(imap_server_host, imap_server_port)
    mail.login(imap_username, email_pass)
    mail.enable("UTF8=ACCEPT")
    mail.select("inbox")
    while attempts > 0:
        status, email_ids = mail.search(
            None, f'FROM "{from_email}" TO "{email_address}"')
        email_id_list = email_ids[0].split()
        if len(email_id_list):
            status, email_data = mail.fetch(email_id_list[-1], "(RFC822)")
            raw_email = email_data[0][1]
            message = email.message_from_bytes(raw_email)
            message_date = datetime.strptime(message.get("Date"), "%a, %d %b %Y %H:%M:%S %z")
            sent_since_date = sent_since.astimezone(message_date.tzinfo).replace(microsecond=0)
            if message_date >= sent_since_date:
                body = ""

                if message.is_multipart():
                    for part in message.walk():
                        content_disposition = str(part.get("Content-Disposition"))
                        if "attachment" not in content_disposition:
                            body += part.get_payload(decode=True).decode()
                else:
                    body = message.get_payload(decode=True).decode()

                if body:
                    match = re.search(r"<b>(\d+)</b>", body)
                    if match:
                        pin_code = match.group(1)
                    if pin_code:
                        return pin_code

        attempts -= 1
        await asyncio.sleep(1)

    print(
        f"No authentication PIN-code received from {from_email} to {email_address} inbox."
    )
    mail.logout()
    return pin_code
