#!/usr/bin/env python

import time

from apps.webdriver_testing.pages import Page

class UnisubsMenu(Page):

    #LANGUAGE DISPLAY OPTIONS
    _MENU = 'span.unisubs-tabTextchoose'
    _SUBTITLES_OFF = 'div.unisubs-languageList li'
    _LANG_LIST = 'div.unisubs-languageList'
    _LANG_TITLE = '.unisubs-languageTitle'
    _ACTIVE_LANG = 'li.unisubs-activeLanguage span.unisubs-languageTitle'

    #ACTIONS
    _NEW_TRANSLATION = '.unisubs-addTranslation a'
    _IMPROVE_SUBS = '.unisubs-improveSubtitles a'
    _SUB_HOMEPAGE = '.unisubs-subtitleHomepage a'
    #_EMBED_CODE = ''  #Just links to homepage - not useful.
    _DOWNLOAD_SUBTITLES = '.unisubs-downloadSubtitles a'
    _MODERATED = 'li.unisubs-moderated'

    #CURRENT USER SETTINGS 
    _USER_PAGE = '%s'    #visible text link - provide username
    _LOGOUT = 'Logout'   #visible text link
    _LANG_PREFERENCES = '.unisubs-languagePreferences'

    _CAPTIONS = "span.unisubs-captionSpan"


    def visible_menu_text(self):
        """Return the text displayed for the Subs menu.

        """
        self.wait_for_element_present(self._MENU)
        ## Giving loading message 10 seconds to update.
        start_time = time.time()
        while time.time() - start_time < 10:
            time.sleep(.2)
            menu_text = self.get_text_by_css(self._MENU)
            if menu_text != 'Loading':
                break
        else:
            self.record_error("> 10 seconds passed, and menu still loading")

        return self.get_text_by_css(self._MENU)

    def _available_languages(self):
        """Return a list of available languages in the menu.

        """
        language_list = []
        elements = self.browser.find_elements_by_css_selector(
            self._LANG_LIST)
        for el in elements:
            lang = el.find_element_by_css(self._LANG_TITLE).text
            language_list.append(lang)
        return language_list

    def _language_status(self, language):
        """Return the displayed status for the language.

        """
        elements = self.browser.find_elements_by_css_selector(
            self._LANG_TITLE)
        for el in elements:
            if el.text == language:
                parent = el.parent()
                status = parent.find_element_by_css_selector(
                    self._LANG_STATUS).text
                return status

    def _language_element(self, language):
        """Return the webdriver object for the language element.

        """
        elements = self.browser.find_elements_by_css_selector(
            self._LANG_TITLE)
        for el in elements:
            self.logger.info(el.text)
            if el.text == language:
                return el

    def select_language(self, language):
        """Choose a language from the subs menu.

        """
        self._language_element(language).click()
 

    def open_menu(self):
        """Click the Subs menu to open it.

        """
        self.wait_for_element_visible(self._MENU)
        self.click_by_css(self._MENU)

    def improve_subtitles(self):
        self.open_menu()
        self.click_by_css(self._IMPROVE_SUBS)

    def new_translation(self):
        self.open_menu()
        self.click_by_css(self._NEW_TRANSLATION)

    def displays_new_translation(self):
        return self.is_element_present(self._NEW_TRANSLATION)

    def displays_improve_subtitles(self):
        return self.is_element_visible(self._IMPROVE_SUBS)

    def displays_moderated_message(self):
        return self.is_element_visible(self._MODERATED)
 
    def open_subtitle_homepage(self):
        """Open the subtitle homepage.

        """
        self.open_menu()
        self.click_by_css(self._SUB_HOMEPAGE) 

    
    def download_subtitles_url(self, language):
        """Returns the download url of the specified language.

        """
        if self.visible_menu_text is not language:
            self.open_menu()
            self.select_language(language)
        self.open_menu()
        return self.get_element_attribute(self._DOWNLOAD_SUBTITLES, 'href')
            
    def start_playback(self, video_position=0):
        self.browser.execute_script("unisubs.widget.Widget.getAllWidgets()[%d].play()"
                                    % video_position)

    def pause_playback(self, video_position=0):
        self.browser.execute_script("unisubs.widget.Widget.getAllWidgets()[%d].pause()" 
                                    % video_position)

    def displays_subs_in_correct_position(self):
        """Return true if subs are found in correct position on video.

        """
        self.wait_for_element_visible(self._CAPTIONS)
        self.pause_playback(video_position)
        size = self.get_size_by_css(self._CAPTIONS)
        height = size["height"]
        if 10 < height < 80:
            return True
 
