# Liquor Sales Analytics Dashboard - Deployment & Usage Guide

## 🌐 How to Access Your Dashboard

### Option 1: Web Application (Current Setup)
Your dashboard is currently running as a **web application** on the Emergent platform at:
**URL:** https://liquor-dashboard.preview.emergentagent.com

- ✅ **No Installation Required** - Access from any device with a web browser
- ✅ **Always Up-to-Date** - Automatic updates and maintenance
- ✅ **Cross-Platform** - Works on Windows, Mac, Linux, tablets, and phones
- ✅ **Secure Cloud Storage** - Your data is safely stored in MongoDB cloud

### Option 2: Local Installation (Advanced Users)

If you want to run this on your own system, you have several options:

#### A) Docker Installation (Recommended)
```bash
# 1. Install Docker Desktop from https://docker.com
# 2. Clone or download the application files
# 3. Run the application
docker-compose up -d
```

#### B) Manual Installation
**Requirements:**
- Node.js 18+ (for frontend)
- Python 3.11+ (for backend) 
- MongoDB (for database)

**Setup Steps:**
1. **Frontend Setup:**
   ```bash
   cd frontend
   npm install
   npm start
   ```

2. **Backend Setup:**
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn server:app --reload --host 0.0.0.0 --port 8001
   ```

3. **Database Setup:**
   ```bash
   # Install MongoDB locally or use MongoDB Atlas
   # Update MONGO_URL in backend/.env
   ```

#### C) Executable File (.exe) - Future Option
Currently, this is a **web application**, not a desktop executable. However, we can create an executable file using:

- **Electron** (for desktop app wrapper)
- **PyInstaller** (for standalone Python executable)
- **Docker Desktop** (for containerized local deployment)

*Would you like me to create a desktop executable version?*

---

## 📊 Using Your Dashboard

### Quick Start Guide

1. **Access the Dashboard**
   - Open https://liquor-dashboard.preview.emergentagent.com in your browser
   - Click "Help Guide" for interactive onboarding

2. **Upload Your Data**
   - Click "Upload Data" button
   - Select your Excel file (.xlsx, .xls, or .csv)
   - Wait for processing (usually takes 5-10 seconds)

3. **Analyze Results**
   - View key metrics in dashboard cards
   - Check "Overstocking Alerts" tab for problem areas
   - Review "Brand Performance" for top sellers
   - Monitor "Sales Trends" for patterns

### Data Format Requirements

Your Excel file should contain these columns:
- **Brand Name** - Name of the liquor brand
- **Rate** - Price per unit
- **Daily Sales Columns** - Date format like "25-Aug-25", "26-Sep-25"
- **Monthly Sale value (a)** - Total monthly sales value
- **Stock value Today** - Current inventory value

### Overstock Configuration

- **Default:** 3x monthly average (recommended)
- **Conservative:** 2x monthly average (stricter control)
- **Relaxed:** 4x or 5x monthly average (more tolerance)

---

## 🔧 Technical Architecture

### Current Tech Stack
- **Frontend:** React 19 + Tailwind CSS
- **Backend:** FastAPI (Python)
- **Database:** MongoDB
- **Hosting:** Emergent Cloud Platform

### System Requirements
- **Browser:** Chrome, Firefox, Safari, Edge (latest versions)
- **Internet:** Stable connection required
- **File Size:** Up to 10MB Excel files supported

---

## 🚀 Deployment Options Summary

| Option | Pros | Cons | Best For |
|--------|------|------|----------|
| **Web App (Current)** | No setup, auto-updates, accessible anywhere | Requires internet | Most users |
| **Docker Local** | Full control, works offline | Technical setup required | IT teams |
| **Manual Install** | Complete customization | Complex setup | Developers |
| **Desktop .exe** | Simple install, offline use | Limited updates | Single users |

---

## 📞 Support & Questions

If you need help with:
- **Deployment issues** - Contact technical support
- **Data format questions** - Use the built-in help guide
- **Custom features** - Request enhancements
- **Desktop version** - Let us know if you need an .exe file

**Current Status:** Your dashboard is live and ready to use at the web URL above! 🎉