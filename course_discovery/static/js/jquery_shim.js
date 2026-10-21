// Expose django.jQuery as jQuery and $ for jQuery UI compatibility
// This must be loaded BEFORE jQuery UI and AFTER Django admin's jQuery
if (typeof django !== 'undefined' && django.jQuery) {
    window.jQuery = window.$ = django.jQuery;
}
