
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
            $studioInstanceError = $(".studio-instance-error"),
            successMessage = interpolateString(
                gettext("You have successfully created a Studio URL ({studioLinkTag}) for {courseRunDetail} with a start date of {startDate}"),
                {
                    "studioLinkTag": "<a href=''>"+ courseKeyValue +"</a>",
                    "courseRunDetail": courseTitleTag,
                    "startDate": startDateTag
                }
            );
        e.preventDefault();
        $studioInstanceError.addClass("hidden");

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
            },
            error: function (response) {
                if(response.responseJSON.lms_course_id) {
                    $studioInstanceError.find(".copy").html(response.responseJSON.lms_course_id['lms_course_id']);
                    if (!response.responseJSON.lms_course_id['lms_course_id']){
                        $studioInstanceError.find(".copy").html(response.responseJSON['lms_course_id'][0]);
                    }
                } else if(response.responseJSON.detail) {
                    $studioInstanceError.find(".copy").html(response.responseJSON.detail);
                } else {
                    $studioInstanceError.find(".copy").html(gettext("There was an error in saving your data."));
                }
                $studioInstanceError.removeClass("hidden");
            }
        });
    });

    $('.data-table-published').DataTable({
        "autoWidth": false
    });

     $('.data-table-preview').DataTable({
         "autoWidth": false
     });

    var inProgressTable = $('.data-table-in-progress').DataTable({
        "autoWidth": false
    });

    $('.btn-filter').click( function (e) {
        var searchValue = 'In Review|In Draft',
            currentFilterColumn = $(this).data('filter-column'),
            oldFilterColumn = $('.btn-filter.active').data('filter-column');
        e.preventDefault();
        $('.btn-filter').removeClass('active');
        $(this).addClass('active');

        if (currentFilterColumn == -1) {
            applyCustomFilter(inProgressTable, oldFilterColumn, '');
        } else {
            if (oldFilterColumn != -1) {
                // Clear previous filter if applied otherwise search will return no record.
                applyCustomFilter(inProgressTable, oldFilterColumn, '');
            }
            applyCustomFilter(inProgressTable, currentFilterColumn, searchValue);
        }
    });

});

function applyCustomFilter(dataTable, columnIndex, value) {
    dataTable.columns(columnIndex).search(value, true, false).draw();
}
