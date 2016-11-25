
$.ajaxSetup({
    headers: {
        'X-CSRFToken': Cookies.get('course_discovery_csrftoken')
    }
});
