# Data Separation Fix - Liquor & Grocery Apps

## Problem
Both apps (Liquor and Grocery) were using the same MongoDB database with overlapping collection names, causing data to mix:
- `upload_history` was shared between both apps
- Both apps could see each other's upload records
- No clear separation of data

## Solution
Added app-specific prefixes to all collections to ensure complete data isolation.

---

## Liquor App Collections (FIXED)

### New Collection Names:
- **liquor_data** → `liquor_data` (main liquor sales data)
- **upload_history** → `liquor_upload_history` ✅ NOW SEPARATED
- **stock_backups** → `liquor_stock_backups` ✅ NOW SEPARATED
- **brands_master** → `liquor_brands_master` ✅ NOW SEPARATED

### Code Changes:
Added in `/app/backend/server.py`:

```python
# Collection name prefixes for data separation
LIQUOR_PREFIX = "liquor_"

# Collection references with proper prefixing
class Collections:
    @property
    def liquor_data(self):
        return db[f"{LIQUOR_PREFIX}data"]
    
    @property
    def upload_history(self):
        return db[f"{LIQUOR_PREFIX}upload_history"]
    
    @property
    def stock_backups(self):
        return db[f"{LIQUOR_PREFIX}stock_backups"]
    
    @property
    def brands_master(self):
        return db[f"{LIQUOR_PREFIX}brands_master"]

collections = Collections()
```

All references changed from `db.liquor_data` to `collections.liquor_data`, etc.

---

## Grocery App Collections (TO BE APPLIED)

### New Collection Names:
- **sales_records** → `grocery_sales_records` ✅
- **upload_history** → `grocery_upload_history` ✅ NOW SEPARATED
- **stock_backups** → `grocery_stock_backups` ✅
- **financial_data** → `grocery_financial_data` ✅

### Code to Add:
Fixed file available at: `/tmp/server_grocery_fixed.py`

```python
# Collection name prefixes for data separation
GROCERY_PREFIX = "grocery_"

# Collection references with proper prefixing
class Collections:
    @property
    def sales_records(self):
        return db[f"{GROCERY_PREFIX}sales_records"]
    
    @property
    def upload_history(self):
        return db[f"{GROCERY_PREFIX}upload_history"]
    
    @property
    def stock_backups(self):
        return db[f"{GROCERY_PREFIX}stock_backups"]
    
    @property
    def financial_data(self):
        return db[f"{GROCERY_PREFIX}financial_data"]

collections = Collections()
```

---

## MongoDB Structure After Fix

```
MongoDB Atlas Cluster
└── Database: URCloh1LiquorSales (or your DB_NAME)
    ├── liquor_data              ← Liquor sales data
    ├── liquor_upload_history    ← ONLY liquor uploads ✅
    ├── liquor_stock_backups     ← ONLY liquor backups ✅
    ├── liquor_brands_master     ← ONLY liquor brands ✅
    ├── grocery_sales_records    ← ONLY grocery sales ✅
    ├── grocery_upload_history   ← ONLY grocery uploads ✅
    ├── grocery_stock_backups    ← ONLY grocery backups ✅
    └── grocery_financial_data   ← ONLY grocery finances ✅
```

---

## Benefits

✅ **Complete Data Isolation**: Each app only sees its own data
✅ **No More Mixed Upload History**: Liquor app shows only liquor uploads
✅ **Future-Proof**: Easy to add more apps with different prefixes
✅ **Same Database**: No need to split into multiple databases
✅ **Backward Compatible**: Old data stays where it is (new uploads use new collections)

---

## Deployment Steps

### For Liquor App (ALREADY DONE):
1. ✅ Code updated in this repo
2. Commit and push to GitHub:
   ```bash
   git add backend/server.py
   git commit -m "Add collection prefixing for data separation"
   git push origin main
   ```
3. Render will auto-deploy

### For Grocery App (YOUR NEXT STEP):
1. Get the fixed file from `/tmp/server_grocery_fixed.py`
2. Replace your grocery app's `server.py` with this fixed version
3. Commit and push to GitHub
4. Render will auto-deploy

---

## Migration of Old Data (Optional)

If you want to move existing data to the new prefixed collections:

**Liquor App:**
```javascript
// In MongoDB Atlas, run these commands:
db.upload_history.find({/* liquor app uploads */}).forEach(doc => {
    db.liquor_upload_history.insert(doc);
});
```

**Grocery App:**
```javascript
// In MongoDB Atlas, run these commands:
db.upload_history.find({/* grocery app uploads */}).forEach(doc => {
    db.grocery_upload_history.insert(doc);
});
```

Or simply start fresh - new uploads will go to the correct collections automatically.

---

## Testing

**After deploying both apps:**

1. **Test Liquor App:**
   - Upload a liquor file
   - Go to Uploads tab
   - Should ONLY see liquor uploads

2. **Test Grocery App:**
   - Upload a grocery file
   - Go to upload history
   - Should ONLY see grocery uploads

3. **Check MongoDB Atlas:**
   - Should see new collections with prefixes
   - Old collections remain untouched (for reference)

---

## Questions?
Contact: [Your Support Channel]
Date: November 30, 2025
