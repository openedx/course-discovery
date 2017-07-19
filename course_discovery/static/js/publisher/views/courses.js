
$(document).ready(function() {
    var data = $('.course-count-heading').data();
    var $coursesTable = $('#dataTableCourse').DataTable({
        'autoWidth': false,
        'processing': true,
        'serverSide': true,
        'lengthMenu': $('.course-count-heading').data('publisherCoursesAllowedPageSizes'),
        'deferLoading': $('.course-count-heading').data('publisherTotalCoursesCount'),
        'data': $('.course-count-heading').data('publisherCourses'),
        'ajax': {
            'url': $('.course-count-heading').data('publisherCoursesUrl'),
            'data': function(d) {
                var table = $('#dataTableCourse').DataTable();
                return {
                    draw: d.draw,
                    pageSize: d.length,
                    page: table.page.info().page + 1,
                    sortColumn: d.order[0].column,
                    sortDirection: d.order[0].dir,
                    searchText: d.search.value.trim()
                };
            },
            'dataSrc': 'courses'
        },
        "columnDefs": [
            {
                "targets": 0,
                "data": "course_title",
                "render": function ( data, type, full, meta ) {
                    if (data.url) {
                        return '<a href="'+data.url+'">' + data.title + '</a>';
                    } else {
                        return data.title;
                    }
                }
            },
            {
                "targets": 1,
                "data": "organization_name",
                "sortable": false
            },
            {
                "targets": 2,
                "data": "project_coordinator_name",
                "sortable": false
            },
            {
                "targets": 3,
                "data": "publisher_course_runs_count"
            },
            {
                "targets": 4,
                "data": "course_team_status",
                "render": function ( data, type, full, meta ) {
                    return data.status + '<br>' + data.date;
                }
            },
            {
                "targets": 5,
                "data": "internal_user_status",
                "render": function ( data, type, full, meta ) {
                    return  data.status + '<br>' + data.date;
                }
            },
            {
                "targets": 6,
                "data": "edit_url",
                "sortable": false,
                "render": function ( data, type, full, meta ) {
                    if (data.url) {
                        return '<a href="'+data.url+ '" class="btn btn-brand btn-small btn-course-edit">' + data.title + '</a>'
                    } else {
                        return null;
                    }
                }
            }
        ],
        'oLanguage': { 'sEmptyTable': gettext('No courses have been created.') }
    });

    $('div.dataTables_filter input').unbind();
    $('div.dataTables_filter input').bind('keyup', function(e) {
        if(e.keyCode == 13) {
            $coursesTable.search( this.value ).draw();
        }
    });
});
