# Django 5.2 Fix: Course Dropdown Search Not Working

## Problem Summary
After upgrading from Django 4.7 to 5.2, the course searchable fields dropdown was showing the error:
```
jQuery.Deferred exception: $(...).select2 is not a function
```

This indicates that the Select2 JavaScript library is not being loaded before the admin tries to use it.

## Root Cause
In Django 5.2, changes were made to how Media classes are loaded in admin interfaces. The Admin Media classes were missing the Select2 CSS/JS files required by django-autocomplete-light.

The load order was:
1. jQuery (loaded)
2. admin/js/autocomplete.js (tries to call `.select2()` - FAILS because Select2 is not loaded)
3. Select2 JS (never loaded)

## Solution

### 1. Created DALAdminMixin (line ~67 in admin.py)
A mixin class that ensures Select2 and autocomplete assets are properly loaded:
```python
class DALAdminMixin(admin.ModelAdmin):
    """
    Mixin for Django admin classes using django-autocomplete-light.
    Ensures Select2 library is properly loaded before autocomplete.js.
    Required for Django 5.2 compatibility.
    """
    class Media:
        css = {
            'all': (
                'admin/css/autocomplete.css',
                'select2/dist/css/select2.css',
                'dal_select2/dist/css/choices.css',
            )
        }
        js = (
            'select2/dist/js/select2.js',
            'admin/js/autocomplete.js',
        )
```

### 2. Updated CourseAdmin (line 161)
Changed from:
```python
class CourseAdmin(DjangoObjectActions, SimpleHistoryAdmin):
```
To:
```python
class CourseAdmin(DALAdminMixin, DjangoObjectActions, SimpleHistoryAdmin):
```

### 3. Updated ProgramAdmin (line 476)
Changed from:
```python
class ProgramAdmin(DjangoObjectActions, SimpleHistoryAdmin):
```
To:
```python
class ProgramAdmin(DALAdminMixin, DjangoObjectActions, SimpleHistoryAdmin):
```

### 4. Updated CourseAdmin and ProgramAdmin Media Classes
Both now include Select2 CSS/JS in the correct order:
```python
class Media:
    css = {
        'all': (
            'admin/css/autocomplete.css',
            'select2/dist/css/select2.css',
            'dal_select2/dist/css/choices.css',
        )
    }
    js = (
        'select2/dist/js/select2.js',
        'admin/js/autocomplete.js',
        'bower_components/jquery-ui/ui/minified/jquery-ui.min.js',
        'bower_components/jquery/dist/jquery.min.js',
        SortableSelectJSPath()
    )
```

### 5. Updated widgets.py
Removed the non-existent import and ensured proper media inheritance:
- Removed: `from django.forms.widgets import MediaDefiningWidget`
- Added: Proper media property and get_context override for Django 5.2

## Files Modified
1. `course_discovery/apps/course_metadata/admin.py`
   - Added DALAdminMixin class
   - Updated CourseAdmin and ProgramAdmin to use the mixin
   - Updated Media classes to include Select2

2. `course_discovery/apps/course_metadata/widgets.py`
   - Fixed imports
  - Added proper Django 5.2 compatible media and context handling

## Load Order (Fixed)
1. Select2 CSS loaded
2. django-autocomplete-light CSS loaded
3. Select2 JS loaded ✓
4. admin/js/autocomplete.js loaded (now works because Select2 is available)
5. jQuery loaded
6. sortable_select.js loaded

## Testing the Fix

### Steps to Test:
1. **Restart Discovery Service:**
   ```bash
   make dev.down.discovery
   make dev.up.discovery
   ```

2. **Collect Static Files (if needed):**
   ```bash
   python manage.py collectstatic --noinput
   ```

3. **Clear Browser Cache:**
   - Press Ctrl+Shift+Delete (or Cmd+Shift+Delete on Mac)
   - Clear cached images and files

4. **Test the Dropdown:**
   - Navigate to: `http://127.0.0.1:18381/admin/course_metadata/program/4/change/`
   - Scroll to the "Courses" field

5. **Expected Behavior:**
   - ✅ Dropdown shows "Select..." placeholder
   - ✅ Click dropdown arrow to see available courses
   - ✅ Type in search box (after 3 characters) to filter courses
   - ✅ AJAX request made to `/course-autocomplete/?q=<search_term>`
   - ✅ Results appear and can be selected
   - ✅ Multiple items can be selected
   - ✅ Selected items maintain their sort order

### Troubleshooting:
If you still see the Select2 error after restart:

1. **Check Browser Console (F12):**
   - Look for any new errors
   - Verify Select2 library is loaded in Network tab

2. **Verify Static Files:**
   ```bash
   python manage.py collectstatic --clear --noinput
   ```

3. **Check Django Admin is Using the Media:**
   - Inspect the page source (Ctrl+U)
   - Search for "select2" - should find CSS and JS links

4. **Check Your Settings:**
   - Ensure 'dal' and 'dal_select2' are in INSTALLED_APPS
   - Verify STATIC_URL is set correctly

## Django 5.2 Specific Notes
- Widget Media inheritance changed - now requires explicit `@property` method
- Admin Media loading order is stricter
- get_context() method needs to handle widget attributes properly
- Static file collection requirements are more strict

## References
- django-autocomplete-light docs: https://django-autocomplete-light.readthedocs.io/
- Django 5.2 release notes: Widget rendering changes
- Select2 documentation: https://select2.org/
