import concurrent.futures
import json
import logging
import smtplib
import time

from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import Select
from models import DataRoot, WatchlistItemPreconditionStep, MailSettings, Watchlist, WatchlistItem, \
    WatchlistItemAlert, WatchlistItemCheckHistory, WebdriverSettings


class DataController(object):
    def __init__(self, data_file_name: str):
        self.data_json_file_name = data_file_name

    def read_data_file(self):
        with open(self.data_json_file_name, 'r') as data_file:
            file_content = data_file.read()
        return DataRoot.from_json(json.loads(file_content))

    def write_data_file(self, file_content: str):
        with open(self.data_json_file_name, 'w') as data_file:
            data_file.write(file_content)


class MailController(object):
    def __init__(self, mail_settings: MailSettings):
        self.settings = mail_settings

    def send_email(self, subject: str, body: str):
        if self.settings.should_send_emails:
            mime_msg = MIMEMultipart()
            mime_msg['From'] = self.settings.mail_server_from
            mime_msg['To'] = self.settings.mail_server_to
            mime_msg['Subject'] = subject
            mime_msg.attach(MIMEText(body))
            mail_server = smtplib.SMTP(self.settings.mail_server_host, self.settings.mail_server_port_number)
            mail_server.login(self.settings.mail_server_login_username, self.settings.mail_server_login_password)
            mail_server.sendmail(self.settings.mail_server_from, self.settings.mail_server_to, mime_msg.as_string())
            mail_server.quit()


class WatchlistItemController(object):
    def __init__(self, driver: webdriver, watchlist_item: WatchlistItem):
        self.driver = driver
        self.watchlist_item = watchlist_item
        self.watchlist_item_web_element = None

    def __go_to_page(self):
        self.driver.get(self.watchlist_item.url)

    def __create_alert(self, alert_message: str):
        title = "SimpleWatchBot: " + self.watchlist_item.name + " " + str(datetime.now())
        message = "An alert condition has been met for '" + self.watchlist_item.name + "': " + alert_message + "\n"
        message += "URL: " + self.watchlist_item.url
        return WatchlistItemAlert(title, message)

    def __perform_select_option_by_text_step(self, step: WatchlistItemPreconditionStep):
        element = self.driver.find_element(step.element_selector_type, step.element_selector)
        select = Select(element)
        select.select_by_visible_text(step.details["option_text"])

    def __perform_click_element_step(self, step: WatchlistItemPreconditionStep):
        element = self.driver.find_element(step.element_selector_type, step.element_selector)
        element.click()

    def __perform_precondition_step(self, step: WatchlistItemPreconditionStep):
        if step.action == "select_option_by_text":
            self.__perform_select_option_by_text_step(step)
        elif step.action == "click_element":
            self.__perform_click_element_step(step)

    def __perform_precondition_steps(self):
        for step in self.watchlist_item.precondition_steps:
            self.__perform_precondition_step(step)

    def __find_watchlist_item_element(self):
        try:
            return self.driver.find_element(self.watchlist_item.element_selector_type,
                                            self.watchlist_item.element_selector)
        except NoSuchElementException:
            return None

    def __check_element_condition_is_displayed(self):
        return self.watchlist_item_web_element is not None \
                and self.watchlist_item.alert_condition.is_displayed

    def __check_element_condition_is_not_displayed(self):
        return self.watchlist_item_web_element is None \
                and self.watchlist_item.alert_condition.is_not_displayed

    def __check_element_condition_text_equals(self):
        return self.watchlist_item.alert_condition.text_equals is not None \
                and self.watchlist_item_web_element.text == self.watchlist_item.alert_condition.text_equals

    def __check_element_condition_text_not_equals(self):
        return self.watchlist_item.alert_condition.text_not_equals is not None \
                and self.watchlist_item_web_element.text != self.watchlist_item.alert_condition.text_not_equals

    def __check_element_condition_text_contains(self):
        return self.watchlist_item.alert_condition.text_contains is not None \
                and self.watchlist_item.alert_condition.text_contains in self.watchlist_item_web_element.text

    def __check_element_condition_text_not_contains(self):
        return self.watchlist_item.alert_condition.text_not_contains is not None \
                and self.watchlist_item.alert_condition.text_not_contains not in self.watchlist_item_web_element.text

    def __check_watchlist_item_element_conditions(self):
        self.watchlist_item_web_element = self.__find_watchlist_item_element()
        if self.watchlist_item_web_element is None:
            if self.__check_element_condition_is_not_displayed():
                return "Element is not displayed."
            elif self.watchlist_item.alert_condition.is_displayed:
                pass
            else:
                raise Exception("Error: expected element to be displayed, but could not be found.")
        else:
            if self.__check_element_condition_is_displayed():
                return "Element is displayed."
            elif self.__check_element_condition_text_equals():
                return "Text equals " + self.watchlist_item.alert_condition.text_equals
            elif self.__check_element_condition_text_not_equals():
                return "Text doesn't equal " + self.watchlist_item.alert_condition.text_not_equals
            elif self.__check_element_condition_text_contains():
                return "Text contains " + self.watchlist_item.alert_condition.text_contains
            elif self.__check_element_condition_text_not_contains():
                return "Text doesn't contain " + self.watchlist_item.alert_condition.text_not_contains
        return None

    def check_watchlist_item(self):
        alert = None
        try:
            logging.info('Started checking item: ' + self.watchlist_item.name)
            self.__go_to_page()
            if self.watchlist_item.precondition_steps is not None:
                self.__perform_precondition_steps()
            alert_message = self.__check_watchlist_item_element_conditions()
            history = WatchlistItemCheckHistory(alert_message, False, str(datetime.now()))
            self.watchlist_item.check_history.append(history)
            logging.info('Item ' + self.watchlist_item.name + ' alert message: ' + (
                alert_message if alert_message is not None else 'N/A'))
            if alert_message is not None and not self.watchlist_item.alert_condition.has_condition_been_met:
                alert = self.__create_alert(alert_message)
            self.watchlist_item.alert_condition.has_condition_been_met = alert is not None
        except Exception as e:
            history = WatchlistItemCheckHistory(str(e), True, str(datetime.now()))
            self.watchlist_item.check_history.append(history)
            if len(self.watchlist_item.check_history) >= 5 \
                    and all(item.did_error for item in self.watchlist_item.check_history[-5:]):
                alert = self.__create_alert(str(e))
                self.watchlist_item.is_active = False
            logging.error(e)
        return alert


