# soc_controller.py
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (NoSuchElementException, NoSuchWindowException)
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

import configparser

import logging

from base_web_bot import BaseWebBot
from soc_base_mixin import SOC_BaseMixin


class SOC_Controller(BaseWebBot, SOC_BaseMixin):
    """
    Specialized bot for SOC overrides automation.
    """

    FINAL_STATE_DROPDOWN_INDEX = 1

    def __init__(self, soc_id=None):
        BaseWebBot.__init__(self)
        SOC_BaseMixin.__init__(self)
        self.warning_message = None
        self.load_configuration()
        
        if soc_id:
            self.SOC_id = soc_id

    def set_soc_id(self, soc_id: str) -> None:
        self.SOC_id = soc_id

    @property
    def base_link(self) -> str:
        return self._base_link

    def load_configuration(self) -> None:
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.config_file, encoding="utf8")

        self.user_name = config.get('Settings', 'user_name', fallback='xxxxxx')
        raw_password = config.get('Settings', 'password', fallback='******')
        self.password = self.process_password(raw_password)

        if '\n' in self.password:
            self.password = 'INCORRECT PASSWORD'

        self._base_link = config.get('Settings', 'base_link', fallback='http://eptw.sakhalinenergy.ru/')
        self.MAX_WAIT_USER_INPUT_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_USER_INPUT_DELAY_SECONDS', fallback=300)
        self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_PAGE_LOAD_DELAY_SECONDS', fallback=30)
        self.SOC_id = config.get('Settings', 'SOC_id', fallback='')

        self.SOC_roles = config.get('Roles', 'SOC_roles', fallback='OAC,OAV').split(',')
        self.good_statuses = config.get(
            'Statuses',
            'good_statuses',
            fallback='принято для установки-запрошено для удаления-установлено, не подтверждено-удалено, не подтверждено').split('-')
        self.SOC_status_approved_for_apply = config.get('Statuses', 'SOC_status_approved_for_apply', fallback='одобрено для установки')

        self.roles = {
            config.get('Roles', 'OAC', fallback='Исполняющий форсирование'): 'OAC',
            config.get('Roles', 'OAV', fallback='Проверяющий форсирование'): 'OAV'
        }

        self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = config.getboolean('Database', 'CONNECT_TO_DB_FOR_PARTIAL_SOC_ID', fallback=False)
        self._load_database_configuration(config)

        if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            self.SOC_ID_PATTERN = r"^\d{4,8}$"
        else:
            self.SOC_ID_PATTERN = r"^\d{7,8}$"

    def _load_database_configuration(self, config: configparser.ConfigParser) -> None:
        if self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID:
            try:
                self.db_server = config.get('Database', 'server')
                raw_db_password = config.get('Database', 'password')
                self.db_password = self.process_password(raw_db_password)
                self.db_database = config.get('Database', 'database')
                self.db_username = config.get('Database', 'username')

                if not all([self.db_server, self.db_database, self.db_username]):
                    raise configparser.NoOptionError('Database', 'Some database credentials are empty')

                self.SQL_template = config.get('SQL', 'SOC_query', fallback="").strip(' \n\r\t')
                if self.SQL_template and not self.SQL_template.strip().lower().startswith('select'):
                    raise ValueError("SQL query must start with SELECT")

            except (configparser.NoSectionError, configparser.NoOptionError) as e:
                self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
                self.warning_message = f"⚠️ Database config incomplete: {e}. Disabling database features."
                logging.warning(self.warning_message)
            except ValueError as e:
                self.CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = False
                self.warning_message = "⚠️ SQL query doesn't start with SELECT. Disabling database features."
                logging.warning(self.warning_message)

    def get_SOC_status(self) -> str:
        script = """
            return document.evaluate(
                "//label[normalize-space()='Состояние']/following-sibling::text()[1]",
                document,
                null,
                XPathResult.STRING_TYPE,
                null
            ).stringValue.trim();
        """
        try:
            status = self.driver.execute_script(script)
            if status == '':
                raise ValueError("SOC status cannot be empty")
            logging.info(f"👆 SOC {self.SOC_id} status: '{status}'")
            return status.lower()
        except Exception as e:
            logging.error(f"❌ Failed to get SOC status: {e}")
            self.inject_error_message(f"❌ Failed to get SOC status: {e}")
            return ''

    def get_current_role(self) -> str:
        try:
            role_span = self.driver.find_element(By.XPATH, "//span[@class='k-state-active' and contains(text(), 'Роль:')]")
            role_text = role_span.text.strip()

            if "Роль:" in role_text:
                role_name = role_text.split("Роль:")[1].strip()
                logging.info(f"👤 Current role: '{role_name}'")
                return self.roles[role_name]
            else:
                logging.warning(f"⚠️ Unexpected role format: '{role_text}'")
                return "unknown"

        except NoSuchElementException:
            logging.warning("⚠️ Role span not found")
            return "unknown"
        except Exception as e:
            logging.warning(f"⚠️ Could not determine role: {e}")
            return "unknown"

    def switch_role(self, role: str) -> None:
        try:
            if self.get_current_role() == role:
                logging.info(f"✅ Already in {role} role")
                return

            self.driver.get(self._base_link + r"User/ChangeRole")
            self.wait_for_kendo_dropdown("CurrentRoleName")

            set_role_script = f"""
                var dropdown = $('#CurrentRoleName').data('kendoDropDownList');
                dropdown.value('{role}');
                dropdown.trigger('change');
                return true;
            """
            self.driver.execute_script(set_role_script)

            WebDriverWait(self.driver, 10).until(
                lambda _: self.driver.execute_script(
                    f"return $('#CurrentRoleName').data('kendoDropDownList').value() === '{role}';"
                )
            )

            self.click_button((By.ID, 'ConfirmHeader'))
            logging.info(f"✅ Switched to {role} role")

        except NoSuchWindowException:
            logging.warning("🏁 Browser closed")
            self.safe_exit()
        except Exception as e:
            logging.error(f"❌ Failed to switch role: {e}")
            self.inject_error_message("❌ Failed to switch role")

    def accept_SOC_to_apply(self) -> None:
        try:
            old_status = self.get_SOC_status()
            logging.info(f"⏳ Current status: '{old_status}' - accepting for apply")

            logging.info("⏳ Waiting for ActionsList dropdown...")
            self.wait_for_kendo_dropdown("ActionsList")
            logging.info("✅ ActionsList ready")

            action_value = f'/Soc/TriggerChangeWorkflowState/{self.SOC_id}?trigger=AcceptForApply'
            logging.info(f"🔧 Setting action: {action_value}")

            set_action_script = """
                var dropdown = $('#ActionsList').data('kendoDropDownList');
                dropdown.value(arguments[0]);
                dropdown.trigger('change');
            """
            self.driver.execute_script(set_action_script, action_value)
            logging.info("✅ Action set")

            WebDriverWait(self.driver, 10).until(
                lambda _: self.driver.execute_script(
                    "return $('#ActionsList').data('kendoDropDownList').value() === arguments[0];",
                    action_value
                )
            )

            self.click_button((By.ID, 'ApplyActionButton'))

            logging.info(f"⏳ Waiting for status change from '{old_status}'...")
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                lambda _: self.get_SOC_status() != old_status
            )

            new_status = self.get_SOC_status()
            logging.info(f"✅ SOC accepted - new status: '{new_status}'")

        except NoSuchWindowException:
            logging.warning("🏁 Browser closed")
            self.safe_exit()
        except Exception as e:
            logging.error(f"❌ Failed to accept SOC: {e}")
            self.inject_error_message(f"❌ Failed to accept SOC {self.SOC_id}")

    def update_points(self):
        try:
            item_xpath = f"//select[@id='CurrentStateSelect' and not(@disabled)]"
            sel_items = self.driver.find_elements(By.XPATH, item_xpath)
            logging.info(f"Updating {len(sel_items)} points")

            for point_index, sel_item in enumerate(sel_items, start=1):
                drop = Select(sel_item)
                if len(drop.options) > 1:
                    drop.select_by_index(self.FINAL_STATE_DROPDOWN_INDEX)
                    selected_text = drop.first_selected_option.text
                    logging.info(f"✅ Point {point_index} updated to {selected_text}")
        except NoSuchElementException as e:
            logging.error(f"❌ Failed to update points: {e}")
            self.inject_error_message("❌ Failed to update some points")

    def navigate_to_soc_and_check_status(self):
        SOC_view_base_link = self._base_link + r"Soc/Details/"
        self.driver.get(SOC_view_base_link + self.SOC_id)

        self.error_404_not_present_check()
        self.url_contains_SOC_Details_check()

        SOC_status = self.get_SOC_status()
        logging.info(f"🔍 Initial SOC status: '{SOC_status}'")

        if SOC_status == self.SOC_status_approved_for_apply:
            logging.info("🔄 SOC needs accept - switching to OAC role")
            self.switch_role('OAC')
            self.driver.get(SOC_view_base_link + self.SOC_id)
            self.accept_SOC_to_apply()
            SOC_status = self.get_SOC_status()
            logging.info(f"🔍 Status after accept: '{SOC_status}'")

        if SOC_status not in self.good_statuses:
            logging.error(f'❌ SOC {self.SOC_id} status "{SOC_status}" - cannot proceed')
            locator = (By.XPATH, "//div[@id='issowFormContainer']//div[contains(@class, 'user-form')]")
            self.inject_error_message(f'❌ SOC {self.SOC_id} status "{SOC_status}"',
                                    locator, style_addons={'width': '100%', 'align': 'center'})

    def process_soc_roles(self):
        for SOC_role in self.SOC_roles:
            self.switch_role(SOC_role)

            SOC_update_base_link = self._base_link + r"Soc/UpdateOverride/"
            self.driver.get(SOC_update_base_link + self.SOC_id)

            self.SOC_locked_check()
            self.access_denied_check()

            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                lambda _: len(self.driver.find_elements(By.XPATH, "//select[@id='CurrentStateSelect' and not(@disabled)]")) >= 1
            )

            self.update_points()
            self.wait_for_user_confirmation()

    def wait_for_user_confirmation(self):
        msg = '⚠️  Скрипт ожидает нажатия кнопки "Подтвердить".'
        xpath = "//div[@id='bottomWindowButtons']/div"
        self.inject_info_message(msg, (By.XPATH, xpath), {'color': 'lawngreen'})
        try:
            WebDriverWait(self.driver, self.MAX_WAIT_USER_INPUT_DELAY_SECONDS).until(
                EC.title_is(self.EXPECTED_HOME_PAGE_TITLE)
            )
            logging.info("🏁 Confirm pressed, home page loaded")
        except NoSuchWindowException:
            logging.error("⚠️ User closed browser")
            self.safe_exit()
        except Exception as e:
            logging.error(f"❌ Failed waiting for confirm: {e}")
            self.inject_error_message("❌ Failed waiting for confirm")

    def run(self, standalone=False):
        if standalone:
            self.navigate_to_base()
            self.enter_credentials_and_prepare_soc_input()
            self.wait_for_soc_input_and_submit()
        self.navigate_to_soc_and_check_status()
        self.process_soc_roles()
        self.safe_exit()

if __name__ == "__main__":
    bot = SOC_Controller()
    bot.run(standalone=True)