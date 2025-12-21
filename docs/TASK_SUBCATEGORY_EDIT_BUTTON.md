# Task: Add Subcategory/Category Name Edit Buttons
**Date:** 2025.12.21
**Status:** ✅ Completed

## Overview
Added UI functionality to edit subcategory and category names on the Tags settings page. This feature allows users to rename both People Tags subcategories and Organization Tags categories directly from the settings interface.

## Completed Work

### 1. People Tags - Subcategory Edit Button
**File Modified:** `app/templates/settings/index.html`
**Location:** Lines 640-648, 1150-1173

**Features:**
- Edit button (pencil icon) added before color picker in subcategory header
- JavaScript function `editSubcategoryName()` prompts for new name
- Backend API `PUT /tags/subcategories/{id}` handles renaming
- Updates all tags that reference the subcategory
- Button order: Edit → Color Picker → Apply → Delete

**Backend:** Already existed at `app/routers/tags.py` (lines 657-705)

### 2. Organization Tags - Category Edit & Color Management
**Files Modified:**
- `app/templates/settings/index.html` (UI and JavaScript)
- `app/routers/tags.py` (Backend endpoints)

**Features Added:**

#### A. Edit Category Name
- Edit button (pencil icon) for both "Firm Category" and "Company Category"
- JavaScript function `editCategoryName()` (lines 1213-1237)
- Backend API `PUT /tags/categories` (lines 846-888)
- Validates uniqueness and updates all tags with new category name

#### B. Apply Color to All Tags in Category
- Color picker input for selecting category color
- "Apply" button to apply color to all tags in category
- JavaScript function `applyCategoryColor()` (lines 1239-1272)
- Backend API `POST /tags/categories/apply-color` (lines 891-926)
- Confirms action before applying color to all tags

#### C. Consistent UI Layout
Updated Organization Tags section to match People Tags formatting:
- **Firm Category** (lines 812-859): Edit → Color Picker → Apply → Add
- **Company Category** (lines 923-970): Edit → Color Picker → Apply → Add
- All buttons in same action bar on right side
- Consistent styling and behavior

## Backend Endpoints Created

### 1. PUT /tags/categories
**Purpose:** Rename a category across all tags
**Request:** Form data with `old_name` and `new_name`
**Response:** Success status with update count
**Features:**
- Validates names are not empty
- Checks for duplicate category names
- Updates all tags with the old category name
- Returns count of updated tags

### 2. POST /tags/categories/apply-color
**Purpose:** Apply a color to all tags in a category
**Request:** JSON with `category` and `color`
**Response:** Success status with update count
**Features:**
- Validates category and color parameters
- Updates color for all tags in category
- Returns count of updated tags

## Testing Completed
✅ Local server running successfully
✅ Edit subcategory name (People Tags)
✅ Edit category name (Organization Tags)
✅ Apply color to category (Organization Tags)
✅ UI consistency between sections
✅ Backend validation and error handling

## Files Modified
1. `app/templates/settings/index.html` - UI and JavaScript
2. `app/routers/tags.py` - Backend API endpoints

## Next Steps for Deployment
1. Test locally: http://localhost:8000/settings?tab=tags
2. Commit changes to git
3. Push to repository
4. Deploy to Synology following standard workflow
5. Run database migrations if needed (none required for this feature)

## User-Facing Benefits
- ✅ Rename subcategories without manual database updates
- ✅ Rename organization tag categories
- ✅ Apply consistent colors to all tags in a category
- ✅ Unified, consistent UI across People and Organization tags
- ✅ Better tag management and organization