class WatchlistController(object):
    def __init__(self, watchlist: Watchlist, mail_controller: MailController, webdriver_settings: WebdriverSettings):
        self.watchlist = watchlist
        self.mail_controller = mail_controller
        self.webdriver_settings = webdriver_settings
        self.max_num_of_workers = webdriver_settings.max_number_of_workers

    def check_watchlist_item(self, watchlist_item: WatchlistItem):
        driver_controller = WebdriverController(self.webdriver_settings)
        driver_controller.create_driver()
        try:
            watchlist_item_controller = WatchlistItemController(driver_controller.driver, watchlist_item)
            watchlist_item_alert = watchlist_item_controller.check_watchlist_item()
            if watchlist_item_alert is not None:
                self.mail_controller.send_email(watchlist_item_alert.title, watchlist_item_alert.message)
        finally:
            driver_controller.close_driver()

    def check_watchlist_items_concurrently(self):
        logging.info('Started checking watchlist items')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_num_of_workers) as executor:
            future_watchlist_item = {executor.submit(self.check_watchlist_item, item): item
                                     for item in self.watchlist.items if item.is_active}
            for future in concurrent.futures.as_completed(future_watchlist_item):
                watchlist_item = future_watchlist_item[future]
                try:
                    future.result()
                except Exception as exc:
                    logging.info(('%s generated an exception: %s' % (watchlist_item.name, exc)))
                else:
                    logging.info('Done checking item ' + watchlist_item.name)
        logging.info('Done checking watchlist items')


class WebdriverController(object):
    def __init__(self, webdriver_settings: WebdriverSettings):
        self.driver = None
        self.webdriver_settings = webdriver_settings

    def create_driver(self):
        driver_options = Options()
        driver_options.headless = self.webdriver_settings.headless
        self.driver = webdriver.Firefox(executable_path=self.webdriver_settings.webdriver_path, options=driver_options)
        self.driver.implicitly_wait(15)

    def close_driver(self):
        self.driver.quit()


class MainController(object):
    def __init__(self, data_file_name: str):
        self.data_controller = DataController(data_file_name)
        self.deserialized_data_file = self.data_controller.read_data_file()
        self.mail_controller = MailController(self.deserialized_data_file.mail_settings)
        self.webdriver_settings = self.deserialized_data_file.webdriver_settings
        self.watchlist_controller = WatchlistController(self.deserialized_data_file.watchlist,
                                                        self.mail_controller, self.webdriver_settings)
        logging.basicConfig(format="%(asctime)s: %(message)s", level=logging.INFO, datefmt="%H:%M:%S")

    def check_watchlist_items_with_recheck(self):
        try:
            while True:
                start_time = time.time()
                self.watchlist_controller.check_watchlist_items_concurrently()
                end_time = time.time()
                elapsed_time = end_time - start_time
                sleep_time = max(self.watchlist_controller.watchlist.recheck_num_of_seconds - elapsed_time, 0)
                if sleep_time > 0:
                    logging.info('Re-running in ' + str(round(sleep_time, 2)) + ' seconds')
                    time.sleep(sleep_time)
        finally:
            # write updated data to file
            # data = json.dumps(self.deserialized_data_file, default=lambda o: o.__dict__, sort_keys=False, indent=2)
            # self.data_controller.write_data_file(data)
            pass
