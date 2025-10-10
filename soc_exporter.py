# soc_exporter.py
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (NoSuchElementException, TimeoutException)
from selenium.webdriver.support.wait import WebDriverWait
import logging
import configparser
import openpyxl
from openpyxl.utils import get_column_letter
from datetime import datetime

from base_web_bot import BaseWebBot
from soc_base_mixin import SOC_BaseMixin


class SOC_Exporter(BaseWebBot, SOC_BaseMixin):
    """
    Specialized bot for exporting SOC (Safety Override Certificate) overrides table to Excel.

    This exporter combines web automation with Excel file generation to extract
    SOC override data with complete re-import capability. It handles:
    - SOC authentication and navigation
    - Kendo Grid data extraction
    - Excel file creation with proper formatting
    - Error handling and user feedback

    The exported data includes all essential fields needed for potential re-import
    operations, making it a complete data backup solution.
    """

    def __init__(self, soc_id=None):
        """Initialize the SOC exporter with combined base and mixin functionality."""
        BaseWebBot.__init__(self)
        SOC_BaseMixin.__init__(self)
        self.load_configuration()
        self.SOC_ID_PATTERN = r"^\d{7,8}$"  # Standard SOC ID pattern
        self.SOC_id = None  # Will be set during user input

        # Use provided SOC ID or maintain existing logic
        if soc_id:
            self.SOC_id = soc_id

    def set_soc_id(self, soc_id: str) -> None:
        """Set SOC ID externally for unified workflow."""
        self.SOC_id = soc_id

    @property
    def base_link(self) -> str:
        """Abstract property implementation - returns the base URL for navigation."""
        return self._base_link

    # ===== CONFIGURATION MANAGEMENT =====

    def load_configuration(self) -> None:
        """
        Load configuration settings from the INI file.

        Reads user credentials, application URLs, and timeout settings from
        the SOC.ini configuration file.
        """
        config = configparser.ConfigParser(interpolation=None)
        config.read(self.config_file, encoding="utf8")

        # Load authentication and application settings
        self.user_name = config.get('Settings', 'user_name', fallback='xxxxxx')

        # Process password with base64 decoding fallback
        raw_password = config.get('Settings', 'password', fallback='******')
        self.password = self.process_password(raw_password)

        # Check for password formatting issues
        if '\n' in self.password:
            self.password = 'INCORRECT PASSWORD'

        self._base_link = config.get('Settings', 'base_link', fallback='http://eptw.sakhalinenergy.ru/')
        self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS = config.getint('Settings', 'MAX_WAIT_PAGE_LOAD_DELAY_SECONDS', fallback=20)

        logging.info(f"✅ Configuration loaded from {self.config_file}")

    # ===== DATA EXTRACTION METHODS =====

    def check_if_overrides_exist(self) -> bool:
        """
        Check if there are any overrides for this SOC.

        Examines the overrides section on the SOC Details page to determine
        if there is data available for export.

        Returns:
            True if overrides exist, False otherwise
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
        Extract the overrides table data from SOC Details page using JavaScript.

        Uses Kendo UI Grid API to extract comprehensive override data including
        all essential fields needed for re-import capability.

        Returns:
            Tuple of (headers, rows) where:
            - headers: List of column names
            - rows: List of data rows with override information
        """
        try:
            logging.info("🔍 Extracting SOC overrides table data via JavaScript...")

            # First check if overrides exist
            if not self.check_if_overrides_exist():
                logging.info("ℹ️  No overrides data available for extraction")
                return [], []

            # Wait for Kendo framework to load
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                lambda _: self.driver.execute_script("return typeof kendo !== 'undefined'")
            )

            # Wait for the Overrides grid to be initialized and have data
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                lambda _: self.driver.execute_script("""
                    var grid = $('#Overrides').data('kendoGrid');
                    return grid && grid.dataSource && grid.dataSource.data().length > 0;
                """)
            )

            # Enhanced extraction script with all essential fields for re-import
            script = """
            var grid = $('#Overrides').data('kendoGrid');
            if (!grid || !grid.dataSource) return null;

            var data = grid.dataSource.data();
            if (data.length === 0) return null;

            // Essential fields for re-import capability
            var headers = [
                'TagNumber',
                'Description',
                'OverrideType',
                'OverrideMethod',
                'AppliedState',
                'RemovedState',
                'Comment',
                'AdditionalValueAppliedState',
                'AdditionalValueRemovedState',
                'CurrentState'
            ];

            var rows = data.map(item => [
                item.TagNumber || '',
                item.Description || '',
                // Extract OverrideType display text (ShortForm preferred, fallback to Title)
                item.OverrideType ? (item.OverrideType.ShortForm || item.OverrideType.Title || '') : '',
                // Extract OverrideMethod display text (ShortForm preferred, fallback to Title)
                item.OverrideMethod ? (item.OverrideMethod.ShortForm || item.OverrideMethod.Title || '') : '',
                // Extract AppliedState display text
                item.OverrideAppliedState ? (item.OverrideAppliedState.Title || '') : '',
                // Extract RemovedState display text
                item.OverrideRemovedState ? (item.OverrideRemovedState.Title || '') : '',
                item.Comment || '',
                item.AdditionalValueAppliedState || '',
                item.AdditionalValueRemovedState || '',
                // Extract CurrentState for reference
                item.CurrentState ? (item.CurrentState.Title || '') : ''
            ]);

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
                logging.info(f"📊 Extracted fields: {', '.join(headers)}")
                return headers, rows

            logging.info("ℹ️  No valid data extracted from Kendo Grid")
            return [], []

        except TimeoutException:
            logging.warning("⚠️  Timeout waiting for overrides data to load")
            return [], []
        except Exception as e:
            logging.error(f"❌ Failed to extract SOC overrides table: {str(e)}")
            return [], []

    # ===== NAVIGATION METHODS =====

    def navigate_to_soc_details(self) -> None:
        """
        Navigate to SOC Details page and verify successful loading.

        Constructs the SOC Details URL and performs various validation checks
        to ensure the page loaded correctly.
        """
        try:
            soc_details_url = self.base_link + f"Soc/Details/{self.SOC_id}"
            logging.info(f"🌐 Navigating to SOC Details: {soc_details_url}")

            self.driver.get(soc_details_url)

            # Wait for page to fully load
            WebDriverWait(self.driver, self.MAX_WAIT_PAGE_LOAD_DELAY_SECONDS).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )

            # Check for 404 error using mixin method
            self.error_404_not_present_check()

            # Verify we're on SOC Details page using mixin method
            self.url_contains_SOC_Details_check()

            logging.info("✅ Successfully navigated to SOC Details page")
        except Exception as e:
            logging.error(f"❌ Failed to navigate to SOC Details: {str(e)}")
            self.inject_error_message(f"❌ Navigation failed: {str(e)}")

    # ===== EXCEL EXPORT METHODS =====

    def create_excel_file(self, headers: list, rows: list, filename: str = None) -> bool:
        """
        Create Excel file with SOC overrides data using openpyxl.

        Generates a formatted Excel file with:
        - Metadata header with export information
        - Bold column headers
        - Auto-adjusted column widths
        - Timestamp in filename for uniqueness

        Args:
            headers: List of column names for the data
            rows: List of data rows to export
            filename: Optional custom filename, auto-generated if not provided

        Returns:
            True if file was created successfully, False otherwise
        """
        if not headers or not rows:
            logging.error("❌ No data available to create Excel file")
            return False

        try:
            # Generate filename with timestamp if not provided
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"soc_import_export/SOC_{self.SOC_id}_overrides_{timestamp}.xlsx"

            workbook = openpyxl.Workbook()
            sheet = workbook.active
            sheet.title = f'SOC_{self.SOC_id}'

            # Add metadata header
            sheet.cell(row=1, column=1, value="SOC Overrides Export")
            sheet.cell(row=2, column=1, value=f"SOC ID: {self.SOC_id}")
            sheet.cell(row=3, column=1, value=f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            sheet.cell(row=4, column=1, value=f"Total Overrides: {len(rows)}")

            # Write headers with bold formatting (starting from row 6)
            header_row = 6
            for col_index, header in enumerate(headers, 1):
                cell = sheet.cell(row=header_row, column=col_index, value=header)
                cell.font = openpyxl.styles.Font(bold=True)

            # Write data rows (starting from row 7)
            for row_index, row_data in enumerate(rows, header_row + 1):
                for col_index, cell_value in enumerate(row_data, 1):
                    sheet.cell(row=row_index, column=col_index, value=cell_value)

            # Auto-adjust column widths for better readability
            self._auto_adjust_column_widths(sheet, headers, rows)

            workbook.save(filename)
            logging.info(f"💾 Successfully saved SOC overrides to: {filename}")
            logging.info(f"📝 Export includes {len(rows)} overrides with fields: {', '.join(headers)}")
            return True

        except Exception as e:
            logging.error(f"❌ Failed to create Excel file: {str(e)}")
            return False

    def _auto_adjust_column_widths(self, sheet, headers: list, rows: list) -> None:
        """
        Automatically adjust column widths based on content length.

        Calculates optimal column widths by finding the maximum length of
        content in each column and applies appropriate widths.

        Args:
            sheet: The openpyxl worksheet to adjust
            headers: List of column headers
            rows: List of data rows
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

            # Apply calculated widths (starting from column A for data headers)
            for col_index, max_len in enumerate(max_lengths, 1):
                adjusted_width = min(max_len + 2, 50)  # Cap at 50 characters
                column_letter = get_column_letter(col_index)
                sheet.column_dimensions[column_letter].width = adjusted_width

            logging.debug(f"📐 Adjusted {len(max_lengths)} column widths")

        except Exception as e:
            logging.warning(f"⚠️  Could not auto-adjust column widths: {str(e)}")

    # ===== MAIN EXPORT WORKFLOW =====

    def extract_and_export_overrides(self) -> None:
        """
        Extract overrides data and export to Excel file.

        Main export method that coordinates data extraction and file creation,
        providing appropriate user feedback for both success and failure scenarios.
        """
        try:
            # Extract table data with enhanced fields
            headers, rows = self.extract_overrides_table_data()

            if not headers or not rows:
                info_msg = f"ℹ️  No overrides data found for SOC {self.SOC_id}. This SOC may not have any overrides configured."
                logging.info(info_msg)
                # Use _inject_message_with_wait to display message and wait for browser close
                self._inject_message_with_wait(info_msg, style_addons={'color': 'orange'})
            else:
                # Create Excel file with enhanced data
                if self.create_excel_file(headers, rows):
                    success_msg = f"✅ SOC {self.SOC_id} overrides successfully exported to Excel"
                    logging.info(success_msg)
                    logging.info(f"📊 Exported {len(rows)} overrides with complete re-import capability")
                    # Use _inject_message_with_wait to display success message and wait for browser close
                    self._inject_message_with_wait(success_msg, style_addons={'color': 'green'})
                else:
                    error_msg = f"❌ Failed to save Excel file for SOC {self.SOC_id}"
                    self.inject_error_message(error_msg)
                    # Use _inject_message_with_wait for error case too
                    self._inject_message_with_wait(error_msg, style_addons={'color': 'red'})

        except Exception as e:
            logging.error(f"❌ Error during extraction and export: {str(e)}")
            error_msg = f"❌ Error during extraction and export: {str(e)}"
            self._inject_message_with_wait(error_msg, style_addons={'color': 'red'})

    # ===== AUTOMATION WORKFLOW COORDINATION =====

    def run(self, standalone=False):
        """
        Main automation workflow for exporting SOC overrides to Excel.

        Execution sequence:
        1. Navigate to base URL and prepare for authentication
        2. Enter credentials and prepare SOC ID input
        3. Wait for SOC ID input and submit form
        4. Navigate to SOC Details page
        5. Extract data and export to Excel
        6. Provide completion feedback

        Enhanced with comprehensive logging and error handling throughout the process.
        """
        try:
            logging.info("🚀 Starting SOC to Excel export automation")

            if standalone:
                self.navigate_to_base()
                self.enter_credentials_and_prepare_soc_input()
                self.wait_for_soc_input_and_submit()

            # Navigate to SOC details page
            self.navigate_to_soc_details()

            # Extract data and export to Excel
            self.extract_and_export_overrides()

            # Show final completion message
            completion_msg = "🏁 SOC export automation completed successfully"
            logging.info(completion_msg)
            self._inject_message_with_wait(completion_msg, style_addons={'color': 'blue'})

        except Exception as e:
            logging.error(f"❌ SOC automation failed: {str(e)}")
            error_msg = f"❌ SOC automation failed: {str(e)}"
            try:
                self._inject_message_with_wait(error_msg, style_addons={'color': 'red'})
            except:
                # If injection fails, just quit safely
                self.safe_exit()


if __name__ == "__main__":
    # Entry point for script execution
    bot = SOC_Exporter()
    bot.run(standalone=True)