# 🏃‍♂️ RunSync

**RunSync** is a personalized fitness data synchronization tool designed specifically for my individual Google Sheets training diary. It automatically manages running activities across multiple platforms, ensuring my training data stays consistent and up-to-date everywhere.

## 🎯 **What does RunSync do?**

RunSync is tailored to my specific training diary structure and solves the common problem of fragmented fitness data by automatically synchronizing activities between:

- **Strava** → **Google Sheets** (Populate my individual training diary structure)
- **Google Sheets** → **P4/P7 Worksheets** (Process data according to my specific calculations)
- **Strava** → **Garmin Connect** (Transfer edited titles and descriptions back to Garmin)

### **Personal Training Diary Workflow**

- **📊 Individual Structure**: Automatically populates my specific Google Sheets training diary format
- **🔄 Smart Data Flow**: Strava activities → Google Sheets → P4/P7 calculations → Garmin titles/descriptions
- **✏️ Edit & Sync**: Edit titles/descriptions in Strava, then sync them back to Garmin Connect
- **📈 Progress Tracking**: Maintain consistent training data across all platforms

### **Key Features**

- ✅ **Personalized Google Sheets integration** tailored to my training diary structure
- ✅ **Smart data processing** with my specific P4/P7 worksheet calculations
- ✅ **Garmin title/description sync** - edit in Strava, sync back to Garmin
- ✅ **Reliable cloud execution** via GitHub Actions
- ✅ **Secure authentication** with password protection
- ✅ **Chrome automation** for Garmin Connect integration
- ✅ **Comprehensive logging** for monitoring and debugging

## 🚀 **How it works**

RunSync operates through a series of automated tasks that can be triggered manually or scheduled:

### **Available Tasks**

1. **📊 Update Sheets Data** (`update_sheets_data`)

   - Syncs all Strava activities since my last incomplete day
   - Processes and updates my specific P4/P7 worksheets with latest data
   - Perfect for maintaining up-to-date training diary analysis

2. **🔄 Transfer to Garmin (Smart)** (`transfer_garmin_stop`)

   - Transfers edited titles and descriptions from Strava back to Garmin Connect
   - Automatically stops at already transferred activities
   - Prevents duplicate entries and overwrites

3. **🔄 Transfer to Garmin (Complete)** (`transfer_garmin_no_stop`)
   - Transfers all edited titles and descriptions from Strava to Garmin Connect
   - No automatic stopping - processes everything
   - Use for initial setup or complete synchronization

### **Execution Methods**

- **🌐 Cloud Execution**: Via GitHub Actions (recommended)
- **💻 Local Execution**: Run directly on your machine
- **⏰ Scheduled**: Automatic daily/weekly execution

## 📋 **Prerequisites**

Before setting up RunSync, ensure you have:

- **GitHub account** with repository access
- **Strava API credentials** (Client ID and Secret)
- **Google Sheets API** service account credentials
- **Garmin Connect account** credentials
- **Python 3.11+** (for local testing)

## 🚀 **Quick Start**

### **Option 1: Cloud Setup (GitHub Actions) - Recommended**

#### **1. Create GitHub Repository**

```bash
# Initialize local repository
git init
git add .
git commit -m "Initial commit"

# Create and connect GitHub repository
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

#### **2. Configure Repository Secrets**

Go to **Settings** → **Secrets and variables** → **Actions** and add:

- `ADMIN_PASSWORD`: Your secure password for authentication
- `SERVICE_ACCOUNT_JSON`: Google Sheets service account credentials
- `DOCUMENT_NAME`: Name of your Google Sheets document
- `CLIENT_ID`: Strava API client ID
- `CLIENT_SECRET`: Strava API client secret
- `GARMIN_EMAIL`: Your Garmin Connect email
- `GARMIN_PASSWORD`: Your Garmin Connect password

#### **3. Execute Tasks**

1. Go to **Actions** in your repository
2. Select **RunSync Tasks**
3. Click **Run workflow**
4. Choose task type and enter password
5. Click **Run workflow**

### **Option 2: Local Setup**

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python main_app.py
```

