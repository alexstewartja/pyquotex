from ..http.qxbroker import Browser


class Login(Browser):
    """Class for Quotex login resource."""

    async def __call__(
        self,
        email,
        password,
        email_pass,
        imap_username=None,
        imap_server_host=None,
        imap_server_port=None,
        user_data_dir=None,
    ):
        """Method to get Quotex API login http request.
        :param str email: The username of a Quotex server.
        :param str password: The password of a Quotex server.
        :param str email_pass: The password of a Email.
        :param str user_data_dir: The optional value for path userdata.
        :returns: The instance of :class:`playwright.cookies`.
        """
        self.user_data_dir = user_data_dir
        self.email = email
        self.password = password
        self.email_pass = email_pass
        self.imap_username = imap_username
        self.imap_server_host = imap_server_host
        self.imap_server_port = imap_server_port
        return await self.get_cookies_and_ssid()
