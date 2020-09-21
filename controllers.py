import json
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
    WatchlistItemAlert, WebdriverSettings


class DataController(object):
    def __init__(self):
        self.data_json_file_name = './data.json'

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


class WatchlistController(object):
    def __init__(self, watchlist: Watchlist):
        self.watchlist = watchlist

    @staticmethod
    def create_alert(watchlist_item: WatchlistItem, alert_message: str):
        title = "SimpleWatchBot: " + watchlist_item.name + " " + str(datetime.now())
        message = "An alert condition has been met for '" + watchlist_item.name + "': " + alert_message + "\n"
        message += "URL: " + watchlist_item.url
        return WatchlistItemAlert(title, message)


class WebdriverController(object):
    def __init__(self, webdriver_settings: WebdriverSettings):
        self.driver = None
        self.webdriver_settings = webdriver_settings

    def create_driver(self):
        driver_options = Options()
        driver_options.headless = self.webdriver_settings.headless
        self.driver = webdriver.Firefox(executable_path=self.webdriver_settings.webdriver_path, options=driver_options)
        self.driver.implicitly_wait(10)

    def close_driver(self):
        self.driver.quit()

    def go_to_page(self, url: str):
        self.driver.get(url)

    def perform_select_option_by_text_step(self, step: WatchlistItemPreconditionStep):
        element = self.driver.find_element(step.element_selector_type, step.element_selector)
        select = Select(element)
        select.select_by_visible_text(step.details["option_text"])

    def perform_click_element_step(self, step: WatchlistItemPreconditionStep):
        element = self.driver.find_element(step.element_selector_type, step.element_selector)
        element.click()

    def perform_precondition_step(self, step: WatchlistItemPreconditionStep):
        if step.action == "select_option_by_text":
            self.perform_select_option_by_text_step(step)
        elif step.action == "click_element":
            self.perform_click_element_step(step)

    def perform_precondition_steps(self, watchlist_item: WatchlistItem):
        for step in watchlist_item.precondition_steps:
            self.perform_precondition_step(step)

    def find_watchlist_item_element(self, watchlist_item: WatchlistItem):
        try:
            return self.driver.find_element(watchlist_item.element_selector_type, watchlist_item.element_selector)
        except NoSuchElementException:
            return None

    def check_watchlist_item_element_conditions(self, watchlist_item: WatchlistItem):
        watchlist_item_element = self.find_watchlist_item_element(watchlist_item)

        # is not displayed
        if watchlist_item_element is None:
            if watchlist_item.alert_condition.is_not_displayed:
                return "Element is not displayed."
            elif watchlist_item.alert_condition.is_displayed:
                pass
            else:
                return "Error: expected element to be displayed, but could not be found."

        # is displayed
        if watchlist_item_element is not None \
                and watchlist_item.alert_condition.is_displayed:
            return "Element is displayed."

        # text equals
        if watchlist_item.alert_condition.text_equals is not None \
                and watchlist_item_element.text == watchlist_item.alert_condition.text_equals:
            return "Text equals " + watchlist_item.alert_condition.text_equals

        # text not equals
        if watchlist_item.alert_condition.text_not_equals is not None \
                and watchlist_item_element.text != watchlist_item.alert_condition.text_not_equals:
            return "Text doesn't equal " + watchlist_item.alert_condition.text_not_equals

        # text contains
        if watchlist_item.alert_condition.text_contains is not None \
                and watchlist_item.alert_condition.text_contains in watchlist_item_element.text:
            return "Text contains " + watchlist_item.alert_condition.text_contains

        # text not contains
        if watchlist_item.alert_condition.text_not_contains is not None \
                and watchlist_item.alert_condition.text_not_contains not in watchlist_item_element.text:
            return "Text doesn't contain " + watchlist_item.alert_condition.text_not_contains

        return None


class MainController(object):
    def __init__(self):
        self.n = None
        self.data_controller = DataController()
        self.deserialized_data_file = self.data_controller.read_data_file()
        self.webdriver_controller = WebdriverController(self.deserialized_data_file.webdriver_settings)
        self.watchlist_controller = WatchlistController(self.deserialized_data_file.watchlist)
        self.mail_controller = MailController(self.deserialized_data_file.mail_settings)

    def check_watchlist_item(self, watchlist_item: WatchlistItem):
        self.webdriver_controller.create_driver()
        try:
            print("Checking item:", watchlist_item.name)
            self.webdriver_controller.go_to_page(watchlist_item.url)
            if watchlist_item.precondition_steps is not None:
                self.webdriver_controller.perform_precondition_steps(watchlist_item)
            alert_message = self.webdriver_controller.check_watchlist_item_element_conditions(watchlist_item)
            print("Alert message:", alert_message)
            if alert_message is not None and not watchlist_item.alert_condition.has_condition_been_met:
                alert = self.watchlist_controller.create_alert(watchlist_item, alert_message)
                self.mail_controller.send_email(alert.title, alert.message)
            watchlist_item.alert_condition.has_condition_been_met = alert_message is not None
        except Exception as e:
            print("ERROR: Exception was caught during execution of watchlist check.", e)
        finally:
            self.webdriver_controller.close_driver()

    def check_watchlist_items(self):
        print(datetime.now(), "checking watchlist items..")
        for watchlist_item in self.watchlist_controller.watchlist.items:
            self.check_watchlist_item(watchlist_item)

    def check_watchlist_items_with_recheck(self):
        while True:
            start_time = time.time()
            self.check_watchlist_items()
            data = json.dumps(self.deserialized_data_file, default=lambda o: o.__dict__, sort_keys=False, indent=2)
            self.data_controller.write_data_file(data)
            end_time = time.time()
            elapsed_time = end_time - start_time
            sleep_time = max(self.watchlist_controller.watchlist.recheck_num_of_seconds - elapsed_time, 0)
            time.sleep(sleep_time)