## 📁 **Project Structure**

```
RunSync/
├── .github/
│   └── workflows/
│       └── runsync.yml          # GitHub Actions Workflow
├── main_app.py                 # Core RunSync functions
├── strava_client.py            # Strava API integration
├── garmin_client.py            # Garmin Connect automation
├── sheets_client.py            # Google Sheets integration
├── requirements.txt            # Python Dependencies
├── strava_tokens.json          # Strava authentication tokens
└── README.md                   # This file
```

## 🎮 **Usage Examples**

### **Daily Training Diary Update**

```bash
# Update my personal training diary with latest activities
Task: update_sheets_data
Result: All Strava activities synced to my Google Sheets, P4/P7 worksheets updated with my specific calculations
```

### **Edit & Sync Workflow**

```bash
# 1. Edit titles/descriptions in Strava
# 2. Sync edited content back to Garmin Connect
Task: transfer_garmin_stop
Result: Edited titles and descriptions now consistent across both platforms
```

### **Complete Title/Description Sync**

```bash
# Transfer all edited titles/descriptions from Strava to Garmin
Task: transfer_garmin_no_stop
Result: All edited content synced back to Garmin Connect
```

## 🔧 **Core Functionality**

### **Personal Training Diary Integration**

- **Individual Structure**: Designed specifically for my Google Sheets training diary format
- **Custom Calculations**: P4/P7 worksheets with my specific analysis formulas
- **Smart Data Flow**: Strava → Google Sheets → P4/P7 processing → Garmin sync

### **Strava Integration**

- **Activity Retrieval**: Fetches all activities from Strava API
- **Data Processing**: Extracts key metrics (distance, time, pace, etc.)
- **Smart Filtering**: Identifies incomplete or missing data for my training diary

### **Google Sheets Integration**

- **Automatic Updates**: Syncs activities to my specific training diary structure
- **P4/P7 Processing**: Calculates advanced running statistics according to my formulas
- **Data Validation**: Ensures consistency across my custom worksheets

### **Garmin Connect Integration**

- **Title/Description Sync**: Transfers edited titles and descriptions from Strava back to Garmin
- **Browser Automation**: Uses Chrome/Selenium for seamless transfer
- **Duplicate Prevention**: Smart detection of already transferred activities
- **Batch Processing**: Handles large numbers of activities efficiently

### **Important Note on Garmin Workflow**

- **Garmin → Strava**: Garmin automatically syncs activities to Strava (built-in feature)
- **Strava → Garmin**: My code transfers edited titles/descriptions back to Garmin Connect
- **Purpose**: After editing titles/descriptions in Strava, sync them back to Garmin for consistency

## 🔒 **Security**

### **Password Protection**

- **Repository Secret** `ADMIN_PASSWORD` for authentication
- **Workflow verification** before each execution

### **Repository Secrets**

```bash
# Generate secure passwords
ADMIN_PASSWORD=$(openssl rand -base64 32)
echo "ADMIN_PASSWORD=$ADMIN_PASSWORD"
```

## 🛠️ **Customization**

### **Change Password**

1. **GitHub Repository** → **Settings** → **Secrets and variables** → **Actions**
2. Edit or recreate **ADMIN_PASSWORD**

### **Add New Functions**

1. Create **Python function** in `main_app.py`
2. Add **workflow step** in `.github/workflows/runsync.yml`
3. Add **task option** in `workflow_dispatch` inputs

## 💡 **Why RunSync?**

### **The Problem**

- **Fragmented Data**: My running data is scattered across multiple platforms
- **Manual Work**: Constantly copying data between Strava, Garmin, and my training diary
- **Inconsistency**: Different platforms show different information
- **Time Wasting**: Hours spent on manual data management for my training diary

### **The Solution**

