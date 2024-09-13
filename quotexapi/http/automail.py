import asyncio
import email
import imaplib
import re


async def get_pin(
    email_address,
    email_pass,
    imap_username=None,
    imap_server_host=None,
    imap_server_port=None,
    from_email="noreply@qxbroker.com",
    attempts=5,
):
    pin_code = None
    imap_username = imap_username or email_address
    imap_server_host = imap_server_host or "imap.gmail.com"
    imap_server_port = imap_server_port or 993
    mail = imaplib.IMAP4_SSL(imap_server_host, imap_server_port)
    mail.enable("UTF8=ACCEPT")
    mail.login(imap_username, email_pass)
    mail.select("inbox")
    while attempts > 0:
        status, email_ids = mail.search(
            None, f'(FROM "{from_email}", TO "{email_address}")'
        )
        email_id_list = email_ids[0].split()

        if not email_id_list:
            print(f"No emails found from {from_email} to {email_address} inbox.")
            mail.logout()
            return None

        status, email_data = mail.fetch(email_id_list[-1], "(RFC822)")
        raw_email = email_data[0][1]
        msg = email.message_from_bytes(raw_email)
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition"))
                if "attachment" not in content_disposition:
                    body += part.get_payload(decode=True).decode()
        else:
            body = msg.get_payload(decode=True).decode()

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
