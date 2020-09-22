from typing import List


class WebdriverSettings(object):
    def __init__(self, webdriver_path: str, headless: bool, max_number_of_workers: int):
        self.webdriver_path = webdriver_path
        self.headless = headless
        self.max_number_of_workers = max_number_of_workers

    @classmethod
    def from_json(cls, data):
        return cls(**data)


class MailSettings(object):
    def __init__(self, mail_server_host: str, mail_server_port_number: int, mail_server_login_username: str,
                 mail_server_login_password: str, mail_server_from: str, mail_server_to: str, should_send_emails: bool):
        self.mail_server_host = mail_server_host
        self.mail_server_port_number = mail_server_port_number
        self.mail_server_login_username = mail_server_login_username
        self.mail_server_login_password = mail_server_login_password
        self.mail_server_from = mail_server_from
        self.mail_server_to = mail_server_to
        self.should_send_emails = should_send_emails

    @classmethod
    def from_json(cls, data):
        return cls(**data)


class WatchlistItemAlert(object):
    def __init__(self, title: str, message: str):
        self.title = title
        self.message = message


class WatchlistItemAlertCondition(object):
    def __init__(self, is_displayed: bool, is_not_displayed: bool, text_equals: str, text_not_equals: str,
                 text_contains: str, text_not_contains: str, has_condition_been_met: bool):
        self.is_displayed = is_displayed
        self.is_not_displayed = is_not_displayed
        self.text_equals = text_equals
        self.text_not_equals = text_not_equals
        self.text_contains = text_contains
        self.text_not_contains = text_not_contains
        self.has_condition_been_met = has_condition_been_met

    @classmethod
    def from_json(cls, data):
        return cls(**data)


class WatchlistItemPreconditionStep(object):
    def __init__(self, action: str, element_selector_type: str, element_selector: str, details: dict):
        self.action = action.lower()
        self.element_selector_type = element_selector_type.lower()
        self.element_selector = element_selector.lower()
        self.details = details

    @classmethod
    def from_json(cls, data):
        return cls(**data)


class WatchlistItem(object):
    def __init__(self, name: str, url: str, element_selector_type: str, element_selector: str,
                 alert_condition: WatchlistItemAlertCondition, precondition_steps: List[WatchlistItemPreconditionStep]):
        self.name = name
        self.url = url
        self.element_selector_type = element_selector_type.lower()
        self.element_selector = element_selector
        self.alert_condition = alert_condition
        self.precondition_steps = precondition_steps

    @classmethod
    def from_json(cls, data):
        deserialized = cls(**data)
        deserialized.alert_condition = WatchlistItemAlertCondition.from_json(data["alert_condition"])
        if deserialized.precondition_steps is not None:
            deserialized.precondition_steps = list(map(WatchlistItemPreconditionStep.from_json, data["precondition_steps"]))
        return deserialized


class Watchlist(object):
    def __init__(self, recheck_num_of_seconds: int, items: List[WatchlistItem]):
        self.recheck_num_of_seconds = max(recheck_num_of_seconds, 5)
        self.items = items

    @classmethod
    def from_json(cls, data):
        recheck_num_of_seconds = data["recheck_num_of_seconds"]
        items = list(map(WatchlistItem.from_json, data["items"]))
        return cls(recheck_num_of_seconds, items)


class DataRoot(object):
    def __init__(self, webdriver_settings: WebdriverSettings, mail_settings: MailSettings, watchlist: Watchlist):
        self.webdriver_settings = webdriver_settings
        self.mail_settings = mail_settings
        self.watchlist = watchlist

    @classmethod
    def from_json(cls, data):
        webdriver_settings = WebdriverSettings.from_json(data["webdriver_settings"])
        mail_settings = MailSettings.from_json(data["mail_settings"])
        watchlist = Watchlist.from_json(data["watchlist"])
        return cls(webdriver_settings, mail_settings, watchlist)
