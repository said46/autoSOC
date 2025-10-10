# soc_exporter.py
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (NoSuchElementException, TimeoutException)
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
import configparser
import openpyxl
from openpyxl.utils import get_column_letter
from datetime import datetime
import time

from base_web_bot import BaseWebBot
from soc_base_mixin import SOC_BaseMixin

class SOC_Exporter(BaseWebBot, SOC_BaseMixin):
    """
    Specialized bot for exporting SOC (Safety Override Control) overrides table to Excel
    """
    
    EXPECTED_HOME_PAGE_TITLE = "СНД - Домашняя страница"
    
    def __init__(self):
        BaseWebBot.__init__(self)
        SOC_BaseMixin.__init__(self)
        self.load_configuration()
        self.SOC_ID_PATTERN = r"^\d{7,8}$"
        self.SOC_id = None

    @property
    def base_link(self) -> str:
        return self._base_link
    
    def load_configuration(self) -> None:
        """Load configuration settings from the INI file"""
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.config_file, encoding="utf8")

        self.user_name = config.get('Settings', 'user_name', fallback='xxxxxx')
        
        raw_password = config.get('Settings', 'password', fallback='******')
        self.password = self.process_password(raw_password)
        
        if '\n' in self.password:
            self.password = 'INCORRECT PASSWORD'
            
        self._base_link = config.get('Settings', 'base_link', fallback='http://eptw.sakhalinenergy.ru/')
        self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_PAGE_LOAD_DELAY_SECONDS', fallback=30)

        logging.info(f"✅ Configuration loaded from {self.config_file}")

    def check_if_overrides_exist(self) -> bool:
        """
        Check if there are any overrides for this SOC
        Returns True if overrides exist, False otherwise
        """
        try:
            # Look for the overrides section and check if it contains data
            overrides_section = self.driver.find_element(By.XPATH, "//label[contains(text(), 'Отчет по форсировкам')]")
            parent_panel = overrides_section.find_element(By.XPATH, "./ancestor::div[contains(@class, 'issow-panel')]")
            
            # Check if there's a message indicating no data
            no_data_elements = parent_panel.find_elements(By.XPATH, ".//*[contains(text(), 'Нет данных') or contains(text(), 'No data')]")
            if no_data_elements:
                logging.info("ℹ️  No overrides data found for this SOC")
                return False
                
            return True
            
        except NoSuchElementException:
            logging.warning("⚠️  Overrides section not found on page")
            return False
        except Exception as e:
            logging.error(f"❌ Error checking overrides existence: {str(e)}")
            return False

    def extract_overrides_table_data(self):
        """
        Extract the overrides table data from SOC Details page using JavaScript
        """
        try:
            logging.info("🔍 Extracting SOC overrides table data via JavaScript...")
            
            # First check if overrides exist
            if not self.check_if_overrides_exist():
                logging.info("ℹ️  No overrides data available for extraction")
                return [], []
            
            # Wait for Kendo framework to load
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                lambda driver: driver.execute_script("return typeof kendo !== 'undefined'")
            )
            
            # Wait for the Overrides grid to be initialized and have data
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                lambda driver: driver.execute_script("""
                    var grid = $('#Overrides').data('kendoGrid');
                    return grid && grid.dataSource && grid.dataSource.data().length > 0;
                """)
            )
            
            # Clean extraction script with guaranteed column alignment
            script = """
            var grid = $('#Overrides').data('kendoGrid');
            if (!grid || !grid.dataSource) return null;
            
            var data = grid.dataSource.data();
            if (data.length === 0) return null;
            
            // Get visible columns in display order
            var visibleColumns = grid.columns.filter(col => 
                col.field && col.title && col.hidden !== true
            );
            
            // Extract headers and rows using the same column order
            var headers = visibleColumns.map(col => col.title);
            var rows = data.map(item => 
                visibleColumns.map(col => {
                    var value = item[col.field];
                    if (value && typeof value === 'object') {
                        return value.ShortForm || value.Title || value.Text || value.Name || '';
                    }
                    return value || '';
                })
            );
            
            return {headers: headers, rows: rows};
            """
            
            result = self.driver.execute_script(script)
            
            if not result:
                logging.info("ℹ️  No data found in Kendo Grid")
                return [], []
            
            headers = result.get('headers', [])
            rows = result.get('rows', [])
            
            if headers and rows:
                logging.info(f"✅ Successfully extracted SOC overrides: {len(headers)} columns, {len(rows)} rows")
                return headers, rows
            
            logging.info("ℹ️  No valid data extracted from Kendo Grid")
            return [], []
                
        except TimeoutException:
            logging.warning("⚠️  Timeout waiting for overrides data to load")
            return [], []
        except Exception as e:
            logging.error(f"❌ Failed to extract SOC overrides table: {str(e)}")
            return [], []

    def navigate_to_soc_details(self):
        """
        Navigate to SOC Details page and verify successful loading
        """
        try:           
            soc_details_url = self.base_link + f"Soc/Details/{self.SOC_id}"
            logging.info(f"🌐 Navigating to SOC Details: {soc_details_url}")
            
            self.driver.get(soc_details_url)
            
            # Wait for page to fully load
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Check for 404 error
            self.error_404_not_present_check()
            
            # Verify we're on SOC Details page
            self.url_contains_SOC_Details_check()
            
            logging.info("✅ Successfully navigated to SOC Details page")            
        except Exception as e:
            logging.error(f"❌ Failed to navigate to SOC Details: {str(e)}")
            self.inject_error_message(f"❌ Navigation failed: {str(e)}")

    def create_excel_file(self, headers: list, rows: list, filename: str = None) -> bool:
        """
        Create Excel file with SOC overrides data using openpyxl
        """
        if not headers or not rows:
            logging.error("❌ No data available to create Excel file")
            return False
            
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"soc_resources/SOC_{self.SOC_id}_overrides_{timestamp}.xlsx"
                       
            workbook = openpyxl.Workbook()
            sheet = workbook.active
            sheet.title = f'SOC_{self.SOC_id}'
            
            # Write headers with bold formatting
            for col_index, header in enumerate(headers, 1):
                cell = sheet.cell(row=1, column=col_index, value=header)
                cell.font = openpyxl.styles.Font(bold=True)
            
            # Write data rows
            for row_index, row_data in enumerate(rows, 2):
                for col_index, cell_value in enumerate(row_data, 1):
                    sheet.cell(row=row_index, column=col_index, value=cell_value)
            
            # Auto-adjust column widths
            self._auto_adjust_column_widths(sheet, headers, rows)
            
            workbook.save(filename)
            logging.info(f"💾 Successfully saved SOC overrides to: {filename}")
            return True
            
        except Exception as e:
            logging.error(f"❌ Failed to create Excel file: {str(e)}")
            return False

    def _auto_adjust_column_widths(self, sheet, headers: list, rows: list) -> None:
        """
        Automatically adjust column widths based on content length
        """
        try:
            max_lengths = []
            
            # Initialize with header lengths
            for header in headers:
                max_lengths.append(len(str(header)))
            
            # Update with data cell lengths
            for row in rows:
                for col_index, cell_value in enumerate(row):
                    if col_index < len(max_lengths):
                        cell_length = len(str(cell_value))
                        if cell_length > max_lengths[col_index]:
                            max_lengths[col_index] = cell_length
            
            # Apply calculated widths
            for col_index, max_len in enumerate(max_lengths, 1):
                adjusted_width = min(max_len + 2, 50)
                column_letter = get_column_letter(col_index)
                sheet.column_dimensions[column_letter].width = adjusted_width
                
            logging.debug(f"📐 Adjusted {len(max_lengths)} column widths")
            
        except Exception as e:
            logging.warning(f"⚠️  Could not auto-adjust column widths: {str(e)}")

    def run_automation(self):
        """
        Main automation workflow for exporting SOC overrides to Excel
        """
        try:
            logging.info("🚀 Starting SOC to Excel export automation")
            
            self.navigate_to_base()
            self.perform_login()
            
            if not self.wait_for_soc_input_and_process():
                self.inject_error_message(f"❌ Failed to get SOC ID input")
                return
            
            if not self.navigate_to_soc_details():
                return
            
            # Step 4: Extract table data
            headers, rows = self.extract_overrides_table_data()
            
            if not headers or not rows:
                info_msg = f"ℹ️  No overrides data found for SOC {self.SOC_id}. This SOC may not have any overrides configured."
                logging.info(info_msg)
                # Use _inject_message_with_wait to display message and wait for browser close
                self._inject_message_with_wait(info_msg, style_addons={'color': 'orange'})
            else:
                # Step 5: Create Excel file
                if self.create_excel_file(headers, rows):
                    success_msg = f"✅ SOC {self.SOC_id} overrides successfully exported to Excel"
                    logging.info(success_msg)
                    # Use _inject_message_with_wait to display success message and wait for browser close
                    self._inject_message_with_wait(success_msg, style_addons={'color': 'green'})
                else:
                    error_msg = f"❌ Failed to save Excel file for SOC {self.SOC_id}"
                    self.inject_error_message(error_msg)
                    # Use _inject_message_with_wait for error case too
                    self._inject_message_with_wait(error_msg, style_addons={'color': 'red'})
            
        except Exception as e:
            logging.error(f"❌ SOC automation failed: {str(e)}")
            error_msg = f"❌ SOC automation failed: {str(e)}"
            try:
                self._inject_message_with_wait(error_msg, style_addons={'color': 'red'})
            except:
                # If injection fails, just quit
                if hasattr(self, 'driver'):
                    self.driver.quit()
        finally:
            # Clean up - _inject_message_with_wait already handles browser closing
            pass

if __name__ == "__main__":
    bot = SOC_Exporter()
    bot.run_automation()