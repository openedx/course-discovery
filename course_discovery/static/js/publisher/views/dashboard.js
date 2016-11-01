
$(document).ready(function() {
    $(".dashboard-nav-tabs a").click(function(event) {
        event.preventDefault();
        $(this).parent().addClass("active");
        $(this).parent().siblings().removeClass("active");
        var tab = $(this).attr("href");
        $(".tab-content").not(tab).css("display", "none");
        $(tab).fadeIn();
    });

    $(".btn-add-course-key").click(function(e) {
        var _this = this,
            courseRunPageURL = $(_this).data('courseRunUrl'),
            courseKeyValue = $(_this).parent().find('input').val(),
            headers = {
                'X-CSRFToken': Cookies.get('course_discovery_csrftoken')
            };
        e.preventDefault();

        $.ajax({
            url: courseRunPageURL,
            type: "PATCH",
            data: JSON.stringify({lms_course_id: courseKeyValue}),
            contentType: "application/json",
            headers: headers,
            success: function (response) {
                $(_this).parent().parent().remove();
            }
        });
    });
});