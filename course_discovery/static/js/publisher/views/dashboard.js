
$(document).ready(function() {
    var data_table_studio = $('.data-table-studio').DataTable({
        "autoWidth": false
    });

    data_table_studio.on('click', '.btn-add-course-key', function(e){
        var $courseRunParentTag = $(this).parent().parent(),
            courseKeyInput = $courseRunParentTag.find('input');

        if (!courseKeyInput.val().trim()){
            courseKeyInput.focus();
            return;
        }

        var updateCourseKeyURL = $(this).data('update-course-key-url'),
            courseKeyValue = courseKeyInput.val().trim(),
            courseTitleTag = $courseRunParentTag.find("#course-title").html().trim(),
            startDateTag = $courseRunParentTag.find("#course-start").html().trim(),
            $studioInstanceSuccess = $(".studio-instance-success"),
            successMessage = interpolateString(
                gettext("You have successfully created a studio instance ({studioLinkTag}) for {courseRunDetail} with a start date of {startDate}"),
                {
                    "studioLinkTag": "<a href=''>"+ courseKeyValue +"</a>",
                    "courseRunDetail": courseTitleTag,
                    "startDate": startDateTag
                }
            );
        e.preventDefault();

        $.ajax({
            url: updateCourseKeyURL,
            type: "PATCH",
            data: JSON.stringify({lms_course_id: courseKeyValue}),
            contentType: "application/json",
            success: function (response) {
                data_table_studio.row($courseRunParentTag).remove().draw();
                $("#studio-count").html(data_table_studio.rows().count());
                $studioInstanceSuccess.find(".copy-meta").html(successMessage);
                $studioInstanceSuccess.css("display", "block");
            }
        });
    });

    $('.data-table-published').DataTable({
        "autoWidth": false
    });

     $('.data-table-preview').DataTable({
          "autoWidth": false
     });

    $('.data-table-in-progress').DataTable({
        "autoWidth": false
    });

});
