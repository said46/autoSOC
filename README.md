SOC Automation Suite
A comprehensive Python-based automation framework for SOC (Safety Override Control) operations using Selenium WebDriver. 
This suite provides tools for controlling, exporting, and importing SOC overrides in electronic permit to work systems (ePTW).

📋 Overview
This project consists of several specialized bots that automate SOC operations:
SOC Controller - Main automation for SOC role processing and status management of override points
SOC Exporter - Extracts SOC overrides data to Excel format
SOC Importer - Imports SOC overrides from Excel files
SOC Launcher - Unified launcher with radio button selection between all modes

🏗️ Project Structure
text
soc-automation/
├── soc_controller.py      # Main SOC processing bot
├── soc_exporter.py        # SOC data export to Excel
├── soc_importer.py        # SOC data import from Excel
├── soc_launcher.py        # Unified launcher with mode selection
├── soc_base_mixin.py      # Shared SOC functionality
├── base_web_bot.py        # Base web automation class
├── soc_DB.py             # Database operations
├── error_types.py         # Error handling definitions
├── logging_setup.py       # Logging configuration
└── SOC.ini               # Configuration file

🚀 Features
Core Capabilities
Automated SOC Processing - Handles role switching and status management
Excel Export/Import - Bidirectional data transfer between web app and Excel
Smart Validation - Real-time SOC ID validation with database lookup
Cascade Handling - Advanced dropdown cascade management in forms
Error Recovery - Comprehensive error handling with severity levels

Technical Features
Session Reuse - Maintains browser sessions between operations
Kendo UI Support - Specialized handling for Kendo UI widgets
Database Integration - Optional SQL Server connectivity for SOC ID resolution
Configurable Timeouts - Adaptive waiting for user input and page loads
Visual Feedback - Real-time UI updates and status messages

🛠️ Installation
Prerequisites
Python 3.8+

Chrome browser
ChromeDriver (automatically managed by Selenium)

Dependencies
bash
pip install selenium openpyxl pymssql configparser colorama

⚙️ Configuration
Edit SOC.ini to configure:

ini
[Settings]
user_name = your_username
password = base64_encoded_password
base_link = http://eptw-training.sakhalinenergy.ru/
MAX_WAIT_USER_INPUT_DELAY_SECONDS = 3600
MAX_WAIT_PAGE_LOAD_DELAY_SECONDS = 20

[Roles]
SOC_roles = OAC,OAV
OAC = Исполняющий форсирование
OAV = Проверяющий форсирование

[Statuses]
good_statuses = принято для установки-запрошено для удаления-установлено, не подтверждено-удалено, не подтверждено
SOC_status_approved_for_apply = одобрено для установки

[Database]
CONNECT_TO_DB_FOR_PARTIAL_SOC_ID = True
server = your_server
database = your_database
username = your_username
password = base64_encoded_db_password
🎯 Usage
Using the Launcher (Recommended)
bash
python soc_launcher.py
The launcher provides a unified interface with radio buttons to select between:

🚀 Control - Process SOC roles and status changes
⏩ Export - Export overrides to Excel
⏪ Import - Import overrides from Excel

Individual Modules
bash
# Run controller directly
python soc_controller.py

# Export SOC data
python soc_exporter.py

# Import SOC data  
python soc_importer.py

📊 Excel Format
Export Format
The exporter creates Excel files with the following structure:

Rows 1-4: Metadata (SOC ID, export date, record count)
Row 5: Empty spacing
Row 6: Headers (bold with gray background)
Rows 7+: Data records

Import Format
The importer expects Excel files with these columns:
TagNumber
Description
OverrideType
OverrideMethod
Comment
AppliedState
AdditionalValueAppliedState
RemovedState
AdditionalValueRemovedState

🔧 Advanced Features
Database Integration
Enable CONNECT_TO_DB_FOR_PARTIAL_SOC_ID in configuration to resolve partial SOC IDs (4-6 digits) to full 7-8 digit IDs using SQL Server queries.

Password Security
Passwords are base64 encoded in the configuration file for basic obfuscation.

Error Handling
Three-tier error severity system:
RECOVERABLE - Continue execution with warning
FATAL - Stop execution with error message
TERMINAL - Browser closed, clean exit

Cascade Management
The importer handles complex dropdown cascades:
Type → Method → Applied State dependencies

Dynamic field visibility
Smart waiting for widget readiness

🐛 Troubleshooting
Common Issues
Browser Not Starting
Check Chrome installation
Verify ChromeDriver compatibility

Login Failures
Verify credentials in SOC.ini
Check password encoding

SOC ID Not Found
Enable database lookup for partial IDs

Verify SOC ID format (7-8 digits)

Timeout Errors
Adjust MAX_WAIT_PAGE_LOAD_DELAY_SECONDS
Check network connectivity

Logs
Detailed logs are saved to [module_name].log with timestamps and function tracing.

🤝 Contributing
Fork the repository
Create a feature branch
Make changes with proper error handling
Test all three modes (control, export, import)
Submit a pull request

📄 License
This project is for internal use at Sakhalin Energy.

🏆 Best Practices
Always test with the training environment first
Monitor logs for unexpected behavior
Validate Excel files before import

Note: This automation suite is designed for specific SOC workflows at Sakhalin Energy and may require modifications for other implementations.