- **🔄 One-Click Sync**: Automatically keep all platforms in sync with my training diary
- **📊 Smart Analysis**: Advanced calculations in my specific Google Sheets structure
- **⏰ Time Saving**: Hours of manual work reduced to minutes
- **🎯 Consistency**: Same data everywhere, always up-to-date
- **✏️ Edit & Sync**: Edit titles/descriptions in Strava, sync back to Garmin

## 📊 **Monitoring & Logs**

### **Real-time Monitoring**

- **GitHub Actions Logs**: Detailed execution logs
- **Error Debugging**: Comprehensive stack traces
- **Performance Metrics**: Runtime statistics and success rates
- **Activity Tracking**: See exactly what was synced when

## 🚨 **Troubleshooting**

### **Common Issues**

1. **Sync fails**

   - Check API credentials and permissions
   - Verify Google Sheets access
   - Test individual platform connections

2. **Data inconsistencies**

   - Check for duplicate activities
   - Verify date ranges and filters
   - Review activity matching logic

3. **Authentication errors**

   - Refresh Strava tokens
   - Verify Garmin credentials
   - Check Google Sheets service account

4. **Performance issues**
   - Check for large activity batches
   - Monitor API rate limits
   - Review Chrome automation settings

### **Debug Mode**

```bash
# Test locally
python main_app.py

# Check individual components
python -c "from strava_client import StravaClient; print('Strava OK')"
python -c "from sheets_client import SheetsClient; print('Sheets OK')"
python -c "from garmin_client import GarminClient; print('Garmin OK')"
```

## 📈 **Advanced Features**

### **Scheduled Execution**

```yaml
# In .github/workflows/runsync.yml
on:
  schedule:
    - cron: '0 6 * * *' # Daily at 6 AM
```

### **Smart Notifications**

```yaml
# Slack/Discord/Email notifications
- name: Notify on completion
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### **Batch Processing**

```yaml
# Run multiple tasks in parallel
strategy:
  matrix:
    task: [update_sheets_data, transfer_garmin_stop, transfer_garmin_no_stop]
```

### **Data Backup**

```yaml
# Store logs and results as artifacts
- name: Upload logs
  uses: actions/upload-artifact@v4
  with:
    name: runsync-logs
    path: logs/
```

## 🔧 **GitHub Actions Implementation**

### **Concurrency Control**

```yaml
# Prevent multiple runs of the same workflow
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

### **Conditional Execution**

```yaml
# Run only on specific conditions
if: github.event_name == 'workflow_dispatch' && github.event.inputs.task_type == 'update_sheets_data'
```

### **Caching Dependencies**

```yaml
# Cache Python dependencies for faster builds
- name: Cache pip dependencies
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
```

## 🎉 **Get Started Today!**

RunSync is ready to transform your fitness data management. Choose your setup method and start syncing!

### **Quick Links**

- **Cloud Setup**: GitHub Actions (recommended)
- **Local Setup**: Direct Python execution
- **Documentation**: Full API reference and examples

## 📞 **Support & Community**

If you encounter issues:

1. **Check the logs** in GitHub Actions or local execution
2. **Test individual components** using the debug commands
3. **Verify credentials** for all platforms
4. **Review the troubleshooting section** above

### **Getting Help**

- **GitHub Issues**: Report bugs and request features
- **Documentation**: Comprehensive guides and examples
- **Community**: Share experiences and solutions

## 🔗 **Resources**

### **API Documentation**

- [Strava API Documentation](https://developers.strava.com/)
- [Google Sheets API Documentation](https://developers.google.com/sheets/api)
- [Garmin Connect API](https://developer.garmin.com/connect-iq/connect-iq-basics/)

### **Technical Resources**

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Python Setup Action](https://github.com/actions/setup-python)
- [Chrome Setup for Selenium](https://github.com/actions/setup-chrome)

---

**Start syncing your fitness data today!** 🏃‍♂️✨
