import time

from django.conf import settings
from django.utils.importlib import import_module
from django.contrib.auth import authenticate

from apps.webdriver_testing.pages import Page

class UnisubsPage(Page):
    """
     Unisubs page contains common web elements found across
     all Universal Subtitles pages. Every new page class is derived from
     UnisubsPage so that every child class can have access to common web
     elements and methods that pertain to those elements.
    """

    _LOGIN = "a[href*='/auth/login']"
    _USER_MENU = "li#me_menu"
    _CREATE_NAV = "li#nav_submit a"
    _FEEDBACK_BUTTON = ".feedback_tab"

    _CURRENT_USER = "li#me_menu div#user_menu div#menu_name a"

    _USER_TEAMS = "li#me_menu  div#user_menu div#menu ul#dropdown li[id^=team] a"
    _SITE_LOGIN_USER_ID = "input#id_username"
    _SITE_LOGIN_USER_PW = "input#id_password"
    _SITE_LOGIN_SUBMIT = "form button[value=login]"

    _MESSAGE = "div#messages"
    _ERROR_MESSAGE = "div#messages h2.error"
    _SUCCESS_MESSAGE = "div#messages h2.success"

    _MODAL_DIALOG = "div.modal"
    _MODAL_CLOSE = "div a.close"
    _SEARCHING_INDICATOR = "img.placeholder"

    def error_message_present(self, message):
        self.logger.info('Check if error message is present')
        if self.is_text_present(self._ERROR_MESSAGE, message):
            return True

    def success_message_present(self, message):
        self.logger.info('Check if success message present')
        self.wait_for_element_present(self._MESSAGE, wait_time=15)
        if self.is_text_present(self._SUCCESS_MESSAGE, message):
            return True

    def open_amara(self):
        self.logger.info('Open amara home page')
        self.browser.get(self.base_url)

    def _current_user(self):
        self.logger.info('Get the username of currently logged in user')

        if self.is_element_present(self._CURRENT_USER):
            return self.get_text_by_css(self._CURRENT_USER)
    
    def logged_in(self):
        self.logger.info('Check if user logged in')

        if self.is_element_visible(self._CURRENT_USER):
            return True

    def log_out(self):
        self.logger.info('Log out of site')
        self.open_page('logout/?next=/videos/create')

    def log_in(self, username, password, set_skip=True):
        """Log in with the specified account type - default as a no-priv user.

        """
        self.logger.info("LOG IN %s" % username)
        host = self.testcase.server_thread.host
        port = self.testcase.server_thread.port
        engine = import_module(settings.SESSION_ENGINE)
        session = engine.SessionStore(self._get_session_id())
        user = authenticate(username=username, password=password)
        if user is None:
            raise ValueError("Invalid auth credentials: %r/%r" %
                             (username, password))
        session['_auth_user_id'] = unicode(user.pk)
        session['_auth_user_backend'] = u'auth.backends.CustomUserBackend'
        session.save()
        self.browser.add_cookie({ u'domain': '%s:%s' % (host, port),
                                  u'name': u'sessionid',
                                  u'value': session.session_key,
                                  u'path': u'/',
                                  u'secure': False,
                                 })
        self.logger.info("login cookie saved")
        if set_skip:
            self.set_skiphowto()

    def set_skiphowto(self):
        self.browser.add_cookie({ u'name': u'skiphowto', 
                          u'value': u'1', 
                          u'secure': False,
                        })


    def _get_session_id(self):
        #jed - modified this because sauce fails when get_cookies used.
        try:
            cookie = self.browser.get_cookie_by_name('sessionid')
            return cookie['value']
        except:
            return None
     
        #for cookie in self.browser.get_cookies():
        #    if (cookie['domain'] == 'unisubs.example.com' and 
        #        cookie['name'] == 'sessionid'):
        #        return cookie['value']
        return None

    def current_teams(self):
        """Returns the href value of any teams that use logged in user is 
           currently a memeber.

        """
        self.logger.info('Get a list of teams for the current user')
        user_teams = []
        if self.logged_in() == True:
            elements = self.browser.find_elements_by_css_selector(
                self._USER_TEAMS)
            for e in elements:
                user_teams.append(e.get_attribute('href'))
        return user_teams

    def close_modal(self):
        try:
            if not self.is_element_visible(self._MODAL_DIALOG) == False:
                self.logger.info('Close the modal dialog')
                self.click_by_css(self._MODAL_CLOSE)
        except:
            pass

    def click_feeback(self):
        self.logger.info('Click the feedback button')

        self.click_by_css(self._FEEDBACK_BUTTON)
 
    def impersonate(self, username):
        self.logger.info('Impersonating the user %s' % username)
        self.open_page('auth/login-trap/')
        self.wait_for_element_present(self._SITE_LOGIN_USER_ID)
        self.type_by_css(self._SITE_LOGIN_USER_ID, username)
        self.click_by_css(self._SITE_LOGIN_SUBMIT)

    def search_complete(self):
        self.logger.info('Waiting for the search indicator to disappear.')
        time.sleep(2)
        self.wait_for_element_not_visible(self._SEARCHING_INDICATOR)

